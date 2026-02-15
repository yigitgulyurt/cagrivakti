import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import sqlite3
import asyncio
import pytz

# Proje kök dizinini Python yoluna ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InputTextMessageContent, InlineQueryResultArticle
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, InlineQueryHandler
from telegram.error import BadRequest
from app.services import PrayerService, UserService, get_country_for_city
from app.config import Config
from app.factory import create_app

# Logging configuration
log_file = Config.TELEGRAM_LOG_FILE
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# Özet veriler
bot_stats = {
    'users': {}, # {user_id: {last_action: time, count: total_actions}}
    'errors': {} # {message: {count: count, last_seen: time}}
}

def save_bot_report():
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"--- TELEGRAM BOT RAPORU (Son Güncelleme: {now}) ---\n\n")
            
            f.write(" [ Hatalar ]\n")
            if not bot_stats['errors']:
                f.write(" Temiz. Hiç hata yok.\n")
            else:
                sorted_errors = sorted(bot_stats['errors'].items(), key=lambda x: x[1]['count'], reverse=True)
                for msg, data in sorted_errors:
                    f.write(f" Sayı: {data['count']:<5} | Son: {data['last_seen']} | Mesaj: {msg}\n")
            
            f.write("\n [ Kullanıcı Özeti ]\n")
            if not bot_stats['users']:
                f.write(" Henüz etkileşim yok.\n")
            else:
                sorted_users = sorted(bot_stats['users'].items(), key=lambda x: x[1]['count'], reverse=True)
                for user_id, data in sorted_users:
                    f.write(f" User: {user_id:<12} | İşlem: {data['count']:<5} | Son: {data['last_seen']}\n")
    except Exception as e:
        print(f"Log yazma hatası: {str(e)}")

class ReportHandler(logging.Handler):
    def emit(self, record):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if record.levelno >= logging.ERROR:
            msg = record.getMessage()
            if msg not in bot_stats['errors']:
                bot_stats['errors'][msg] = {'count': 0, 'last_seen': now}
            bot_stats['errors'][msg]['count'] += 1
            bot_stats['errors'][msg]['last_seen'] = now
            save_bot_report()
        elif record.levelno >= logging.INFO:
            # Kullanıcı etkileşimlerini yakalamaya çalış (varsa)
            msg = record.getMessage()
            if "User:" in msg or "user_id" in msg:
                # Basit bir parser eklenebilir ama şimdilik genel loglamayı yapalım
                pass

# Root logger setup
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Raporlama handler'ı
report_handler = ReportHandler()
root_logger.addHandler(report_handler)

# Console Handler (Sadece kritik hataları göster)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

# Kullanıcı işlemlerini loglayan yardımcı fonksiyon
def log_user_action(user_id, db=None):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if user_id not in bot_stats['users']:
        bot_stats['users'][user_id] = {'count': 0, 'last_seen': now_str}
    bot_stats['users'][user_id]['count'] += 1
    bot_stats['users'][user_id]['last_seen'] = now_str
    
    if db:
        try:
            db.update_user(user_id, last_active=datetime.now())
        except:
            pass
            
    save_bot_report()

# Reduce noise from other libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

