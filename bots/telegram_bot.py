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
from app.services import PrayerService, UserService, get_country_for_city, get_daily_content, get_guides, get_guide_by_slug, DiniGunlerService
from app.services.ramadan_service import RamadanService
from app.config import Config
from app.factory import create_app

# Türkçe ay ve gün isimleri
TURKISH_MONTHS = [
    '', 'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
    'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'
]
TURKISH_DAYS = [
    'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'
]

def format_turkish_date(dt):
    """Tarihi Türkçe formatta döndürür: 21 Mayıs 2026 Perşembe"""
    day = dt.day
    month = TURKISH_MONTHS[dt.month]
    year = dt.year
    weekday = TURKISH_DAYS[dt.weekday()]
    return f"{day} {month} {year} {weekday}"

def strip_html_tags(text):
    """HTML etiketlerini temizler ve Telegram uyumlu hale getirir."""
    import re
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'<p>', '', text)
    text = re.sub(r'<h\d>', '<b>', text)
    text = re.sub(r'</h\d>', '</b>', text)
    text = re.sub(r'<li>', '• ', text)
    text = re.sub(r'</li>', '\n', text)
    text = re.sub(r'<ul>|</ul>|<ol>|</ol>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text

# Logging configuration
log_file = Config.TELEGRAM_LOG_FILE
os.makedirs(os.path.dirname(log_file), exist_ok=True)

import logging
from logging.handlers import TimedRotatingFileHandler
from app.logging_config import IstanbulFormatter, compress_rotator

# Özet veriler
bot_stats = {
    'users': {},
    'errors': {}
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
            msg = record.getMessage()
            if "User:" in msg or "user_id" in msg:
                pass

logger = logging.getLogger('telegram_bot')
logger.setLevel(logging.INFO)
logger.propagate = False

file_handler = TimedRotatingFileHandler(
    log_file, when='midnight', interval=1,
    backupCount=getattr(Config, 'LOG_RETENTION_DAYS', 7),
    encoding='utf-8'
)
file_handler.rotator = compress_rotator
formatter = IstanbulFormatter(
    '[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

report_handler = ReportHandler()
logger.addHandler(report_handler)

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
        self.app = create_app()
        self.token = Config.TELEGRAM_TOKEN
        self.db = TelegramDB()
        self.tz = pytz.timezone('Europe/Istanbul')
        with self.app.app_context():
            self.cities = UserService.get_sehirler('ALL')
        self.gonderilen_dini_gunler = set()

    def get_main_keyboard(self) -> InlineKeyboardMarkup:
        """Ana menü klavyesini döner."""
        with self.app.app_context():
            ramadan_info = RamadanService.get_ramadan_info()
        is_ramadan = ramadan_info['is_ramadan']
        
        keyboard = [
            [InlineKeyboardButton("🕒 Bugünün Vakitleri", callback_data="vakitler"),
             InlineKeyboardButton("⏳ Sonraki Vakit", callback_data="kalan_sure")],
            [InlineKeyboardButton("📅 Haftalık", callback_data="haftalik_takvim"),
             InlineKeyboardButton("📆 Aylık Takvim", callback_data="aylik_takvim")],
            [InlineKeyboardButton("📍 Şehir Seç", switch_inline_query_current_chat="")],
        ]
        
        if is_ramadan:
            keyboard.append([InlineKeyboardButton("🌙 Ramazan", callback_data="ramazan")])
        
        keyboard.append([
            InlineKeyboardButton("🔔 Bildirimler", callback_data="bildirim_ayarlari"),
            InlineKeyboardButton("☰ Daha Fazla", callback_data="yardim")
        ])
        
        return InlineKeyboardMarkup(keyboard)

    def get_notification_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Bildirim ayarları klavyesini döner."""
        user = self.db.get_user(user_id)
        is_active = user['bildirim_aktif'] if user else False
        
        keyboard = [
            [InlineKeyboardButton("🔕 Bildirimleri Kapat" if is_active else "🔔 Bildirimleri Aç",
                                 callback_data="bildirim_toggle")],
            [InlineKeyboardButton("🎯 Hangi Vakitler?", callback_data="vakit_secimi"),
             InlineKeyboardButton("⏱ Süre Ayarı", callback_data="bildirim_sure_menu")],
            [InlineKeyboardButton("⬅️ Ana Menü", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_vakit_selection_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Hangi vakitler için bildirim alınacağını seçen klavyeyi döner."""
        user = self.db.get_user(user_id)
        preferred = user['preferred_vakitler'].split(',') if user and user['preferred_vakitler'] else []
        
        with self.app.app_context():
            ramadan_info = RamadanService.get_ramadan_info()
        is_ramadan = ramadan_info['is_ramadan']
        
        vakitler = {
            'imsak': 'Sahur' if is_ramadan else 'İmsak',
            'gunes': 'Güneş',
            'ogle': 'Öğle',
            'ikindi': 'İkindi',
            'aksam': 'İftar' if is_ramadan else 'Akşam',
            'yatsi': 'Yatsı'
        }
        
        keyboard = []
        v_keys = list(vakitler.keys())
        for i in range(0, len(v_keys), 2):
            row = []
            for j in range(2):
                if i + j < len(v_keys):
                    k = v_keys[i + j]
                    label = vakitler[k]
                    icon = "✅" if k in preferred else "☐"
                    row.append(InlineKeyboardButton(f"{icon} {label}", callback_data=f"toggle_vakit_{k}"))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("⬅️ Bildirim Ayarları", callback_data="bildirim_ayarlari")])
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/start komutunu karşılar."""
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name or "Kardeşim"
        log_user_action(user_id, self.db)
        self.db.add_user(user_id)
        
        # Şehir seçilmemiş mi?
        user = self.db.get_user(user_id)
        sehir_notu = ""
        if not user or not user['sehir']:
            sehir_notu = "\n\n💡 <b>İpucu:</b> Vakitleri görmek için önce <b>📍 Şehir Seç</b> butonuna basın."
        
        welcome_msg = (
            f"Hoş geldiniz, <b>{first_name}</b>! 🕌\n\n"
            f"Namaz vakitlerini takip edebilir, vakit bildirimlerinizi ayarlayabilirsiniz."
            f"{sehir_notu}"
        )
        
        with self.app.app_context():
            daily_content = get_daily_content()
        
        if daily_content:
            type_emoji = {'ayet': '📖', 'hadis': '📜', 'soz': '💬', 'söz': '💬'}
            type_label = {'ayet': 'Günün Ayeti', 'hadis': 'Günün Hadisi', 'soz': 'Günün Sözü', 'söz': 'Günün Sözü'}

            emoji = type_emoji.get(daily_content.get('type'), '💫')
            label = type_label.get(daily_content.get('type'), 'Günlük İçerik')
            
            welcome_msg += f"\n\n─────────────────────\n"
            welcome_msg += f"{emoji} <b>{label}</b>\n\n"
            welcome_msg += f"<i>{daily_content.get('text')}</i>"
            if daily_content.get('source'):
                welcome_msg += f"\n\n📚 <i>{daily_content['source']}</i>"
        
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
                "📍 <b>Şehir Seçilmemiş</b>\n\n"
                "Vakitleri görmek için önce şehrinizi belirlemeniz gerekiyor.\n\n"
                "Aşağıdaki <b>Şehir Seç</b> butonuna basarak arama yapabilirsiniz."
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📍 Şehir Seç", switch_inline_query_current_chat="")],
                [InlineKeyboardButton("⬅️ Ana Menü", callback_data="main_menu")]
            ])
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, reply_markup=keyboard, parse_mode='HTML')
            else:
                await update.effective_message.reply_text(msg, reply_markup=keyboard, parse_mode='HTML')
            return

        sehir = user['sehir']
        now = datetime.now(self.tz)
        with self.app.app_context():
            country = get_country_for_city(sehir)
            prayer_times = PrayerService.get_vakitler(sehir, country, now.strftime('%Y-%m-%d'))
            next_v = PrayerService.get_next_vakit(sehir, country)
            ramadan_info = RamadanService.get_ramadan_info()
        is_ramadan = ramadan_info['is_ramadan']
        
        if not prayer_times:
            msg = "❌ Vakit bilgileri şu an alınamıyor. Lütfen bir süre sonra tekrar deneyin."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            else:
                await update.effective_message.reply_text(msg)
            return

        vakit_labels = {
            'imsak': 'Sahur' if is_ramadan else 'İmsak',
            'gunes': 'Güneş',
            'ogle': 'Öğle',
            'ikindi': 'İkindi',
            'aksam': 'İftar' if is_ramadan else 'Akşam',
            'yatsi': 'Yatsı'
        }
        
        message = (
            f"📍 <b>{sehir}</b>  —  🗓 {format_turkish_date(now)}\n"
            f"─────────────────────\n"
        )
        
        now_time = now.time().replace(second=0, microsecond=0)
        
        for key, label in vakit_labels.items():
            time_val = prayer_times.get(key, '--:--')
            is_next = next_v and next_v['sonraki_vakit'] == key
            
            # Geçmiş vakit tespiti
            try:
                v_time = datetime.strptime(time_val, '%H:%M').time()
                is_past = v_time < now_time and not is_next
            except:
                is_past = False
            
            if is_next:
                message += f"▶️ <b>{label:<8}: {time_val}</b> ✨\n"
            elif is_past:
                message += f"  <s>{label:<8}: {time_val}</s>\n"
            else:
                message += f"  {label:<8}: {time_val}\n"
        
        message += f"─────────────────────\n"
        
        if next_v:
            kalan = next_v['kalan_sure']
            h = kalan // 3600
            m = (kalan % 3600) // 60
            v_label = vakit_labels.get(next_v['sonraki_vakit'], '')
            if h > 0:
                message += f"⌛ <b>{v_label}</b> vaktine <b>{h} saat {m} dakika</b> kaldı."
            else:
                message += f"⌛ <b>{v_label}</b> vaktine <b>{m} dakika</b> kaldı."

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(message, reply_markup=self.get_main_keyboard(), parse_mode='HTML')
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await update.callback_query.answer("Vakitler zaten güncel.")
                else:
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=self.get_main_keyboard(), parse_mode='HTML')

    async def handle_kalan_sure(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user['sehir']:
            await update.callback_query.answer("Önce bir şehir seçmelisiniz.", show_alert=True)
            return

        sehir = user['sehir']
        with self.app.app_context():
            country = get_country_for_city(sehir)
            next_v = PrayerService.get_next_vakit(sehir, country)
            ramadan_info = RamadanService.get_ramadan_info()
        is_ramadan = ramadan_info['is_ramadan']
        
        if not next_v:
            await update.callback_query.answer("Vakit bilgisi alınamadı.", show_alert=True)
            return

        vakit_labels = {
            'imsak': 'Sahur' if is_ramadan else 'İmsak',
            'gunes': 'Güneş',
            'ogle': 'Öğle',
            'ikindi': 'İkindi',
            'aksam': 'İftar' if is_ramadan else 'Akşam',
            'yatsi': 'Yatsı'
        }
        
        kalan = next_v['kalan_sure']
        h = kalan // 3600
        m = (kalan % 3600) // 60
        v_label = vakit_labels.get(next_v['sonraki_vakit'], '')
        
        if h > 0:
            kalan_str = f"{h} saat {m} dakika"
        else:
            kalan_str = f"{m} dakika"
        
        msg = (
            f"📍 <b>{sehir}</b>\n"
            f"─────────────────────\n"
            f"Sonraki vakit: <b>{v_label}</b>\n"
            f"Saat: <b>{next_v['vakit']}</b>\n\n"
            f"⏳ <b>{kalan_str}</b> kaldı."
        )
        
        try:
            await update.callback_query.edit_message_text(msg, reply_markup=self.get_main_keyboard(), parse_mode='HTML')
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await update.callback_query.answer("Bilgi zaten güncel.")
            else:
                raise e

    async def handle_haftalik_takvim(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Haftalık vakit takvimini gösterir — geçmiş günler soluk, bugün işaretli."""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user['sehir']:
            msg = "📍 Önce bir şehir seçmelisiniz."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            else:
                await update.effective_message.reply_text(msg)
            return
        
        sehir = user['sehir']
        now = datetime.now(self.tz)
        bugun = now.date()
        baslangic = bugun - timedelta(days=bugun.weekday())
        
        with self.app.app_context():
            country = get_country_for_city(sehir)
            ramadan_info = RamadanService.get_ramadan_info()
        is_ramadan = ramadan_info['is_ramadan']
        
        vakit_labels = {
            'imsak': 'Sahur' if is_ramadan else 'İmsak',
            'gunes': 'Güneş',
            'ogle': 'Öğle',
            'ikindi': 'İkindi',
            'aksam': 'İftar' if is_ramadan else 'Akşam',
            'yatsi': 'Yatsı'
        }
        
        message = f"📍 <b>{sehir}</b> — Haftalık Vakitler\n─────────────────────\n"
        now_time = now.time().replace(second=0, microsecond=0)
        
        for i in range(7):
            gun_tarihi = baslangic + timedelta(days=i)
            with self.app.app_context():
                prayer_times = PrayerService.get_vakitler(sehir, country, gun_tarihi.strftime('%Y-%m-%d'))
            
            if not prayer_times:
                continue
            
            bugun_mu = (gun_tarihi == bugun)
            gecmis_gun_mu = (gun_tarihi < bugun)
            
            if bugun_mu:
                message += f"\n📌 <b>{format_turkish_date(gun_tarihi)}</b>\n"
            elif gecmis_gun_mu:
                message += f"\n<i>{format_turkish_date(gun_tarihi)}</i>\n"
            else:
                message += f"\n{format_turkish_date(gun_tarihi)}\n"
            
            for key, label in vakit_labels.items():
                time_val = prayer_times.get(key, '--:--')
                
                if bugun_mu:
                    # Bugün: geçmiş vakitler üstü çizili, sonraki bold
                    try:
                        v_time = datetime.strptime(time_val, '%H:%M').time()
                        is_past = v_time < now_time
                    except:
                        is_past = False
                    
                    if is_past:
                        message += f"  <s>{label:<8}: {time_val}</s>\n"
                    else:
                        message += f"  <b>{label:<8}: {time_val}</b>\n"
                elif gecmis_gun_mu:
                    message += f"  <i>{label:<8}: {time_val}</i>\n"
                else:
                    message += f"  {label:<8}: {time_val}\n"
        
        keyboard = [[InlineKeyboardButton("⬅️ Ana Menü", callback_data="main_menu")]]
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def handle_aylik_takvim(self, update: Update, context: ContextTypes.DEFAULT_TYPE, sayfa=0):
        """Aylık vakit takvimini gösterir (bu ay, sayfalama, bugün işaretli)."""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user['sehir']:
            msg = "📍 Önce bir şehir seçmelisiniz."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            else:
                await update.effective_message.reply_text(msg)
            return
        
        sehir = user['sehir']
        now = datetime.now(self.tz)
        bugun = now.date()
        
        ayin_ilk_gunu = bugun.replace(day=1)
        if ayin_ilk_gunu.month == 12:
            gelecek_ayin_ilk_gunu = ayin_ilk_gunu.replace(year=ayin_ilk_gunu.year+1, month=1, day=1)
        else:
            gelecek_ayin_ilk_gunu = ayin_ilk_gunu.replace(month=ayin_ilk_gunu.month+1, day=1)
        ayin_son_gunu = gelecek_ayin_ilk_gunu - timedelta(days=1)
        
        gunler = []
        g = ayin_ilk_gunu
        while g <= ayin_son_gunu:
            gunler.append(g)
            g += timedelta(days=1)
        
        sayfa_basina = 10
        
        if len(gunler) == 30:
            toplam_sayfa = 3
            if sayfa == 0:
                baslangic_indeks, bitis_indeks = 0, 10
            elif sayfa == 1:
                baslangic_indeks, bitis_indeks = 10, 20
            else:
                baslangic_indeks, bitis_indeks = 20, 30
        elif len(gunler) == 31:
            toplam_sayfa = 3
            if sayfa == 0:
                baslangic_indeks, bitis_indeks = 0, 10
            elif sayfa == 1:
                baslangic_indeks, bitis_indeks = 10, 20
            else:
                baslangic_indeks, bitis_indeks = 20, 31
        else:
            toplam_sayfa = (len(gunler) + sayfa_basina - 1) // sayfa_basina
            baslangic_indeks = sayfa * sayfa_basina
            bitis_indeks = baslangic_indeks + sayfa_basina
        
        gosterilecek_gunler = gunler[baslangic_indeks:bitis_indeks]
        
        with self.app.app_context():
            country = get_country_for_city(sehir)
            ramadan_info = RamadanService.get_ramadan_info()
        is_ramadan = ramadan_info['is_ramadan']
        
        vakit_labels = {
            'imsak': 'Sahur' if is_ramadan else 'İmsak',
            'gunes': 'Güneş',
            'ogle': 'Öğle',
            'ikindi': 'İkindi',
            'aksam': 'İftar' if is_ramadan else 'Akşam',
            'yatsi': 'Yatsı'
        }
        
        ay_adi = TURKISH_MONTHS[ayin_ilk_gunu.month]
        message = (
            f"📍 <b>{sehir}</b> — {ay_adi} {ayin_ilk_gunu.year}\n"
            f"Sayfa {sayfa+1}/{toplam_sayfa}\n"
            f"─────────────────────\n"
        )
        now_time = now.time().replace(second=0, microsecond=0)
        
        for gun_tarihi in gosterilecek_gunler:
            with self.app.app_context():
                prayer_times = PrayerService.get_vakitler(sehir, country, gun_tarihi.strftime('%Y-%m-%d'))
            
            if not prayer_times:
                continue
            
            bugun_mu = (gun_tarihi == bugun)
            gecmis_gun_mu = (gun_tarihi < bugun)
            
            if bugun_mu:
                message += f"\n📌 <b>{format_turkish_date(gun_tarihi)}</b>\n"
            elif gecmis_gun_mu:
                message += f"\n<i>{format_turkish_date(gun_tarihi)}</i>\n"
            else:
                message += f"\n{format_turkish_date(gun_tarihi)}\n"
            
            for key, label in vakit_labels.items():
                time_val = prayer_times.get(key, '--:--')
                
                if bugun_mu:
                    try:
                        v_time = datetime.strptime(time_val, '%H:%M').time()
                        is_past = v_time < now_time
                    except:
                        is_past = False
                    if is_past:
                        message += f"  <s>{label:<8}: {time_val}</s>\n"
                    else:
                        message += f"  <b>{label:<8}: {time_val}</b>\n"
                elif gecmis_gun_mu:
                    message += f"  <i>{label:<8}: {time_val}</i>\n"
                else:
                    message += f"  {label:<8}: {time_val}\n"
        
        keyboard = []
        nav_row = []
        if sayfa > 0:
            nav_row.append(InlineKeyboardButton("◀️ Önceki", callback_data=f"aylik_sayfa_{sayfa-1}"))
        if sayfa < toplam_sayfa - 1:
            nav_row.append(InlineKeyboardButton("Sonraki ▶️", callback_data=f"aylik_sayfa_{sayfa+1}"))
        if nav_row:
            keyboard.append(nav_row)
        keyboard.append([InlineKeyboardButton("⬅️ Ana Menü", callback_data="main_menu")])
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def _show_notification_menu(self, query, user_id):
        user = self.db.get_user(user_id)
        is_active = user['bildirim_aktif']
        status = "Aktif ✅" if is_active else "Kapalı 🔕"
        city = user['sehir'] or "Seçilmemiş"
        lead_time = user['bildirim_suresi'] or 5
        preferred = user['preferred_vakitler'] or ''
        vakit_sayisi = len([v for v in preferred.split(',') if v]) if preferred else 0
        
        msg = (
            f"🔔 <b>Bildirim Ayarları</b>\n"
            f"─────────────────────\n"
            f"Durum:       <b>{status}</b>\n"
            f"Şehir:         <b>{city}</b>\n"
            f"Kaç dakika önce: <b>{lead_time} dk</b>\n"
            f"Seçili vakit:  <b>{vakit_sayisi}/6</b>"
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
        
        await query.answer()

        if data == "haftalik_takvim":
            await self.handle_haftalik_takvim(update, context)
        elif data == "aylik_takvim":
            await self.handle_aylik_takvim(update, context)
        elif data.startswith("aylik_sayfa_"):
            sayfa = int(data.split("_")[2])
            await self.handle_aylik_takvim(update, context, sayfa)
        elif data == "main_menu":
            welcome_msg = "🕌 <b>Ana Menü</b>\n\nAşağıdan istediğiniz özelliği seçebilirsiniz."
            
            with self.app.app_context():
                daily_content = get_daily_content()
            
            if daily_content:
                type_emoji = {'ayet': '📖', 'hadis': '📜', 'soz': '💬', 'söz': '💬'}
                type_label = {'ayet': 'Günün Ayeti', 'hadis': 'Günün Hadisi', 'soz': 'Günün Sözü', 'söz': 'Günün Sözü'}
                emoji = type_emoji.get(daily_content.get('type'), '💫')
                label = type_label.get(daily_content.get('type'), 'Günlük İçerik')
                
                welcome_msg += f"\n\n─────────────────────\n"
                welcome_msg += f"{emoji} <b>{label}</b>\n\n"
                welcome_msg += f"<i>{daily_content.get('text')}</i>"
                if daily_content.get('source'):
                    welcome_msg += f"\n\n📚 <i>{daily_content['source']}</i>"
            
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
                    "🎯 <b>Bildirim Alınacak Vakitler</b>\n\nHangi vakitler için bildirim almak istediğinizi işaretleyin:",
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
            await query.answer("✅ Bildirimler " + ("açıldı!" if new_status else "kapatıldı."), show_alert=False)
            await self._show_notification_menu(query, user_id)
        elif data == "bildirim_sure_menu":
            keyboard = [
                [InlineKeyboardButton("1 dk", callback_data="set_sure_1"),
                 InlineKeyboardButton("5 dk", callback_data="set_sure_5"),
                 InlineKeyboardButton("10 dk", callback_data="set_sure_10")],
                [InlineKeyboardButton("15 dk", callback_data="set_sure_15"),
                 InlineKeyboardButton("30 dk", callback_data="set_sure_30")],
                [InlineKeyboardButton("⬅️ Geri", callback_data="bildirim_ayarlari")]
            ]
            try:
                await query.edit_message_text(
                    "⏱ <b>Bildirim Süresi</b>\n\nVakit girmeden kaç dakika önce bildirim almak istersiniz?",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        elif data.startswith("set_sure_"):
            sure = int(data.split("_")[2])
            self.db.update_user(user_id, bildirim_suresi=sure)
            await query.answer(f"✅ {sure} dakika olarak ayarlandı.")
            await self._show_notification_menu(query, user_id)
        elif data == "yardim":
            await self.handle_help(update, context)
        elif data == "ramazan":
            await self.handle_ramazan(update, context)
        elif data == "gunluk":
            await self.handle_gunluk(update, context)
        elif data == "rehberler":
            await self.handle_rehberler(update, context)
        elif data.startswith("rehber_"):
            slug = data.replace("rehber_", "")
            await self.handle_rehber_detay(update, context, slug)
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
            "☰ <b>Tüm Özellikler</b>\n"
            "─────────────────────\n"
            "Aşağıdan bir özelliğe ulaşabilirsiniz:"
        )
        
        keyboard = [
            [InlineKeyboardButton("💫 Günlük İçerik", callback_data="gunluk"),
             InlineKeyboardButton("📚 Bilgi Köşesi", callback_data="rehberler")],
            [InlineKeyboardButton("🌙 Ramazan", callback_data="ramazan"),
             InlineKeyboardButton("📅 Dini Günler", callback_data="dini_gunler")],
            [InlineKeyboardButton("🧭 Kıble Yönü", callback_data="kible_yonu"),
             InlineKeyboardButton("👥 Grup Ayarları", callback_data="grup_ayarlari")],
            [InlineKeyboardButton("📢 Botu Paylaş", callback_data="arkadas_oner_cb"),
             InlineKeyboardButton("📱 İletişim", callback_data="iletisim")],
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
        with self.app.app_context():
            dini_gunler_list = DiniGunlerService.get_dini_gunler()
        
        message = "📅 <b>Dini Günler ve Geceler</b>\n─────────────────────\n\n"
        
        tur_emoji = {
            'kandil': '🌙',
            'ramazan': '🌙',
            'bayram': '🎊',
            'ozel': '✨'
        }
        
        for gun in dini_gunler_list:
            emoji = tur_emoji.get(gun['tur'], '🔸')
            tarih_str = format_turkish_date(gun['tarih'])
            kalan = gun['kalan_gun']
            
            if kalan == 0:
                kalan_str = "📌 Bugün"
            elif kalan == 1:
                kalan_str = "⏳ Yarın"
            elif kalan > 0:
                kalan_str = f"⏳ {kalan} gün sonra"
            else:
                kalan_str = "✅ Geçti"
            
            message += f"{emoji} <b>{gun['ad']}</b>\n"
            message += f"   {tarih_str} · {kalan_str}\n\n"
        
        message += "<i>Tarihler Hicri takvime göre hesaplanmıştır.</i>"
        
        keyboard = [[InlineKeyboardButton("⬅️ Geri", callback_data="yardim")]]
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def handle_kible_yonu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kıble yönü hakkında bilgi verir."""
        kible_text = (
            "🧭 <b>Kıble Yönü</b>\n\n"
            "Konumunuzdan kıble yönünü bulmak için sitemizdeki kıble pusulasını kullanabilirsiniz:\n\n"
            "🔗 <a href='https://cagrivakti.com.tr/kible-pusulasi'>cagrivakti.com.tr/kible-pusulasi</a>"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Geri", callback_data="yardim")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                kible_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        else:
            await update.effective_message.reply_text(kible_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML', disable_web_page_preview=True)

    async def handle_ramazan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ramazan bilgilerini gösterir."""
        with self.app.app_context():
            ramadan_info = RamadanService.get_ramadan_info()
        
        keyboard = [[InlineKeyboardButton("⬅️ Ana Menü", callback_data="main_menu")]]
        
        if ramadan_info['is_ramadan']:
            message = (
                f"🌙 <b>Ramazan-ı Şerif</b>\n"
                f"─────────────────────\n"
                f"<b>{ramadan_info['current_day']}. gün</b>  ·  {ramadan_info['days_remaining']} gün kaldı\n"
            )
            
            if ramadan_info['is_laylat_al_qadr_day']:
                message += "\n✨ <b>Hayırlı Kadir Geceleri!</b>\n"
            elif ramadan_info['is_laylat_al_qadr_next_day']:
                message += "\n⏳ Yarın Kadir Gecesi!\n"
            
            if ramadan_info.get('ramadan_content'):
                message += f"\n💬 <b>Günün İçeriği</b>\n<i>{ramadan_info['ramadan_content']}</i>\n"
        else:
            if ramadan_info['status'] == 'upcoming':
                message = (
                    f"🌙 <b>Ramazan Yaklaşıyor</b>\n"
                    f"─────────────────────\n"
                    f"Başlangıç: <b>{format_turkish_date(ramadan_info['start_date'])}</b>\n"
                    f"Kalan: <b>{ramadan_info['days_to_start']} gün</b>"
                )
            elif ramadan_info['status'] == 'finished':
                message = (
                    f"✅ <b>Ramazan Sona Erdi</b>\n"
                    f"─────────────────────\n"
                    f"Gelecek Ramazan: <b>{format_turkish_date(ramadan_info['next_ramadan_date'])}</b>\n"
                    f"Kalan: <b>{ramadan_info['days_to_next']} gün</b>"
                )
            else:
                message = "Ramazan bilgileri şu an alınamıyor."
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def handle_gunluk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Günlük içeriği gösterir."""
        with self.app.app_context():
            daily_content = get_daily_content()
        
        keyboard = [[InlineKeyboardButton("⬅️ Ana Menü", callback_data="main_menu")]]
        
        if daily_content:
            type_emoji = {'ayet': '📖', 'hadis': '📜', 'soz': '💬', 'söz': '💬'}
            type_label = {'ayet': 'Günün Ayeti', 'hadis': 'Günün Hadisi', 'soz': 'Günün Sözü', 'söz': 'Günün Sözü'}

            emoji = type_emoji.get(daily_content.get('type'), '💫')
            label = type_label.get(daily_content.get('type'), 'Günlük İçerik')
            
            message = (
                f"{emoji} <b>{label}</b>\n"
                f"─────────────────────\n\n"
                f"<i>{daily_content.get('text')}</i>"
            )
            
            if daily_content.get('source'):
                message += f"\n\n📚 <i>{daily_content['source']}</i>"
        else:
            message = "Günlük içerik şu an gösterilemiyor."
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def handle_rehberler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Rehberleri listeler."""
        with self.app.app_context():
            guides = get_guides()
        
        keyboard_buttons = []
        if guides:
            for guide in guides:
                keyboard_buttons.append([InlineKeyboardButton(f"📖 {guide['title']}", callback_data=f"rehber_{guide['slug']}")])
        
        keyboard_buttons.append([InlineKeyboardButton("⬅️ Geri", callback_data="yardim")])
        
        message = (
            "📚 <b>Bilgi Köşesi</b>\n"
            "─────────────────────\n\n"
            + ("Bir rehber seçin:" if guides else "Henüz rehber eklenmemiş.")
        )
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard_buttons), parse_mode='HTML')
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard_buttons), parse_mode='HTML')

    async def handle_rehber_detay(self, update: Update, context: ContextTypes.DEFAULT_TYPE, slug: str):
        """Belirli bir rehberi detaylı gösterir."""
        with self.app.app_context():
            guide = get_guide_by_slug(slug)
        
        keyboard = [[InlineKeyboardButton("⬅️ Rehberler", callback_data="rehberler")]]
        
        if not guide:
            message = "Rehber bulunamadı."
        else:
            message = (
                f"📖 <b>{guide['title']}</b>\n"
                f"─────────────────────\n\n"
                f"{strip_html_tags(guide['content'])}"
            )
            if len(message) > 4096:
                message = message[:4090] + "…"
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML', disable_web_page_preview=True)
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML', disable_web_page_preview=True)

    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        contact_text = (
            "📱 <b>İletişim</b>\n"
            "─────────────────────\n\n"
            "👨‍💻 <b>Geliştirici:</b> Yiğit Gülyurt\n"
            "📧 yigitgulyurt@proton.me\n"
            "🌐 <a href='https://yigitgulyurt.com'>yigitgulyurt.com</a>\n"
            "🐙 <a href='https://github.com/yigitgulyurt'>github.com/yigitgulyurt</a>"
        )
        keyboard = [[InlineKeyboardButton("⬅️ Geri", callback_data="yardim")]]
        
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
            "📖 <b>Bu Bot Nedir?</b>\n\n"
            "Dünya genelindeki namaz vakitlerini takip etmenizi ve "
            "vakitlerden önce bildirim almanızı sağlar.\n\n"
            "<b>Özellikler:</b>\n"
            "• 81 il ve dünya şehirleri\n"
            "• Vakit öncesi hatırlatma bildirimleri\n"
            "• Haftalık ve aylık takvim\n"
            "• Günlük ayet / hadis / söz\n"
            "• Ramazan ve dini gün takibi\n"
            "• Grup bildirimleri\n\n"
            "<i>/start ile ana menüye dönebilirsiniz.</i>"
        )
        await update.effective_message.reply_text(aciklama, parse_mode='HTML')

    async def handle_temizle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sohbet geçmişini temizler."""
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
        
        await status_msg.edit_text(f"✅ {deleted_count} mesaj silindi.")
        await asyncio.sleep(2)
        await status_msg.delete()
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="🕌 Ana Menü",
            reply_markup=self.get_main_keyboard()
        )

    async def handle_arkadas_oner(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        import urllib.parse
        
        share_text_plain = (
            "🕌 Namaz Vakitleri Botu\n\n"
            "Ezan vakitlerini takip etmek ve bildirim almak için:\n\n"
            "👉 t.me/namaz_vaktibot"
        )
        
        encoded_text = urllib.parse.quote(share_text_plain)
        whatsapp_url = f"https://api.whatsapp.com/send?text={encoded_text}"
        twitter_url = f"https://twitter.com/intent/tweet?text={encoded_text}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Telegram'da Paylaş 🚀", switch_inline_query=share_text_plain)],
            [InlineKeyboardButton("WhatsApp 🟢", url=whatsapp_url),
             InlineKeyboardButton("Twitter 🐦", url=twitter_url)],
            [InlineKeyboardButton("⬅️ Geri", callback_data="yardim")]
        ])
        
        share_msg = (
            "📢 <b>Botu Paylaş</b>\n\n"
            "Arkadaşlarınızın da vakitlerden haberdar olması için botu paylaşabilirsiniz."
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(share_msg, reply_markup=keyboard, parse_mode='HTML')
        else:
            await update.effective_message.reply_text(share_msg, reply_markup=keyboard, parse_mode='HTML')

    async def handle_inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Şehir arama sonuçlarını inline olarak gösterir."""
        query_text = update.inline_query.query.lower().strip()
        
        if not query_text:
            # Boş sorguda yönlendirme kartı göster
            results = [
                InlineQueryResultArticle(
                    id="placeholder",
                    title="🔍 Şehir adı yazın",
                    description="Örnek: Ankara, İstanbul, Bursa…",
                    input_message_content=InputTextMessageContent("Lütfen yukarıdaki arama kutusuna şehir adını yazın."),
                    thumbnail_url="https://raw.githubusercontent.com/yigitgulyurt/namaz-vakitleri-api/master/assets/mosque.png"
                )
            ]
            await update.inline_query.answer(results, cache_time=5, is_personal=False)
            return
        
        matching_cities = [c for c in self.cities if query_text in c.lower()][:10]
        
        results = []
        now = datetime.now(self.tz)
        with self.app.app_context():
            for city in matching_cities:
                country = get_country_for_city(city)
                prayer_times = PrayerService.get_vakitler(city, country, now.strftime('%Y-%m-%d'))
                
                if prayer_times:
                    desc = f"İmsak {prayer_times['imsak']}  ·  Öğle {prayer_times['ogle']}  ·  Akşam {prayer_times['aksam']}"
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
        """Gelen metin mesajlarını işler."""
        if not update.message or not update.message.text:
            return
            
        text = update.message.text
        user_id = update.effective_user.id

        if text.startswith("!sehirsec_"):
            city = text.split("_", 1)[1]
            if city in self.cities:
                self.db.update_user(user_id, sehir=city)
                await update.message.reply_text(
                    f"✅ <b>{city}</b> seçildi!\n\n"
                    "Artık ana menüden vakitleri görebilir, bildirim ayarlarınızı yapabilirsiniz.",
                    reply_markup=self.get_main_keyboard(),
                    parse_mode='HTML'
                )
            else:
                logger.warning(f"Geçersiz şehir seçimi denemesi: {city}")
                await update.message.reply_text(
                    "⚠️ Geçersiz bir şehir seçildi. Lütfen listeden tekrar seçin.",
                    parse_mode='HTML'
                )
        elif text == "Ezan Vakti 🕒":
            await self.handle_vakitler(update, context)
        else:
            await update.message.reply_text(
                "Menüyü kullanmak için aşağıdaki butonlara basın ya da /start yazın.",
                reply_markup=self.get_main_keyboard(),
                parse_mode='HTML'
            )

    async def handle_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user_id = update.effective_user.id
        
        if chat.type == 'private':
            msg = (
                "👥 <b>Grup Ayarları</b>\n\n"
                "Bu özellik yalnızca gruplarda kullanılabilir.\n\n"
                "Botu bir gruba ekleyip yönetici yetkisi verdikten sonra "
                "grupta /grup komutunu çalıştırın."
            )
            keyboard = [[InlineKeyboardButton("⬅️ Geri", callback_data="yardim")]]
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            else:
                await update.effective_message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            return

        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        if bot_member.status != 'administrator':
            await context.bot.send_message(chat.id, "⚠️ Bildirim gönderebilmem için lütfen beni yönetici yapın.")

        member = await context.bot.get_chat_member(chat.id, user_id)
        if member.status not in ['creator', 'administrator']:
            msg = "❌ Bu ayarı yalnızca grup yöneticileri yapabilir."
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
        msg = f"✅ Bu grup için <b>{user['sehir']}</b> vakitleri paylaşılacak.\nBildirimlerinizi özel mesaj üzerinden yönetebilirsiniz."
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.effective_message.reply_text(msg, parse_mode='HTML')

    async def check_notifications(self, context: ContextTypes.DEFAULT_TYPE):
        now = datetime.now(self.tz)
        active_users = self.db.get_active_users()
        city_times_cache = {}

        for user in active_users:
            city = user['sehir']
            if not city: continue
            
            preferred = user['preferred_vakitler'].split(',') if user['preferred_vakitler'] else []
            if not preferred: continue

            if city not in city_times_cache:
                with self.app.app_context():
                    country = get_country_for_city(city)
                    prayer_times = PrayerService.get_vakitler(city, country, now.strftime('%Y-%m-%d'))
                    city_times_cache[city] = prayer_times
            
            prayer_times = city_times_cache[city]
            if not prayer_times: continue

            lead_time = user['bildirim_suresi'] or 5
            
            with self.app.app_context():
                ramadan_info = RamadanService.get_ramadan_info()
            is_ramadan = ramadan_info['is_ramadan']
            
            vakit_labels = {
                'imsak': 'Sahur' if is_ramadan else 'İmsak',
                'gunes': 'Güneş',
                'ogle': 'Öğle',
                'ikindi': 'İkindi',
                'aksam': 'İftar' if is_ramadan else 'Akşam',
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
                    
                    is_sahur = (vakit_key == 'imsak' and is_ramadan)
                    is_iftar = (vakit_key == 'aksam' and is_ramadan)
                    
                    # Hatırlatma (X dakika kala)
                    if abs(diff - (lead_time * 60)) < 30:
                        if is_sahur:
                            text = f"🌙 <b>Sahur Hatırlatması</b>\n\nSahura {lead_time} dakika kaldı! ({city})\n\n<i>Hayırlı sahurlayın.</i>"
                        elif is_iftar:
                            text = f"🌙 <b>İftar Hatırlatması</b>\n\nİftara {lead_time} dakika kaldı! ({city})\n\n<i>Hayırlı iftarlar dileriz.</i>"
                        else:
                            text = f"⏰ <b>{v_name}</b> vaktine {lead_time} dakika kaldı. ({city})"
                        
                        await self._safe_send_message(context.bot, user['user_id'], text)
                        if user['grup_id']:
                            await self._safe_send_message(context.bot, user['grup_id'], text)
                    
                    # Vakit Girdi (tam anında)
                    elif abs(diff) < 30:
                        if is_sahur:
                            text = f"🌙 <b>Sahur Vakti Girdi</b> — {city}\n\n<i>Hayırlı sahurlayın, orucunuz kabul olsun.</i>"
                        elif is_iftar:
                            text = f"🌙 <b>İftar Vakti Girdi</b> — {city}\n\n<i>Hayırlı iftarlar, dualarınız kabul olsun.</i>"
                        else:
                            text = f"🕌 <b>{v_name} Vakti Girdi</b> — {city}\n\n<i>Rabbimiz ibadetlerinizi kabul eylesin.</i>"
                        
                        await self._safe_send_message(context.bot, user['user_id'], text)
                        if user['grup_id']:
                            await self._safe_send_message(context.bot, user['grup_id'], text)
                                
                except Exception as e:
                    logger.error(f"Error in notification loop for user {user['user_id']}: {e}")
        
        # Dini Günler Hatırlatıcıları
        try:
            today = now.date()
            with self.app.app_context():
                dini_gunler_list = DiniGunlerService.get_dini_gunler(today)
            
            tur_emoji = {
                'kandil': '🌙',
                'ramazan': '🌙',
                'bayram': '🎊',
                'ozel': '✨'
            }
            
            active_users = self.db.get_active_users()
            
            for gun in dini_gunler_list:
                gun_tarihi = gun['tarih']
                kalan = gun['kalan_gun']
                gun_adi = gun['ad']
                emoji = tur_emoji.get(gun['tur'], '🔸')
                gun_key = f"{gun_adi}_{gun_tarihi}"
                
                if kalan == 1 and now.hour == 9 and now.minute < 5:
                    hatirlatma_key = f"{gun_key}_1gun"
                    if hatirlatma_key not in self.gonderilen_dini_gunler:
                        mesaj = f"{emoji} <b>Yarın {gun_adi}!</b>\n{DiniGunlerService.format_turkish_date(gun_tarihi)}\n\n<i>Bu kutsal günü en iyi şekilde karşılayalım.</i>"
                        for user in active_users:
                            await self._safe_send_message(context.bot, user['user_id'], mesaj)
                            if user['grup_id']:
                                await self._safe_send_message(context.bot, user['grup_id'], mesaj)
                        self.gonderilen_dini_gunler.add(hatirlatma_key)
                
                elif kalan == 0 and now.hour == 9 and now.minute < 5:
                    bugun_key = f"{gun_key}_bugun"
                    if bugun_key not in self.gonderilen_dini_gunler:
                        mesaj = f"{emoji} <b>Bugün {gun_adi}!</b>\n{DiniGunlerService.format_turkish_date(gun_tarihi)}\n\n<i>Bu kutsal günü en iyi şekilde değerlendirelim.</i>"
                        for user in active_users:
                            await self._safe_send_message(context.bot, user['user_id'], mesaj)
                            if user['grup_id']:
                                await self._safe_send_message(context.bot, user['grup_id'], mesaj)
                        self.gonderilen_dini_gunler.add(bugun_key)
        
        except Exception as e:
            logger.error(f"Dini günler hatırlatıcıları hatası: {e}")

    async def _safe_send_message(self, bot, chat_id, text):
        """Mesaj gönderir, hata durumunda kullanıcıyı pasif yapar."""
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')
            return True
        except Exception as e:
            err_msg = str(e).lower()
            logger.error(f"Could not send message to {chat_id}: {e}")
            if "bot was blocked" in err_msg or "chat not found" in err_msg or "user is deactivated" in err_msg:
                self.db.set_user_inactive(chat_id)
                logger.info(f"User {chat_id} deactivated. Notifications disabled.")
            return False

    async def handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Hataları yakalar ve loglar."""
        err_str = str(context.error)
        
        if "No item with that key" in err_str:
            logger.warning(f"Ignored 'No item with that key' error. Update: {update}")
            return

        logger.error(f"Update {update} caused error {context.error}")
        
        if isinstance(update, Update) and update.effective_message:
            try:
                if "Forbidden" not in err_str:
                    await update.effective_message.reply_text(
                        "Bir hata oluştu. /start yazarak ana menüye dönebilirsiniz."
                    )
            except:
                pass

    async def post_init(self, application: Application) -> None:
        commands = [
            ("start", "Ana menüyü açar"),
            ("help", "Tüm özellikler"),
            ("aciklama", "Bot hakkında bilgi"),
            ("grup", "Grup bildirimlerini ayarlar"),
            ("temizle", "Sohbeti temizler"),
            ("iletisim", "Geliştiriciye ulaş"),
            ("arkadas_oner", "Botu paylaş"),
            ("ramazan", "Ramazan bilgileri"),
            ("gunluk", "Günlük içerik"),
            ("rehberler", "Bilgi köşesi"),
            ("haftalik", "Haftalık vakit takvimi"),
            ("aylik", "Aylık vakit takvimi")
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot komutları başarıyla ayarlandı.")

    def run(self):
        application = Application.builder().token(self.token).post_init(self.post_init).build()
        
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.handle_help))
        application.add_handler(CommandHandler("aciklama", self.handle_aciklama))
        application.add_handler(CommandHandler("temizle", self.handle_temizle))
        application.add_handler(CommandHandler("arkadas_oner", self.handle_arkadas_oner))
        application.add_handler(CommandHandler("iletisim", self.handle_contact))
        application.add_handler(CommandHandler("grup", self.handle_group))
        application.add_handler(CommandHandler("ramazan", self.handle_ramazan))
        application.add_handler(CommandHandler("gunluk", self.handle_gunluk))
        application.add_handler(CommandHandler("gundelik", self.handle_gunluk))
        application.add_handler(CommandHandler("rehberler", self.handle_rehberler))
        application.add_handler(CommandHandler("bilgi_kosesi", self.handle_rehberler))
        application.add_handler(CommandHandler("haftalik", self.handle_haftalik_takvim))
        application.add_handler(CommandHandler("aylik", self.handle_aylik_takvim))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(InlineQueryHandler(self.handle_inline_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        application.add_error_handler(self.handle_error)
        application.job_queue.run_repeating(self.check_notifications, interval=60, first=10)
        
        logger.info("Telegram bot is running...")
        application.run_polling()

if __name__ == '__main__':
    bot = NamazBot()
    bot.run()