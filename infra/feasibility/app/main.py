"""Isolated cloud connectivity probe. No application data or credentials."""

import os

from fastapi import FastAPI

app = FastAPI(
    title="Wonderland MOCK cloud feasibility", docs_url=None, redoc_url=None, openapi_url=None
)


@app.get("/smoke/health")
def health():
    return {
        "service": "wonderland-cloud-probe",
        "mode": "MOCK",
        "status": "ok",
        "pod": os.environ.get("HOSTNAME", "local"),
    }
