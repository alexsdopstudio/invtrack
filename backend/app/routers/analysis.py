from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..analysis import report as analysis
from ..db import get_db
from ..schemas import AiReportOut

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/{ticker}", response_model=AiReportOut)
def get_report(ticker: str, db: Session = Depends(get_db)):
    result = analysis.latest_report(db, ticker.strip().upper())
    if result is None:
        raise HTTPException(404, f"no AI report for {ticker} yet")
    return result


@router.post("/{ticker}", response_model=AiReportOut)
def run_analysis(ticker: str, force: bool = False, db: Session = Depends(get_db)):
    """Analyze the ticker's latest 10-K with Claude (opt-in; requires
    ANTHROPIC_API_KEY). Cached per filing — re-runs are free unless a newer
    10-K exists or force=true."""
    try:
        return analysis.analyze(db, ticker.strip().upper(), force=force)
    except analysis.AnalysisError as exc:
        raise HTTPException(400, str(exc)) from exc
