"""Phase 1d — sample failing GitHub Actions runs from the GHALogs dataset.

Source: Zenodo 10.5281/zenodo.10154920, `runs.json.gz` only (~1.06GB
compressed metadata, JSON-Lines). Per INSTRUCTIONS.md 1d, this deliberately
does NOT download `github_run_logs.zip` (142GB of raw logs) — instead it
streams runs.json.gz directly off Zenodo (never buffered fully to disk),
decompressing on the fly, and keeps only records whose `conclusion` is a
failure outcome, stopping once --limit failing runs are collected or
--max-compressed-mb of the stream has been scanned (whichever first).

Each kept record already carries a `log_insights` field (GHALogs' own
parsed per-step breakdown: actions/versions/shell commands, and an `error`
blob for steps that failed) — this is the "parsed step/error info" the
corpus needs; it does not require the raw log archive.

Output: data/raw/github_actions/ghalogs_failures_sample.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.http import new_session  # noqa: E402

URL = "https://zenodo.org/api/records/10154920/files/runs.json.gz/content"
FAILURE_CONCLUSIONS = {"failure", "timed_out"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500, help="max failing runs to collect")
    parser.add_argument("--max-compressed-mb", type=int, default=400, help="safety cap on bytes streamed")
    parser.add_argument("--out-file", default="data/raw/github_actions/ghalogs_failures_sample.jsonl")
    args = parser.parse_args()

    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    session = new_session()
    resp = session.get(URL, stream=True, timeout=60)
    resp.raise_for_status()

    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    buffer = ""
    bytes_read = 0
    lines_scanned = 0
    conclusions: dict[str, int] = {}
    kept = 0

    with out_file.open("w", encoding="utf-8") as out:
        for compressed_chunk in resp.iter_content(chunk_size=1 << 20):
            bytes_read += len(compressed_chunk)
            try:
                decompressed = decompressor.decompress(compressed_chunk)
            except zlib.error as e:
                print(f"decompression stopped: {e}", file=sys.stderr)
                break
            buffer += decompressed.decode("utf-8", errors="replace")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue
                lines_scanned += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                conclusion = (record.get("metadata") or {}).get("conclusion") or "unknown"
                conclusions[conclusion] = conclusions.get(conclusion, 0) + 1
                if conclusion in FAILURE_CONCLUSIONS:
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    kept += 1

            if lines_scanned % 20000 == 0:
                print(
                    f"  scanned={lines_scanned} kept={kept} mb_read={bytes_read / 1e6:.1f} "
                    f"conclusions={conclusions}",
                    file=sys.stderr,
                )

            if kept >= args.limit:
                print(f"Reached --limit ({args.limit} failing runs).")
                break
            if bytes_read >= args.max_compressed_mb * 1_000_000:
                print(f"Reached --max-compressed-mb ({args.max_compressed_mb}MB) safety cap.")
                break

    resp.close()
    print(f"\nScanned {lines_scanned} run records ({bytes_read / 1e6:.1f}MB compressed)")
    print(f"Conclusion breakdown: {conclusions}")
    print(f"Kept {kept} failing runs -> {out_file}")


if __name__ == "__main__":
    main()
