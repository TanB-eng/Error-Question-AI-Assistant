from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def main() -> None:
    fixture_dir = Path(__file__).resolve().parents[1]
    image_buffer = BytesIO()
    image = Image.new("RGB", (320, 160), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 300, 140), outline="black", width=2)
    draw.line((40, 100, 280, 60), fill="black", width=3)
    image.save(image_buffer, format="PNG")

    image_path = fixture_dir / "image_only_source.png"
    image_path.write_bytes(image_buffer.getvalue())
    output_path = fixture_dir / "image_only.pdf"
    pdf = canvas.Canvas(str(output_path), pagesize=letter)
    pdf.drawImage(str(image_path), 72, 560, width=320, height=160)
    pdf.save()
    image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
