#!/usr/bin/env python3
"""Web bridge for the unified Optiqal intervention frontier."""

from __future__ import annotations

import json
import sys

from optiqal.web_api import build_frontier_response


def main() -> int:
    payload = json.load(sys.stdin)
    json.dump(build_frontier_response(payload), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
