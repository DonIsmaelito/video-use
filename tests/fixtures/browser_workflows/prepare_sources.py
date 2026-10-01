#!/usr/bin/env python3
"""Prepare original synthetic source fixtures for document/data/audio workflows.

Run locally before the cloud smoke test. ReportLab is a fixture-only dependency;
the worker only needs the generated PDF, CSV, XLSX and PNG source files.
"""
from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[3]
METRICS = [("Q1", 12), ("Q2", 18), ("Q3", 27)]
PAPER = "#F4EEDC"
INK = "#221831"
PURPLE = "#805BDC"
LIGHT_PURPLE = "#B5A0EF"
MUTED = "#70657A"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def write_pdf(path: Path) -> None:
    document = canvas.Canvas(str(path), pagesize=(640, 360), invariant=1, pageCompression=1)
    document.setTitle("Synthetic fixture metrics - three quarters")
    document.setAuthor("Video-use synthetic test fixtures")
    document.setSubject("Synthetic completed-project counts: Q1=12, Q2=18, Q3=27")

    def text(x, y, value, size=12, color=INK, font="Helvetica", width=552):
        assert stringWidth(value, font, size) <= width, f"Fixture text exceeds its column: {value}"
        document.setFont(font, size)
        document.setFillColor(HexColor(color))
        document.drawString(x, y, value)

    def base(page):
        document.setFillColor(HexColor(PAPER))
        document.rect(0, 0, 640, 360, fill=1, stroke=0)
        text(44, 323, "FIXTURE LAB", 11, PURPLE, "Helvetica-Bold")
        text(410, 323, "SYNTHETIC SAMPLE DATA", 9, MUTED, width=186)
        document.setStrokeColor(HexColor("#D9D0DD"))
        document.setLineWidth(.65)
        document.line(44, 48, 596, 48)
        text(44, 29, "Source: fixture_metrics.csv / synthetic test data", 9, MUTED)
        text(574, 29, f"0{page}", 9, MUTED, width=22)

    base(1)
    text(44, 267, "THREE QUARTERS", 10, MUTED, "Helvetica-Bold")
    text(44, 222, "From 12 to 27", 38, INK, "Helvetica-Bold", width=290)
    text(44, 195, "Completed projects, Q1 through Q3.", 12, MUTED, width=280)
    text(44, 121, "+125%", 43, PURPLE, "Helvetica-Bold", width=270)
    text(46, 100, "change from the first quarter", 11, MUTED, width=270)
    for index, (quarter, count) in enumerate(METRICS):
        x = 355 + index * 76
        height = count / 27 * 122
        document.setFillColor(HexColor(["#C3B4E7", LIGHT_PURPLE, PURPLE][index]))
        document.roundRect(x, 104, 44, height, 5, fill=1, stroke=0)
        text(x + 7, 116 + height, str(count), 19, INK, "Helvetica-Bold", width=44)
        text(x + 11, 80, quarter, 11, MUTED, width=44)
    document.showPage()

    base(2)
    text(44, 267, "READ THE SOURCE", 10, MUTED, "Helvetica-Bold")
    text(44, 222, "Keep the story honest.", 35, INK, "Helvetica-Bold")
    text(44, 195, "Three stored values. A clear comparison. No invented cause.", 12, MUTED)
    for index, (quarter, count) in enumerate(METRICS):
        x = 44 + index * 190
        document.setFillColor(HexColor("#FFFCF5"))
        document.roundRect(x, 94, 172, 79, 8, fill=1, stroke=0)
        text(x + 15, 150, quarter, 11, MUTED, "Helvetica-Bold", width=142)
        text(x + 14, 108, str(count), 38, PURPLE if index == 2 else INK, "Helvetica-Bold", width=70)
        text(x + 79, 119, "completed", 9, MUTED, width=80)
        text(x + 79, 106, "projects", 9, MUTED, width=80)
    text(44, 68, "27 is 125% above 12. These are fixtures, not business results.", 10, MUTED)
    document.showPage()
    document.save()


