from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..ingestion.runner import ALL_SOURCES, run_sources
from ..models import IngestionRun
from ..schemas import IngestionRunOut
from ..scoring import engine

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/{source}", response_model=list[IngestionRunOut])
def ingest(source: str, db: Session = Depends(get_db)):
    """Run ingestion synchronously for one source (or 'all'), then recompute
    scores so the dashboard reflects the fresh data."""
    if source != "all" and source not in ALL_SOURCES:
        raise HTTPException(404, f"unknown source {source}; one of {ALL_SOURCES} or 'all'")
    sources = ALL_SOURCES if source == "all" else [source]
    runs = run_sources(db, sources)
    engine.compute_and_store(db)
    return runs


@router.get("/runs", response_model=list[IngestionRunOut])
def runs(limit: int = 50, db: Session = Depends(get_db)):
    return db.scalars(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    ).all()
