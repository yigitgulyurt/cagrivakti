from flask import Blueprint, render_template, request, redirect, url_for, session, make_response, send_from_directory, current_app, abort, flash, jsonify
from functools import wraps
from app.services import UserService, PrayerService, RamadanService, get_timezone_for_city, get_daily_content, get_guides, get_guide_by_slug, get_country_for_city, CITY_DISPLAY_NAME_MAPPING
from app.models import NamazVakti, ContactMessage, DailyContent, Guide
from app.extensions import cache, db, limiter
from datetime import datetime, timedelta
import os
import json
import bleach
import requests
from threading import Thread

import re
import hashlib

views_bp = Blueprint('views', __name__)

def is_latin_only(text):
    """Metnin yalnızca Latin karakterler, sayılar ve izin verilen sembollerden oluştuğunu kontrol eder."""
    if not text:
        return True
    # İngilizce Latin harfleri (A-Z, a-z), Sayılar (0-9), URL standardına uygun karakterler (-, _, space)
    # Not: Space karakteri URL'de %20'ye dönüşür ama path parametresi olarak geldiğinde decoded halini kontrol ediyoruz.
    return bool(re.match(r'^[A-Za-z0-9\-\_\s\.]+$', text))

@views_bp.route('/')
def index():
    # Kullanıcı tercihlerini al
    prefs = UserService.get_current_user_preferences()
    sehir = prefs['sehir']
    country_code = prefs['country_code']
    
    # Bugünün vakitlerini getir
    vakitler = PrayerService.get_vakitler(sehir, country_code)
    
    # Dinamik SEO
    current_year = datetime.now().year
    title = f"Namaz Vakitleri {current_year} - Ezan Saatleri, İftar ve Sahur Vakitleri"
    description = f"{sehir} için bugün imsak: {vakitler['imsak']}, akşam: {vakitler['aksam']}. En doğru ve güncel {sehir} namaz vakitleri, ezan saatleri ve imsakiye."
    
    return render_template('main/index.html', 
                         sehir=sehir, 
                         country_code=country_code,
                         vakitler=vakitler,
                         daily_content=get_daily_content(),
                         ramadan_info=RamadanService.get_ramadan_info(),
                         guides=get_guides()[:3], # İlk 3 rehberi göster
                         seo_title=title,
                         seo_description=description)

@views_bp.route('/sehir/<sehir>')
def sehir_sayfasi(sehir):
    # Latin karakter kontrolü
    if not is_latin_only(sehir):
        abort(400, description="Gecersiz karakter iceren sehir ismi.")
        
    country_code = request.args.get('country')
    if not country_code:
        country_code = get_country_for_city(sehir) or 'TR'

    if not is_latin_only(country_code):
        abort(400, description="Gecersiz karakter iceren ulke kodu.")
    
    # Tercihleri güncelle (Session)
    UserService.save_user_preferences(sehir, country_code)
    
    # Bugünün vakitlerini getir
    vakitler = PrayerService.get_vakitler(sehir, country_code)
    
    # Dinamik SEO
    title = f"{sehir} Namaz Vakitleri - Ezan Saatleri"
    description = f"{sehir} ezan vakitleri: İmsak {vakitler['imsak']}, Öğle {vakitler['ogle']}, Akşam {vakitler['aksam']}. {sehir} günlük namaz vakitleri ve aylık imsakiye."
    
    response = make_response(render_template('city/city_page.html', 
                         sehir=sehir, 
                         country_code=country_code,
                         vakitler=vakitler,
                         daily_content=get_daily_content(),
                         ramadan_info=RamadanService.get_ramadan_info(),
                         seo_title=title,
                         seo_description=description))
    
    # PWA shortcut ismi için cookie set et (1 yıl geçerli)
    response.set_cookie('user_city', sehir, max_age=31536000, path='/')
    return response

@views_bp.route('/sehir')
@cache.cached(timeout=3600)
def sehir_secimi():
    # SEO İçin Server-Side Rendering: Tüm şehirleri backend'den çekip gönderiyoruz
    # Türkiye Şehirleri (Bölgelere göre gruplu değil düz liste olarak alıp template'de işleyebiliriz veya burada gruplayabiliriz)
    # Performans için sadece isim ve ülke kodu listesi gönderelim.
    
    # Not: UserService.get_sehirler('ALL') tüm şehirleri döndürüyor olabilir ama yapıya bakmamız lazım.
    # Sitemap fonksiyonunda kullanıldığı gibi:
    all_cities = UserService.get_sehirler('ALL')
    
    # Şehir verilerini (isim, ülke) listesi haline getirelim
    city_data = []
    for city in all_cities:
        country = get_country_for_city(city)
        # Sadece Türkiye şehirlerini öne çıkarmak veya hepsini göndermek isteyebiliriz.
        # Sayfa yapısına uygun olarak hepsini gönderelim, template'de JS ile filtreleme zaten var ama
        # SEO için HTML içinde olması önemli.
        city_data.append({'name': city, 'country': country})
        
    # Şehirleri alfabetik sırala
    city_data.sort(key=lambda x: x['name'])

    return render_template('city/city_selection.html', cities=city_data)

@views_bp.route('/kible-pusulasi')
@cache.cached(timeout=86400)
def kible_pusulasi():
    """Kıble pusulası sayfasını gösterir."""
    title = "Kıble Pusulası - Online Kıble Yönü Bulma"
    description = "Pusula ve harita yardımıyla online kıble yönünü bulun. Telefonunuzun sensörlerini kullanarak en doğru kıble açısını hesaplayın."
    return render_template('utils/qibla_compass.html',
                         seo_title=title,
                         seo_description=description)

@views_bp.route('/offline')
@cache.cached(timeout=86400)
def offline():
    return render_template('utils/offline.html')

