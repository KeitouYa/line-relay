from sqlalchemy import Column, Integer, String, Float, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.database import Base
from pydantic import BaseModel

class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    movie_title: Mapped[str] = mapped_column(String(255), nullable=False)
    movie_year: Mapped[int] = mapped_column(Integer, nullable=True)
    imdb_id: Mapped[str] = mapped_column(String(20), nullable=True)
    character_name: Mapped[str] = mapped_column(String(255), nullable=True)
    start_time: Mapped[float] = mapped_column(Float, nullable=True)
    end_time: Mapped[float] = mapped_column(Float, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    embedding = mapped_column(Vector(1536), nullable=True)

    __table_args__ = (
        Index("idx_quotes_movie_title", "movie_title"),
        Index("idx_quotes_language", "language"),
    )

class QuoteResponse(BaseModel):
    id: int
    text: str
    movie_title: str
    movie_year: int | None
    imdb_id: str | None
    character_name: str | None
    start_time: float | None
    end_time: float | None
    language: str

    class Config:
        from_attributes = True

class QuoteSearchRequest(BaseModel):
    query: str
    language: str = "en"
    limit: int = 20

class QuoteWithScoreResponse(QuoteResponse):
    distance: float
    similarity: float
