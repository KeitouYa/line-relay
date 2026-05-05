# Line Relay - AI台词接龙视频生成器

输入一句电影台词，AI自动生成搞笑台词接龙视频。

## 快速启动

```bash
# 1. 复制环境变量
cp .env.example .env
# 编辑 .env，填入你的 API keys

# 2. 启动所有服务
docker compose up --build

# 3. 访问
# 前端: http://localhost:3000
# 后端API文档: http://localhost:8000/docs
# 健康检查: http://localhost:8000/health
# MinIO管理界面: http://localhost:9001
```

## 技术栈

- **前端**: Next.js 15 + React 19 + shadcn/ui + Tailwind CSS
- **后端**: Python + FastAPI
- **任务队列**: Celery + Redis
- **数据库**: PostgreSQL + Pgvector
- **缓存**: Redis
- **LLM**: Claude API (LangChain)
- **Embedding**: OpenAI Embedding API
- **视频处理**: FFmpeg
- **对象存储**: MinIO (开发) / AWS S3 (生产)
- **容器化**: Docker Compose
