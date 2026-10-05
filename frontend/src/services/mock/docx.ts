// Minimal DOCX writer for the mock report: WordprocessingML parts in an uncompressed ZIP,
// with editable paragraphs, bordered tables, and a page footer. Layout fidelity is not a goal.

import type { ReportBlock } from "./report";

const W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';

const escapeXml = (s: string) =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    // Characters XML 1.0 does not allow.
    // eslint-disable-next-line no-control-regex
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, "");

/** One paragraph; line breaks inside the text become <w:br/>. Size is in half-points. */
const paragraph = (text: string, size = 20, bold = false) => {
  const props = `<w:rPr>${bold ? "<w:b/>" : ""}<w:sz w:val="${size}"/></w:rPr>`;
  const runs = text
    .split("\n")
    .map((line, i) => `${i > 0 ? "<w:br/>" : ""}<w:t xml:space="preserve">${escapeXml(line)}</w:t>`)
    .join("");
  return `<w:p><w:r>${props}${runs}</w:r></w:p>`;
};

const table = (header: string[], rows: string[][]) => {
  const border = (side: string) =>
    `<w:${side} w:val="single" w:sz="4" w:space="0" w:color="999999"/>`;
  const borders = ["top", "left", "bottom", "right", "insideH", "insideV"].map(border).join("");
  const cell = (text: string, bold: boolean) =>
    `<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>${paragraph(text, 18, bold)}</w:tc>`;
  const row = (cells: string[], bold: boolean) =>
    `<w:tr>${cells.map((c) => cell(c, bold)).join("")}</w:tr>`;
  const grid = header.map(() => "<w:gridCol/>").join("");
  return (
    `<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>${borders}</w:tblBorders></w:tblPr>` +
    `<w:tblGrid>${grid}</w:tblGrid>${row(header, true)}${rows.map((r) => row(r, false)).join("")}</w:tbl>` +
    paragraph("")
  );
};

const blockXml = (block: ReportBlock) => {
  if (block.kind === "title") return paragraph(block.text, 32, true);
  if (block.kind === "heading") return paragraph(block.text, 24, true);
  if (block.kind === "paragraph") return paragraph(block.text);
  return table(block.header, block.rows);
};

const documentXml = (blocks: ReportBlock[]) =>
  `${XML_HEAD}<w:document xmlns:w="${W_NS}" xmlns:r="${R_NS}"><w:body>` +
  blocks.map(blockXml).join("") +
  '<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/>' +
  '<w:pgSz w:w="11906" w:h="16838"/>' +
  '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/>' +
  "</w:sectPr></w:body></w:document>";

const footerXml = (footer: string[]) =>
  `${XML_HEAD}<w:ftr xmlns:w="${W_NS}">${footer.map((t) => paragraph(t, 14)).join("")}</w:ftr>`;

const PACKAGE_PARTS = {
  "[Content_Types].xml":
    `${XML_HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
    '<Default Extension="xml" ContentType="application/xml"/>' +
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>' +
    '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>' +
    "</Types>",
  "_rels/.rels":
    `${XML_HEAD}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>' +
    "</Relationships>",
  "word/_rels/document.xml.rels":
    `${XML_HEAD}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
    '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>' +
    "</Relationships>",
};

/* ------------------------------ ZIP ------------------------------ */

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

export const crc32 = (data: Uint8Array): number => {
  let crc = 0xffffffff;
  for (const byte of data) crc = CRC_TABLE[(crc ^ byte) & 0xff]! ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
};

/** ZIP header fields shared by the local and central records, after the version field(s). */
const commonFields = (
  view: DataView,
  at: number,
  crc: number,
  size: number,
  nameLength: number,
) => {
  view.setUint16(at, 0, true); // flags
  view.setUint16(at + 2, 0, true); // method: stored
  view.setUint16(at + 4, 0, true); // time
  view.setUint16(at + 6, 0x21, true); // date: 1980-01-01
  view.setUint32(at + 8, crc, true);
  view.setUint32(at + 12, size, true); // compressed size
  view.setUint32(at + 16, size, true); // uncompressed size
  view.setUint16(at + 20, nameLength, true);
};

/** An uncompressed ZIP archive of the given files. */
export const zipStored = (files: Array<[string, Uint8Array]>): Uint8Array<ArrayBuffer> => {
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;
  for (const [name, data] of files) {
    const nameBytes = encoder.encode(name);
    const crc = crc32(data);
    const local = new Uint8Array(30 + nameBytes.length);
    const lv = new DataView(local.buffer);
    lv.setUint32(0, 0x04034b50, true);
    lv.setUint16(4, 20, true);
    commonFields(lv, 6, crc, data.length, nameBytes.length);
    local.set(nameBytes, 30);
    const entry = new Uint8Array(46 + nameBytes.length);
    const cv = new DataView(entry.buffer);
    cv.setUint32(0, 0x02014b50, true);
    cv.setUint16(4, 20, true);
    cv.setUint16(6, 20, true);
    commonFields(cv, 8, crc, data.length, nameBytes.length);
    cv.setUint32(42, offset, true);
    entry.set(nameBytes, 46);
    chunks.push(local, data);
    central.push(entry);
    offset += local.length + data.length;
  }
  return concat([...chunks, ...central, endOfCentralDirectory(files.length, central, offset)]);
};

const endOfCentralDirectory = (count: number, central: Uint8Array[], offset: number) => {
  const end = new Uint8Array(22);
  const view = new DataView(end.buffer);
  view.setUint32(0, 0x06054b50, true);
  view.setUint16(8, count, true);
  view.setUint16(10, count, true);
  view.setUint32(
    12,
    central.reduce((n, c) => n + c.length, 0),
    true,
  );
  view.setUint32(16, offset, true);
  return end;
};

const concat = (parts: Uint8Array[]) => {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const part of parts) {
    out.set(part, at);
    at += part.length;
  }
  return out;
};

/** Renders the report as a DOCX. */
export const renderDocx = (blocks: ReportBlock[], footer: string[]): Blob => {
  const encoder = new TextEncoder();
  const parts: Record<string, string> = {
    ...PACKAGE_PARTS,
    "word/document.xml": documentXml(blocks),
    "word/footer1.xml": footerXml(footer),
  };
  const zip = zipStored(Object.entries(parts).map(([name, xml]) => [name, encoder.encode(xml)]));
  return new Blob([zip], {
    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  });
};
