import os
import pandas as pd
from datetime import datetime
import sys
import os

# Proje kök dizinini Python yoluna ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.factory import create_app
from app.extensions import db
from app.models import NamazVakti

app = create_app()
import re

def parse_date(date_str):
    """
    '02 Ocak 2026 Cuma' formatındaki tarihi datetime.date objesine çevirir.
    """
    months = {
        'Ocak': 1, 'Şubat': 2, 'Mart': 3, 'Nisan': 4, 'Mayıs': 5, 'Haziran': 6,
        'Temmuz': 7, 'Ağustos': 8, 'Eylül': 9, 'Ekim': 10, 'Kasım': 11, 'Aralık': 12
    }
    try:
        parts = date_str.split()
        day = int(parts[0])
        month = months[parts[1]]
        year = int(parts[2])
        return datetime(year, month, day).date()
    except Exception as e:
        print(f"Tarih parse hatası ({date_str}): {e}")
        return None

def normalize_sehir_name(name):
    translation_table = str.maketrans({
        'Ç': 'C', 'ç': 'c',
        'Ğ': 'G', 'ğ': 'g',
        'İ': 'I', 'I': 'I', 'ı': 'i',
        'Ö': 'O', 'ö': 'o',
        'Ş': 'S', 'ş': 's',
        'Ü': 'U', 'ü': 'u',
    })
    normalized = name.translate(translation_table)
    return normalized

def import_excel_files():
    folder_path = os.path.join(os.path.dirname(__file__), '2026')
    if not os.path.exists(folder_path):
        print(f"Klasör bulunamadı: {folder_path}")
        return

    with app.app_context():
        # Veritabanı tablolarını oluştur (Yoksa)
        try:
            db.create_all()
            print("Veritabanı tabloları kontrol edildi/oluşturuldu.")
        except Exception as e:
            print(f"Tablo oluşturma hatası: {e}")

        # Veritabanı sütunlarını kontrol et ve eksikse ekle (Migration yoksa manuel çözüm)
        try:
            # Sütunların varlığını kontrol etmeden tek tek deniyoruz
            alter_commands = [
                "ALTER TABLE namaz_vakti ADD COLUMN country_code VARCHAR(5) DEFAULT 'TR'",
                "ALTER TABLE namaz_vakti ADD COLUMN timezone VARCHAR(50) DEFAULT 'Europe/Istanbul'",
                "ALTER TABLE namaz_vakti ADD COLUMN kaynak VARCHAR(20) DEFAULT 'diyanet'",
                "ALTER TABLE namaz_vakti ADD COLUMN guncelleme_tarihi DATETIME"
            ]
            for cmd in alter_commands:
                try:
                    db.session.execute(db.text(cmd))
                    db.session.commit()
                    print(f"Sütun eklendi ya da zaten var: {cmd.split('ADD COLUMN ')[1].split(' ')[0]}")
                except Exception:
                    db.session.rollback()
            print("Veritabanı şeması güncel.")
        except Exception as e:
            print(f"Şema güncelleme hatası: {e}")
            pass

        files = [f for f in os.listdir(folder_path) if f.endswith('.xlsx') and not f.startswith('.~lock')]
        print(f"Toplam {len(files)} dosya bulundu.")

        for file_name in files:
            file_path = os.path.join(folder_path, file_name)
            
            # Dosya adından şehir adını çıkar (Örn: "Adana Namaz Vakitleri...")
            raw_sehir = file_name.split(' Namaz Vakitleri')[0].strip()
            sehir = normalize_sehir_name(raw_sehir)
            print(f"İşleniyor: {raw_sehir} -> {sehir} ({file_name})")

            try:
                # Excel'i oku (Header 3. satırda olabilir, Miladi Tarih yazan satırı bulalım)
                # Diyanet Excel formatında genelde ilk birkaç satır başlık
                df = pd.read_excel(file_path)
                
                # Verinin başladığı satırı bul (Miladi Tarih hücresini içeren satır)
                start_row = None
                for i, row in df.iterrows():
                    if any("Miladi Tarih" in str(cell) for cell in row):
                        start_row = i
                        break
                
                if start_row is None:
                    print(f"HATA: {sehir} için tablo başlığı bulunamadı.")
                    continue

                # Başlıkları ayarla ve veriyi al
                df.columns = df.iloc[start_row]
                df = df.iloc[start_row + 1:].reset_index(drop=True)
                
                # Sütun isimlerini temizle
                df.columns = [str(c).strip() for c in df.columns]

                count = 0
                for _, row in df.iterrows():
                    tarih_str = str(row.get('Miladi Tarih', '')).strip()
                    if not tarih_str or tarih_str == 'nan':
                        continue
                    
                    tarih = parse_date(tarih_str)
                    if not tarih:
                        continue

                    # Mevcut kaydı kontrol et
                    existing = NamazVakti.query.filter_by(
                        sehir=sehir, 
                        tarih=tarih, 
                        country_code='TR'
                    ).first()

                    vakit_data = {
                        'imsak': str(row.get('İmsak', '')).strip(),
                        'gunes': str(row.get('Güneş', '')).strip(),
                        'ogle': str(row.get('Öğle', '')).strip(),
                        'ikindi': str(row.get('İkindi', '')).strip(),
                        'aksam': str(row.get('Akşam', '')).strip(),
                        'yatsi': str(row.get('Yatsı', '')).strip(),
                        'kaynak': 'diyanet_excel',
                        'country_code': 'TR',
                        'timezone': 'Europe/Istanbul'
                    }

                    if existing:
                        for key, value in vakit_data.items():
                            setattr(existing, key, value)
                    else:
                        new_vakit = NamazVakti(
                            sehir=sehir,
                            tarih=tarih,
                            **vakit_data
                        )
                        db.session.add(new_vakit)
                    
                    count += 1
                
                db.session.commit()
                print(f"BAŞARILI: {sehir} için {count} gün kaydedildi.")

            except Exception as e:
                db.session.rollback()
                print(f"HATA: {file_name} işlenirken hata oluştu: {e}")

if __name__ == "__main__":
    import_excel_files()
