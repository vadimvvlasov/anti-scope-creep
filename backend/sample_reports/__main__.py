"""Render the guest samples (data/samples/*.json, issue #120) into static PDF and DOCX reports with the
backend's own report renderer, for the frontend's public assets (issue #124), and copy the sample JSON
next to them for the public sample route (issue #125).

    uv run python -m sample_reports            # from backend/: writes frontend/public/samples/

The report is what a signed-in user would export for the same analysis, exported at the recording time,
so a rerun gives the same content. The files are static: there is no public export endpoint.
"""

import argparse
import json
import sys
from pathlib import Path

from app.models import ContractDetail
from app.report import report_blocks
from app.report_docx import render_docx
from app.report_pdf import render_pdf

REPO = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO / "data" / "samples"
OUTPUT_DIR = REPO / "frontend" / "public" / "samples"


def sample_contract(path: Path) -> ContractDetail:
    """The `contract` of a sample file, validated as the API's ContractDetail."""
    return ContractDetail.model_validate(json.loads(path.read_text(encoding="utf-8"))["contract"])


def render_sample(path: Path, output_dir: Path) -> list[Path]:
    """Write <name>.json (a byte copy), <name>.pdf and <name>.docx for one sample; return their paths."""
    contract = sample_contract(path)
    assert contract.analyzed_at is not None
    blocks = report_blocks(contract, exported_at=contract.analyzed_at)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = [output_dir / path.name]
    written[0].write_bytes(path.read_bytes())
    for extension, render in (("pdf", render_pdf), ("docx", render_docx)):
        target = output_dir / f"{path.stem}.{extension}"
        target.write_bytes(render(blocks))
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--samples", type=Path, default=SAMPLES_DIR, help="folder with the sample JSON files")
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT_DIR, help="folder for the PDF and DOCX files")
    args = parser.parse_args(argv)
    samples = sorted(args.samples.glob("*.json"))
    if not samples:
        print(f"error: no sample JSON in {args.samples}", file=sys.stderr)
        return 1
    for path in samples:
        for written in render_sample(path, args.output):
            print(written.relative_to(REPO) if written.is_relative_to(REPO) else written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
