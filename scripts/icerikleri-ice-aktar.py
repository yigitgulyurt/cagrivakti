import os
import sys
import argparse
import json

# Proje kök dizinini Python yoluna ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.factory import create_app
from app.extensions import db
from app.models import DailyContent

def add_content(category, content_type, text, source=None, day_index=None):
    app = create_app()
    with app.app_context():
        # En son day_index'i bul (eğer verilmemişse)
        if day_index is None:
            last_item = DailyContent.query.filter_by(category=category).order_by(DailyContent.day_index.desc()).first()
            day_index = (last_item.day_index + 1) if last_item else 1

        new_item = DailyContent(
            category=category,
            content_type=content_type,
            text=text,
            source=source,
            day_index=day_index
        )
        db.session.add(new_item)
        db.session.commit()
        print(f"Başarıyla eklendi: [{category}] {content_type}: {text[:50]}...")

def list_content(category=None):
    app = create_app()
    with app.app_context():
        query = DailyContent.query
        if category:
            query = query.filter_by(category=category)
        
        items = query.order_by(DailyContent.category, DailyContent.day_index).all()
        
        print(f"{'ID':<5} | {'Kategori':<10} | {'Tür':<10} | {'İndeks':<8} | {'İçerik'}")
        print("-" * 80)
        for item in items:
            text = item.text[:60] + "..." if len(item.text) > 60 else item.text
            print(f"{item.id:<5} | {item.category:<10} | {item.content_type:<10} | {item.day_index:<8} | {text}")

def delete_content(content_id):
    app = create_app()
    with app.app_context():
        item = db.session.get(DailyContent, content_id)
        if item:
            db.session.delete(item)
            db.session.commit()
            print(f"ID {content_id} başarıyla silindi.")
        else:
            print(f"ID {content_id} bulunamadı.")

def export_content(file_path, category=None):
    app = create_app()
    with app.app_context():
        query = DailyContent.query
        if category:
            query = query.filter_by(category=category)
        
        items = query.order_by(DailyContent.category, DailyContent.day_index).all()
        
        data = []
        for item in items:
            data.append({
                "id": item.id,
                "category": item.category,
                "type": item.content_type,
                "text": item.text,
                "source": item.source,
                "day_index": item.day_index
            })
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        print(f"{len(data)} adet içerik {file_path} dosyasına aktarıldı.")

def bulk_add(file_path):
    if not os.path.exists(file_path):
        print(f"Dosya bulunamadı: {file_path}")
        return

    app = create_app()
    with app.app_context():
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                items = data if isinstance(data, list) else data.get('content', [])
                
                count = 0
                for item in items:
                    category = item.get('category', 'daily')
                    c_type = item.get('type') or item.get('content_type', 'soz')
                    text = item.get('text')
                    source = item.get('source')
                    
                    if not text:
                        continue

                    # Mükerrer kontrolü
                    exists = DailyContent.query.filter_by(
                        category=category,
                        text=text
                    ).first()

                    if not exists:
                        # Otomatik day_index atama (Kategorideki en yüksek index + 1)
                        last_item = DailyContent.query.filter_by(category=category).order_by(DailyContent.day_index.desc()).first()
                        new_index = (last_item.day_index + 1) if last_item else 1
                        
                        new_item = DailyContent(
                            category=category,
                            content_type=c_type,
                            text=text,
                            source=source,
                            day_index=new_index
                        )
                        db.session.add(new_item)
                        count += 1
                
                db.session.commit()
                if count > 0:
                    print(f"{count} adet yeni içerik başarıyla eklendi.")
                else:
                    print("Eklenecek yeni içerik bulunamadı (tümü zaten mevcut).")
            except Exception as e:
                print(f"Hata oluştu: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DailyContent Veritabanı Yönetim Aracı')
    subparsers = parser.add_subparsers(dest='command', help='Komutlar')

    # Add komutu
    add_parser = subparsers.add_parser('add', help='Yeni içerik ekle')
    add_parser.add_argument('--category', choices=['daily', 'ramadan'], default='daily', help='Kategori')
    add_parser.add_argument('--type', choices=['ayet', 'hadis', 'soz'], required=True, help='İçerik türü')
    add_parser.add_argument('--text', required=True, help='İçerik metni')
    add_parser.add_argument('--source', help='Kaynak')
    add_parser.add_argument('--index', type=int, help='Gün/Sıra indeksi')

    # List komutu
    list_parser = subparsers.add_parser('list', help='İçerikleri listele')
    list_parser.add_argument('--category', choices=['daily', 'ramadan'], help='Sadece bu kategoriyi listele')

    # Delete komutu
    del_parser = subparsers.add_parser('delete', help='İçerik sil')
    del_parser.add_argument('id', type=int, help='Silinecek içeriğin ID\'si')

    # Bulk komutu
    bulk_parser = subparsers.add_parser('bulk', help='Dosyadan toplu ekle (JSON)')
    bulk_parser.add_argument('file', help='JSON dosya yolu')

    # Sync komutu
    sync_parser = subparsers.add_parser('sync', help='Varsayılan daily_content.json dosyasını veritabanına aktar')

    # Export komutu
    export_parser = subparsers.add_parser('export', help='İçerikleri dosyaya aktar (JSON)')
    export_parser.add_argument('file', help='JSON dosya yolu')
    export_parser.add_argument('--category', choices=['daily', 'ramadan'], help='Sadece bu kategoriyi aktar')

    args = parser.parse_args()

    if args.command == 'add':
        add_content(args.category, args.type, args.text, args.source, args.index)
    elif args.command == 'list':
        list_content(args.category)
    elif args.command == 'delete':
        delete_content(args.id)
    elif args.command == 'bulk':
        bulk_add(args.file)
    elif args.command == 'sync':
        default_path = os.path.join(os.path.dirname(__file__), 'daily_content.json')
        bulk_add(default_path)
    elif args.command == 'export':
        export_content(args.file, args.category)
    else:
        parser.print_help()
