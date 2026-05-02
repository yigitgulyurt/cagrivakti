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

    # ── Çağrı Vakti — Şehir sayfaları (turkuaz-altın) ────────────────────────
    'city': {
        'bg':      '#0a0f14',
        'accent':  '#2dd4bf',   # turkuaz
        'accent2': '#f59e0b',   # amber/altın
        'text':    '#e2e8f0',
        'text2':   '#64748b',
    },

    # ── Çağrı Vakti — Ramazan sayfaları (altın-mor, mistik) ─────────────────
    'ramadan': {
        'bg':      '#0c0a14',
        'accent':  '#d4af37',   # altın
        'accent2': '#a78bfa',   # mor
        'text':    '#fdf6e3',
        'text2':   '#6b7280',
    },

    # ── Çağrı Vakti — Ana sayfa / genel (turuncu-kırmızı) ───────────────────
    'home': {
        'bg':      '#110a08',
        'accent':  '#fb923c',   # turuncu
        'accent2': '#ef4444',   # kırmızı
        'text':    '#fef3c7',
        'text2':   '#78716c',
    },

    # ── Standart Temalar (yigitgulyurt.net.tr ile uyumlu) ────────────────────
    'default': {
        'bg':      '#0d0d0d',
        'accent':  '#4ade80',   # yeşil (Terminal accent)
        'accent2': '#60a5fa',   # mavi
        'text':    '#e2e2e2',
        'text2':   '#888888',
    },
    'live': {
        'bg':      '#0d0d0d',
        'accent':  '#f87171',   # kırmızı (Recording/Live)
        'accent2': '#60a5fa',   # mavi
        'text':    '#e2e2e2',
        'text2':   '#888888',
    },
    'ataturk': {
        'bg':      '#080808',
        'accent':  '#e30a17',   # Türk kırmızısı
        'accent2': '#c5a059',   # altın
        'text':    '#f0f0f0',
        'text2':   '#999999',
    },
    'blog': {
        'bg':      '#0d0d0d',
        'accent':  '#fb923c',   # turuncu (Yazı/Blog)
        'accent2': '#fcd34d',   # kehribar
        'text':    '#e2e2e2',
        'text2':   '#888888',
    },
    'project': {
        'bg':      '#0d0d0d',
        'accent':  '#818cf8',   # indigo (Yaratıcılık/Proje)
        'accent2': '#22d3ee',   # cyan
        'text':    '#e2e2e2',
        'text2':   '#888888',
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
    prompt   = request.args.get('prompt',   '☪ cagrivakti.com.tr')[:60]
    domain   = request.args.get('domain',   'cagrivakti.com.tr')[:50]

    data = _cached_og(title, subtitle, theme, prompt, domain)
    resp = send_file(io.BytesIO(data), mimetype='image/png')
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp
