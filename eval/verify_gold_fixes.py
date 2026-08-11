"""Validates every hand-curated fix_generation gold answer against the
real validators before the eval set is trusted. A gold snippet that fails
its own validator would silently corrupt the parse-pass-rate metric and
the eval set's credibility — this must be run (and pass) whenever
curated_fix_generation.py changes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.fix_agent import _validate  # noqa: E402
from curated_fix_generation import FIX_GENERATION_ITEMS  # noqa: E402


def main() -> None:
    failures = 0
    for item in FIX_GENERATION_ITEMS:
        is_valid, errors = _validate(item["domain"], item["gold_fix"])
        status = "OK" if is_valid else "FAIL"
        print(f"[{status}] {item['domain']}: {item['query'][:70]}")
        if not is_valid:
            failures += 1
            for e in errors:
                print(f"    {e}")

    print(f"\n{len(FIX_GENERATION_ITEMS) - failures}/{len(FIX_GENERATION_ITEMS)} gold fixes pass their validator")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
