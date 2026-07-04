from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DimTicker, WatchlistItem
from ..schemas import WatchlistCreate, WatchlistItemOut, WatchlistUpdate

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(db: Session = Depends(get_db)):
    return db.scalars(select(WatchlistItem).order_by(WatchlistItem.ticker)).all()


@router.post("", response_model=WatchlistItemOut, status_code=201)
def add_to_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db)):
    ticker = payload.ticker.strip().upper()
    existing = db.scalar(select(WatchlistItem).where(WatchlistItem.ticker == ticker))
    if existing is not None:
        raise HTTPException(409, f"{ticker} is already on the watchlist")
    # Create a bare dim_ticker row if the SEC ticker map hasn't been ingested
    # yet; name/CIK are filled in by the next tickers ingestion run.
    if db.get(DimTicker, ticker) is None:
        db.add(DimTicker(ticker=ticker))
    item = WatchlistItem(ticker=ticker, notes=payload.notes)
    db.add(item)
    db.commit()
    return item


@router.patch("/{ticker}", response_model=WatchlistItemOut)
def update_watchlist_item(ticker: str, payload: WatchlistUpdate, db: Session = Depends(get_db)):
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.ticker == ticker.upper()))
    if item is None:
        raise HTTPException(404, f"{ticker} is not on the watchlist")
    item.notes = payload.notes
    db.commit()
    return item


@router.delete("/{ticker}", status_code=204)
def remove_from_watchlist(ticker: str, db: Session = Depends(get_db)):
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.ticker == ticker.upper()))
    if item is None:
        raise HTTPException(404, f"{ticker} is not on the watchlist")
    db.delete(item)
    db.commit()