def write_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["quarter", "completed_projects", "data_status"])
        writer.writerows((quarter, count, "synthetic fixture") for quarter, count in METRICS)


def write_xlsx(path: Path) -> None:
    rows = ['<row r="1"><c r="A1" t="inlineStr"><is><t>quarter</t></is></c><c r="B1" t="inlineStr"><is><t>completed_projects</t></is></c><c r="C1" t="inlineStr"><is><t>data_status</t></is></c></row>']
    for row, (quarter, count) in enumerate(METRICS, 2):
        rows.append(f'<row r="{row}"><c r="A{row}" t="inlineStr"><is><t>{quarter}</t></is></c><c r="B{row}"><v>{count}</v></c><c r="C{row}" t="inlineStr"><is><t>synthetic fixture</t></is></c></row>')
    rows.append('<row r="5"><c r="A5" t="inlineStr"><is><t>Total</t></is></c><c r="B5"><f>SUM(B2:B4)</f><v>57</v></c><c r="C5" t="inlineStr"><is><t>cached fixture value</t></is></c></row>')
    parts = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": f'<Relationships xmlns="{PACKAGE_REL}"><Relationship Id="document" Type="{REL_NS}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="{SHEET_NS}" xmlns:r="{REL_NS}"><workbookPr date1904="0"/><sheets><sheet name="Metrics" sheetId="1" r:id="sheet1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{PACKAGE_REL}"><Relationship Id="sheet1" Type="{REL_NS}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{SHEET_NS}"><dimension ref="A1:C5"/><sheetData>{"".join(rows)}</sheetData></worksheet>',
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, value)


def font(size, bold=False):
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def write_cover(path: Path) -> None:
    # The lower 80 pixels remain quiet for a composited audio waveform.
    cover = Image.new("RGB", (640, 360), "#171222")
    draw = ImageDraw.Draw(cover)
    draw.text((44, 31), "FIXTURE LAB / AUDIO STUDY", font=font(12, True), fill=LIGHT_PURPLE)
    draw.text((42, 80), "Quarterly", font=font(43, True), fill=PAPER)
    draw.text((42, 132), "signals", font=font(43, True), fill=PAPER)
    draw.text((45, 202), "12 to 18 to 27 completed projects", font=font(14), fill="#C5BBCE")
    draw.text((45, 230), "Synthetic sample data", font=font(11), fill="#8F829E")
    for index, (_, count) in enumerate(METRICS):
        x = 414 + index * 55
        height = round(count / 27 * 134)
        draw.rounded_rectangle((x, 220 - height, x + 35, 220), radius=5,
                               fill=["#6C508F", LIGHT_PURPLE, PAPER][index])
    cover.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".pilot-workflow-proofs" / "inputs")
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    files = {
        "pdf": destination / "fixture_report.pdf",
        "csv": destination / "fixture_metrics.csv",
        "xlsx": destination / "fixture_metrics.xlsx",
        "audio_cover": destination / "audio_cover.png",
    }
    write_pdf(files["pdf"])
    write_csv(files["csv"])
    write_xlsx(files["xlsx"])
    write_cover(files["audio_cover"])
    manifest = {
        "synthetic": True,
        "files": {name: str(path) for name, path in files.items()},
        "metrics": [{"quarter": quarter, "completed_projects": count} for quarter, count in METRICS],
        "pdf_pages": 2,
        "pdf_page_points": [640, 360],
        "cover_pixels": [640, 360],
        "waveform_region": {"x": 44, "y": 282, "width": 552, "height": 42, "color": "#B5A0EF"},
        "xlsx_assertions": {"sheet": "Metrics", "B2": "12", "B3": "18", "B4": "27", "B5_formula": "SUM(B2:B4)", "B5_cached_value": "57"},
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
