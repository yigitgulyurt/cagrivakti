#!/usr/bin/env python3
"""
Veritabanı Yedekleme Scripti
Bu script, veritabanını yedeklemek ve Google Drive'a göndermek için kullanılır.
"""

import os
import sys
import shutil
import gzip
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Proje kök dizinini ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_backup():
    load_dotenv()
    
    # Yedekleme dizinini oluştur
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Veritabanı dosyası yolu (instance dizininde)
    instance_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance')
    db_files = []
    
    # Instance dizinindeki tüm .db dosyalarını bul
    for filename in os.listdir(instance_dir):
        if filename.endswith('.db'):
            db_files.append(os.path.join(instance_dir, filename))
    
    if not db_files:
        print(f"Hata: Instance dizininde veritabanı dosyası bulunamadı: {instance_dir}")
        return False
    
    success = True
    all_backup_paths = []
    
    # Her veritabanı dosyası için yedek al
    for db_path in db_files:
        if not os.path.exists(db_path):
            print(f"Hata: Veritabanı dosyası bulunamadı: {db_path}")
            continue
        
        db_filename = os.path.basename(db_path).replace('.db', '')
        
        # Yedek dosyası adı
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'{db_filename}_backup_{timestamp}.db.gz'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Yedekleme ve sıkıştırma
        try:
            with open(db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            print(f"Başarılı! Yedek oluşturuldu: {backup_path}")
            all_backup_paths.append(backup_path)
        except Exception as e:
            print(f"Hata: Yedekleme başarısız {db_path}: {e}")
            success = False
    
    # Eski yedekleri temizle (son 30 günü tut)
    clean_old_backups(backup_dir, days=30)
    
    # Rclone ile tüm yedekleri Google Drive'a gönder
    for backup_path in all_backup_paths:
        upload_to_google_drive(backup_path)
    
    # Google Drive'daki eski yedekleri temizle (hem ana klasör hem de bot-backups)
    try:
        # Remote adını bul (gdrive veya drive)
        remote_name = 'gdrive:'
        result = subprocess.run(['rclone', 'listremotes'], capture_output=True, text=True)
        if 'gdrive:' not in result.stdout and 'drive:' in result.stdout:
            remote_name = 'drive:'
        
        # Ana klasörü temizle
        clean_remote_backups(f'{remote_name}cagrivakti/database-backups', days=30)
        # Bot-backups klasörünü temizle
        clean_remote_backups(f'{remote_name}cagrivakti/database-backups/bot-backups', days=30)
    except Exception as e:
        print(f"Uyarı: Remote temizleme başarısız: {e}")
    
    return success

def upload_to_google_drive(backup_path):
    """Yedek dosyasını rclone ile Google Drive'a gönderir"""
    rclone_configured = False
    
    # Rclone yapılandırmasını kontrol et
    try:
        result = subprocess.run(
            ['rclone', 'listremotes'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if 'gdrive:' in result.stdout or 'drive:' in result.stdout:
            rclone_configured = True
    except FileNotFoundError:
        print("Uyarı: rclone bulunamadı. Google Drive'a yükleme atlanıyor.")
        return
    except Exception as e:
        print(f"Uyarı: rclone kontrolü başarısız: {e}")
        return
    
    if not rclone_configured:
        print("\nGoogle Drive için rclone yapılandırılmamış!")
        print("Lütfen şu adımları izleyin:")
        print("1. rclone'ı indirin: https://rclone.org/downloads/")
        print("2. 'rclone config' komutu ile Google Drive'u yapılandırın (isim olarak 'gdrive' kullanın)")
        print("3. Daha sonra tekrar bu scripti çalıştırın.\n")
        return
    
    # Google Drive'a yükle
    try:
        # Remote adını bul (gdrive veya drive)
        remote_name = 'gdrive:'
        result = subprocess.run(['rclone', 'listremotes'], capture_output=True, text=True)
        if 'gdrive:' not in result.stdout and 'drive:' in result.stdout:
            remote_name = 'drive:'
        
        # Dosya adına göre klasör belirle
        backup_filename = os.path.basename(backup_path)
        if 'discord_users' in backup_filename or 'telegram_bot' in backup_filename:
            remote_folder = f'{remote_name}cagrivakti/database-backups/bot-backups'
        else:
            remote_folder = f'{remote_name}cagrivakti/database-backups'
        
        print(f"Yedek Google Drive'a yükleniyor: {backup_path}")
        
        subprocess.run(
            ['rclone', 'copy', backup_path, remote_folder],
            check=True,
            timeout=300
        )
        
        print(f"Başarılı! Yedek Google Drive'a yüklendi: {remote_folder}")
        
    except Exception as e:
        print(f"Hata: Google Drive'a yükleme başarısız: {e}")

def clean_remote_backups(remote_folder, days=30):
    """Google Drive'daki eski yedekleri temizler"""
    try:
        print("Google Drive'daki eski yedekler kontrol ediliyor...")
        # Remote dosyaları listele
        result = subprocess.run(
            ['rclone', 'lsjson', remote_folder],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print("Uyarı: Remote dosyalar listelenemedi")
            return
        
        import json
        files = json.loads(result.stdout)
        
        # Şu anki zamanı al
        from datetime import datetime
        now = datetime.now().timestamp()
        cutoff = now - (days * 86400)
        
        for file_info in files:
            if 'ModTime' in file_info and 'Name' in file_info:
                file_name = file_info['Name']
                if file_name.startswith('cagrivakti_backup_') or file_name.endswith('.db.gz') or file_name.startswith('discord_users_backup_') or file_name.startswith('telegram_bot_backup_'):
                    # ModTime'ı parse et (RFC3339 formatı)
                    try:
                        mod_time = datetime.fromisoformat(file_info['ModTime'].replace('Z', '+00:00'))
                        mod_timestamp = mod_time.timestamp()
                        
                        if mod_timestamp < cutoff:
                            # Dosyayı sil
                            remote_path = f'{remote_folder}/{file_name}'
                            print(f"Eski remote yedek siliniyor: {file_name}")
                            subprocess.run(
                                ['rclone', 'deletefile', remote_path],
                                timeout=30
                            )
                    except Exception as e:
                        print(f"Uyarı: Dosya işlenemedi {file_name}: {e}")
        
    except Exception as e:
        print(f"Uyarı: Remote temizleme başarısız: {e}")

def clean_old_backups(backup_dir, days=30):
    """Eski yedek dosyalarını siler"""
    import time
    
    now = time.time()
    cutoff = now - (days * 86400)
    
    for filename in os.listdir(backup_dir):
        if filename.endswith('.db.gz'):
            file_path = os.path.join(backup_dir, filename)
            file_mtime = os.path.getmtime(file_path)
            
            if file_mtime < cutoff:
                try:
                    os.remove(file_path)
                    print(f"Eski yedek silindi: {filename}")
                except Exception as e:
                    print(f"Hata: Eski yedek silinemedi {filename}: {e}")

if __name__ == '__main__':
    success = create_backup()
    sys.exit(0 if success else 1)
