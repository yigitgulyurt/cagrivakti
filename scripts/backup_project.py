#!/usr/bin/env python3
"""
Proje Yedekleme Scripti
Bu script, tüm projeyi Google Drive'a yedeklemek için kullanılır.
"""

import os
import sys
import subprocess
import shutil
import gzip
from datetime import datetime
from dotenv import load_dotenv

# Proje kök dizinini ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_project_backup():
    load_dotenv()
    
    # Proje kök dizini
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Yedekleme için geçici dizin oluştur
    temp_backup_dir = os.path.join(project_root, 'temp_backup')
    os.makedirs(temp_backup_dir, exist_ok=True)
    
    try:
        print("Proje dosyaları hazırlanıyor...")
        
        # Yedeklenecek dosyaları ve klasörleri belirle
        items_to_backup = [
            'app/',
            'scripts/',
            'migrations/',
            'app.py',
            'wsgi.py',
            'requirements.txt',
            '.env.example',
            'README.md'
        ]
        
        # Dosyaları geçici dizine kopyala
        for item in items_to_backup:
            item_path = os.path.join(project_root, item)
            if os.path.exists(item_path):
                dest_path = os.path.join(temp_backup_dir, item)
                
                if os.path.isdir(item_path):
                    # Klasörü kopyala (.git, __pycache__, .venv gibi dizinleri atla)
                    shutil.copytree(
                        item_path, 
                        dest_path, 
                        ignore=shutil.ignore_patterns(
                            '*.pyc', '__pycache__', '.git', '.venv', 'venv', 
                            'node_modules', '.DS_Store', '*.log', 'backups/', 
                            'temp_backup/', 'instance/'
                        )
                    )
                else:
                    # Dosyayı kopyala
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(item_path, dest_path)
                print(f"  ✓ Kopyalandı: {item}")
            else:
                print(f"  ✗ Atlandı (bulunamadı): {item}")
        
        # Yedek dosyasını sıkıştır (tar.gz formatında)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'cagrivakti_project_backup_{timestamp}.tar.gz'
        backup_path = os.path.join(project_root, backup_filename)
        
        print(f"\nYedek sıkıştırılıyor: {backup_filename}")
        
        # Tar.gz oluştur
        import tarfile
        with tarfile.open(backup_path, 'w:gz') as tar:
            tar.add(temp_backup_dir, arcname='cagrivakti')
        
        print(f"✓ Yedek oluşturuldu: {backup_path}")
        
        # Google Drive'a yükle
        upload_to_google_drive(backup_path)
        
        return True
        
    except Exception as e:
        print(f"Hata: Proje yedekleme başarısız: {e}")
        return False
    finally:
        # Geçici dizini temizle
        try:
            shutil.rmtree(temp_backup_dir)
        except Exception:
            pass
        # Yerel yedek dosyasını sil (sadece Drive'da kalsın)
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
                print(f"✓ Yerel yedek dosyası silindi: {backup_path}")
        except Exception as e:
            print(f"Uyarı: Yerel yedek silinemedi: {e}")

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
        
        # Proje yedekleri için klasör
        remote_folder = f'{remote_name}cagrivakti/project-backups'
        
        print(f"\nYedek Google Drive'a yükleniyor: {os.path.basename(backup_path)}")
        
        subprocess.run(
            ['rclone', 'copy', backup_path, remote_folder],
            check=True,
            timeout=600  # Büyük dosyalar için 10 dakika zaman aşımı
        )
        
        print(f"✓ Başarılı! Yedek Google Drive'a yüklendi: {remote_folder}")
        
        # Google Drive'daki eski yedekleri temizle (son 15 günü tut)
        clean_remote_backups(remote_folder, days=15)
        
    except Exception as e:
        print(f"Hata: Google Drive'a yükleme başarısız: {e}")

def clean_remote_backups(remote_folder, days=15):
    """Google Drive'daki eski yedekleri temizler"""
    try:
        print(f"\nGoogle Drive'daki eski proje yedekleri kontrol ediliyor (son {days} gün saklanacak)...")
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
        
        deleted_count = 0
        for file_info in files:
            if 'ModTime' in file_info and 'Name' in file_info:
                file_name = file_info['Name']
                if file_name.startswith('cagrivakti_project_backup_') and file_name.endswith('.tar.gz'):
                    # ModTime'ı parse et (RFC3339 formatı)
                    try:
                        mod_time = datetime.fromisoformat(file_info['ModTime'].replace('Z', '+00:00'))
                        mod_timestamp = mod_time.timestamp()
                        
                        if mod_timestamp < cutoff:
                            # Dosyayı sil
                            remote_path = f'{remote_folder}/{file_name}'
                            print(f"  ✓ Eski yedek siliniyor: {file_name}")
                            subprocess.run(
                                ['rclone', 'deletefile', remote_path],
                                timeout=30
                            )
                            deleted_count += 1
                    except Exception as e:
                        print(f"  Uyarı: Dosya işlenemedi {file_name}: {e}")
        
        if deleted_count > 0:
            print(f"\n✓ Toplam {deleted_count} eski yedek silindi.")
        else:
            print("\n✓ Silinecek eski yedek bulunamadı.")
        
    except Exception as e:
        print(f"Uyarı: Remote temizleme başarısız: {e}")

if __name__ == '__main__':
    print("=" * 70)
    print("Çağrı Vakti - Proje Yedekleme")
    print("=" * 70)
    print()
    success = create_project_backup()
    print("\n" + "=" * 70)
    sys.exit(0 if success else 1)
