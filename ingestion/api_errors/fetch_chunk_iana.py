"""Phase 1e — pull + chunk the IANA HTTP Status Code Registry (authoritative,
machine-readable CSV, public registry).

One chunk per assigned status code (skips "Unassigned"/reserved ranges).

Output: data/processed/api_errors/iana_status_chunks.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402
from common.http import new_session  # noqa: E402

URL = "https://www.iana.org/assignments/http-status-codes/http-status-codes-1.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-file", default="data/raw/api_errors/iana_status_codes.csv")
    parser.add_argument("--out-file", default="data/processed/api_errors/iana_status_chunks.jsonl")
    args = parser.parse_args()

    raw_path = Path(args.raw_file)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    session = new_session()
    resp = session.get(URL, timeout=20)
    resp.raise_for_status()
    raw_path.write_text(resp.text, encoding="utf-8")

    reader = csv.DictReader(StringIO(resp.text))
    total = 0
    with out_file.open("w", encoding="utf-8") as out:
        for row in reader:
            value = row["Value"].strip()
            desc = row["Description"].strip()
            if "-" in value or desc.lower() in ("unassigned", ""):
                continue  # unassigned ranges, not real status codes
            reference = row.get("Reference", "").strip()
            text = f"HTTP status code {value}: {desc}\nIANA reference: {reference}"
            out.write(
                json.dumps(
                    {
                        "id": stable_chunk_id("iana-status", value),
                        "text": text,
                        "metadata": {
                            "domain": "api_errors",
                            "artifact_type": "http_status_registry",
                            "status_code": value,
                            "description": desc,
                            "source_url": "https://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml",
                            "source": "iana_registry",
                            "license": "public registry (authoritative reference, no additional license terms)",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            total += 1

    print(f"Chunked {total} assigned status codes -> {out_file}")


if __name__ == "__main__":
    main()
