from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alerts import mark_all_seen
from ..db import get_db
from ..models import Alert
from ..schemas import AlertOut

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(unseen_only: bool = False, limit: int = 100, db: Session = Depends(get_db)):
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if unseen_only:
        stmt = stmt.where(Alert.seen.is_(False))
    return db.scalars(stmt).all()


@router.post("/seen")
def mark_seen(db: Session = Depends(get_db)):
    return {"marked": mark_all_seen(db)}