class TelegramDB:
    def __init__(self, db_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'telegram_bot.db')):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    sehir TEXT,
                    bildirim_aktif INTEGER DEFAULT 0,
                    bildirim_suresi INTEGER DEFAULT 5,
                    grup_id TEXT,
                    arkadas_onerisi INTEGER DEFAULT 0,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    preferred_vakitler TEXT DEFAULT 'imsak,gunes,ogle,ikindi,aksam,yatsi'
                )
            ''')
            conn.commit()

    def get_user(self, user_id):
        with self.get_connection() as conn:
            return conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()

    def update_user(self, user_id, **kwargs):
        cols = ', '.join(f"{k} = ?" for k in kwargs.keys())
        vals = list(kwargs.values()) + [user_id]
        with self.get_connection() as conn:
            conn.execute(f'UPDATE users SET {cols} WHERE user_id = ?', vals)
            conn.commit()

    def set_user_inactive(self, user_id):
        with self.get_connection() as conn:
            conn.execute('UPDATE users SET bildirim_aktif = 0 WHERE user_id = ?', (user_id,))
            conn.commit()

    def add_user(self, user_id):
        with self.get_connection() as conn:
            conn.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
            conn.commit()

    def get_active_users(self):
        with self.get_connection() as conn:
            return conn.execute('SELECT * FROM users WHERE bildirim_aktif = 1').fetchall()

class NamazBot:
    """Namaz Vakitleri Telegram Bot ana sınıfı."""
    
    def __init__(self) -> None:
        """Botu başlatır ve gerekli servisleri yükler."""
        self.app = create_app()
        self.token = Config.TELEGRAM_TOKEN
        self.db = TelegramDB()
        self.tz = pytz.timezone('Europe/Istanbul')
        with self.app.app_context():
            self.cities = UserService.get_sehirler('ALL')

    def get_main_keyboard(self) -> InlineKeyboardMarkup:
        """Ana menü klavyesini döner - Ultra Sadeleştirilmiş Versiyon."""
        keyboard = [
            [InlineKeyboardButton("Namaz Vakitleri 🕒", callback_data="vakitler")],
            [InlineKeyboardButton("⏳ Kalan Süre", callback_data="kalan_sure")],
            [InlineKeyboardButton("Ayarlar ve Yardım ⚙️", callback_data="yardim")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_notification_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Bildirim ayarları klavyesini döner."""
        user = self.db.get_user(user_id)
        is_active = user['bildirim_aktif'] if user else False
        
        keyboard = [
            [InlineKeyboardButton("Bildirimleri Kapat 🔕" if is_active else "Bildirimleri Aç 🔔", 
                                 callback_data="bildirim_toggle")],
            [InlineKeyboardButton("Vakit Seçimi 🎯", callback_data="vakit_secimi")],
            [InlineKeyboardButton("Bildirim Süresini Ayarla ⚙️", callback_data="bildirim_sure_menu")],
            [InlineKeyboardButton("Ana Menüye Dön ⬅️", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_vakit_selection_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Hangi vakitler için bildirim alınacağını seçen klavyeyi döner."""
        user = self.db.get_user(user_id)
        preferred = user['preferred_vakitler'].split(',') if user and user['preferred_vakitler'] else []
        
        vakitler = {
            'imsak': 'İmsak', 'gunes': 'Güneş', 'ogle': 'Öğle', 
            'ikindi': 'İkindi', 'aksam': 'Akşam', 'yatsi': 'Yatsı'
        }
        
        keyboard = []
        v_keys = list(vakitler.keys())
        for i in range(0, len(v_keys), 2):
            row = []
            for j in range(2):
                if i + j < len(v_keys):
                    k = v_keys[i + j]
                    label = vakitler[k]
                    icon = "✅" if k in preferred else "❌"
                    row.append(InlineKeyboardButton(f"{label} {icon}", callback_data=f"toggle_vakit_{k}"))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("Geri Dön ⬅️", callback_data="bildirim_ayarlari")])
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/start komutunu karşılar."""
        user_id = update.effective_user.id
        log_user_action(user_id, self.db)
        self.db.add_user(user_id)
        
        welcome_msg = (
            "✨ <b>Namaz Vakitleri Botuna Hoş Geldiniz!</b>\n\n"
            "Bu bot ile dünya genelindeki namaz vakitlerini anlık takip edebilir ve "
            "vakitlerden önce hatırlatıcılar kurabilirsiniz.\n\n"
            "🚀 <b>Hızlı Başlangıç:</b>\n"
            "Aşağıdaki menüden vakitleri görebilir veya ⚙️ <b>Ayarlar</b> kısmından şehrinizi belirleyebilirsiniz.\n\n"
            "<i>Huzurlu ve bereketli vakitler dileriz.</i>"
        )
        
        await update.effective_message.reply_text(
            welcome_msg,
            reply_markup=self.get_main_keyboard(),
            parse_mode='HTML'
        )

    async def handle_vakitler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user['sehir']:
            msg = (
                "⚠️ <b>Henüz Şehir Seçilmedi</b>\n\n"
                "Vakitleri gösterebilmem için önce bir şehir seçmelisiniz.\n\n"
                "🚀 <b>Şehir Seçimi 📍</b> butonuna tıklayarak şehrinizi belirleyebilirsiniz."
            )
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, reply_markup=self.get_main_keyboard(), parse_mode='HTML')
            else:
                await update.effective_message.reply_text(msg, reply_markup=self.get_main_keyboard(), parse_mode='HTML')
            return

        sehir = user['sehir']
        now = datetime.now(self.tz)
        with self.app.app_context():
            country = get_country_for_city(sehir)
            prayer_times = PrayerService.get_vakitler(sehir, country, now.strftime('%Y-%m-%d'))
            next_v = PrayerService.get_next_vakit(sehir, country)
        
        if not prayer_times:
            msg = "❌ <b>Hata:</b> Vakit bilgileri şu an alınamıyor. Lütfen daha sonra tekrar deneyin."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            else:
                await update.effective_message.reply_text(msg, parse_mode='HTML')
            return

        vakit_labels = {
            'imsak': 'İmsak', 'gunes': 'Güneş', 'ogle': 'Öğle', 
            'ikindi': 'İkindi', 'aksam': 'Akşam', 'yatsi': 'Yatsı'
        }
        
        message = (
            f"📍 <b>{sehir.upper()}</b>\n"
            f"🗓 <b>{now.strftime('%d %B %Y')}</b>\n"
            f"───────────────────\n"
        )
        
        for key, label in vakit_labels.items():
            time_val = prayer_times.get(key, '--:--')
            if next_v and next_v['sonraki_vakit'] == key:
                message += f"▶️ <b>{label:<7} : {time_val}</b> ✨\n"
            else:
                message += f"▫️ <code>{label:<7} : {time_val}</code>\n"
        
        message += f"───────────────────\n"
        
        if next_v:
            kalan = next_v['kalan_sure']
            h = kalan // 3600
            m = (kalan % 3600) // 60
            v_label = vakit_labels.get(next_v['sonraki_vakit'])
            message += f"⌛ <b>{v_label}</b> vaktine <b>{h}s {m}d</b> kaldı."

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(message, reply_markup=self.get_main_keyboard(), parse_mode='HTML')
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await update.callback_query.answer("Zaten en güncel vakitleri görüyorsunuz.")
                else:
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=self.get_main_keyboard(), parse_mode='HTML')

    async def handle_kalan_sure(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user['sehir']:
            await update.callback_query.answer("❌ Önce bir şehir seçmelisiniz!", show_alert=True)
            return

        sehir = user['sehir']
        with self.app.app_context():
            country = get_country_for_city(sehir)
            next_v = PrayerService.get_next_vakit(sehir, country)
        
        if not next_v:
            await update.callback_query.answer("❌ Vakit bilgisi alınamadı.", show_alert=True)
            return

        vakit_labels = {
            'imsak': 'İmsak', 'gunes': 'Güneş', 'ogle': 'Öğle', 
            'ikindi': 'İkindi', 'aksam': 'Akşam', 'yatsi': 'Yatsı'
        }
        
        kalan = next_v['kalan_sure']
        h = kalan // 3600
        m = (kalan % 3600) // 60
        
        msg = f"📍 {sehir}\n⏳ <b>{vakit_labels.get(next_v['sonraki_vakit'])}</b> vaktine:\n\n"
        msg += f"🕒 <b>{h} saat {m} dakika</b> kaldı.\n"
        msg += f"⏰ Vakit saati: <b>{next_v['vakit']}</b>"
        
        await update.callback_query.edit_message_text(msg, reply_markup=self.get_main_keyboard(), parse_mode='HTML')

    async def _show_notification_menu(self, query, user_id):
        user = self.db.get_user(user_id)
        status = "Aktif ✅" if user['bildirim_aktif'] else "Kapalı 🔕"
        city = user['sehir'] or "Seçilmemiş"
        time = user['bildirim_suresi'] or 5
        
        msg = (
            f"🔔 <b>Bildirim Yönetimi</b>\n\n"
            f"Sizin için vakitlerden önce hatırlatıcı gönderiyoruz.\n\n"
            f"🔹 <b>Durum:</b> {status}\n"
            f"🔹 <b>Süre:</b> {time} dakika önce\n"
            f"📍 <b>Şehir:</b> {city}\n\n"
            f"<i>Ayarlarınızı aşağıdan güncelleyebilirsiniz:</i>"
        )
        try:
            await query.edit_message_text(msg, reply_markup=self.get_notification_keyboard(user_id), parse_mode='HTML')
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer()
            else:
                raise e

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Inline buton tıklamalarını yönetir."""
        query = update.callback_query
        if not query:
            return
            
        user_id = query.from_user.id
        log_user_action(user_id, self.db)
        data = query.data
        
        # Her butona tıklandığında dönen animasyonu durdur
        await query.answer()

        if data == "main_menu":
            welcome_msg = (
                "✨ <b>Namaz Vakitleri Botuna Hoş Geldiniz!</b>\n\n"
                "Aşağıdaki menüden vakitleri görebilir veya ⚙️ <b>Ayarlar</b> kısmından şehrinizi belirleyebilirsiniz."
            )
            try:
                await query.edit_message_text(
                    welcome_msg,
                    reply_markup=self.get_main_keyboard(),
                    parse_mode='HTML'
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        elif data == "vakitler":
            await self.handle_vakitler(update, context)
        elif data == "kalan_sure":
            await self.handle_kalan_sure(update, context)
        elif data == "bildirim_ayarlari":
            await self._show_notification_menu(query, user_id)
        elif data == "vakit_secimi":
            try:
                await query.edit_message_text(
                    "🎯 <b>Bildirim Alınacak Vakitler</b>\n\nHangi vakitler için bildirim almak istediğinizi seçin:",
                    reply_markup=self.get_vakit_selection_keyboard(user_id),
                    parse_mode='HTML'
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        elif data.startswith("toggle_vakit_"):
            vakit = data.replace("toggle_vakit_", "")
            user = self.db.get_user(user_id)
            if not user: return
            
            preferred = user['preferred_vakitler'].split(',') if user['preferred_vakitler'] else []
            
            if vakit in preferred:
                preferred.remove(vakit)
            else:
                preferred.append(vakit)
            
            self.db.update_user(user_id, preferred_vakitler=','.join(preferred))
            try:
                await query.edit_message_reply_markup(reply_markup=self.get_vakit_selection_keyboard(user_id))
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        elif data == "bildirim_toggle":
            user = self.db.get_user(user_id)
            if not user: return
            
            new_status = 0 if user['bildirim_aktif'] else 1
            self.db.update_user(user_id, bildirim_aktif=new_status)
            await query.answer("✅ Bildirimler " + ("açıldı" if new_status else "kapatıldı"), show_alert=False)
            await self._show_notification_menu(query, user_id)
        elif data == "bildirim_sure_menu":
            keyboard = [
                [InlineKeyboardButton("5 Dakika ⏰", callback_data="set_sure_5"),
                 InlineKeyboardButton("10 Dakika ⏰", callback_data="set_sure_10")],
                [InlineKeyboardButton("15 Dakika ⏰", callback_data="set_sure_15")],
                [InlineKeyboardButton("Geri Dön ⬅️", callback_data="bildirim_ayarlari")]
            ]
            try:
                await query.edit_message_text("⚙️ Bildirim Süresini Ayarla\n\nKaç dakika önce bildirim istersiniz?", 
                                             reply_markup=InlineKeyboardMarkup(keyboard))
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        elif data.startswith("set_sure_"):
            sure = int(data.split("_")[2])
            self.db.update_user(user_id, bildirim_suresi=sure)
            await query.answer(f"✅ Süre {sure} dakika olarak ayarlandı")
            await self._show_notification_menu(query, user_id)
        elif data == "yardim":
            await self.handle_help(update, context)
        elif data == "dini_gunler":
            await self.handle_dini_gunler(update, context)
        elif data == "kible_yonu":
            await self.handle_kible_yonu(update, context)
        elif data == "arkadas_oner_cb":
            await self.handle_arkadas_oner(update, context)
        elif data == "iletisim":
            await self.handle_contact(update, context)
        elif data == "grup_ayarlari":
            await self.handle_group(update, context)

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "⚙️ <b>Ayarlar ve Yardım Menüsü</b>\n\n"
            "Botun tüm ayarlarına ve yardımcı özelliklerine buradan erişebilirsiniz.\n\n"
            "📌 <b>Hızlı Komutlar:</b>\n"
            "/start - Ana menüyü açar\n"
            "/aciklama - Bot hakkında bilgi\n"
            "/temizle - Sohbet geçmişini temizler\n\n"
            "👥 <b>Grup Kullanımı:</b> Botu bir gruba ekleyip /grup komutunu vererek o grupta vakitlerin otomatik paylaşılmasını sağlayabilirsiniz."
        )
        
        keyboard = [
            [InlineKeyboardButton("🔔 Bildirim Ayarları", callback_data="bildirim_ayarlari")],
            [InlineKeyboardButton("🔍 Şehir Seçimi 📍", switch_inline_query_current_chat="")],
            [InlineKeyboardButton("📅 Dini Günler", callback_data="dini_gunler"),
             InlineKeyboardButton("🧭 Kıble Yönü", callback_data="kible_yonu")],
            [InlineKeyboardButton("👥 Grup Ayarı", callback_data="grup_ayarlari"),
             InlineKeyboardButton("📱 İletişim", callback_data="iletisim")],
            [InlineKeyboardButton("📢 Botu Paylaş", callback_data="arkadas_oner_cb")],
            [InlineKeyboardButton("⬅️ Ana Menü", callback_data="main_menu")]
        ]
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        else:
            await update.effective_message.reply_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def handle_dini_gunler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Yaklaşan dini günleri listeler."""
        # Şimdilik statik bir liste, ileride API'den çekilebilir
        current_year = datetime.now().year
        dini_gunler = (
            f"📅 <b>{current_year} Yılı Dini Günler ve Geceler</b>\n\n"
            "🔸 <b>Regaip Kandili:</b> 26 Ocak Pazar\n"
            "🔸 <b>Miraç Kandili:</b> 17 Şubat Pazartesi\n"
            "🔸 <b>Berat Kandili:</b> 3 Mart Pazartesi\n"
            "🔸 <b>Ramazan Başlangıcı:</b> 23 Mart Pazar\n"
            "🔸 <b>Kadir Gecesi:</b> 17 Nisan Perşembe\n"
            "🔸 <b>Ramazan Bayramı:</b> 21 Nisan Pazartesi\n"
            "🔸 <b>Kurban Bayramı:</b> 28 Haziran Cumartesi\n\n"
            "<i>Not: Tarihler Diyanet İşleri Başkanlığı takvimine göredir.</i>"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Geri Dön", callback_data="yardim")]]
        
        await update.callback_query.edit_message_text(
            dini_gunler, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='HTML'
        )

    async def handle_kible_yonu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kıble yönü hakkında bilgi verir."""
        kible_text = (
            "🧭 <b>Kıble Yönü Nasıl Bulunur?</b>\n\n"
            "Bulunduğunuz konumdan kıble yönünü en doğru şekilde bulmak için sitemizdeki kıble bulucu aracını kullanabilirsiniz:\n\n"
            "🔗 <a href='https://namazvakitleri.yigitgulyurt.com/kible'>namazvakitleri.yigitgulyurt.com/kible</a>\n\n"
            "<i>Sitemiz üzerinden konum izni vererek tam yönünüzü görebilirsiniz.</i>"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Geri Dön", callback_data="yardim")]]
        
        await update.callback_query.edit_message_text(
            kible_text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='HTML',
            disable_web_page_preview=True
        )

    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        contact_text = (
            "📱 <b>İletişim</b>\n\n"
            "👨‍💻 <b>Geliştirici:</b> Yiğit Gülyurt\n"
            "📧 <b>E-posta:</b> yigitgulyurt@proton.me\n"
            "🌐 <b>Web:</b> <a href='https://yigitgulyurt.com'>yigitgulyurt.com</a>\n"
            "🐙 <b>GitHub:</b> <a href='https://github.com/yigitgulyurt'>github.com/yigitgulyurt</a>"
        )
        keyboard = [[InlineKeyboardButton("⬅️ Geri Dön", callback_data="yardim")]]
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(contact_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML', disable_web_page_preview=True)
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await update.callback_query.answer()
                else:
                    raise e
        else:
            await update.effective_message.reply_text(contact_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML', disable_web_page_preview=True)

    async def handle_aciklama(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        aciklama = (
            "📖 <b>Namaz Vakti Botu Nedir?</b>\n\n"
            "Bu bot, dünya genelindeki namaz vakitlerini anlık olarak takip etmenizi ve "
            "vakitlerden önce bildirim almanızı sağlar.\n\n"
            "✨ <b>Özellikler:</b>\n"
            "• 81 il ve dünya şehirleri desteği\n"
            "• Vakitlerden önce hatırlatma (5-15 dk)\n"
            "• Grup desteği ile toplu bilgilendirme\n"
            "• Temiz ve hızlı arayüz\n\n"
            "💡 <b>İpucu:</b> /start yazarak her zaman ana menüye dönebilirsiniz."
        )
        await update.effective_message.reply_text(aciklama, parse_mode='HTML')

    async def handle_temizle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sohbet geçmişini (mümkün olduğunca) temizler."""
        chat_id = update.effective_chat.id
        message_id = update.effective_message.message_id
        
        status_msg = await update.effective_message.reply_text("🧹 Temizleniyor...")
        
        deleted_count = 0
        for i in range(100):
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id - i)
                deleted_count += 1
            except:
                continue
        
        await status_msg.edit_text(f"✅ Sohbet temizlendi ({deleted_count} mesaj).")
        await asyncio.sleep(2)
        await status_msg.delete()
        
        # Ana menüyü tekrar gönder
        await context.bot.send_message(
            chat_id=chat_id,
            text="🕌 Ana Menü",
            reply_markup=self.get_main_keyboard()
        )

    async def handle_arkadas_oner(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        import urllib.parse
        
        share_text_plain = (
            "🕌 Namaz Vakitleri Botu\n\n"
            "Namaz vakitlerini takip etmek ve bildirim almak için bu botu kullanabilirsin!\n\n"
            "👉 t.me/namaz_vaktibot"
        )
        
        encoded_text = urllib.parse.quote(share_text_plain)
        
        # Share links
        whatsapp_url = f"https://api.whatsapp.com/send?text={encoded_text}"
        twitter_url = f"https://twitter.com/intent/tweet?text={encoded_text}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Telegram'da Paylaş 🚀", switch_inline_query=share_text_plain)],
            [InlineKeyboardButton("WhatsApp'ta Paylaş 🟢", url=whatsapp_url)],
            [InlineKeyboardButton("Twitter'da Paylaş 🐦", url=twitter_url)],
            [InlineKeyboardButton("⬅️ Geri Dön", callback_data="yardim")]
        ])
        
        share_msg = (
            "📢 <b>Botu Paylaş</b>\n\n"
            "Aşağıdaki butonları kullanarak botu arkadaşlarınızla her yerden paylaşabilirsiniz."
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(share_msg, reply_markup=keyboard, parse_mode='HTML')
        else:
            await update.effective_message.reply_text(share_msg, reply_markup=keyboard, parse_mode='HTML')

    async def handle_inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Şehir arama sonuçlarını inline olarak gösterir."""
        query = update.inline_query.query.lower()
        
        results = []
        # Eğer sorgu boşsa en popüler/ilk 10 şehri göster
        if not query:
            matching_cities = self.cities[:10]
        else:
            matching_cities = [c for c in self.cities if query in c.lower()][:10]
        
        now = datetime.now(self.tz)
        with self.app.app_context():
            for city in matching_cities:
                country = get_country_for_city(city)
                prayer_times = PrayerService.get_vakitler(city, country, now.strftime('%Y-%m-%d'))
                
                if prayer_times:
                    desc = f"İmsak: {prayer_times['imsak']} | Öğle: {prayer_times['ogle']} | Akşam: {prayer_times['aksam']}"
                else:
                    desc = "Vakit bilgisi alınamadı."

                results.append(
                    InlineQueryResultArticle(
                        id=city,
                        title=f"📍 {city}",
                        description=desc,
                        input_message_content=InputTextMessageContent(f"!sehirsec_{city}"),
                        thumbnail_url="https://raw.githubusercontent.com/yigitgulyurt/namaz-vakitleri-api/master/assets/mosque.png"
                    )
                )

        await update.inline_query.answer(results, cache_time=60, is_personal=True)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Gelen metin mesajlarını işler (Örn: Inline'dan gelen şehir seçimi)."""
        if not update.message or not update.message.text:
            return
            
        text = update.message.text
        user_id = update.effective_user.id

        if text.startswith("!sehirsec_"):
            city = text.split("_", 1)[1]
            if city in self.cities:
                self.db.update_user(user_id, sehir=city)
                await update.message.reply_text(
                    f"✅ <b>{city}</b> başarıyla seçildi!\n\n"
                    "Artık ana menüden vakitleri görebilir veya bildirim ayarlarınızı yapabilirsiniz.",
                    reply_markup=self.get_main_keyboard(),
                    parse_mode='HTML'
                )
            else:
                logger.warning(f"Geçersiz şehir seçimi denemesi: {city}")
                await update.message.reply_text("⚠️ <b>Hata:</b> Geçersiz bir şehir seçildi. Lütfen listeden tekrar seçin.", parse_mode='HTML')
        elif text == "Namaz Vakitleri 🕒":
            await self.handle_vakitler(update, context)
        else:
            # Anlaşılmayan mesajlar için yönlendirme
            await update.message.reply_text(
                "💬 <b>Bunu anlayamadım...</b>\n\n"
                "Lütfen aşağıdaki menüyü kullanın veya /start yazarak ana menüye dönün.",
                reply_markup=self.get_main_keyboard(),
                parse_mode='HTML'
            )

    async def handle_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user_id = update.effective_user.id
        
        if chat.type == 'private':
            msg = (
                "❌ <b>Bu özellik sadece gruplarda kullanılabilir.</b>\n\n"
                "Botu bir gruba ekleyip yönetici yetkisi verdikten sonra bu komutu kullanabilirsiniz."
            )
            keyboard = [[InlineKeyboardButton("⬅️ Geri Dön", callback_data="yardim")]]
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            else:
                await update.effective_message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            return

        # Check bot permissions in group
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        if bot_member.status != 'administrator':
            msg = "⚠️ Botun bildirim gönderebilmesi için grupta 'Yönetici' yetkisine sahip olması önerilir."
            await context.bot.send_message(chat.id, msg)

        member = await context.bot.get_chat_member(chat.id, user_id)
        if member.status not in ['creator', 'administrator']:
            msg = "❌ Sadece grup yöneticileri bu ayarı yapabilir."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            else:
                await update.effective_message.reply_text(msg)
            return

        user = self.db.get_user(user_id)
        if not user or not user['sehir']:
            msg = "❌ Önce özel mesaj üzerinden bir şehir seçmelisiniz."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            else:
                await update.effective_message.reply_text(msg)
            return

        self.db.update_user(user_id, grup_id=str(chat.id))
        msg = f"✅ Bu grup için <b>{user['sehir']}</b> vakitleri paylaşılacaktır.\n🔔 Bildirimlerinizi özel mesaj üzerinden yönetebilirsiniz."
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.effective_message.reply_text(msg, parse_mode='HTML')

    async def send_vakit_notification(self, user_id, chat_id, vakit_name, vakit_time, is_reminder=False, lead_time=5):
        try:
            if is_reminder:
                text = f"⏰ <b>Hatırlatıcı:</b> {vakit_name} vaktine {lead_time} dakika kaldı! ({vakit_time})"
            else:
                text = f"🕌 <b>{vakit_name} vakti girdi!</b> ({vakit_time})"
            
            return text
        except Exception as e:
            logger.error(f"Error preparing notification: {e}")
            return None

    async def check_notifications(self, context: ContextTypes.DEFAULT_TYPE):
        now = datetime.now(self.tz)
        active_users = self.db.get_active_users()
        
        city_times_cache = {}
        processed_cities = set()

        for user in active_users:
            city = user['sehir']
            if not city: continue
            
            preferred = user['preferred_vakitler'].split(',') if user['preferred_vakitler'] else []
            if not preferred: continue

            if city not in city_times_cache:
                with self.app.app_context():
                    # Ülke kodunu şehre göre tespit et
                    country = get_country_for_city(city)
                    prayer_times = PrayerService.get_vakitler(city, country, now.strftime('%Y-%m-%d'))
                    city_times_cache[city] = prayer_times
            
            prayer_times = city_times_cache[city]
            if not prayer_times: continue

            lead_time = user['bildirim_suresi'] or 5
            
            # Vakit isimleri eşlemesi
            vakit_labels = {
                'imsak': 'İmsak',
                'gunes': 'Güneş',
                'ogle': 'Öğle',
                'ikindi': 'İkindi',
                'aksam': 'Akşam',
                'yatsi': 'Yatsı'
            }
            
            for vakit_key, vakit_time_str in prayer_times.items():
                if vakit_key not in vakit_labels or not vakit_time_str or vakit_time_str == "--:--":
                    continue
                
                if vakit_key not in preferred:
                    continue
                
                try:
                    v_time = datetime.strptime(vakit_time_str, '%H:%M').time()
                    v_dt = now.replace(hour=v_time.hour, minute=v_time.minute, second=0, microsecond=0)
                    
                    diff = (v_dt - now).total_seconds()
                    v_name = vakit_labels[vakit_key]
                    
                    # 1. Hatırlatma (X dakika kala)
                    if abs(diff - (lead_time * 60)) < 30:
                        text = f"⏰ <b>Hatırlatma:</b> {v_name} vaktine {lead_time} dakika kaldı. ({city})"
                        await self._safe_send_message(context.bot, user['user_id'], text)
                        if user['grup_id']:
                            await self._safe_send_message(context.bot, user['grup_id'], text)
                    
                    # 2. Vakit Girdi Bildirimi (Tam anında)
                    elif abs(diff) < 30:
                        # Interval 60 olduğu için 30 sn tolerans yeterli olacaktır
                        text = f"🕌 <b>{v_name} vakti girdi!</b> ({city})\n\n<i>Rabbimiz ibadetlerinizi kabul eylesin.</i>"
                        await self._safe_send_message(context.bot, user['user_id'], text)
                        if user['grup_id']:
                            await self._safe_send_message(context.bot, user['grup_id'], text)
                                
                except Exception as e:
                    logger.error(f"Error in notification loop for user {user['user_id']}: {e}")

    async def _safe_send_message(self, bot, chat_id, text):
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            return True
        except Exception as e:
            err_msg = str(e).lower()
            logger.error(f"Could not send message to {chat_id}: {e}")
            if "bot was blocked" in err_msg or "chat not found" in err_msg or "user is deactivated" in err_msg:
                self.db.set_user_inactive(chat_id)
                logger.info(f"User {chat_id} blocked the bot. Notifications disabled.")
            return False

    async def handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Hataları yakalar ve loglar."""
        # 'No item with that key' hatası genellikle job_queue veya callback query'lerde 
        # olmayan bir referansa erişmeye çalışırken oluşur.
        err_str = str(context.error)
        
        if "No item with that key" in err_str:
            logger.warning(f"Ignored 'No item with that key' error. Update: {update}")
            return

        logger.error(f"Update {update} caused error {context.error}")
        
        if isinstance(update, Update) and update.effective_message:
            try:
                # Kullanıcıyı bıktırmamak için sadece kritik hatalarda mesaj gönder
                if "Forbidden" not in err_str:
                    await update.effective_message.reply_text("❌ İşleminiz sırasında bir hata oluştu. Lütfen /start ile ana menüye dönün.")
            except:
                pass

    async def post_init(self, application: Application) -> None:
        """Bot başlatıldıktan sonra yapılacak işlemler."""
        commands = [
            ("start", "Ana menüyü açar"),
            ("help", "Yardım ve özellikler"),
            ("aciklama", "Bot hakkında bilgi"),
            ("grup", "Grup bildirimlerini ayarlar"),
            ("temizle", "Sohbeti temizler"),
            ("iletisim", "Geliştiriciye ulaş"),
            ("arkadas_oner", "Botu paylaş")
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot komutları başarıyla ayarlandı.")

    def run(self):
        application = Application.builder().token(self.token).post_init(self.post_init).build()
        
        # Handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.handle_help))
        application.add_handler(CommandHandler("aciklama", self.handle_aciklama))
        application.add_handler(CommandHandler("temizle", self.handle_temizle))
        application.add_handler(CommandHandler("arkadas_oner", self.handle_arkadas_oner))
        application.add_handler(CommandHandler("iletisim", self.handle_contact))
        application.add_handler(CommandHandler("grup", self.handle_group))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(InlineQueryHandler(self.handle_inline_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error handler
        application.add_error_handler(self.handle_error)
        
        # Job queue
        application.job_queue.run_repeating(self.check_notifications, interval=60, first=10)
        
        logger.info("Telegram bot is running...")
        application.run_polling()

if __name__ == '__main__':
    bot = NamazBot()
    bot.run()
