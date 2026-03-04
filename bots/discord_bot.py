import nextcord
from nextcord.ext import commands, tasks
import os
import sys
import sqlite3
import logging
from logging.handlers import RotatingFileHandler

# Proje kök dizinini Python yoluna ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
from app.services import PrayerService, UserService
from app.config import Config
from app.factory import create_app

# Logging configuration
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'discord_bot.log')

log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# File Handler
file_handler = RotatingFileHandler(log_file, maxBytes=5000000, backupCount=3, encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Console Handler (Only WARNING and above)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.WARNING)

# Root logger setup
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

# Reduce noise
logging.getLogger('nextcord').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

class DiscordDB:
    def __init__(self, db_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'discord_users.db')):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                sehir TEXT,
                bildirim_aktif INTEGER DEFAULT 0,
                bildirim_suresi INTEGER DEFAULT 5
            )''')
            conn.commit()

    def get_user(self, user_id):
        with self.get_connection() as conn:
            return conn.execute('SELECT * FROM users WHERE user_id = ?', (str(user_id),)).fetchone()

    def update_user(self, user_id, **kwargs):
        cols = ', '.join(f"{k} = ?" for k in kwargs.keys())
        vals = list(kwargs.values()) + [str(user_id)]
        with self.get_connection() as conn:
            conn.execute(f'UPDATE users SET {cols} WHERE user_id = ?', vals)
            conn.commit()

    def add_or_update_user(self, user_id, sehir):
        with self.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, sehir) VALUES (?, ?)", (str(user_id), sehir))
            conn.commit()

    def get_active_users(self):
        with self.get_connection() as conn:
            return conn.execute('SELECT * FROM users WHERE bildirim_aktif = 1').fetchall()

class NamazDiscordBot(commands.Bot):
    def __init__(self):
        self.app = create_app()
        intents = nextcord.Intents.default()
        super().__init__(intents=intents)
        self.db = DiscordDB()
        with self.app.app_context():
            self.cities = UserService.get_sehirler('ALL')
        self.token = Config.DISCORD_TOKEN

    async def on_ready(self):
        logger.info(f"Discord Bot giriş yaptı: {self.user}")
        self.bildirim_kontrol.start()

    @tasks.loop(minutes=1)
    async def bildirim_kontrol(self):
        now = datetime.now(timezone.utc) + timedelta(hours=3) # Istanbul time
        users = self.db.get_active_users()
        
        city_times_cache = {}

        for user in users:
            sehir = user['sehir']
            if not sehir: continue
            
            if sehir not in city_times_cache:
                with self.app.app_context():
                    city_times_cache[sehir] = PrayerService.get_vakitler(sehir, 'TR', now.strftime('%Y-%m-%d'))
            
            vakitler = city_times_cache[sehir]
            lead_time = user['bildirim_suresi'] or 5
            
            for v_key, v_time_str in vakitler.items():
                if v_key == "timezone" or v_time_str == "null" or not v_time_str: continue
                
                try:
                    v_time = datetime.strptime(v_time_str, '%H:%M')
                    v_dt = now.replace(hour=v_time.hour, minute=v_time.minute, second=0, microsecond=0)
                    
                    # Exact time
                    if abs((now - v_dt).total_seconds()) < 30:
                        await self.send_notification(user, v_key, v_time_str, is_reminder=False)
                    # Reminder time
                    elif abs((now - (v_dt - timedelta(minutes=lead_time))).total_seconds()) < 30:
                        await self.send_notification(user, v_key, v_time_str, is_reminder=True, lead_time=lead_time)
                except Exception as e:
                    logger.error(f"Time parse error in Discord bot: {e}")

    async def send_notification(self, user, v_key, v_time_str, is_reminder=False, lead_time=0):
        v_names = {'imsak':'İmsak','gunes':'Güneş','ogle':'Öğle','ikindi':'İkindi','aksam':'Akşam','yatsi':'Yatsı'}
        v_name = v_names.get(v_key, v_key)
        
        if is_reminder:
            msg = f"⏰ {v_name} vaktine {lead_time} dakika kaldı!\n📍 {user['sehir']}\n🕒 Vakit: {v_time_str}"
        else:
            msg = f"🕌 {v_name} vakti geldi!\n📍 {user['sehir']}\n🕒 Vakit: {v_time_str}"
            
        try:
            discord_user = await self.fetch_user(int(user['user_id']))
            await discord_user.send(msg)
        except Exception as e:
            logger.error(f"Discord notify error for {user['user_id']}: {e}")

bot = NamazDiscordBot()

@bot.slash_command(description="Botun çalıştığını test eder.")
async def ping(interaction: nextcord.Interaction):
    await interaction.send("Pong!", ephemeral=True)

@bot.slash_command(description="Tüm şehirlerin listesini gösterir.")
async def sehirler(interaction: nextcord.Interaction):
    sehirler_str = ", ".join(bot.cities[:30]) + "..."
    await interaction.send(f"Türkiye'deki bazı şehirler:\n{sehirler_str}\n\nToplam {len(bot.cities)} şehir mevcut.", ephemeral=True)

@bot.slash_command(description="Şehrini seç ve kaydet.")
async def sehir_sec(interaction: nextcord.Interaction, sehir: str):
    sehir = sehir.title()
    if sehir not in bot.cities:
        await interaction.send(f"❌ {sehir} geçerli bir şehir değil.", ephemeral=True)
        return
    bot.db.add_or_update_user(interaction.user.id, sehir)
    await interaction.send(f"✅ Şehriniz başarıyla kaydedildi: {sehir}", ephemeral=True)

@bot.slash_command(description="Kayıtlı şehrin için bugünkü ezan vakitlerini gösterir.")
async def vakitler(interaction: nextcord.Interaction):
    user = bot.db.get_user(interaction.user.id)
    if not user or not user["sehir"]:
        await interaction.send("❌ Önce bir şehir seçmelisiniz. /sehir_sec komutunu kullanın.", ephemeral=True)
        return
    
    sehir = user["sehir"]
    bugun = datetime.now().strftime('%Y-%m-%d')
    with bot.app.app_context():
        v = PrayerService.get_vakitler(sehir, 'TR', bugun)
    
    msg = f"📅 {sehir} için Namaz Vakitleri:\n\n"
    msg += f"🌅 İmsak: {v['imsak']}\n🌞 Güneş: {v['gunes']}\n🌆 Öğle: {v['ogle']}\n🌅 İkindi: {v['ikindi']}\n🌆 Akşam: {v['aksam']}\n🌙 Yatsı: {v['yatsi']}"
    await interaction.send(msg, ephemeral=True)

@bot.slash_command(description="Ezan vakti bildirimi açar.")
async def bildirim(interaction: nextcord.Interaction):
    user = bot.db.get_user(interaction.user.id)
    if not user or not user["sehir"]:
        await interaction.send("❌ Önce bir şehir seçmelisiniz. /sehir_sec komutunu kullanın.", ephemeral=True)
        return
    bot.db.update_user(interaction.user.id, bildirim_aktif=1)
    await interaction.send("🔔 Namaz vakti bildirimi açıldı.", ephemeral=True)

@bot.slash_command(description="Namaz vakti bildirimini kapatır.")
async def bildirim_kapat(interaction: nextcord.Interaction):
    bot.db.update_user(interaction.user.id, bildirim_aktif=0)
    await interaction.send("🔕 Namaz vakti bildirimi kapatıldı.", ephemeral=True)

@bot.slash_command(description="Bildirim ayarlarını ve durumunu gösterir.")
async def bildirim_durum(interaction: nextcord.Interaction):
    user = bot.db.get_user(interaction.user.id)
    if not user:
        await interaction.send("❌ Kayıtlı bilginiz bulunamadı.", ephemeral=True)
        return
    durum = "Açık ✅" if user["bildirim_aktif"] else "Kapalı 🔕"
    await interaction.send(f"📊 Durum: {durum}\n⏰ Süre: {user['bildirim_suresi']} dk önce\n📍 Şehir: {user['sehir']}", ephemeral=True)

@bot.slash_command(description="Bildirim süresini (kaç dakika önce) ayarla.")
async def bildirim_ayarla(interaction: nextcord.Interaction, dakika: int):
    if dakika < 1 or dakika > 60:
        await interaction.send("❌ Bildirim süresi 1-60 dakika arası olmalı.", ephemeral=True)
        return
    bot.db.update_user(interaction.user.id, bildirim_suresi=dakika)
    await interaction.send(f"✅ Bildirim süresi {dakika} dakika olarak ayarlandı.", ephemeral=True)

if __name__ == "__main__":
    bot.run(bot.token)
