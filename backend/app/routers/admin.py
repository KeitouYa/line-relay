import asyncio
from fastapi import APIRouter, Header, HTTPException
from redis import Redis
from sqlalchemy import text
from app.database import engine, Base, SessionLocal
from app.config import settings
from app.models.quote import Quote
from app.services.opensubtitles import OpenSubtitlesClient
from app.services.subtitle_parser import parse_srt, merge_short_quotes
from app.services.embedding import get_embeddings_batch

router = APIRouter()

SEED_MOVIES = [
    {"imdb_id": "tt0111161", "title": "The Shawshank Redemption", "year": 1994},
    {"imdb_id": "tt0068646", "title": "The Godfather", "year": 1972},
    {"imdb_id": "tt0468569", "title": "The Dark Knight", "year": 2008},
    {"imdb_id": "tt0071562", "title": "The Godfather Part II", "year": 1974},
    {"imdb_id": "tt0050083", "title": "12 Angry Men", "year": 1957},
    {"imdb_id": "tt0108052", "title": "Schindler's List", "year": 1993},
    {"imdb_id": "tt0167260", "title": "The Lord of the Rings: The Return of the King", "year": 2003},
    {"imdb_id": "tt0110912", "title": "Pulp Fiction", "year": 1994},
    {"imdb_id": "tt0120737", "title": "The Lord of the Rings: The Fellowship of the Ring", "year": 2001},
    {"imdb_id": "tt0109830", "title": "Forrest Gump", "year": 1994},
    {"imdb_id": "tt0137523", "title": "Fight Club", "year": 1999},
    {"imdb_id": "tt0133093", "title": "The Matrix", "year": 1999},
    {"imdb_id": "tt0099685", "title": "Goodfellas", "year": 1990},
    {"imdb_id": "tt0073486", "title": "One Flew Over the Cuckoo's Nest", "year": 1975},
    {"imdb_id": "tt0114369", "title": "Se7en", "year": 1995},
    {"imdb_id": "tt0102926", "title": "The Silence of the Lambs", "year": 1991},
    {"imdb_id": "tt0038650", "title": "It's a Wonderful Life", "year": 1946},
    {"imdb_id": "tt0120815", "title": "Saving Private Ryan", "year": 1998},
    {"imdb_id": "tt0816692", "title": "Interstellar", "year": 2014},
    {"imdb_id": "tt0245429", "title": "Spirited Away", "year": 2001},
]


@router.post("/reset-limits")
def reset_limits(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    """清空所有限流计数器 (Redis keys: global_relay_count / ip_relay_count / ip_freq)"""
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    r = Redis.from_url(settings.redis_url)
    deleted = 0
    for prefix in ("global_relay_count", "ip_relay_count", "ip_freq"):
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match=f"{prefix}:*", count=100)
            if keys:
                deleted += r.delete(*keys)
            if cursor == 0:
                break

    return {"status": "ok", "deleted_keys": deleted}


@router.post("/setup-db")
def setup_db(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    """一键安装 pgvector 扩展 + 建表（手动调一次，永久生效）"""
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.create_all(bind=engine)

    return {"status": "ok", "message": "pgvector extension + tables ready"}


@router.post("/import-data")
async def import_data(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    """一键导入20部电影字幕 + 生成embedding（约需3-5分钟，超时等待）"""
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    db = SessionLocal()
    client = OpenSubtitlesClient()
    total_imported = 0
    import_log = []

    # Step 1: 导入字幕
    for movie in SEED_MOVIES:
        existing = db.query(Quote).filter(Quote.imdb_id == movie["imdb_id"]).count()
        if existing > 0:
            import_log.append(f"SKIP {movie['title']} (already {existing} quotes)")
            continue

        subtitles = await client.search_by_imdb(movie["imdb_id"], language="en")
        if not subtitles:
            import_log.append(f"FAIL {movie['title']} (no subtitles)")
            continue

        best_sub = subtitles[0]
        file_id = best_sub["attributes"]["files"][0]["file_id"]
        try:
            srt_content = await client.download_subtitle(file_id)
        except Exception as e:
            import_log.append(f"FAIL {movie['title']} (download: {e})")
            continue

        quotes = parse_srt(srt_content)
        quotes = merge_short_quotes(quotes)
        count = 0
        for q in quotes:
            if len(q["text"]) < 5 or len(q["text"]) > 500:
                continue
            db_quote = Quote(
                text=q["text"],
                movie_title=movie["title"],
                movie_year=movie["year"],
                imdb_id=movie["imdb_id"],
                start_time=q["start_time"],
                end_time=q["end_time"],
                language="en",
            )
            db.add(db_quote)
            count += 1
        db.commit()
        total_imported += count
        import_log.append(f"OK {movie['title']} ({count} quotes)")
        await asyncio.sleep(0.5)

    # Step 2: 生成embedding
    batch_size = 100
    embed_count = 0
    while True:
        quotes = db.query(Quote).filter(Quote.embedding.is_(None)).limit(batch_size).all()
        if not quotes:
            break
        texts = [q.text for q in quotes]
        embeddings = get_embeddings_batch(texts, batch_size=batch_size)
        for quote, emb in zip(quotes, embeddings):
            quote.embedding = emb
        db.commit()
        embed_count += len(quotes)

    db.close()

    return {
        "status": "ok",
        "quotes_imported": total_imported,
        "embeddings_generated": embed_count,
        "import_log": import_log,
    }