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
from app.services import PrayerService, UserService
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
def log_user_action(user_id):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if user_id not in bot_stats['users']:
        bot_stats['users'][user_id] = {'count': 0, 'last_seen': now}
    bot_stats['users'][user_id]['count'] += 1
    bot_stats['users'][user_id]['last_seen'] = now
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
                    arkadas_onerisi INTEGER DEFAULT 0
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

    def add_user(self, user_id):
        with self.get_connection() as conn:
            conn.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
            conn.commit()

    def get_active_users(self):
        with self.get_connection() as conn:
            return conn.execute('SELECT * FROM users WHERE bildirim_aktif = 1').fetchall()

class NamazBot:
    def __init__(self):
        self.app = create_app()
        self.token = Config.TELEGRAM_TOKEN
        self.db = TelegramDB()
        self.tz = pytz.timezone('Europe/Istanbul')
        with self.app.app_context():
            self.cities = UserService.get_sehirler('ALL')

    def get_main_keyboard(self):
        keyboard = [
            [InlineKeyboardButton("Namaz Vakitleri 🕒", callback_data="vakitler"),
             InlineKeyboardButton("🔍 Şehir Seçimi 📍", switch_inline_query_current_chat="")],
            [InlineKeyboardButton("Bildirim Ayarları 🔔", callback_data="bildirim_ayarlari"),
             InlineKeyboardButton("Grup Ayarları 👥", callback_data="grup_ayarlari")],
            [InlineKeyboardButton("Yardım ❓", callback_data="yardim"),
             InlineKeyboardButton("İletişim 📱", callback_data="iletisim")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_notification_keyboard(self, user_id):
        user = self.db.get_user(user_id)
        is_active = user['bildirim_aktif'] if user else False
        
        keyboard = [
            [InlineKeyboardButton("Bildirimleri Kapat 🔕" if is_active else "Bildirimleri Aç 🔔", 
                                 callback_data="bildirim_toggle")],
            [InlineKeyboardButton("Bildirim Süresini Ayarla ⚙️", callback_data="bildirim_sure_menu")],
            [InlineKeyboardButton("Ana Menüye Dön ⬅️", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        log_user_action(user_id)
        self.db.add_user(user_id)

        chat_id = update.effective_chat.id
        current_msg_id = update.effective_message.message_id
        
        # Show a temporary cleaning message
        status_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="🧹 Sohbet temizleniyor, lütfen bekleyiniz..."
        )
        
        # Try to delete the last 50 messages to "clean" the chat
        for i in range(50):
            try:
                # Don't delete the status message we just sent
                if current_msg_id - i == status_msg.message_id:
                    continue
                await context.bot.delete_message(chat_id=chat_id, message_id=current_msg_id - i)
            except:
                continue

        # Delete the status message before sending main menu
        try:
            await status_msg.delete()
        except:
            pass

        welcome_text = (
            '🕌 Merhaba! Namaz Vakitleri Bot\'a hoş geldiniz!\n\n'
            'Ben size namaz vakitlerini hatırlatmak için buradayım. Aşağıdaki butonları kullanarak işlemlerinizi gerçekleştirebilirsiniz.'
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=self.get_main_keyboard()
        )

    async def handle_vakitler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user['sehir']:
            msg = "❌ Önce bir şehir seçmelisiniz!\n\n💡 Şehir seçmek için 'Şehir Seçimi' butonunu kullanın."
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, reply_markup=self.get_main_keyboard())
            else:
                await update.effective_message.reply_text(msg, reply_markup=self.get_main_keyboard())
            return

        sehir = user['sehir']
        now = datetime.now(self.tz)
        with self.app.app_context():
            prayer_times = PrayerService.get_vakitler(sehir, 'TR', now.strftime('%Y-%m-%d'))
        
        message = f"📅 {now.strftime('%d.%m.%Y')} Namaz Vakitleri ({sehir}):\n\n"
        message += f"🌅 İmsak: {prayer_times.get('imsak', 'N/A')}\n"
        message += f"🌞 Güneş: {prayer_times.get('gunes', 'N/A')}\n"
        message += f"🌆 Öğle: {prayer_times.get('ogle', 'N/A')}\n"
        message += f"🌅 İkindi: {prayer_times.get('ikindi', 'N/A')}\n"
        message += f"🌆 Akşam: {prayer_times.get('aksam', 'N/A')}\n"
        message += f"🌙 Yatsı: {prayer_times.get('yatsi', 'N/A')}\n"
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(message, reply_markup=self.get_main_keyboard())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await update.callback_query.answer("Zaten güncel vakitleri görüyorsunuz.")
                else:
                    raise e
        else:
            await update.effective_message.reply_text(message, reply_markup=self.get_main_keyboard())

    async def _show_notification_menu(self, query, user_id):
        user = self.db.get_user(user_id)
        status = "Aktif ✅" if user['bildirim_aktif'] else "Kapalı 🔕"
        city = user['sehir'] or "Seçilmemiş"
        time = user['bildirim_suresi'] or 5
        
        msg = (f"📊 Bildirim Durumunuz:\n\n"
               f"🔔 Bildirimler: {status}\n"
               f"⏰ Bildirim Süresi: {time} dakika\n"
               f"📍 Seçili Şehir: {city}\n\n"
               "Ayarlarınızı değiştirmek için butonları kullanın:")
        try:
            await query.edit_message_text(msg, reply_markup=self.get_notification_keyboard(user_id))
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer()
            else:
                raise e

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        log_user_action(user_id)
        data = query.data

        if data == "main_menu":
            try:
                await query.edit_message_text(
                    '🕌 Merhaba! Namaz Vakitleri Bot\'a hoş geldiniz!',
                    reply_markup=self.get_main_keyboard()
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer()
                else:
                    raise e
        elif data == "vakitler":
            await self.handle_vakitler(update, context)
        elif data == "bildirim_ayarlari":
            await self._show_notification_menu(query, user_id)
        elif data == "bildirim_toggle":
            user = self.db.get_user(user_id)
            new_status = 0 if user['bildirim_aktif'] else 1
            self.db.update_user(user_id, bildirim_aktif=new_status)
            await query.answer("✅ Bildirimler " + ("açıldı" if new_status else "kapatıldı"))
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
                if "Message is not modified" in str(e):
                    await query.answer()
                else:
                    raise e
        elif data.startswith("set_sure_"):
            sure = int(data.split("_")[2])
            self.db.update_user(user_id, bildirim_suresi=sure)
            await query.answer(f"✅ Süre {sure} dakika olarak ayarlandı")
            await self._show_notification_menu(query, user_id)
        elif data == "yardim":
            await self.handle_help(update, context)
        elif data == "iletisim":
            await self.handle_contact(update, context)
        elif data == "grup_ayarlari":
            await self.handle_group(update, context)

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "🕌 *Namaz Vakitleri Bot - Yardım*\n\n"
            "📌 *Komutlar:*\n"
            "/start - Ana menüyü açar\n"
            "/aciklama - Bot hakkında bilgi verir\n"
            "/temizle - Sohbet geçmişini temizler\n"
            "/arkadas_oner - Botu başkalarıyla paylaşır\n"
            "/help - Bu yardım mesajını gösterir\n\n"
            "📍 *Şehir Seçimi:* Arama butonunu kullanarak şehrinizi bulun.\n"
            "🕒 *Vakitler:* Günlük namaz vakitlerini anlık görün.\n"
            "🔔 *Bildirimler:* Vakitlerden önce hatırlatıcı alın.\n"
            "👥 *Gruplar:* Botu grubunuza ekleyip vakitleri paylaşın."
        )
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(help_text, reply_markup=self.get_main_keyboard(), parse_mode='Markdown')
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await update.callback_query.answer()
                else:
                    raise e
        else:
            await update.effective_message.reply_text(help_text, reply_markup=self.get_main_keyboard(), parse_mode='Markdown')

    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        contact_text = (
            "📱 İletişim\n\n"
            "👨‍💻 Geliştirici: Yiğit Gülyurt\n"
            "📧 E-posta: yigitgulyurt@proton.me\n"
            "🌐 GitHub: github.com/yigitgulyurt"
        )
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(contact_text, reply_markup=self.get_main_keyboard())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await update.callback_query.answer()
                else:
                    raise e
        else:
            await update.effective_message.reply_text(contact_text, reply_markup=self.get_main_keyboard())

    async def handle_aciklama(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        aciklama = (
            "📖 *Namaz Vakti Botu Nedir?*\n\n"
            "Bu bot, dünya genelindeki namaz vakitlerini anlık olarak takip etmenizi ve "
            "vakitlerden önce bildirim almanızı sağlar.\n\n"
            "✨ *Özellikler:*\n"
            "• 81 il ve dünya şehirleri desteği\n"
            "• Vakitlerden önce hatırlatma (5-15 dk)\n"
            "• Grup desteği ile toplu bilgilendirme\n"
            "• Temiz ve hızlı arayüz\n\n"
            "💡 *İpucu:* /start yazarak her zaman ana menüye dönebilirsiniz."
        )
        await update.effective_message.reply_text(aciklama, parse_mode='Markdown')

    async def handle_temizle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        current_msg_id = update.effective_message.message_id
        
        status_msg = await update.effective_message.reply_text("🧹 Sohbet temizleniyor...")
        
        # Try to delete the last 50 messages
        deleted_count = 0
        for i in range(50):
            try:
                # Don't delete the status message we just sent
                if current_msg_id - i == status_msg.message_id:
                    continue
                await context.bot.delete_message(chat_id=chat_id, message_id=current_msg_id - i)
                deleted_count += 1
            except:
                continue
        
        await status_msg.edit_text(f"✅ {deleted_count} mesaj temizlendi ve sohbet sıfırlandı.")
        # Automatically delete the status message after 3 seconds
        await asyncio.sleep(3)
        try:
            await status_msg.delete()
        except:
            pass

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
            [InlineKeyboardButton("Twitter'da Paylaş 🐦", url=twitter_url)]
        ])
        
        await update.effective_message.reply_text(
            "📢 *Botu Paylaş*\n\n"
            "Aşağıdaki butonları kullanarak botu arkadaşlarınızla her yerden paylaşabilirsiniz.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def handle_inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.inline_query.query.lower().strip()
        results = []
        
        filtered = [c for c in self.cities if query in c.lower()][:20]
        if not query: filtered = self.cities[:20]

        for i, city in enumerate(filtered):
            results.append(InlineQueryResultArticle(
                id=str(i),
                title=city,
                description=f"{city} için vakitleri seç",
                input_message_content=InputTextMessageContent(f"!sehirsec_{city}"),
                thumbnail_url="https://static.vecteezy.com/system/resources/previews/019/619/771/non_2x/sultan-ahamed-mosque-icon-sultan-ahamed-mosque-blue-illustration-blue-mosque-icon-vector.jpg"
            ))
        
        await update.inline_query.answer(results, cache_time=1)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return
            
        text = update.message.text
        user_id = update.effective_user.id

        if text.startswith("!sehirsec_"):
            city = text.split("_")[1]
            if city in self.cities:
                self.db.update_user(user_id, sehir=city)
                await update.message.reply_text(f"✅ {city} seçildi!", reply_markup=self.get_main_keyboard())
        elif text == "Namaz Vakitleri 🕒":
            await self.handle_vakitler(update, context)

    async def handle_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user_id = update.effective_user.id
        
        if chat.type == 'private':
            msg = "❌ Bu özellik sadece gruplarda kullanılabilir."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            else:
                await update.effective_message.reply_text(msg)
            return

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
            msg = "❌ Önce özelden bir şehir seçmelisiniz."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            else:
                await update.effective_message.reply_text(msg)
            return

        self.db.update_user(user_id, grup_id=str(chat.id))
        msg = f"✅ Bu grup için {user['sehir']} vakitleri paylaşılacaktır."
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.effective_message.reply_text(msg)

    async def send_vakit_notification(self, user_id, chat_id, vakit_name, vakit_time, is_reminder=False, lead_time=5):
        try:
            if is_reminder:
                text = f"⏰ Hatırlatıcı: {vakit_name} vaktine {lead_time} dakika kaldı! ({vakit_time})"
            else:
                text = f"🕌 {vakit_name} vakti girdi! ({vakit_time})"
            
            from telegram.ext import Application
            # We need a way to send message without having the 'context' in some cases, 
            # but here we are usually inside a job which has 'context'.
            # However, this method is called from check_notifications.
            return text
        except Exception as e:
            logger.error(f"Error preparing notification: {e}")
            return None

    async def check_notifications(self, context: ContextTypes.DEFAULT_TYPE):
        now = datetime.now(self.tz)
        active_users = self.db.get_active_users()
        
        city_times_cache = {}

        for user in active_users:
            city = user['sehir']
            if not city: continue
            
            if city not in city_times_cache:
                with self.app.app_context():
                    city_times_cache[city] = PrayerService.get_vakitler(city, 'TR', now.strftime('%Y-%m-%d'))
            
            prayer_times = city_times_cache[city]
            if not prayer_times: continue

            lead_time = user['bildirim_suresi'] or 5
            
            for vakit_key, vakit_time_str in prayer_times.items():
                if vakit_key == "timezone" or vakit_time_str == "null" or not vakit_time_str: continue
                
                try:
                    v_time = datetime.strptime(vakit_time_str, '%H:%M').time()
                    v_dt = now.replace(hour=v_time.hour, minute=v_time.minute, second=0, microsecond=0)
                    
                    diff = (v_dt - now).total_seconds()
                    
                    # Exact time (within 30 seconds of the minute)
                    if abs(diff) < 30:
                        v_name = {'imsak':'İmsak','gunes':'Güneş','ogle':'Öğle','ikindi':'İkindi','aksam':'Akşam','yatsi':'Yatsı'}.get(vakit_key, vakit_key)
                        text = f"🕌 {v_name} vakti girdi! ({vakit_time_str})"
                        await self._safe_send_message(context.bot, user['user_id'], text)
                        if user['grup_id']:
                            await self._safe_send_message(context.bot, user['grup_id'], text)
                            
                    # Reminder time
                    elif abs(diff - (lead_time * 60)) < 30:
                        v_name = {'imsak':'İmsak','gunes':'Güneş','ogle':'Öğle','ikindi':'İkindi','aksam':'Akşam','yatsi':'Yatsı'}.get(vakit_key, vakit_key)
                        text = f"⏰ Hatırlatıcı: {v_name} vaktine {lead_time} dakika kaldı! ({vakit_time_str})"
                        await self._safe_send_message(context.bot, user['user_id'], text)
                        if user['grup_id']:
                            await self._safe_send_message(context.bot, user['grup_id'], text)
                            
                except Exception as e:
                    logger.error(f"Error in notification loop for user {user['user_id']}: {e}")

    async def _safe_send_message(self, bot, chat_id, text):
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            logger.error(f"Could not send message to {chat_id}: {e}")
            if "bot was blocked" in str(e) or "chat not found" in str(e):
                # Optionally disable notifications for this user/group
                pass

    async def handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Update {update} caused error {context.error}")
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text("❌ Bir hata oluştu. Çok fazla istek gönderdiniz. /start kullanarak tekrar deneyin.")
            except:
                pass

    def run(self):
        application = Application.builder().token(self.token).build()
        
        # Handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.handle_help))
        application.add_handler(CommandHandler("aciklama", self.handle_aciklama))
        application.add_handler(CommandHandler("temizle", self.handle_temizle))
        application.add_handler(CommandHandler("arkadas_oner", self.handle_arkadas_oner))
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
