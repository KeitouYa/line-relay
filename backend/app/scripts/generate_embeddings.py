"""
用法: python -m app.scripts.generate_embeddings

为数据库中所有台词生成embedding向量。
34,908条台词，约需3-5分钟，费用约$0.007。
"""
from sqlalchemy import func
from app.database import SessionLocal, engine
from app.models.quote import Quote
from app.services.embedding import get_embeddings_batch

BATCH_SIZE = 100


def main():
    db = SessionLocal()

    # 统计需要处理的台词数
    total = db.query(func.count(Quote.id)).filter(Quote.embedding.is_(None)).scalar()
    print(f"Total quotes without embedding: {total}")

    if total == 0:
        print("All quotes already have embeddings!")
        db.close()
        return

    processed = 0
    while True:
        # 取一批没有embedding的台词
        quotes = (
            db.query(Quote)
            .filter(Quote.embedding.is_(None))
            .limit(BATCH_SIZE)
            .all()
        )

        if not quotes:
            break

        texts = [q.text for q in quotes]
        embeddings = get_embeddings_batch(texts, batch_size=BATCH_SIZE)

        for quote, emb in zip(quotes, embeddings):
            quote.embedding = emb

        db.commit()
        processed += len(quotes)
        print(f"  Processed {processed}/{total} ({processed * 100 // total}%)")

    print(f"\nDone! Generated embeddings for {processed} quotes.")
    db.close()


if __name__ == "__main__":
    main()