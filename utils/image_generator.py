from PIL import Image, ImageDraw, ImageFont
import io
import os

def generate_story_image(fake_name, fake_id, role="Top Talent"):
    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), (12, 12, 12))
    d = ImageDraw.Draw(img)

    # -------------------------
    # Font loader (safe)
    # -------------------------
    def load_font(size, bold=False):
        try:
            if os.name == "nt":
                path = "C:\\Windows\\Fonts\\courbd.ttf" if bold else "C:\\Windows\\Fonts\\cour.ttf"
            else:
                path = (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
                    if bold else
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
                )
            return ImageFont.truetype(path, size)
        except:
            return ImageFont.load_default()

    title_font = load_font(110, bold=True)
    section_font = load_font(60, bold=True)
    body_font = load_font(46)
    small_font = load_font(34)

    # -------------------------
    # Subtle grid background
    # -------------------------
    for y in range(0, height, 80):
        d.line((0, y, width, y), fill=(20, 20, 20))

    # -------------------------
    # TOP SECRET watermark (SAFE)
    # -------------------------
    watermark_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    wd = ImageDraw.Draw(watermark_layer)

    wd.text(
        (width // 2, height // 2),
        "TOP SECRET",
        font=load_font(180, bold=True),
        fill=(180, 180, 180, 35),
        anchor="mm"
    )

    watermark_layer = watermark_layer.rotate(35, resample=Image.BICUBIC)
    img = Image.alpha_composite(img.convert("RGBA"), watermark_layer).convert("RGB")
    d = ImageDraw.Draw(img)

    # -------------------------
    # Header
    # -------------------------
    d.rectangle((0, 0, width, 180), fill=(30, 30, 30))
    d.text((60, 50), "CLASSIFIED DOSSIER", font=section_font, fill=(200, 200, 200))
    d.text((60, 120), "CAMPUS TALENT INTELLIGENCE UNIT", font=small_font, fill=(120, 120, 120))
    d.line((60, 190, width - 60, 190), fill=(140, 0, 0), width=4)

    # -------------------------
    # Subject block
    # -------------------------
    y = 300
    d.text((60, y), "SUBJECT NAME", font=small_font, fill=(130, 130, 130))
    d.text((60, y + 50), fake_name.upper(), font=title_font, fill=(220, 220, 220))

    y += 200
    d.text((60, y), f"IDENTITY CODE : {fake_id}", font=body_font, fill=(150, 150, 150))
    d.text((60, y + 70), f"ROLE          : {role.upper()}", font=body_font, fill=(150, 150, 150))
    d.text((60, y + 140), "STATUS        : ACTIVE", font=body_font, fill=(150, 150, 150))

    # -------------------------
    # Warning box
    # -------------------------
    box_y = 1200
    d.rectangle((60, box_y, width - 60, box_y + 260), outline=(140, 0, 0), width=3)
    d.text((80, box_y + 40), "⚠ WARNING", font=section_font, fill=(140, 0, 0))
    d.text(
        (80, box_y + 120),
        "This intelligence file is restricted.\nUnauthorized access is prohibited.",
        font=body_font,
        fill=(200, 200, 200)
    )

    # -------------------------
    # Footer
    # -------------------------
    d.text(
        (60, height - 70),
        "END OF FILE — CAMPUS TALENT SYSTEM",
        font=small_font,
        fill=(100, 100, 100)
    )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
