from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///results.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class AnalysisRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str
    strategy: str
    signal: str
    latency_ms: int
    format_correct: bool
    analysis: str
    timestamp: datetime = Field(default_factory=datetime.now)
    # Token tracking
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    # Hallucination detection
    hallucination_detected: bool = Field(default=False)
    flagged_terms: str = Field(default="")
    # Consistency scorer (populated via POST /api/evaluate)
    consistency_pct: Optional[float] = Field(default=None)
    is_consistent: Optional[bool] = Field(default=None)


def create_db() -> None:
    SQLModel.metadata.create_all(engine)


def save_result(
    ticker: str,
    strategy: str,
    signal: str,
    latency_ms: int,
    format_correct: bool,
    analysis: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    hallucination_detected: bool = False,
    flagged_terms: str = "",
    consistency_pct: Optional[float] = None,
    is_consistent: Optional[bool] = None,
) -> None:
    with Session(engine) as session:
        record = AnalysisRecord(
            ticker=ticker,
            strategy=strategy,
            signal=signal,
            latency_ms=latency_ms,
            format_correct=format_correct,
            analysis=analysis,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            hallucination_detected=hallucination_detected,
            flagged_terms=flagged_terms,
            consistency_pct=consistency_pct,
            is_consistent=is_consistent,
        )
        session.add(record)
        session.commit()


def get_all_results(ticker: Optional[str] = None) -> list[AnalysisRecord]:
    with Session(engine) as session:
        stmt = select(AnalysisRecord)
        if ticker:
            stmt = stmt.where(AnalysisRecord.ticker == ticker)
        return session.exec(stmt).all()


def get_results_by_ticker(ticker: str) -> list[AnalysisRecord]:
    return get_all_results(ticker=ticker)
