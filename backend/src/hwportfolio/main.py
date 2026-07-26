"""FastAPI application entry point.

Run: uvicorn hwportfolio.main:app --reload   (or `hwp serve`)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import storage
from .api import batches, org, review, shares, students, timeline
from .db import init_db
from .pipeline import runner  # noqa: F401  (registers the process_batch job handler)
from .skills_loader import seed_skills


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_skills()
    yield


app = FastAPI(title="hwportfolio", version="0.1.0a0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(org.router)
app.include_router(students.router)
app.include_router(batches.router)
app.include_router(review.router)
app.include_router(timeline.router)
app.include_router(shares.router)


@app.get("/media/{name}")
def media(name: str):
    """Serve stored artifact images (local storage backend only)."""
    try:
        path = storage.resolve(f"local://{name}")
    except ValueError:
        raise HTTPException(404, "Not found")
    if "/" in name or "\\" in name or ".." in name or not path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(path)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/usage")
def usage():
    """Today's estimated Gemini spend against the daily budget cap."""
    from .transcribe.costs import today_usage

    return today_usage()
