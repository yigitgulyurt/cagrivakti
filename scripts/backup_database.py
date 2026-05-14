#!/usr/bin/env python3
"""
Veritabanı Yedekleme Scripti
Bu script, veritabanını yedeklemek için kullanılır.
"""

import os
import sys
import shutil
import gzip
from datetime import datetime
from dotenv import load_dotenv

# Proje kök dizinini ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_backup():
    load_dotenv()
    
    # Yedekleme dizinini oluştur
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Veritabanı dosyası yolu (SQLite için)
    db_path = os.environ.get('DATABASE_URL')
    if db_path and db_path.startswith('sqlite:///'):
        db_path = db_path.replace('sqlite:///', '')
    else:
        # Varsayılan instance dizini
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'cagrivakti.db')
    
    if not os.path.exists(db_path):
        print(f"Hata: Veritabanı dosyası bulunamadı: {db_path}")
        return False
    
    # Yedek dosyası adı
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'cagrivakti_backup_{timestamp}.db.gz'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Yedekleme ve sıkıştırma
    try:
        with open(db_path, 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        print(f"Başarılı! Yedek oluşturuldu: {backup_path}")
        
        # Eski yedekleri temizle (son 30 günü tut)
        clean_old_backups(backup_dir, days=30)
        
        return True
    except Exception as e:
        print(f"Hata: Yedekleme başarısız: {e}")
        return False

def clean_old_backups(backup_dir, days=30):
    """Eski yedek dosyalarını siler"""
    import time
    
    now = time.time()
    cutoff = now - (days * 86400)
    
    for filename in os.listdir(backup_dir):
        if filename.startswith('cagrivakti_backup_') and filename.endswith('.db.gz'):
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
