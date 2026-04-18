#!/usr/bin/env python3
"""Web bridge for canonical baseline life expectancy and QALY projection."""

from __future__ import annotations

import json
import sys

from optiqal.web_api import build_baseline_response


def main() -> int:
    payload = json.load(sys.stdin)
    json.dump(build_baseline_response(payload), sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
