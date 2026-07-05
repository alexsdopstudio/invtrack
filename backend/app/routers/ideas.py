from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..queries import idea_rows
from ..schemas import IdeaRow

router = APIRouter(prefix="/api/ideas", tags=["ideas"])


@router.get("", response_model=list[IdeaRow])
def ideas(limit: int = 20, db: Session = Depends(get_db)):
    """Radar: tickers with recent congressional activity that are not on the
    watchlist, ranked by composite score then net congressional buying."""
    return idea_rows(db, limit=limit)
