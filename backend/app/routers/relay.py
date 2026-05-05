import asyncio
import json
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.relay_engine import RelayEngine
from app.middleware.rate_limit import check_rate_limits

router = APIRouter()


@router.get("/stream")
async def relay_stream(
    request: Request,
    seed: str = Query(..., min_length=1, description="起始台词"),
    rounds: int = Query(5, ge=2, le=10, description="接龙轮数"),
    db: Session = Depends(get_db),
):
    """
    SSE 流式接龙端点。

    每接出一句立即推送一个 SSE event。
    """

    # 限流检查（超限直接抛 429，不进入 SSE 流）
    # 前端 fetch probe 会带 X-Relay-Probe header，此时只读检查不消耗配额
    is_probe = request.headers.get("X-Relay-Probe") == "1"
    check_rate_limits(request, consume=not is_probe)

    # 如果是探测请求，直接返回 204，不建立 SSE
    if is_probe:
        from fastapi.responses import Response
        return Response(status_code=204)

    async def event_generator():
        engine = RelayEngine(db)

        # 找起始台词
        seed_quote = engine.find_seed_quote(seed)
        if seed_quote is None:
            yield f"event: error\ndata: {json.dumps({'message': 'No matching quote found'})}\n\n"
            return

        # 推送起始台词作为 round 0
        seed_payload = {
            "round": 0,
            "quote_id": seed_quote.id,
            "text": seed_quote.text,
            "movie_title": seed_quote.movie_title,
            "movie_year": seed_quote.movie_year,
            "start_time": seed_quote.start_time,
            "end_time": seed_quote.end_time,
        }
        yield f"event: seed\ndata: {json.dumps(seed_payload)}\n\n"

        # 接龙循环
        current = seed_quote
        used_ids = [seed_quote.id]
        used_movies = [seed_quote.movie_title]
        chain = [seed_quote]

        for round_num in range(1, rounds + 1):
            # 客户端断线检测
            if await request.is_disconnected():
                break

            result = engine.step(current, used_ids, used_movies)

            if result is None:
                yield f"event: error\ndata: {json.dumps({'message': f'No candidates left at round {round_num}'})}\n\n"
                break

            next_quote = result["quote"]
            payload = {
                "round": round_num,
                "quote_id": next_quote.id,
                "text": next_quote.text,
                "movie_title": next_quote.movie_title,
                "movie_year": next_quote.movie_year,
                "start_time": next_quote.start_time,
                "end_time": next_quote.end_time,
                "mode": result["mode"],
                "reason": result["reason"],
            }
            yield f"event: round\ndata: {json.dumps(payload)}\n\n"

            # 让出控制权,让 SSE 真的能 flush
            await asyncio.sleep(0)

            current = next_quote
            used_ids.append(next_quote.id)
            used_movies.append(next_quote.movie_title)
            chain.append(next_quote)

        # 推送完成事件
        done_payload = {
            "total_rounds": len(chain) - 1,
            "chain": [
                {
                    "quote_id": q.id,
                    "text": q.text,
                    "movie_title": q.movie_title,
                    "start_time": q.start_time,
                    "end_time": q.end_time,
                }
                for q in chain
            ],
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )
