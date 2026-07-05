from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import ScreenerRow
from ..screener import screen_all

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("", response_model=list[ScreenerRow])
def screener(db: Session = Depends(get_db)):
    """Aggressive-growth screen over watchlist + discovery tickers, ranked by
    criteria passed. Missing data reports 'unknown', never a silent verdict."""
    return screen_all(db)
