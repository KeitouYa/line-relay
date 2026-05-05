from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.quote import QuoteResponse, QuoteWithScoreResponse
from app.services.quote_search import QuoteSearchService

router = APIRouter()

@router.get("/search", response_model=list[QuoteResponse])
def search_quotes(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    language: str = Query("en", description="语言代码"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db),
):
    """搜索台词"""
    service = QuoteSearchService(db)
    results = service.search(q, language, limit)
    return results


@router.get("/semantic-search", response_model=list[QuoteWithScoreResponse])
def semantic_search_quotes(
    q: str = Query(..., min_length=1, description="语义搜索内容"),
    language: str = Query("en", description="语言代码"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    min_length: int = Query(15, ge=0, le=200, description="台词最短字符数"),
    db: Session = Depends(get_db),
):
    """语义搜索台词(基于向量相似度,带相似度分数)"""
    service = QuoteSearchService(db)
    rows = service.semantic_search(q, language, limit, min_length=min_length)

    return [
        QuoteWithScoreResponse(
            id=quote.id,
            text=quote.text,
            movie_title=quote.movie_title,
            movie_year=quote.movie_year,
            imdb_id=quote.imdb_id,
            character_name=quote.character_name,
            start_time=quote.start_time,
            end_time=quote.end_time,
            language=quote.language,
            distance=float(distance),
            similarity=float(1 - distance),
        )
        for quote, distance in rows
    ]
