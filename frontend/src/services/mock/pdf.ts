// Minimal PDF writer for the mock report: A4 pages, Helvetica, word-wrapped text, and simple
// tables drawn as wrapped columns with rules between rows. Layout fidelity is not a goal.

import type { ReportBlock } from "./report";

const PAGE_W = 595;
const PAGE_H = 842;
const MARGIN = 50;
const FOOTER_TOP = 70; // body text stays above this line
const BODY_W = PAGE_W - 2 * MARGIN;

type Op = string; // one PDF content-stream instruction

/** Helvetica in the PDF uses WinAnsi; map common typography to ASCII, drop the rest. */
const toPdfText = (s: string) =>
  s
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[–—]/g, "-")
    .replace(/…/g, "...")
    .replace(/[^\x20-\x7e\xa0-\xff]/g, "?")
    .replace(/([\\()])/g, "\\$1");

/** Word-wraps text (keeping its line breaks) to lines of at most `width` points. */
export const wrapText = (text: string, width: number, size: number): string[] => {
  const maxChars = Math.max(8, Math.floor(width / (size * 0.52)));
  const lines: string[] = [];
  for (const paragraph of text.split("\n")) {
    let line = "";
    for (const word of paragraph.split(" ")) {
      const next = line ? `${line} ${word}` : word;
      if (next.length <= maxChars) {
        line = next;
        continue;
      }
      if (line) lines.push(line);
      // A word longer than a line is split, never cut.
      let rest = word;
      while (rest.length > maxChars) {
        lines.push(rest.slice(0, maxChars));
        rest = rest.slice(maxChars);
      }
      line = rest;
    }
    lines.push(line);
  }
  return lines;
};

class PdfLayout {
  pages: Op[][] = [[]];
  private y = PAGE_H - MARGIN;

  /** Reserves vertical space, starting a new page when it does not fit. */
  space(height: number) {
    if (this.y - height < FOOTER_TOP) {
      this.pages.push([]);
      this.y = PAGE_H - MARGIN;
    }
    this.y -= height;
  }

  text(x: number, size: number, bold: boolean, s: string) {
    const font = bold ? "F2" : "F1";
    this.page().push(`BT /${font} ${size} Tf ${x} ${this.y} Td (${toPdfText(s)}) Tj ET`);
  }

  rule() {
    this.space(4);
    this.page().push(`${MARGIN} ${this.y} m ${PAGE_W - MARGIN} ${this.y} l S`);
  }

  private page() {
    return this.pages[this.pages.length - 1]!;
  }
}

const drawLines = (layout: PdfLayout, text: string, size: number, bold: boolean) => {
  for (const line of wrapText(text, BODY_W, size)) {
    layout.space(size * 1.35);
    layout.text(MARGIN, size, bold, line);
  }
};

const drawRow = (layout: PdfLayout, cells: string[], bold: boolean) => {
  const colW = BODY_W / cells.length;
  const columns = cells.map((cell) => wrapText(cell, colW - 8, 9));
  const height = Math.max(...columns.map((c) => c.length));
  for (let i = 0; i < height; i++) {
    layout.space(12);
    columns.forEach((lines, col) => {
      const line = lines[i];
      if (line) layout.text(MARGIN + col * colW, 9, bold, line);
    });
  }
  layout.rule();
};

const drawBlock = (layout: PdfLayout, block: ReportBlock) => {
  if (block.kind === "title") drawLines(layout, block.text, 16, true);
  else if (block.kind === "heading") {
    layout.space(8);
    drawLines(layout, block.text, 12, true);
  } else if (block.kind === "paragraph") drawLines(layout, block.text, 10, false);
  else {
    layout.rule();
    drawRow(layout, block.header, true);
    block.rows.forEach((row) => drawRow(layout, row, false));
  }
  layout.space(6);
};

const footerOps = (footer: string[]): Op[] => {
  let y = FOOTER_TOP - 20;
  return footer.flatMap((text) =>
    wrapText(text, BODY_W, 7).map((line) => {
      const op = `BT /F1 7 Tf ${MARGIN} ${y} Td (${toPdfText(line)}) Tj ET`;
      y -= 9;
      return op;
    }),
  );
};

/** Serializes pages into PDF objects with a cross-reference table. */
const serialize = (pages: Op[][], footer: Op[]): string => {
  const objects: string[] = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "", // pages tree, filled once the page object numbers are known
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
  ];
  const kids: string[] = [];
  for (const ops of pages) {
    const stream = [...ops, ...footer].join("\n");
    objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
    const contentRef = objects.length;
    objects.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_W} ${PAGE_H}] ` +
        `/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${contentRef} 0 R >>`,
    );
    kids.push(`${objects.length} 0 R`);
  }
  objects[1] = `<< /Type /Pages /Kids [${kids.join(" ")}] /Count ${kids.length} >>`;

  let out = "%PDF-1.4\n";
  const offsets = objects.map((body, i) => {
    const offset = out.length;
    out += `${i + 1} 0 obj\n${body}\nendobj\n`;
    return offset;
  });
  const xref = out.length;
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  out += offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return out;
};

/** Renders the report as a PDF. Every character is single-byte, so string offsets are bytes. */
export const renderPdf = (blocks: ReportBlock[], footer: string[]): Blob => {
  const layout = new PdfLayout();
  blocks.forEach((block) => drawBlock(layout, block));
  const pdf = serialize(layout.pages, footerOps(footer));
  const bytes = new Uint8Array(pdf.length);
  for (let i = 0; i < pdf.length; i++) bytes[i] = pdf.charCodeAt(i);
  return new Blob([bytes], { type: "application/pdf" });
};
