"""The counter-proposal report as a PDF (A4 portrait), rendered from report.report_blocks.

DejaVu Sans is embedded so that curly quotes, dashes and non-Latin-1 characters from contracts
render correctly; the PDF core fonts only cover Latin-1. Generated in memory, never stored.
"""

import logging
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import WrapMode, XPos, YPos
from fpdf.fonts import FontFace

from app.report import REPORT_FOOTER, Block

# fontTools logs every font subsetting step at INFO; that would flood the application logs.
logging.getLogger("fontTools").setLevel(logging.WARNING)

FONT_DIR = Path(__file__).parent / "fonts"
FONT = "DejaVu"
PROTOCOL_WIDTHS = (34, 33, 33)
SUMMARY_WIDTHS = (30, 20)
# The header row is bold on grey and repeats on every page a long table spans.
HEADER_STYLE = FontFace(emphasis="BOLD", fill_color=(235, 235, 235))


class _ReportPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-18)
        self.set_font(FONT, size=7)
        self.set_text_color(110)
        for line in REPORT_FOOTER:
            self.multi_cell(0, 3.5, line, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0)


def render_pdf(blocks: list[Block]) -> bytes:
    pdf = _ReportPDF(orientation="portrait", format="A4")
    pdf.add_font(FONT, "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font(FONT, "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_title(blocks[0].text if blocks else "Counter-proposal")
    pdf.set_creator("Anti-Scope Creep")
    pdf.add_page()
    for block in blocks:
        _render(pdf, block)
    return bytes(pdf.output())


def _render(pdf: FPDF, block: Block) -> None:
    if block.kind == "title":
        pdf.set_font(FONT, "B", 16)
        pdf.multi_cell(0, 8, block.text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, wrapmode=WrapMode.WORD)
        pdf.ln(1)
    elif block.kind == "heading":
        pdf.ln(4)
        pdf.set_font(FONT, "B", 12)
        pdf.multi_cell(0, 7, block.text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)
    elif block.kind == "paragraph":
        pdf.set_font(FONT, size=10)
        pdf.multi_cell(0, 5, block.text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, wrapmode=WrapMode.WORD)
        pdf.ln(2)
    else:
        _table(pdf, block)


def _table(pdf: FPDF, block: Block) -> None:
    pdf.set_font(FONT, size=9)
    widths = PROTOCOL_WIDTHS if len(block.header) == 3 else SUMMARY_WIDTHS
    table_width = pdf.epw if len(block.header) == 3 else pdf.epw * 0.5
    with pdf.table(
        col_widths=widths, width=table_width, align="LEFT", text_align="LEFT",
        line_height=4.6, wrapmode=WrapMode.WORD, headings_style=HEADER_STYLE,
    ) as table:
        header = table.row()
        for text in block.header:
            header.cell(text)
        for values in block.rows:
            row = table.row()
            for text in values:
                row.cell(text)
    pdf.ln(2)
