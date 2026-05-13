from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    status: str
    request_id: str | None = Field(None, alias="request_id")


class CurrencyConversion(BaseResponse):
    from_currency: str = Field(..., alias="from")
    to_currency: str = Field(..., alias="to")
    initial_amount: float
    converted: float
    last: dict[str, Any] | None = None


class LastQuote(BaseResponse):
    symbol: str | None = None
    last: dict[str, Any] | None = None


class ForexAggregate(BaseModel):
    v: float = Field(..., description="Volume")
    vw: float | None = Field(None, description="Volume weighted average price")
    o: float = Field(..., description="Open")
    c: float = Field(..., description="Close")
    h: float = Field(..., description="High")
    l: float = Field(..., description="Low")
    t: int = Field(..., description="Timestamp")
    n: int | None = Field(None, description="Number of transactions")


class ForexAggregatesResponse(BaseResponse):
    ticker: str
    queryCount: int | None = None
    resultsCount: int | None = None
    adjusted: bool | None = None
    results: list[ForexAggregate] = []


class Snapshot(BaseModel):
    ticker: str
    todaysChange: float | None = None
    todaysChangePerc: float | None = None
    updated: int | None = None
    day: dict[str, Any] | None = None
    lastQuote: dict[str, Any] | None = None
    min: dict[str, Any] | None = None
    prevDay: dict[str, Any] | None = None


class ForexSnapshotResponse(BaseResponse):
    ticker: Snapshot | None = None


class ForexMarketSnapshotResponse(BaseResponse):
    tickers: list[Snapshot] = []


class TickerDetails(BaseResponse):
    results: dict[str, Any] | None = None


class TickerList(BaseResponse):
    results: list[dict[str, Any]] = []
    next_url: str | None = None
