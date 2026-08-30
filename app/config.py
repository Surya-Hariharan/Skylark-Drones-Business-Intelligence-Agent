from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    monday_api_token: str
    deals_board_id: str
    work_orders_board_id: str
    gemini_api_key: str

    monday_api_url: str = "https://api.monday.com/v2"
    monday_timeout_s: float = 15.0
    board_cache_ttl_seconds: int = 120
    gemini_model: str = "gemini-2.5-flash"
    max_tool_hops: int = 4
    # Comma-separated allowed origins for the separately-deployed Next.js
    # frontend (no cookies/credentials are used, so this only needs to allow
    # the browser to read the response, not restrict who can send a token).
    frontend_origins: str = "*"


settings = Settings()
