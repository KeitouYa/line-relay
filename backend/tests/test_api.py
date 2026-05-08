"""集成测试 - 测试 FastAPI endpoints 在请求级别的行为。

注意: TestClient 不真正建立 SSE 长连接,所以我们只测请求路由 + 参数校验。
真正测 SSE 流要用 E2E (Playwright),MVP 阶段不做。
"""
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_response():
    """/health 必须返回 200 + 包含 status 字段。

    在 CI 环境没有真数据库/Redis,所以 status 可能是 unhealthy,
    但 endpoint 本身必须正常工作。
    """
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "unhealthy"]
    assert "checks" in data
    assert "api" in data["checks"]


def test_relay_stream_requires_seed_param():
    """缺 seed 参数应该返回 422 (FastAPI 参数校验失败的标准码)。"""
    response = client.get("/api/relay/stream")

    assert response.status_code == 422


def test_relay_stream_validates_rounds_range():
    """rounds 超出 [2, 10] 范围应该被拒绝 (Query 里设了 ge=2, le=10)。"""
    response = client.get("/api/relay/stream?seed=test&rounds=20")

    assert response.status_code == 422
