from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import PoliticianRow, TrackRecordSummary
from ..trackrecord import politician_stats, summary

router = APIRouter(prefix="/api", tags=["track-record"])


@router.get("/track-record", response_model=TrackRecordSummary)
def track_record(db: Session = Depends(get_db)):
    return summary(db)


@router.get("/politicians", response_model=list[PoliticianRow])
def politicians(db: Session = Depends(get_db)):
    return politician_stats(db)
