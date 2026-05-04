from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def main() -> None:
    output_path = Path(__file__).resolve().parents[1] / "sample_exam.pdf"
    pdf = canvas.Canvas(str(output_path), pagesize=letter)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(72, 720, "1. Solve x plus one equals two.")
    pdf.drawString(72, 700, "2. Factor y squared minus one.")
    pdf.drawString(72, 680, "3. Find area.")
    pdf.save()


if __name__ == "__main__":
    main()
