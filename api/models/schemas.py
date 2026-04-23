from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

StrategyType = Literal["zero_shot", "few_shot", "chain_of_thought", "self_critique", "all"]
SingleStrategyType = Literal["zero_shot", "few_shot", "chain_of_thought", "self_critique"]
SignalType = Literal["BUY", "HOLD", "SELL"]


class AnalyzeRequest(BaseModel):
    tickers: list[str] = ["AAPL"]
    strategy: StrategyType = "few_shot"

    @field_validator("tickers")
    @classmethod
    def uppercase_tickers(cls, v: list[str]) -> list[str]:
        return [t.strip().upper() for t in v]


class EvaluateRequest(BaseModel):
    ticker: str
    strategy: SingleStrategyType = "few_shot"
    runs: int = 3

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.strip().upper()


class StrategyResult(BaseModel):
    ticker: str
    strategy: str
    signal: str
    latency_ms: int
    format_correct: bool
    analysis: str
    timestamp: Optional[datetime] = None


class AnalyzeResponse(BaseModel):
    results: list[StrategyResult]
