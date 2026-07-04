from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..queries import dashboard_rows, latest_score_for
from ..schemas import DashboardRow, ScoreOut
from ..scoring import engine

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.get("", response_model=list[DashboardRow])
def scores(db: Session = Depends(get_db)):
    return dashboard_rows(db)


@router.post("/recompute", response_model=list[ScoreOut])
def recompute(db: Session = Depends(get_db)):
    stored = engine.compute_and_store(db)
    return [
        ScoreOut(
            ticker=s.ticker,
            total=s.total,
            computed_at=s.computed_at,
            components=s.components,
        )
        for s in stored
    ]


@router.get("/{ticker}", response_model=ScoreOut)
def score_breakdown(ticker: str, db: Session = Depends(get_db)):
    score = latest_score_for(db, ticker.strip().upper())
    if score is None:
        raise HTTPException(404, f"no score computed for {ticker}")
    return ScoreOut(
        ticker=score.ticker,
        total=score.total,
        computed_at=score.computed_at,
        components=score.components,
    )
