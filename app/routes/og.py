"""
og.py — Çağrı Vakti Dinamik OG Image Üretici
=============================================
Endpoint: /og-image

Query parametreleri:
  title    — Ana başlık metni           (max 80 karakter)
  subtitle — Alt başlık metni           (max 120 karakter)
  theme    — Renk teması                (city|ramadan|home|default|live|ataturk|blog|project)
  prompt   — Sol üstteki terminal komutu (max 60 karakter)
  domain   — Sağ alttaki domain metni  (max 50 karakter)
"""

import io
from functools import lru_cache
from flask import Blueprint, request, send_file
from PIL import Image, ImageDraw, ImageFont

og_bp = Blueprint('og', __name__)

# ─────────────────────────────────────────────────────────────────────────────
# GÖRSEL BOYUTLARI
# ─────────────────────────────────────────────────────────────────────────────
W = 1200
H = 630

# ─────────────────────────────────────────────────────────────────────────────
# RENK TEMALAR
# ─────────────────────────────────────────────────────────────────────────────
THEMES: dict[str, dict[str, str]] = {

    # ── ANA SAYFA (Sıcak ve Karşılayıcı) ────────────────────────────────────
    'index': {
        'bg':      '#0f0a09',   # Çok koyu kahve/siyah
        'accent':  '#f97316',   # Turuncu (Enerji)
        'accent2': '#facc15',   # Sarı (Aydınlık)
        'text':    '#fff7ed',
        'text2':   '#a8a29e',
    },

    # ── ŞEHİR VE KONUM (Huzurlu ve Manevi) ──────────────────────────────────
    'city': {
        'bg':      '#061014',   # Koyu gece mavisi
        'accent':  '#14b8a6',   # Teal/Turkuaz (İslami sanat tonu)
        'accent2': '#fbbf24',   # Kehribar (Kandil ışığı)
        'text':    '#f0fdfa',
        'text2':   '#94a3b8',
    },
    'city-page': {
        'bg':      '#061014',
        'accent':  '#14b8a6',
        'accent2': '#fbbf24',
        'text':    '#f0fdfa',
        'text2':   '#94a3b8',
    },
    'location-page': {
        'bg':      '#061014',
        'accent':  '#06b6d4',   # Cyan (GPS/Teknoloji vurgusu)
        'accent2': '#fbbf24',
        'text':    '#ecfeff',
        'text2':   '#94a3b8',
    },

    # ── RAMAZAN VE İMSAKİYE (Mistik ve Derin) ────────────────────────────────
    'ramadan': {
        'bg':      '#0d0817',   # Derin patlıcan moru
        'accent':  '#f59e0b',   # Altın sarısı
        'accent2': '#c084fc',   # Lavanta
        'text':    '#faf5ff',
        'text2':   '#9ca3af',
    },
    'ramadan-fasting': {
        'bg':      '#0d0817',
        'accent':  '#f59e0b',
        'accent2': '#c084fc',
        'text':    '#faf5ff',
        'text2':   '#9ca3af',
    },
    'imsakiye': {
        'bg':      '#0d0817',
        'accent':  '#fbbf24',
        'accent2': '#d8b4fe',
        'text':    '#faf5ff',
        'text2':   '#9ca3af',
    },
    'imsakiye-page': {
        'bg':      '#0d0817',
        'accent':  '#fbbf24',
        'accent2': '#d8b4fe',
        'text':    '#faf5ff',
        'text2':   '#9ca3af',
    },

    # ── BİLGİ KÖŞESİ (Okunabilirlik ve Odak) ───────────────────────────────
    'knowledge': {
        'bg':      '#0c0a09',   # Taş rengi siyah
        'accent':  '#ea580c',   # Yanık turuncu (Kitap/Kağıt tonu)
        'accent2': '#fcd34d',   # Parlak kehribar
        'text':    '#fafaf9',
        'text2':   '#a8a29e',
    },
    'knowledge-page': {
        'bg':      '#0c0a09',
        'accent':  '#ea580c',
        'accent2': '#fcd34d',
        'text':    '#fafaf9',
        'text2':   '#a8a29e',
    },

    # ── ARAÇLAR VE İNDİRMELER (Modern ve Teknolojik) ────────────────────────
    'add-widget': {
        'bg':      '#020617',   # Safir siyahı
        'accent':  '#6366f1',   # İndigo (Yazılım)
        'accent2': '#22d3ee',   # Cyan (Modernite)
        'text':    '#f8fafc',
        'text2':   '#94a3b8',
    },
    'qibla-page': {
        'bg':      '#020617',
        'accent':  '#3b82f6',   # Mavi (Pusula/Navigasyon)
        'accent2': '#2dd4bf',   # Turkuaz
        'text':    '#f8fafc',
        'text2':   '#94a3b8',
    },
    'download-page': {
        'bg':      '#020617',
        'accent':  '#818cf8',
        'accent2': '#38bdf8',
        'text':    '#f8fafc',
        'text2':   '#94a3b8',
    },
    'rainmeter-guide': {
        'bg':      '#020617',
        'accent':  '#4f46e5',
        'accent2': '#06b6d4',
        'text':    '#f8fafc',
        'text2':   '#94a3b8',
    },

    # ── KURUMSAL VE İLETİŞİM (Güven ve Profesyonellik) ─────────────────────
    'why-us-page': {
        'bg':      '#050505',
        'accent':  '#10b981',   # Zümrüt yeşili (Güven/Doğruluk)
        'accent2': '#3b82f6',   # Mavi (Profesyonellik)
        'text':    '#f0fdf4',
        'text2':   '#9ca3af',
    },
    'policies-page': {
        'bg':      '#050505',
        'accent':  '#059669',
        'accent2': '#2563eb',
        'text':    '#f0fdf4',
        'text2':   '#9ca3af',
    },
    'contact-page': {
        'bg':      '#050505',
        'accent':  '#6366f1',
        'accent2': '#06b6d4',
        'text':    '#f8fafc',
        'text2':   '#94a3b8',
    },

    # ── ÖZEL SAYFALAR ──────────────────────────────────────────────────────
    'ataturk-page': {
        'bg':      '#050505',
        'accent':  '#dc2626',   # Türk Kırmızısı (Daha canlı)
        'accent2': '#d4af37',   # Metalik Altın
        'text':    '#ffffff',
        'text2':   '#d1d5db',
    },
    'prime-number': {
        'bg':      '#08070b',
        'accent':  '#8b5cf6',   # Mor (Matematik/Gizem)
        'accent2': '#ec4899',   # Pembe
        'text':    '#fdf2f8',
        'text2':   '#9ca3af',
    },
    'game-page': {
        'bg':      '#0f0505',   # Kan kırmızısı siyah
        'accent':  '#b91c1c',   # Koyu kırmızı
        'accent2': '#f59e0b',   # Kehribar (Ateş/Işık)
        'text':    '#fee2e2',
        'text2':   '#7f1d1d',
    },

    # ── VARSAYILAN ─────────────────────────────────────────────────────────
    'default': {
        'bg':      '#0a0a0a',
        'accent':  '#4ade80',
        'accent2': '#60a5fa',
        'text':    '#e5e7eb',
        'text2':   '#9ca3af',
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# FONT YOLLARI (Ubuntu/Debian sunucu için)
# ─────────────────────────────────────────────────────────────────────────────
FONT_BOLD = '/usr/share/fonts/JetBrainsMono/JetBrainsMonoNerdFont-Bold.ttf'
FONT_REG  = '/usr/share/fonts/JetBrainsMono/JetBrainsMonoNerdFont-Regular.ttf'

# ─────────────────────────────────────────────────────────────────────────────
# DİZAYN SABİTLERİ
# ─────────────────────────────────────────────────────────────────────────────
PAD          = 64     # sol/sağ kenar boşluğu
MARGIN       = 40     # domain kutusu kenar boşluğu
DOM_PAD_X    = 16     # domain kutusu yatay iç boşluk
DOM_PAD_Y    = 10     # domain kutusu dikey iç boşluk
DOM_FONT_SZ  = 20     # domain font boyutu
PROMPT_SZ    = 22     # prompt font boyutu
SUBTITLE_SZ  = 24     # alt başlık font boyutu
BRACKET_LW   = 2      # bracket çizgi kalınlığı
TITLE_SIZES  = (72, 58, 46, 36, 28)  # başlık için denenen font boyutları

# ─────────────────────────────────────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────────────────────────────────────

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    """'#rrggbb' → (r, g, b)"""
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Font yükle, bulamazsa varsayılanı kullan"""
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def _fit_title_font(draw: ImageDraw.ImageDraw, text: str, max_width: int) -> tuple[ImageFont.FreeTypeFont, int]:
    """Başlığı taşırmadan sığacak en büyük font boyutunu bul"""
    for size in TITLE_SIZES:
        font = _load_font(FONT_BOLD, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] < max_width:
            return font, size
    font = _load_font(FONT_BOLD, TITLE_SIZES[-1])
    return font, TITLE_SIZES[-1]

def _draw_bracket(draw, x1, y1, x2, y2, color):
    """4 köşeli bracket (⌐ ¬) çerçevesi çizer."""
    arm = max(20, min(36, int((x2 - x1) * 0.18)))
    lw  = BRACKET_LW

    # Sol üst ⌐
    draw.rectangle([x1,       y1,       x1 + arm, y1 + lw], fill=color)
    draw.rectangle([x1,       y1,       x1 + lw,  y1 + arm], fill=color)
    # Sağ üst
    draw.rectangle([x2 - arm, y1,       x2,        y1 + lw], fill=color)
    draw.rectangle([x2 - lw,  y1,       x2,        y1 + arm], fill=color)
    # Sol alt
    draw.rectangle([x1,       y2 - lw,  x1 + arm,  y2], fill=color)
    draw.rectangle([x1,       y2 - arm, x1 + lw,   y2], fill=color)
    # Sağ alt ¬
    draw.rectangle([x2 - arm, y2 - lw,  x2,        y2], fill=color)
    draw.rectangle([x2 - lw,  y2 - arm, x2,        y2], fill=color)

def _draw_subtitle_multiline(draw, text, x, y, font, color, max_width, line_spacing=12):
    """Alt başlığı çok satırlı çizer (manuel '|' veya otomatik wrap)."""
    if '|' in text:
        line_h = draw.textbbox((0, 0), 'A', font=font)[3] + line_spacing
        for i, line in enumerate(text.split('|')):
            draw.text((x, y + i * line_h), line.strip(), font=font, fill=color)
        return

    words = text.split(' ')
    line, cy = '', y
    for word in words:
        test = (line + ' ' + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            line = test
        else:
            if line:
                draw.text((x, cy), line, font=font, fill=color)
                cy += draw.textbbox((0, 0), line, font=font)[3] + line_spacing
            line = word
    if line:
        draw.text((x, cy), line, font=font, fill=color)

# ─────────────────────────────────────────────────────────────────────────────
# ANA GÖRSEL ÜRETİCİ
# ─────────────────────────────────────────────────────────────────────────────

def make_og(title, subtitle, theme, prompt, domain):
    t   = THEMES.get(theme, THEMES['default'])
    img = Image.new('RGB', (W, H), _hex_to_rgb(t['bg']))
    d   = ImageDraw.Draw(img)

    # 1. Üst accent çizgisi
    d.rectangle([0, 0, W, 3], fill=_hex_to_rgb(t['accent']))

    # 2. Prompt (sol üst)
    f_prompt = _load_font(FONT_REG, PROMPT_SZ)
    d.text((PAD, 48), prompt, font=f_prompt, fill=_hex_to_rgb(t['accent']))

    # 3. Ana başlık (dikey merkez üstü)
    max_title_w = W - PAD * 2
    f_title, title_size = _fit_title_font(d, title, max_title_w)
    title_y = H // 2 - title_size - 16
    d.text((PAD, title_y), title, font=f_title, fill=_hex_to_rgb(t['text']))

    # 4. Alt başlık (multiline support)
    f_sub = _load_font(FONT_REG, SUBTITLE_SZ)
    _draw_subtitle_multiline(d, subtitle, PAD, title_y + title_size + 24, f_sub, _hex_to_rgb(t['text2']), max_title_w)

    # 5. Domain + bracket (sağ alt, merkezlenmiş)
    f_domain = _load_font(FONT_REG, DOM_FONT_SZ)
    db = d.textbbox((0, 0), domain, font=f_domain)
    dw, dh = db[2] - db[0], db[3] - db[1]

    bx_w, bx_h = dw + DOM_PAD_X * 2, dh + DOM_PAD_Y * 2
    bx2, by2 = W - MARGIN, H - MARGIN
    bx1, by1 = bx2 - bx_w, by2 - bx_h

    d.text(((bx1 + bx2) / 2, (by1 + by2) / 2), domain, font=f_domain, fill=_hex_to_rgb(t['accent2']), anchor="mm")
    _draw_bracket(d, bx1, by1, bx2, by2, _hex_to_rgb(t['accent2']))

    return img

# ─────────────────────────────────────────────────────────────────────────────
# FLASK ROUTE
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=300)
def _cached_og(title, subtitle, theme, prompt, domain):
    img = make_og(title, subtitle, theme, prompt, domain)
    buf = io.BytesIO()
    img.save(buf, 'PNG', optimize=True)
    return buf.getvalue()

@og_bp.route('/og-image')
def og_image():
    title    = request.args.get('title',    'Çağrı Vakti')[:80]
    subtitle = request.args.get('subtitle', 'Türkiye Namaz Vakitleri')[:120]
    theme    = request.args.get('theme',    'default')
    icon     = request.args.get('icon',     '')[:20]
    prompt   = request.args.get('prompt',   'cagrivakti.com.tr')[:60]
    domain   = request.args.get('domain',   'cagrivakti.com.tr')[:50]

    # Sadece ikon parametresini Unicode kaçış dizilerinden arındır
    try:
        if icon:
            # URL'den gelen çift backslash veya düz metin halindeki \u dizilerini işle
            if "\\" in icon:
                icon = icon.encode('utf-8').decode('unicode_escape').encode('utf-16', 'surrogatepass').decode('utf-16')
            # Bazı durumlarda unicode_escape yetmezse manuel temizlik (opsiyonel ama güvenli)
            icon = icon.replace('\\', '') if '\\u' not in icon else icon
    except Exception:
        pass

    # İkon varsa prompt'un başına ekle
    full_prompt = f"{icon} {prompt}".strip() if icon else prompt

    data = _cached_og(title, subtitle, theme, full_prompt, domain)
    resp = send_file(io.BytesIO(data), mimetype='image/png')
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp
