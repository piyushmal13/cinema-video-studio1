#!/usr/bin/env python3
"""Emit concise reference direction for the storyboard model."""
from __future__ import annotations

import argparse
from scripts.reference_analyzer import reference_prompt_context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--existing", default="")
    args = parser.parse_args()
    parts = [args.existing.strip(), reference_prompt_context(args.report)]
    print("\n".join(part for part in parts if part)[:5000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
