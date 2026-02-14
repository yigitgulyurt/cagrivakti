import argparse
import sys
from app.factory import create_app
from app.extensions import db
from flask_migrate import migrate as flask_migrate_command, upgrade as flask_upgrade_command, init as flask_init_command

def manage_db():
    parser = argparse.ArgumentParser(description='Namaz Vakitleri DB Kontrol Aracı')
    parser.add_argument('command', choices=['init', 'migrate', 'update', 'drop', 'reset', 'help'], 
                        help='Çalıştırılacak komut: init, migrate, update, drop, reset, help')
    parser.add_argument('-m', '--message', help='Migrate komutu için açıklama mesajı', default='Auto migration')

    args = parser.parse_args()

    if args.command == 'help':
        print("""
Namaz Vakitleri DB Kontrol Aracı - Kullanım Kılavuzu:

Komutlar:
  init     : Veritabanı tablolarını oluşturur ve migrations klasörünü hazırlar.
  migrate  : Modellerdeki değişiklikleri algılar ve yeni bir migrasyon dosyası oluşturur.
             Kullanım: python db.py migrate -m "mesaj"
  update   : Bekleyen migrasyonları veritabanına uygular (upgrade).
  drop     : Veritabanındaki TÜM tabloları siler (Onay ister).
  reset    : Tüm tabloları siler ve her şeyi yeniden oluşturur (Onay ister).
  help     : Bu yardım mesajını gösterir.

Örnekler:
  python db.py init
  python db.py migrate -m "kullanici tablosu eklendi"
  python db.py update
        """)
        return

    app = create_app()
    with app.app_context():
        if args.command == 'init':
            print("Veritabanı tabloları oluşturuluyor...")
            db.create_all()
            try:
                flask_init_command()
                print("Migrations klasörü oluşturuldu.")
            except Exception as e:
                print(f"Bilgi: Migrations klasörü zaten mevcut ya da: {e}")
            print("İşlem tamamlandı.")

        elif args.command == 'drop':
            confirm = input("TÜM tablolar silinecek. Emin misiniz? (y/n): ")
            if confirm.lower() == 'y':
                print("Tablolar siliniyor...")
                db.drop_all()
                print("Tüm tablolar silindi.")
            else:
                print("İşlem iptal edildi.")

        elif args.command == 'reset':
            confirm = input("TÜM veriler silinecek ve tablolar yeniden oluşturulacak. Emin misiniz? (y/n): ")
            if confirm.lower() == 'y':
                print("Reset işlemi başlatılıyor...")
                db.drop_all()
                db.create_all()
                print("Veritabanı başarıyla resetlendi.")
            else:
                print("İşlem iptal edildi.")

        elif args.command == 'migrate':
            print(f"Migrasyon dosyası oluşturuluyor: {args.message}")
            try:
                flask_migrate_command(message=args.message)
                print("Migrasyon dosyası hazır.")
            except Exception as e:
                print(f"Hata: {e}")

        elif args.command == 'update':
            print("Veritabanı güncelleniyor (upgrade)...")
            try:
                flask_upgrade_command()
                print("Veritabanı başarıyla güncellendi.")
            except Exception as e:
                print(f"Hata: {e}")

if __name__ == '__main__':
    manage_db()
