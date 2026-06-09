from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

logger = logging.getLogger("optiqal.api")


PROJECT_ROOT = Path(__file__).resolve().parent
IMPORT_ROOTS = [
    PROJECT_ROOT,
    PROJECT_ROOT.parent / "python",
]

for import_root in IMPORT_ROOTS:
    if import_root.exists() and str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from optiqal.web_api import build_baseline_response, build_frontier_response


app = FastAPI(title="Optiqal Model API")


def _coerce_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    return payload


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/baseline")
def baseline(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return build_baseline_response(_coerce_payload(payload))
    except HTTPException:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        # Log the detail server-side; return a generic message so tracebacks
        # and internal paths never reach the client.
        logger.exception("Unhandled error in /baseline")
        raise HTTPException(status_code=500, detail="Internal server error") from error


@app.post("/frontier")
def frontier(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return build_frontier_response(_coerce_payload(payload))
    except HTTPException:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        # Log the detail server-side; return a generic message so tracebacks
        # and internal paths never reach the client.
        logger.exception("Unhandled error in /frontier")
        raise HTTPException(status_code=500, detail="Internal server error") from error
