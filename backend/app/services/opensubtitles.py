import httpx
from app.config import settings

OPENSUBTITLES_BASE = "https://api.opensubtitles.com/api/v1"

class OpenSubtitlesClient:
    def __init__(self):
        self.headers = {
            "Api-Key": settings.opensubtitles_api_key,
            "Content-Type": "application/json",
            "User-Agent": "LineRelay v0.1",
        }

    async def search_subtitles(
        self, query: str, language: str = "en", limit: int = 10
    ) -> list[dict]:
        """搜索字幕文件，返回字幕元数据列表"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OPENSUBTITLES_BASE}/subtitles",
                headers=self.headers,
                params={
                    "query": query,
                    "languages": language,
                    "order_by": "download_count",
                    "order_direction": "desc",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])[:limit]

    async def download_subtitle(self, file_id: int) -> str:
        """下载字幕文件内容（SRT格式）"""
        async with httpx.AsyncClient() as client:
            # Step 1: 获取下载链接
            response = await client.post(
                f"{OPENSUBTITLES_BASE}/download",
                headers=self.headers,
                json={"file_id": file_id},
                timeout=10.0,
            )
            response.raise_for_status()
            download_url = response.json().get("link")

            # Step 2: 下载SRT文件
            srt_response = await client.get(download_url, timeout=15.0)
            srt_response.raise_for_status()
            return srt_response.text

    async def search_by_imdb(self, imdb_id: str, language: str = "en") -> list[dict]:
        """按IMDB ID搜索字幕"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OPENSUBTITLES_BASE}/subtitles",
                headers=self.headers,
                params={
                    "imdb_id": imdb_id.replace("tt", ""),
                    "languages": language,
                    "order_by": "download_count",
                    "order_direction": "desc",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])