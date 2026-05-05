"""临时调试脚本:直接调 DeepSeek 看返回。
跑法:docker compose exec backend python -m app.scripts.test_deepseek
"""
from app.config import settings
from openai import OpenAI


def main():
    print(f"API key prefix: {settings.deepseek_api_key[:10]}...")

    # 测试 1: 不带 /v1
    print("\n=== Test 1: base_url WITHOUT /v1 ===")
    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
    )
    try:
        resp = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": "Say hi in one word"}],
            max_tokens=50,
        )
        print(f"  content: {resp.choices[0].message.content!r}")
        print(f"  finish_reason: {resp.choices[0].finish_reason}")
        print(f"  usage: {resp.usage}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    # 测试 2: 用 deepseek-chat (legacy alias)
    print("\n=== Test 2: model=deepseek-chat ===")
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Say hi in one word"}],
            max_tokens=50,
        )
        print(f"  content: {resp.choices[0].message.content!r}")
        print(f"  finish_reason: {resp.choices[0].finish_reason}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    # 测试 3: 列出所有可用 model
    print("\n=== Test 3: list available models ===")
    try:
        models = client.models.list()
        for m in models.data:
            print(f"  - {m.id}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
