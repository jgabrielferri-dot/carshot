"""
Watermark utility for SpotGrid.

Fotos "Só à venda" (is_for_sale=True, is_public=False) recebem:
  - Resolução reduzida para no máximo PREVIEW_MAX_PX no lado maior
  - Grade densa de "SPOTGRID" em diagonal, bem visível
  - Overlay escurecido para dificultar uso sem compra
  - Qualidade JPEG baixa (PREVIEW_QUALITY)
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Configurações do preview protegido ────────────────────────
PREVIEW_MAX_PX   = 900    # lado maior do preview (px)
PREVIEW_QUALITY  = 42     # qualidade JPEG (0-95)
WM_OPACITY       = 160    # opacidade da marca d'água (0-255) — 160 ≈ 63%
DARKEN_OPACITY   = 90     # overlay escuro sobre a imagem (0-255)
WM_TEXT          = "SPOTGRID"
# ──────────────────────────────────────────────────────────────

_FONT_PATHS = [
    # macOS
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/ArialHB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    # Windows
    "C:/Windows/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/Calibri.ttf",
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
    """
    Gera uma versão protegida da imagem:
    - Resolução reduzida
    - Grade densa de marca d'água diagonal
    - Overlay escuro
    - Qualidade JPEG baixa
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with Image.open(input_path) as src:
        img = src.convert("RGBA")

    # ── 1. Reduzir resolução ──────────────────────────────────
    w, h = img.size
    scale = min(PREVIEW_MAX_PX / max(w, h), 1.0)
    if scale < 1.0:
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
    w, h = img.size

    # ── 2. Overlay escuro (dificulta leitura visual) ──────────
    dark = Image.new("RGBA", (w, h), (0, 0, 0, DARKEN_OPACITY))
    img = Image.alpha_composite(img, dark)

    # ── 3. Grade densa de marcas d'água ───────────────────────
    font_size = max(18, w // 14)          # texto compacto para caber mais repetições
    font = _get_font(font_size)

    # Camada de watermark em alta resolução para depois rotacionar
    wm_layer = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wm_layer)

    bbox = draw.textbbox((0, 0), WM_TEXT, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    step_x = tw + 24   # espaçamento reduzido — grade mais densa
    step_y = th + 20

    # Duas passagens: texto principal + versão menor entre as linhas
    for pass_idx, (txt, fsize, alpha) in enumerate([
        (WM_TEXT,           font_size,       WM_OPACITY),
        (WM_TEXT,           font_size // 2,  WM_OPACITY - 30),
    ]):
        f = _get_font(fsize)
        b = draw.textbbox((0, 0), txt, font=f)
        bw, bh = b[2] - b[0], b[3] - b[1]
        offset_x = (step_x // 2) * pass_idx
        offset_y = (step_y // 2) * pass_idx
        for xi in range(-step_x, w * 2 + step_x, step_x):
            for yi in range(-step_y, h * 2 + step_y, step_y):
                draw.text(
                    (xi + offset_x, yi + offset_y),
                    txt,
                    fill=(255, 255, 255, alpha),
                    font=f,
                )

    # Rotacionar e recortar para o tamanho da imagem
    wm_layer = wm_layer.rotate(-25, expand=False)
    # Recortar a região central que corresponde à imagem
    cx = (wm_layer.width  - w) // 2
    cy = (wm_layer.height - h) // 2
    wm_layer = wm_layer.crop((cx, cy, cx + w, cy + h))

    watermarked = Image.alpha_composite(img, wm_layer).convert("RGB")

    # ── 4. Salvar com qualidade baixa ─────────────────────────
    watermarked.save(output_path, "JPEG", quality=PREVIEW_QUALITY, optimize=True)
