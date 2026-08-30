from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    monday_api_token: str
    gemini_api_key: str
    # Comma-separated board IDs. Any number of boards is accepted; each
    # board's kind is inferred from its own schema (app/canonical/board_kind.py),
    # so the order they're listed in carries no meaning.
    monday_board_ids: str

    monday_api_url: str = "https://api.monday.com/v2"
    monday_timeout_s: float = 15.0
    board_cache_ttl_seconds: int = 120
    gemini_model: str = "gemini-2.5-flash"
    max_tool_hops: int = 4

    @property
    def board_ids(self) -> list[str]:
        return [b.strip() for b in self.monday_board_ids.split(",") if b.strip()]


settings = Settings()
