"""
Watermark utility for SpotGrid.

Estilo: grade horizontal de badges coloridos semitransparentes,
foto completamente visível por baixo.
"""

import os
from PIL import Image, ImageDraw, ImageFont

# ── Configurações ──────────────────────────────────────────────
PREVIEW_MAX_PX  = 1200   # lado maior do preview (px)
PREVIEW_QUALITY = 72     # qualidade JPEG — mais alta pois não escurecemos a foto
WM_TEXT         = "SPOTGRID"
BADGE_BG        = (180, 20, 20, 140)   # vermelho semitransparente (RGBA)
TEXT_COLOR      = (255, 255, 255, 240) # branco quase opaco
PADDING_X       = 10     # espaço interno horizontal do badge
PADDING_Y       = 5      # espaço interno vertical do badge
STEP_X_EXTRA    = 60     # espaço horizontal entre badges
STEP_Y_EXTRA    = 48     # espaço vertical entre linhas
# ──────────────────────────────────────────────────────────────

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/ArialHB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def add_watermark(input_path: str, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with Image.open(input_path) as src:
        img = src.convert("RGBA")

    # ── 1. Reduzir resolução ──────────────────────────────────
    w, h = img.size
    scale = min(PREVIEW_MAX_PX / max(w, h), 1.0)
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    w, h = img.size

    # ── 2. Camada de watermark (badges horizontais em grade) ──
    font_size = max(14, w // 22)
    font = _get_font(font_size)

    wm_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wm_layer)

    bbox = draw.textbbox((0, 0), WM_TEXT, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    badge_w = tw + PADDING_X * 2
    badge_h = th + PADDING_Y * 2
    step_x  = badge_w + STEP_X_EXTRA
    step_y  = badge_h + STEP_Y_EXTRA

    row = 0
    y = -badge_h
    while y < h + badge_h:
        # Linhas alternadas deslocadas pela metade para parecer mais profissional
        offset_x = (step_x // 2) if (row % 2 == 1) else 0
        x = -badge_w + offset_x
        while x < w + badge_w:
            # Fundo do badge
            draw.rounded_rectangle(
                [x, y, x + badge_w, y + badge_h],
                radius=4,
                fill=BADGE_BG,
            )
            # Texto
            draw.text(
                (x + PADDING_X - bbox[0], y + PADDING_Y - bbox[1]),
                WM_TEXT,
                font=font,
                fill=TEXT_COLOR,
            )
            x += step_x
        y += step_y
        row += 1

    watermarked = Image.alpha_composite(img, wm_layer).convert("RGB")

    # ── 3. Salvar ─────────────────────────────────────────────
    watermarked.save(output_path, "JPEG", quality=PREVIEW_QUALITY, optimize=True)