@views_bp.route('/sitemap.xml')
@cache.cached(timeout=86400)
def serve_sitemap():
    """Dinamik Sitemap oluşturur."""
    from flask import make_response
    
    pages = []
    
    # Statik ana sayfalar
    static_urls = [
        'views.index', 'views.sehir_secimi', 'views.imsakiye_secimi', 
        'views.ramazan_nedir', 'views.orucu_bozan_durumlar', 
        'views.neden_biz', 'views.indir', 'views.konum_bul', 
        'views.iletisim', 'views.ilkelerimiz',
        'views.bilgi_kosesi_liste','views.prime_number'
    ]
    
    for rule in static_urls:
        pages.append({
            "loc": url_for(rule, _external=True),
            "lastmod": datetime.now().strftime("%Y-%m-%d"),
            "priority": "1.0" if rule == 'views.index' else "0.8"
        })
    
    # Şehir sayfaları (TR + INT)
    sehirler = UserService.get_sehirler('ALL')
    for sehir in sehirler:
        # get_country_for_city yardımıyla doğru ülke kodu alınır
        country = get_country_for_city(sehir)
        
        pages.append({
            "loc": url_for('views.sehir_sayfasi', sehir=sehir, _external=True),
            "lastmod": datetime.now().strftime("%Y-%m-%d"),
            "priority": "0.9"
        })
        # İmsakiye sayfaları (Sadece Türkiye şehirleri için)
        if country == 'TR':
            pages.append({
                "loc": url_for('views.imsakiye_detay', sehir=sehir, _external=True),
                "lastmod": datetime.now().strftime("%Y-%m-%d"),
                "priority": "0.7"
            })
        
    # Bilgi Köşesi sayfaları
    guides = get_guides()
    for guide in guides:
        pages.append({
            "loc": url_for('views.bilgi_kosesi_detay', slug=guide['slug'], _external=True),
            "lastmod": datetime.now().strftime("%Y-%m-%d"),
            "priority": "0.6"
        })

    sitemap_xml = render_template('utils/sitemap_template.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response

@views_bp.route('/robots.txt')
@cache.cached(timeout=86400)
def serve_robots():
    """robots.txt dosyasını sunar."""
    content = "User-agent: *\n"
    content += "Allow: /\n"
    content += "Disallow: /admin/\n"
    content += "Disallow: /offline\n"
    content += "Disallow: /static/data/\n"
    content += f"Sitemap: {url_for('views.serve_sitemap', _external=True)}\n"
    
    response = make_response(content)
    response.headers["Content-Type"] = "text/plain"
    return response

@views_bp.route('/sw.js')
def serve_sw():
    response = make_response(send_from_directory(os.path.join(current_app.root_path, 'static', 'js'), 'sw.js'))
    response.headers['Cache-Control'] = 'no-cache' # Service Worker her zaman güncel kontrol edilmeli
    return response

@views_bp.route('/manifest.json')
def serve_manifest():
    # manifest_base.json dosyasını kullan (önceden manifest.json idi, isim değişikliği yapıldı)
    manifest_path = os.path.join(current_app.root_path, 'static', 'manifest_base.json')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        
        # Kullanıcının şehrini cookie'den veya query parametresinden al
        user_city = request.cookies.get('user_city') or request.args.get('city')
        
        if "shortcuts" in manifest_data:
            found = False
            for shortcut in manifest_data["shortcuts"]:
                # Mevcut konum-bul shortcut'ını güncelle
                if shortcut.get("url") == "/konum-bul":
                    found = True
                    if user_city:
                        display_name = CITY_DISPLAY_NAME_MAPPING.get(user_city, user_city)
                        shortcut["name"] = f"{display_name} Vakitleri"
                        shortcut["short_name"] = display_name
                        shortcut["url"] = f"/sehir/{user_city}"
                        # İkonu güncelle
                        shortcut["icons"] = [{
                            "src": "/static/icons/android/android-launchericon-96-96.png",
                            "sizes": "96x96",
                            "type": "image/png"
                        }]
                    break
            
            # Eğer listede yoksa ve şehir varsa yeni ekle
            if not found and user_city:
                display_name = CITY_DISPLAY_NAME_MAPPING.get(user_city, user_city)
                new_shortcut = {
                    "name": f"{display_name} Vakitleri",
                    "short_name": display_name,
                    "url": f"/sehir/{user_city}",
                    "icons": [{
                        "src": "/static/icons/android/android-launchericon-96-96.png",
                        "sizes": "96x96",
                        "type": "image/png"
                    }]
                }
                manifest_data["shortcuts"].insert(0, new_shortcut)
        
        response = jsonify(manifest_data)
        # Önbelleği agresif bir şekilde devre dışı bırak
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['Surrogate-Control'] = 'no-store'
        return response
    except Exception as e:
        current_app.logger.error(f"Manifest generation error: {e}")
        return send_from_directory(os.path.join(current_app.root_path, 'static'), 'manifest_base.json')

@views_bp.route('/ilkelerimiz')
@cache.cached(timeout=86400)
def ilkelerimiz():
    return render_template('info/policies.html')

@views_bp.route('/MUSTAFA-KEMAL-ATATÜRK')
@cache.cached(timeout=86400)
def ataturk():
    return render_template('main/ataturk.html')

# @views_bp.route('/api-dokuman')
# @cache.cached(timeout=86400)
# def api_dokuman():
#     return render_template('info/api_docs.html')

@views_bp.route('/ramazan')
@cache.cached(timeout=3600)
def ramazan_nedir():
    return render_template('ramadan/what_is_ramadan.html')

@views_bp.route('/orucu-bozan-durumlar')
@cache.cached(timeout=3600)
def orucu_bozan_durumlar():
    return render_template('ramadan/things_that_break_fast.html')

@views_bp.route('/neden-biz')
@cache.cached(timeout=86400)
def neden_biz():
    return render_template('info/why_us.html')

@views_bp.route('/indir')
@cache.cached(timeout=86400)
def indir():
    return render_template('utils/download.html')

@views_bp.route('/imsakiye')
@cache.cached(timeout=3600)
def imsakiye_secimi():
    return render_template('ramadan/ramadan_schedule_selection.html')

@views_bp.route('/imsakiye/<sehir>')
def imsakiye_detay(sehir):
    if not is_latin_only(sehir):
        abort(400, description="Gecersiz karakter iceren sehir ismi.")
        
    country_code = request.args.get('country')
    if not country_code:
        country_code = get_country_for_city(sehir) or 'TR'

    if not is_latin_only(country_code):
        abort(400, description="Gecersiz karakter iceren ulke kodu.")
        
    return render_template('ramadan/ramadan_schedule_detail.html', 
                         sehir=sehir, 
                         country_code=country_code,
                         ramadan_info=RamadanService.get_ramadan_info())

@views_bp.route('/bilgi-kosesi')
@cache.cached(timeout=3600)
def bilgi_kosesi_liste():
    guides = get_guides()
    return render_template('guide/guide_list.html', guides=guides)

@views_bp.route('/bilgi-kosesi/<slug>')
@cache.cached(timeout=3600)
def bilgi_kosesi_detay(slug):
    if not is_latin_only(slug):
        abort(400, description="Gecersiz karakter iceren slug.")
        
    guide = get_guide_by_slug(slug)
    if not guide:
        abort(404)
    guides = get_guides()
    return render_template('guide/guide_detail.html', guide=guide, guides=guides)

@views_bp.route('/sitene-ekle')
@cache.cached(timeout=86400)
def sitene_ekle():
    """Kullanıcıların sitelerine ekleyebileceği embed kodunu oluşturma sayfası."""
    # Tüm şehirleri gönder (Dropdown için)
    all_cities = UserService.get_sehirler('ALL')
    all_cities.sort()
    
    title = "Namaz Vakitleri Widget - Sitenize Ekleyin"
    description = "Web siteniz için ücretsiz namaz vakitleri widget'ı. Renkleri özelleştirin, şehrinizi seçin ve kodu sitenize ekleyin."
    
    return render_template('embed/builder.html', 
                         cities=all_cities,
                         seo_title=title,
                         seo_description=description)

@views_bp.route('/embed/<sehir>')
def embed_widget(sehir):
    """İframe içinde gösterilecek widget sayfası."""
    if not is_latin_only(sehir):
        abort(400)
        
    country_code = request.args.get('country', 'TR')
    
    # Bugünün vakitlerini getir
    try:
        vakitler = PrayerService.get_vakitler(sehir, country_code)
        
        # Yarının imsak vaktini ekle (Gece yarısı geçişi için)
        try:
            yarin = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            yarin_vakitler = PrayerService.get_vakitler(sehir, country_code, yarin)
            if yarin_vakitler:
                vakitler['yarin'] = {'imsak': yarin_vakitler.get('imsak')}
        except:
            pass # Yarın verisi alınamazsa sorun değil, sadece countdown çalışmaz
            
    except:
        return "Şehir bulunamadı", 404

    # Tema parametreleri
    theme = request.args.get('theme', 'dark')
    bg_color = request.args.get('bg', '')
    text_color = request.args.get('text', '')
    
    display_name = CITY_DISPLAY_NAME_MAPPING.get(sehir, sehir.replace("-", " ").title())

    # ETag Generation (Smart Caching)
    # ETag = Hash(Version + City + Date + Theme + Params)
    widget_version = current_app.config.get('WIDGET_VERSION', '1.0')
    current_date = datetime.now().strftime('%Y-%m-%d')
    version_string = f"{widget_version}-{sehir}-{current_date}-{theme}-{bg_color}-{text_color}"
    etag = hashlib.md5(version_string.encode('utf-8')).hexdigest()

    # Check if client has matching ETag (If-None-Match)
    if request.if_none_match and request.if_none_match.contains(etag):
        return "", 304

    response = make_response(render_template('embed/widget.html', 
                         sehir=sehir,
                         display_name=display_name,
                         vakitler=vakitler,
                         theme=theme,
                         bg_color=bg_color,
                         text_color=text_color))
    
    # Cache Control: Public, but MUST revalidate with server (no-cache)
    # Browser will cache, but ask server "Is this ETag still valid?" every time.
    # If valid -> 304 (Not Modified) -> Instant load, no data transfer
    # If invalid -> 200 (OK) -> New content
    response.headers['Cache-Control'] = 'public, no-cache'
    response.set_etag(etag)
            
    return response

@views_bp.route('/konum-bul')
def konum_bul():
    return render_template('city/detect_location.html')

def send_async_notification(app, name, email, subject, message):
    with app.app_context():
        send_admin_notification(name, email, subject, message)

def send_admin_notification(name, email, subject, message):
    # Telegram Notification
    telegram_token = current_app.config.get('TELEGRAM_TOKEN')
    admin_id = current_app.config.get('ADMIN_TELEGRAM_ID')
    if telegram_token and admin_id:
        try:
            text = f"📩 *Yeni Geri Bildirim*\n\n" \
                   f"👤 *Gönderen:* {name}\n" \
                   f"📧 *E-posta:* {email}\n" \
                   f"📌 *Konu:* {subject.capitalize()}\n\n" \
                   f"📝 *Mesaj:*\n{message}"
            requests.post(f"https://api.telegram.org/bot{telegram_token}/sendMessage", 
                         json={"chat_id": admin_id, "text": text, "parse_mode": "Markdown"},
                         timeout=10)
        except Exception as e:
            current_app.logger.error(f"Telegram notification error: {e}")

@views_bp.route('/iletisim', methods=['GET', 'POST'])
@limiter.limit("10 per hour", methods=['POST'])
def iletisim():
    if request.method == 'POST':
        # Honeypot kontrolü
        if request.form.get('website'):
            # Bot tespit edildi, sessizce ana sayfaya yönlendir
            return redirect(url_for('views.index'))

        # Inputları temizle (XSS koruması)
        name = bleach.clean(request.form.get('name', ''))
        email = bleach.clean(request.form.get('email', ''))
        subject = bleach.clean(request.form.get('subject', ''))
        message = bleach.clean(request.form.get('message', ''))

        if not all([name, email, subject, message]):
            flash('Lütfen tüm alanları doldurun.', 'error')
            return redirect(url_for('views.iletisim'))

        # Basit e-posta doğrulama ve uzunluk kontrolü
        if len(message) < 10:
            flash('Mesajınız çok kısa, lütfen biraz daha detay verin.', 'error')
            return redirect(url_for('views.iletisim'))
        
        if len(message) > 2000:
            flash('Mesajınız çok uzun, lütfen daha kısa bir mesaj gönderin.', 'error')
            return redirect(url_for('views.iletisim'))

        try:
            new_message = ContactMessage(
                name=name,
                email=email,
                subject=subject,
                message=message
            )
            db.session.add(new_message)
            db.session.commit()
            
            # Botlara asenkron bildirim gönder
            app = current_app._get_current_object()
            Thread(target=send_async_notification, args=(app, name, email, subject, message)).start()
            
            flash('Mesajınız başarıyla iletildi. Teşekkür ederiz!', 'success')
            return redirect(url_for('views.iletisim'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"İletişim formu hatası: {str(e)}")
            flash('Bir hata oluştu, lütfen daha sonra tekrar deneyin.', 'error')
            return redirect(url_for('views.iletisim'))

    return render_template('main/contact.html')

def admin_required(f):
    """Admin yetkisi kontrolü için decorator."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        admin_user = current_app.config.get('ADMIN_USER')
        admin_pass = current_app.config.get('ADMIN_PASS')
        
        if not auth or not (auth.username == admin_user and auth.password == admin_pass):
            return make_response('Yetkisiz Erişim', 401, {'WWW-Authenticate': 'Basic realm="Admin Panel"'})
        return f(*args, **kwargs)
    return decorated_function

@views_bp.route('/admin')
@admin_required
def admin_dashboard():
    """Admin paneli ana sayfası."""
    stats = {
        'guides_count': Guide.query.count(),
        'messages_count': ContactMessage.query.filter_by(is_read=False).count(),
        'daily_content_count': DailyContent.query.count()
    }
    return render_template('admin/dashboard.html', stats=stats)

@views_bp.route('/admin/rehberler')
@admin_required
def admin_guides():
    """Rehber yazıları yönetimi."""
    guides = Guide.query.order_by(Guide.updated_at.desc()).all()
    return render_template('admin/guides.html', guides=guides)

@views_bp.route('/admin/rehber/ekle', methods=['GET', 'POST'])
@views_bp.route('/admin/rehber/duzenle/<int:guide_id>', methods=['GET', 'POST'])
@admin_required
def admin_guide_edit(guide_id=None):
    """Rehber ekleme veya düzenleme."""
    guide = Guide.query.get_or_404(guide_id) if guide_id else None
    
    if request.method == 'POST':
        title = request.form.get('title')
        slug = request.form.get('slug')
        category = request.form.get('category')
        description = request.form.get('description')
        content = request.form.get('content')
        image_url = request.form.get('image_url')
        is_active = 'is_active' in request.form
        
        # Sadece slug için Latin karakter kontrolü (URL uyumluluğu için kritik)
        if not is_latin_only(slug):
            flash('Slug yalnızca Latin karakterler içerebilir (URL uyumu için).', 'danger')
            return render_template('admin/guide_form.html', guide=guide)
            
        if not guide:
            guide = Guide(slug=slug)
            db.session.add(guide)
            
        guide.title = title
        guide.slug = slug
        guide.category = category
        guide.description = description
        guide.content = content
        guide.image_url = image_url
        guide.is_active = is_active
        
        try:
            db.session.commit()
            flash('Rehber başarıyla kaydedildi.', 'success')
            return redirect(url_for('views.admin_guides'))
        except Exception as e:
            db.session.rollback()
            flash(f'Hata oluştu: {str(e)}', 'danger')
            
    return render_template('admin/guide_form.html', guide=guide)

@views_bp.route('/admin/icerikler')
@admin_required
def admin_contents():
    """Günlük ayet, hadis ve söz yönetimi."""
    contents = DailyContent.query.order_by(DailyContent.id.desc()).all()
    return render_template('admin/contents.html', contents=contents)

@views_bp.route('/admin/icerik/ekle', methods=['GET', 'POST'])
@views_bp.route('/admin/icerik/duzenle/<int:content_id>', methods=['GET', 'POST'])
@admin_required
def admin_content_edit(content_id=None):
    """Günlük içerik ekleme veya düzenleme."""
    content = DailyContent.query.get_or_404(content_id) if content_id else None
    
    if request.method == 'POST':
        content_type = request.form.get('content_type')
        category = request.form.get('category')
        text = request.form.get('text')
        source = request.form.get('source')
        day_index = request.form.get('day_index')
        is_active = 'is_active' in request.form
        
        if not content:
            content = DailyContent()
            db.session.add(content)
            
        content.content_type = content_type
        content.category = category
        content.text = text
        content.source = source
        content.day_index = int(day_index) if day_index else None
        content.is_active = is_active
        
        try:
            db.session.commit()
            flash('İçerik başarıyla kaydedildi.', 'success')
            return redirect(url_for('views.admin_contents'))
        except Exception as e:
            db.session.rollback()
            flash(f'Hata oluştu: {str(e)}', 'danger')
            
    return render_template('admin/content_form.html', content=content)

@views_bp.route('/admin/mesajlar')
@admin_required
def admin_messages():
    """İletişim mesajları yönetimi."""
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages)

@views_bp.route('/admin/mesaj/oku/<int:message_id>')
@admin_required
def admin_message_read(message_id):
    """Mesajı okundu olarak işaretle ve detayları gör."""
    message = ContactMessage.query.get_or_404(message_id)
    message.is_read = True
    db.session.commit()
    return render_template('admin/message_detail.html', message=message)

@views_bp.route('/admin/rehber/sil/<int:guide_id>', methods=['POST'])
@admin_required
def admin_guide_delete(guide_id):
    """Rehber yazısını sil."""
    guide = Guide.query.get_or_404(guide_id)
    try:
        db.session.delete(guide)
        db.session.commit()
        flash('Rehber başarıyla silindi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {str(e)}', 'danger')
    return redirect(url_for('views.admin_guides'))

@views_bp.route('/admin/icerik/sil/<int:content_id>', methods=['POST'])
@admin_required
def admin_content_delete(content_id):
    """İçeriği sil."""
    content = DailyContent.query.get_or_404(content_id)
    try:
        db.session.delete(content)
        db.session.commit()
        flash('İçerik başarıyla silindi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {str(e)}', 'danger')
    return redirect(url_for('views.admin_contents'))

@views_bp.route('/admin/mesaj/sil/<int:message_id>', methods=['POST'])
@admin_required
def admin_message_delete(message_id):
    """Mesajı sil."""
    message = ContactMessage.query.get_or_404(message_id)
    try:
        db.session.delete(message)
        db.session.commit()
        flash('Mesaj başarıyla silindi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {str(e)}', 'danger')
    return redirect(url_for('views.admin_messages'))

@views_bp.route('/admin/logs')
@admin_required
def admin_logs():
    """Uygulama loglarını görselleştiren admin paneli."""
    log_file = current_app.config.get('LOG_FILE')
    api_log_file = current_app.config.get('API_LOG_FILE')
    bot_log_file = current_app.config.get('TELEGRAM_LOG_FILE')
    
    web_logs = ""
    api_logs = ""
    bot_logs = ""
    
    # Log Analizi (Görselleştirme için)
    import re
    from collections import Counter
    
    stats = {'hourly': {}, 'pages': {}}
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Son 200 satırı gösterim için al
                web_logs = "".join(lines[-200:])
                
                # Analiz için TÜM satırları kullan (Limit kaldırıldı)
                analyze_lines = lines
                
            # Hem eski (INFO in ...) hem yeni formatı destekleyen regex
            log_pattern = re.compile(r'\[(.*?)\] (?:INFO in .*: )?.*? ziyaret: (.*)')
            hourly_counts = Counter()
            page_counts = Counter()
            
            for line in analyze_lines:
                match = log_pattern.search(line)
                if match:
                    timestamp_str, path = match.groups()
                    try:
                        # Sadece saati al (Örn: 14:00)
                        if ' ' in timestamp_str:
                            hour = timestamp_str.split(' ')[1][:2] + ":00"
                        else:
                            # T ile ayrılmış olabilir veya sadece saat olabilir
                            hour = timestamp_str[11:13] + ":00" if len(timestamp_str) > 13 else "00:00"
                            
                        hourly_counts[hour] += 1
                        page_counts[path.strip()] += 1
                    except Exception as e:
                        current_app.logger.error(f"Log satır hatası: {e} - Satır: {line}")
                        continue
            
            stats['hourly'] = dict(sorted(hourly_counts.items()))
            stats['pages'] = dict(page_counts.most_common())
            
            # Debug log
            # current_app.logger.info(f"Log analizi tamamlandı: {len(hourly_counts)} saat dilimi, {len(page_counts)} sayfa.")
            
        except Exception as e:
            current_app.logger.error(f"Log analiz hatası: {e}")
            
    if os.path.exists(api_log_file):
        with open(api_log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            api_logs = "".join(lines[-200:])

    if bot_log_file and os.path.exists(bot_log_file):
        with open(bot_log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            bot_logs = "".join(lines[-200:])
            
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'web_logs': web_logs if web_logs else 'Log verisi bulunamadı.',
            'api_logs': api_logs if api_logs else 'API log verisi bulunamadı.',
            'bot_logs': bot_logs if bot_logs else 'Bot log verisi bulunamadı.',
            'stats': stats
        })

    return render_template('admin/logs.html', 
                         web_logs=web_logs, 
                         api_logs=api_logs,
                         bot_logs=bot_logs,
                         stats=stats)
                         
@views_bp.route('/asal-sayi')
def prime_number():
    return render_template('prime-number.html')