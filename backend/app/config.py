from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "linerelay-videos"
    anthropic_api_key: str
    openai_api_key: str = ""
    gemini_api_key: str = ""
    clipcafe_api_url: str = "https://api.clip.cafe"
    opensubtitles_api_key: str = ""
    global_daily_limit: int = 100
    ip_daily_limit: int = 3
    freq_limit_seconds: int = 30
    deepseek_api_key: str = ""
    llm_provider: str = "deepseek-flash"  # deepseek-flash / deepseek-pro / claude
    admin_token: str = ""

    class Config:
        env_file = ".env"

settings = Settings()