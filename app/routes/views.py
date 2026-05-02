from flask import Blueprint, render_template, request, redirect, url_for, session, make_response, send_from_directory, current_app, abort, flash, jsonify
from functools import wraps
from app.services import UserService, PrayerService, RamadanService, get_timezone_for_city, get_daily_content, get_guides, get_guide_by_slug, get_country_for_city, CITY_DISPLAY_NAME_MAPPING
from app.models import ContactMessage, DailyContent, Guide, QrRedirect
from app.extensions import cache, db, limiter, csrf
from datetime import datetime, timedelta
import os
import json
import bleach
import requests
from threading import Thread
import re
import hashlib

views_bp = Blueprint('views', __name__)

# Mevcut yıl bilgisini global olarak tanımlayalım
suanki_yil = datetime.now().year

def is_latin_only(text):
    """Metnin yalnızca Latin karakterler, sayılar ve izin verilen sembollerden oluştuğunu kontrol eder."""
    if not text:
        return True
    return bool(re.match(r'^[A-Za-z0-9\-\_\s\.]+$', text))

# ======================================================
# ==== MAIN ====
# ======================================================

@views_bp.route('/')
def index():
    prefs        = UserService.get_current_user_preferences()
    sehir        = prefs['sehir']
    country_code = prefs['country_code']
    vakitler     = PrayerService.get_vakitler(sehir, country_code)

    og_image_url = url_for(
        'og.og_image',
        title     = 'Çağrı Vakti',
        subtitle  = 'Türkiye ve Dünya ülkeleri namaz vakitleri anında ve güncel elinde.',
        theme     = 'home',
        # prompt    = 'prompt',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    title        = f"Ezan Vakitleri {suanki_yil} - Çağrı Vakti"
    description  = f"En doğru ve güncel ezan vakitleri ve imsakiye."

    return render_template('main/index.html',
                           sehir=sehir,
                           country_code=country_code,
                           vakitler=vakitler,
                           daily_content=get_daily_content(),
                           ramadan_info=RamadanService.get_ramadan_info(),
                           guides=get_guides()[:3],
                           seo_title=title,
                           seo_description=description,
                           SHOW_LIVE_SECTION=current_app.config.get('SHOW_LIVE_SECTION', False),
                           STREAM_KEY=current_app.config.get('STREAM_KEY', ''),
                           og_image_url=og_image_url)

# ======================================================
# ==== CITY ====
# ======================================================

@views_bp.route('/sehir/<sehir>')
def sehir_sayfasi(sehir):
    if not is_latin_only(sehir):
        abort(400, description="Gecersiz karakter iceren sehir ismi.")

    country_code = request.args.get('country')
    if not country_code:
        country_code = get_country_for_city(sehir) or 'TR'

    if not is_latin_only(country_code):
        abort(400, description="Gecersiz karakter iceren ulke kodu.")

    UserService.save_user_preferences(sehir, country_code)
    vakitler = PrayerService.get_vakitler(sehir, country_code)

    # Gösterim adı (örn. "istanbul" → "İstanbul")
    sehir_adi = CITY_DISPLAY_NAME_MAPPING.get(sehir, sehir.replace('-', ' ').title())
    # Subtitle: ilk satır İmsak·Güneş·Öğle, ikinci satır İkindi·Akşam·Yatsı
    og_subtitle  = (
        f"İmsak {vakitler['imsak']} · Güneş {vakitler['gunes']} · Öğle {vakitler['ogle']}|"
        f"İkindi {vakitler['ikindi']} · Akşam {vakitler['aksam']} · Yatsı {vakitler['yatsi']}"
    )
    og_image_url = url_for(
        'og.og_image',
        title     = f"{sehir_adi} {suanki_yil} Namaz Vakitleri",
        subtitle  = og_subtitle,
        theme     = 'city',
        prompt    = f"\udb80\udd46 {sehir}",
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    title       = f"{sehir_adi} Ezan Vakitleri - Çağrı Vakti"
    description = f"{sehir_adi} ezan vakitleri. {sehir_adi} günlük ezan vakitleri ve aylık imsakiye."

    response = make_response(render_template('city/city_page.html',
                                             sehir=sehir,
                                             country_code=country_code,
                                             vakitler=vakitler,
                                             daily_content=get_daily_content(),
                                             ramadan_info=RamadanService.get_ramadan_info(),
                                             seo_title=title,
                                             seo_description=description,
                                             og_image_url=og_image_url))
    response.set_cookie('user_city', sehir, max_age=31536000, path='/')
    return response


@views_bp.route('/sehir')
@cache.cached(timeout=3600)
def sehir_secimi():
    all_cities = UserService.get_sehirler('ALL')

    og_image_url = url_for(
        'og.og_image',
        title     = 'Çağrı Vakti — Şehir Seçimi',
        subtitle  = 'Hangi şehrin namaz vakitlerini görmek istiyorsunuz?',
        theme     = 'city',
        prompt    = '\udb80\udd46 Şehrini seç',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    title       = f"Çağrı Vakti — Şehir Seçimi"
    description = f"Hangi şehrin namaz vakitlerini görmek istiyorsunuz?"

    city_data = sorted(
        [{'name': c, 'country': get_country_for_city(c)} for c in all_cities],
        key=lambda x: x['name'],
    )
    return render_template('city/city_selection.html', cities=city_data, og_image_url=og_image_url, seo_title=title, seo_description=description)

# ======================================================
# ==== RAMADAN ====
# ======================================================

@views_bp.route('/ramazan')
@cache.cached(timeout=3600)
def ramazan_nedir():
    og_image_url = url_for(
        'og.og_image',
        title     = 'Ramazan Nedir?',
        subtitle  = 'Ramazan ayının önemi, ibadetleri ve fazileti hakkında bilgi edinin.',
        theme     = 'ramadan',
        prompt    = '\udb82\udd79 Ramazan Ayı Mübarek Olsun',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    title       = f"Ramazan Nedir?"
    description = f"Ramazan ayının önemi, ibadetleri ve fazileti hakkında bilgi edinin."
    return render_template('ramadan/what_is_ramadan.html', og_image_url=og_image_url, seo_title=title, seo_description=description)


@views_bp.route('/orucu-bozan-durumlar')
@cache.cached(timeout=3600)
def orucu_bozan_durumlar():
    og_image_url = url_for(
        'og.og_image',
        title     = 'Orucu Bozan Durumlar',
        subtitle  = 'Hangi durumlar orucu bozar? Detaylı İslami bilgi.',
        theme     = 'ramadan',
        prompt    = '\udb82\udd79 Ramazan Ayı Mübarek Olsun',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    title       = f"Orucu Bozan Durumlar"
    description = f"Hangi durumlar orucu bozar? Varışca Slami bilgi."
    return render_template('ramadan/things_that_break_fast.html', og_image_url=og_image_url, seo_title=title, seo_description=description)


@views_bp.route('/imsakiye')
@cache.cached(timeout=3600)
def imsakiye_secimi():
    og_image_url = url_for(
        'og.og_image',
        title     = f"{suanki_yil} İmsakiyesi",
        subtitle  = 'Şehrinizi seçin, sahur ve iftar vakitlerini görün.',
        theme     = 'ramadan',
        prompt    = '\udb82\udd79 İmsakiye',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    title       = f"{suanki_yil} İmsakiyesi"
    description = f"Şehrinizi seçin, sahur ve iftar vakitlerini görün."
    return render_template('ramadan/ramadan_schedule_selection.html', og_image_url=og_image_url, seo_title=title, seo_description=description)


@views_bp.route('/imsakiye/<sehir>')
def imsakiye_detay(sehir):
    if not is_latin_only(sehir):
        abort(400, description="Gecersiz karakter iceren sehir ismi.")

    country_code = request.args.get('country')
    if not country_code:
        country_code = get_country_for_city(sehir) or 'TR'

    if not is_latin_only(country_code):
        abort(400, description="Gecersiz karakter iceren ulke kodu.")

    sehir_adi = CITY_DISPLAY_NAME_MAPPING.get(sehir, sehir.replace('-', ' ').title())

    og_image_url = url_for(
        'og.og_image',
        title     = f"{sehir_adi} {suanki_yil} İmsakiyesi",
        subtitle  = f"{suanki_yil} Yılı Sahur ve İftar Vakitleri",
        theme     = 'ramadan',
        prompt    = f'\udb82\udd79 {sehir_adi} İmsakiyesi',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    title       = f"{sehir_adi} {suanki_yil} İmsakiyesi"
    description = f"{suanki_yil} Yılı Sahur ve İftar Vakitleri"
    return render_template('ramadan/ramadan_schedule_detail.html',
                           sehir=sehir,
                           country_code=country_code,
                           ramadan_info=RamadanService.get_ramadan_info(),
                           og_image_url=og_image_url,
                           seo_title=title,
                           seo_description=description)

# ======================================================
# ==== GUIDES ====
# ======================================================

@views_bp.route('/bilgi-kosesi')
@cache.cached(timeout=3600)
def bilgi_kosesi_liste():
    guides      = get_guides()
    title       = "Bilgi Köşesi - Çagrı Vakti"
    description = "Ezan vakitleri, kıble yönü, namaz bilgileri ve daha fazlası hakkında rehber yazılar."

    og_image_url = url_for(
        'og.og_image',
        title     = title,
        subtitle  = description,
        theme     = 'default',
        prompt    = '\uede2 Bilgi Köşesi',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )



    return render_template('guide/guide_list.html',
                           guides=guides,
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url)


@views_bp.route('/bilgi-kosesi/<slug>')
@cache.cached(timeout=3600)
def bilgi_kosesi_detay(slug):
    if not is_latin_only(slug):
        abort(400, description="Gecersiz karakter iceren slug.")

    guide = get_guide_by_slug(slug)
    if not guide:
        abort(404)

    guides      = get_guides()
    title       = f"{guide['title']} - Çağrı Vakti"
    description = guide['description']

    og_image_url = url_for(
        'og.og_image',
        title     = f'{guide["title"]}',
        subtitle  = description,
        theme     = 'blog',
        prompt    = f'\uede2 Bilgi Köşesi - {guide["title"]}',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    return render_template('guide/guide_detail.html',
                           guide=guide,
                           guides=guides,
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url)

# ======================================================
# ==== EMBED ====
# ======================================================

@views_bp.route('/sitene-ekle')
@cache.cached(timeout=86400)
def sitene_ekle():
    all_cities  = sorted(UserService.get_sehirler('ALL'))
    title       = "Sitenize Ekleyin - Çağrı Vakti"
    description = "Web siteniz için ücretsiz ezan vakitleri widget'ı. Renkleri özelleştirin, şehrinizi seçin ve kodu sitenize ekleyin."

    og_image_url = url_for(
        'og.og_image',
        title     = 'Sitenize Ekleyin',
        subtitle  = description,
        theme     = 'project',
        prompt    = '\udb82\udd79 Sitenize Ekleyin',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    return render_template('embed/builder.html',
                           cities=all_cities,
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url)


@views_bp.route('/embed/<sehir>')
def embed_widget(sehir):
    if not is_latin_only(sehir):
        abort(400)

    country_code = request.args.get('country', 'TR')

    try:
        vakitler = PrayerService.get_vakitler(sehir, country_code)
        try:
            yarin         = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            yarin_vakitler = PrayerService.get_vakitler(sehir, country_code, yarin)
            if yarin_vakitler:
                vakitler['yarin'] = {'imsak': yarin_vakitler.get('imsak')}
        except Exception:
            pass
    except Exception:
        return "Şehir bulunamadı", 404

    theme      = request.args.get('theme', 'dark')
    bg_color   = request.args.get('bg', '')
    text_color = request.args.get('text', '')

    display_name    = CITY_DISPLAY_NAME_MAPPING.get(sehir, sehir.replace('-', ' ').title())
    widget_version  = current_app.config.get('APP_VERSION', '1.0')
    current_date    = datetime.now().strftime('%Y-%m-%d')
    version_string  = f"{widget_version}-{sehir}-{current_date}-{theme}-{bg_color}-{text_color}"
    etag            = hashlib.md5(version_string.encode('utf-8')).hexdigest()

    if request.if_none_match and request.if_none_match.contains(etag):
        return "", 304

    response = make_response(render_template('embed/widget.html',
                                             sehir=sehir,
                                             display_name=display_name,
                                             vakitler=vakitler,
                                             theme=theme,
                                             bg_color=bg_color,
                                             text_color=text_color))
    response.headers['Cache-Control'] = 'public, no-cache'
    response.set_etag(etag)
    return response

# ======================================================
# ==== STATIC ====
# ======================================================

@views_bp.route('/kible-pusulasi')
@cache.cached(timeout=86400)
def kible_pusulasi():
    title       = "Kıble Pusulası - Çağrı Vakti"
    description = "Pusula ve harita yardımıyla online kıble yönünü bulun. Telefonunuzun sensörlerini kullanarak en doğru kıble açısını hesaplayın."

    og_image_url = url_for(
        'og.og_image',
        title     = 'Kıble Pusulası',
        subtitle  = description,
        theme     = 'default',
        prompt    = '\udb82\udd79 Kıble bul',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    return render_template('utils/qibla_compass.html',
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url)


@views_bp.route('/neden-biz')
@cache.cached(timeout=86400)
def neden_biz():

    title       = "Neden Çağrı Vakti?"
    description = "Doğruluk, hız ve gizlilik odaklı namaz vakitleri platformu."
    
    og_image_url = url_for(
        'og.og_image',
        title     = title,
        subtitle  = description,
        theme     = 'home',
        prompt    = '\udb82\udd79 Neden?',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )
    
    return render_template('info/why_us.html',
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url)


@views_bp.route('/ilkelerimiz')
@cache.cached(timeout=86400)
def ilkelerimiz():

    title       = "İlkelerimiz"
    description = "Çağrı Vakti\'nin temel değerleri ve kullanım ilkeleri."

    og_image_url = url_for(
        'og.og_image',
        title     = title,
        subtitle  = description,
        theme     = 'default',
        prompt    = '\uf0c0 İlkelerimiz',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )
    
    return render_template('info/policies.html',
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url)


@views_bp.route('/indir')
@cache.cached(timeout=86400)
def indir():
    og_image_url = url_for(
        'og.og_image',
        title     = 'Çağrı Vakti\'ni İndirin',
        subtitle  = 'Rainmeter widget, Discord botu ve daha fazlası.',
        theme     = 'project',
        prompt    = '\udb80\uddda İndir',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    title       = "Çağrı Vakti\'ni İndirin"
    description = "Rainmeter widget, Discord botu ve daha fazlası."



    return render_template('utils/download.html',
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url)




@views_bp.route('/Mustafa-Kemal-Ataturk')
@cache.cached(timeout=86400)
def ataturk():
    title       = "Mustafa Kemal Atatürk - Çağrı Vakti"
    description = "Mustafa Kemal Atatürk ve islama kattığı şeyler hakkında bilgi edinin."
    
    og_image_url = url_for(
        'og.og_image',
        title     = 'Mustafa Kemal Atatürk',
        subtitle  = description,
        theme     = 'project',
        prompt    = '\udb82\udd79 Mustafa Kemal Atatürk',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    return render_template('main/ataturk.html',
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url)

# ======================================================
# ==== ADMIN ====
# ======================================================

def admin_required(f):
    """Admin yetkisi kontrolü için decorator."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth       = request.authorization
        admin_user = current_app.config.get('ADMIN_USER')
        admin_pass = current_app.config.get('ADMIN_PASS')
        if not auth or not (auth.username == admin_user and auth.password == admin_pass):
            return make_response('Yetkisiz Erişim', 401, {'WWW-Authenticate': 'Basic realm="Admin Panel"'})
        return f(*args, **kwargs)
    return decorated_function


@views_bp.route('/admin')
@admin_required
def admin_dashboard():
    stats = {
        'guides_count':       Guide.query.count(),
        'messages_count':     ContactMessage.query.filter_by(is_read=False).count(),
        'daily_content_count': DailyContent.query.count(),
    }
    return render_template('admin/dashboard.html', stats=stats)


@views_bp.route('/admin/rehberler')
@admin_required
def admin_guides():
    guides = Guide.query.order_by(Guide.updated_at.desc()).all()
    return render_template('admin/guides.html', guides=guides)


@views_bp.route('/admin/rehber/ekle', methods=['GET', 'POST'])
@views_bp.route('/admin/rehber/duzenle/<int:guide_id>', methods=['GET', 'POST'])
@admin_required
def admin_guide_edit(guide_id=None):
    guide = Guide.query.get_or_404(guide_id) if guide_id else None

    if request.method == 'POST':
        title       = request.form.get('title')
        slug        = request.form.get('slug')
        category    = request.form.get('category')
        description = request.form.get('description')
        content     = request.form.get('content')
        image_url   = request.form.get('image_url')
        is_active   = 'is_active' in request.form

        if not is_latin_only(slug):
            flash('Slug yalnızca Latin karakterler içerebilir (URL uyumu için).', 'danger')
            return render_template('admin/guide_form.html', guide=guide)

        if not guide:
            guide = Guide(slug=slug)
            db.session.add(guide)

        guide.title       = title
        guide.slug        = slug
        guide.category    = category
        guide.description = description
        guide.content     = content
        guide.image_url   = image_url
        guide.is_active   = is_active

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
    contents = DailyContent.query.order_by(DailyContent.id.desc()).all()
    return render_template('admin/contents.html', contents=contents)


@views_bp.route('/admin/icerik/ekle', methods=['GET', 'POST'])
@views_bp.route('/admin/icerik/duzenle/<int:content_id>', methods=['GET', 'POST'])
@admin_required
def admin_content_edit(content_id=None):
    content = DailyContent.query.get_or_404(content_id) if content_id else None

    if request.method == 'POST':
        content_type = request.form.get('content_type')
        category     = request.form.get('category')
        text         = request.form.get('text')
        source       = request.form.get('source')
        day_index    = request.form.get('day_index')
        is_active    = 'is_active' in request.form

        if not content:
            content = DailyContent()
            db.session.add(content)

        content.content_type = content_type
        content.category     = category
        content.text         = text
        content.source       = source
        content.day_index    = int(day_index) if day_index else None
        content.is_active    = is_active

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
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages)


@views_bp.route('/admin/mesaj/oku/<int:message_id>')
@admin_required
def admin_message_read(message_id):
    message          = ContactMessage.query.get_or_404(message_id)
    message.is_read  = True
    db.session.commit()
    return render_template('admin/message_detail.html', message=message)


@views_bp.route('/admin/rehber/sil/<int:guide_id>', methods=['POST'])
@admin_required
def admin_guide_delete(guide_id):
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
    log_file          = current_app.config.get('LOG_FILE')
    api_log_file      = current_app.config.get('API_LOG_FILE')
    bot_log_file      = current_app.config.get('TELEGRAM_LOG_FILE')
    security_log_file = current_app.config.get('SECURITY_LOG_FILE')

    web_logs = api_logs = bot_logs = security_logs = ""
    stats    = {'hourly': {}, 'pages': {}}

    import re as _re
    from collections import Counter

    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            web_logs      = "".join(lines[-200:])
            log_pattern   = _re.compile(r'\[(.*?)\] (?:INFO in .*: )?.*? ziyaret: (.*)')
            hourly_counts = Counter()
            page_counts   = Counter()
            for line in lines:
                match = log_pattern.search(line)
                if match:
                    timestamp_str, path = match.groups()
                    try:
                        hour = (timestamp_str.split(' ')[1][:2] + ":00"
                                if ' ' in timestamp_str
                                else (timestamp_str[11:13] + ":00" if len(timestamp_str) > 13 else "00:00"))
                        hourly_counts[hour] += 1
                        page_counts[path.strip()] += 1
                    except Exception as e:
                        current_app.logger.error(f"Log satır hatası: {e} - Satır: {line}")
            stats['hourly'] = dict(sorted(hourly_counts.items()))
            stats['pages']  = dict(page_counts.most_common())
        except Exception as e:
            current_app.logger.error(f"Log analiz hatası: {e}")

    for attr, path in [('api_logs', api_log_file), ('bot_logs', bot_log_file), ('security_logs', security_log_file)]:
        if path and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    locals()[attr]  # noqa — just referencing; assignment below
                    val = "".join(f.readlines()[-200:])
                if attr == 'api_logs':      api_logs      = val
                elif attr == 'bot_logs':    bot_logs      = val
                elif attr == 'security_logs': security_logs = val
            except Exception as e:
                current_app.logger.error(f"{attr} okuma hatası: {e}")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'web_logs':      web_logs      or 'Log verisi bulunamadı.',
            'api_logs':      api_logs      or 'API log verisi bulunamadı.',
            'bot_logs':      bot_logs      or 'Bot log verisi bulunamadı.',
            'security_logs': security_logs or 'Güvenlik log verisi bulunamadı.',
            'stats':         stats,
        })

    return render_template('admin/logs.html',
                           web_logs=web_logs,
                           api_logs=api_logs,
                           bot_logs=bot_logs,
                           security_logs=security_logs,
                           stats=stats)

# ======================================================
# ==== EXTRA ====
# ======================================================

@views_bp.route('/asal-sayi')
@cache.cached(timeout=86400)
def prime_number():
    title       = "20000 Basamaklı Asal Sayı"
    description = "Asal sayı, 1 ve kendi kendisiyle sadece 2 tane bölen sayıdır."

    og_image_url = url_for(
        'og.og_image',
        title     = title,
        subtitle  = description,
        theme     = 'project',
        prompt    = '\uf4f7 Asal sayı',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    return render_template('extra/prime-number/prime-number.html',
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url
                           )


@views_bp.route('/rainmeter-rehber')
def rainmeter_guide():
    title       = "Rainmeter Rehber"
    description = "Rainmeter Rehberi, Rainmeter'ün kullanımda gerekli bilgileri ve ipucları sunar."

    og_image_url = url_for(
        'og.og_image',
        title     = title,
        subtitle  = description,
        theme     = 'project',
        prompt    = '\uf4f7 Rainmeter Rehber',
        domain    = 'cagrivakti.com.tr',
        _external = True,
    )

    return render_template('info/rainmeter_guide.html',
                           seo_title=title,
                           seo_description=description,
                           og_image_url=og_image_url
                           )


@views_bp.route('/download-widget')
def download_widget():
    directory = os.path.dirname(current_app.root_path)
    return send_from_directory(directory, 'cagrivakti-widget.rmskin', as_attachment=True)


# @views_bp.route('/qr-okuyucu')
# @cache.cached(timeout=86400)
# def qr_okuyucu():
#     title       = "Qr Okuyucu"
#     description = "Qr Okuyucu, kullanıcıların girdiği qr kodun okunmasını sağlar."

#     og_image_url = url_for(
#         'og.og_image',
#         title     = title,
#         subtitle  = description,
#         theme     = 'project',
#         prompt    = '\udb81\udc33 Qr Okuyucu',
#         domain    = 'cagrivakti.com.tr',
#         _external = True,
#     )
#     return render_template('extra/qr-reader/qr-reader.html',
#                            seo_title=title,
#                            seo_description=description,
#                            og_image_url=og_image_url
#                            )


# @views_bp.route('/r/<short_id>')
# @csrf.exempt
# def redirect_url(short_id):
#     obj           = QrRedirect.query.get_or_404(short_id)
#     obj.hit_count += 1
#     db.session.commit()
#     return redirect(obj.url)


@views_bp.route('/oyunlar/under-the-red-sky')
def under_the_red_sky():
    return render_template('extra/oyun/oyun.html', oyun_adi="Under the Red Sky")


@views_bp.route('/kaynak/under-the-red-sky/<path:filename>')
def serve_game_files(filename):
    game_dir = os.path.join(current_app.root_path, 'static', 'games', 'under-the-red-sky')
    return send_from_directory(game_dir, filename)

# ======================================================
# ==== STREAM ====
# ======================================================

@views_bp.route('/offline')
@cache.cached(timeout=86400)
def offline():
    return render_template('utils/offline.html')

# ======================================================
# ==== UTILS (sitemap, robots, favicon, sw, manifest) ====
# ======================================================

@views_bp.route('/sitemap.xml')
@cache.cached(timeout=86400)
def serve_sitemap():
    pages = []

    static_urls = [
        'views.index', 'views.sehir_secimi', 'views.imsakiye_secimi',
        'views.ramazan_nedir', 'views.orucu_bozan_durumlar',
        'views.neden_biz', 'views.indir', 'views.konum_bul',
        'views.iletisim', 'views.ilkelerimiz',
        'views.bilgi_kosesi_liste', 'views.prime_number', 'views.qr_okuyucu',
        'views.under_the_red_sky',
    ]
    for rule in static_urls:
        pages.append({
            'loc':     url_for(rule, _external=True),
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'priority': '1.0' if rule == 'views.index' else '0.8',
        })

    sehirler = UserService.get_sehirler('ALL')
    for s in sehirler:
        country = get_country_for_city(s)
        pages.append({'loc': url_for('views.sehir_sayfasi', sehir=s, _external=True),
                      'lastmod': datetime.now().strftime('%Y-%m-%d'), 'priority': '0.9'})
        if country == 'TR':
            pages.append({'loc': url_for('views.imsakiye_detay', sehir=s, _external=True),
                          'lastmod': datetime.now().strftime('%Y-%m-%d'), 'priority': '0.7'})

    for guide in get_guides():
        pages.append({'loc': url_for('views.bilgi_kosesi_detay', slug=guide['slug'], _external=True),
                      'lastmod': datetime.now().strftime('%Y-%m-%d'), 'priority': '0.6'})

    sitemap_xml = render_template('utils/sitemap_template.xml', pages=pages)
    response    = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response


@views_bp.route('/robots.txt')
@cache.cached(timeout=86400)
def serve_robots():
    content  = "User-agent: *\n"
    content += "Allow: /\n"
    content += "Disallow: /admin/\n"
    content += "Disallow: /offline\n"
    content += "Disallow: /static/data/\n"
    content += f"Sitemap: {url_for('views.serve_sitemap', _external=True)}\n"
    response = make_response(content)
    response.headers['Content-Type'] = 'text/plain'
    return response


@views_bp.route('/favicon.ico')
def favicon():
    response = make_response(send_from_directory(
        os.path.join(current_app.root_path, 'static', 'icons'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon',
    ))
    response.headers.pop('ETag', None)
    response.headers.pop('Last-Modified', None)
    return response


@views_bp.route('/sw.js')
def serve_sw():
    version = current_app.config.get('APP_VERSION', '1.0')
    sw_path = os.path.join(current_app.root_path, 'static', 'js', 'sw.js')
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace('${VERSION}', version)
        resp    = make_response(content)
        resp.headers['Content-Type']  = 'application/javascript; charset=utf-8'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp
    except Exception:
        response = make_response(send_from_directory(
            os.path.join(current_app.root_path, 'static', 'js'), 'sw.js'))
        response.headers['Cache-Control'] = 'no-cache'
        return response


@views_bp.route('/manifest.json')
def serve_manifest():
    manifest_path = os.path.join(current_app.root_path, 'static', 'manifest_base.json')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)

        user_city = request.cookies.get('user_city') or request.args.get('city')

        if 'shortcuts' in manifest_data:
            found = False
            for shortcut in manifest_data['shortcuts']:
                if shortcut.get('url') == '/konum-bul':
                    found = True
                    if user_city:
                        display_name          = CITY_DISPLAY_NAME_MAPPING.get(user_city, user_city)
                        shortcut['name']      = f"{display_name} Vakitleri"
                        shortcut['short_name'] = display_name
                        shortcut['url']       = f"/sehir/{user_city}"
                        shortcut['icons']     = [{'src': '/static/icons/android/android-launchericon-96-96.png',
                                                   'sizes': '96x96', 'type': 'image/png'}]
                    break

            if not found and user_city:
                display_name   = CITY_DISPLAY_NAME_MAPPING.get(user_city, user_city)
                new_shortcut   = {
                    'name':       f"{display_name} Vakitleri",
                    'short_name': display_name,
                    'url':        f"/sehir/{user_city}",
                    'icons':      [{'src': '/static/icons/android/android-launchericon-96-96.png',
                                    'sizes': '96x96', 'type': 'image/png'}],
                }
                manifest_data['shortcuts'].insert(0, new_shortcut)

        response = jsonify(manifest_data)
        response.headers['Cache-Control']    = 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0'
        response.headers['Pragma']           = 'no-cache'
        response.headers['Expires']          = '0'
        response.headers['Surrogate-Control'] = 'no-store'
        return response
    except Exception as e:
        current_app.logger.error(f"Manifest generation error: {e}")
        return send_from_directory(os.path.join(current_app.root_path, 'static'), 'manifest_base.json')


@views_bp.route('/konum-bul')
def konum_bul():
    return render_template('city/detect_location.html')

# ======================================================
# ==== CONTACT ====
# ======================================================

def send_async_notification(app, name, email, subject, message):
    with app.app_context():
        send_admin_notification(name, email, subject, message)


def send_admin_notification(name, email, subject, message):
    telegram_token = current_app.config.get('TELEGRAM_TOKEN')
    admin_id       = current_app.config.get('ADMIN_TELEGRAM_ID')
    if telegram_token and admin_id:
        try:
            text = (f"📩 *Yeni Geri Bildirim*\n\n"
                    f"👤 *Gönderen:* {name}\n"
                    f"📧 *E-posta:* {email}\n"
                    f"📌 *Konu:* {subject.capitalize()}\n\n"
                    f"📝 *Mesaj:*\n{message}")
            requests.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={"chat_id": admin_id, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
        except Exception as e:
            current_app.logger.error(f"Telegram notification error: {e}")


@views_bp.route('/iletisim', methods=['GET', 'POST'])
@limiter.limit("10 per hour", methods=['POST'])
def iletisim():
    if request.method == 'POST':
        if request.form.get('website'):
            return redirect(url_for('views.index'))

        name    = bleach.clean(request.form.get('name', ''))
        email   = bleach.clean(request.form.get('email', ''))
        subject = bleach.clean(request.form.get('subject', ''))
        message = bleach.clean(request.form.get('message', ''))

        if not all([name, email, subject, message]):
            flash('Lütfen tüm alanları doldurun.', 'error')
            return redirect(url_for('views.iletisim'))

        if len(message) < 10:
            flash('Mesajınız çok kısa, lütfen biraz daha detay verin.', 'error')
            return redirect(url_for('views.iletisim'))

        if len(message) > 2000:
            flash('Mesajınız çok uzun, lütfen daha kısa bir mesaj gönderin.', 'error')
            return redirect(url_for('views.iletisim'))

        try:
            new_message = ContactMessage(name=name, email=email, subject=subject, message=message)
            db.session.add(new_message)
            db.session.commit()
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