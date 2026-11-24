from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # LLM Configuration
    llm_api_keys: str = ""  # Comma-separated keys
    llm_model: str = "groq/openai/gpt-oss-20b"

    # Database
    database_url: str = "sqlite:////data/app.db"

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Failure simulation
    enable_failure_simulation: bool = False

    # LiteLLM cache
    cache_enabled: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def api_keys_list(self) -> List[str]:
        """Parse comma-separated API keys, stripping whitespace and quotes."""
        return [k.strip(' "\'\r\n\t') for k in self.llm_api_keys.split(",") if k.strip(' "\'\r\n\t')]

    @property
    def origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
