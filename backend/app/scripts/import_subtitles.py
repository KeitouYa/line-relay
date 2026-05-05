"""
用法: python -m app.scripts.import_subtitles

批量下载热门电影字幕并导入数据库。
MVP阶段先导入20部热门电影，约5000-10000条台词。
"""
import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.quote import Quote
from app.services.opensubtitles import OpenSubtitlesClient
from app.services.subtitle_parser import parse_srt, merge_short_quotes

# MVP种子数据：20部经典电影的IMDB ID
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


async def import_movie(client: OpenSubtitlesClient, db: Session, movie: dict):
    """导入单部电影的字幕"""
    print(f"Importing: {movie['title']} ({movie['year']})")

    # 去重检查
    existing = db.query(Quote).filter(Quote.imdb_id == movie["imdb_id"]).count()
    if existing > 0:
        print(f"  Already imported {movie['title']}, skipping ({existing} quotes)")
        return 0

    # 搜索该电影的英文字幕
    subtitles = await client.search_by_imdb(movie["imdb_id"], language="en")
    if not subtitles:
        print(f"  No subtitles found for {movie['title']}")
        return 0

    # 取下载量最高的字幕
    best_sub = subtitles[0]
    file_id = best_sub["attributes"]["files"][0]["file_id"]

    # 下载SRT
    try:
        srt_content = await client.download_subtitle(file_id)
    except Exception as e:
        print(f"  Download failed: {e}")
        return 0

    # 解析SRT
    quotes = parse_srt(srt_content)
    quotes = merge_short_quotes(quotes)

    # 写入数据库
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
    print(f"  Imported {count} quotes")
    return count


async def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    client = OpenSubtitlesClient()
    total = 0

    for movie in SEED_MOVIES:
        count = await import_movie(client, db, movie)
        total += count
        await asyncio.sleep(1)  # 避免触发API限流

    print(f"\nDone! Total quotes imported: {total}")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())