from app.extensions import db
from datetime import datetime

class NamazVakti(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sehir = db.Column(db.String(50), nullable=False)
    country_code = db.Column(db.String(5), default='TR')
    timezone = db.Column(db.String(50), default='Europe/Istanbul') # Şehrin timezone'u
    tarih = db.Column(db.Date, nullable=False)
    imsak = db.Column(db.String(5))
    gunes = db.Column(db.String(5))
    ogle = db.Column(db.String(5))
    ikindi = db.Column(db.String(5))
    aksam = db.Column(db.String(5))
    yatsi = db.Column(db.String(5))
    kaynak = db.Column(db.String(20), default='diyanet')
    guncelleme_tarihi = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_vakit_sehir_ulke_tarih', 'sehir', 'country_code', 'tarih'),
    )

class DailyContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(20), nullable=False, default='daily') # 'daily' or 'ramadan'
    content_type = db.Column(db.String(20), nullable=False) # 'ayet', 'hadis', 'soz'
    text = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(100))
    day_index = db.Column(db.Integer) # Ramazan için gün numarası (1-30), Normal için sıra numarası
    is_active = db.Column(db.Boolean, default=True)
    last_shown = db.Column(db.Date) # Son gösterilme tarihi

    __table_args__ = (
        db.Index('idx_daily_content_query', 'category', 'is_active', 'last_shown'),
    )

    def to_dict(self):
        return {
            "type": self.content_type,
            "text": self.text,
            "source": self.source
        }

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(50), nullable=False) # 'tavsiye', 'sikayet', 'gorus', 'diger'
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.Index('idx_contact_msg_read_date', 'is_read', 'created_at'),
    )

    def __repr__(self):
        return f'<ContactMessage {self.email}>'

class Guide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.Index('idx_guide_slug', 'slug'),
        db.Index('idx_guide_active', 'is_active'),
    )

    def to_dict(self):
        return {
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "content": self.content,
            "image_url": self.image_url,
            "last_updated": self.updated_at.strftime("%Y-%m-%d") if self.updated_at else None
        }

class ApiUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    api_key = db.Column(db.String(255), index=True, nullable=False)
    is_vip = db.Column(db.Boolean, default=False, index=True)
    total_requests = db.Column(db.Integer, default=0)
    last_ip = db.Column(db.String(45))
    last_path = db.Column(db.String(255))
    last_status = db.Column(db.Integer)
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
