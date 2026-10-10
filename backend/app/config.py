"""Application configuration loaded from environment / .env.

Secrets are NEVER hard-coded. See `.env.example` at the repo root.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database. Defaults to a local SQLite file so the app runs with zero setup
    # in development. For production/demo, set DATABASE_URL to a PostgreSQL URL,
    # e.g. postgresql+psycopg2://user:pass@localhost:5432/textile
    database_url: str = "sqlite:///./textile.db"

    # Dify AI assistant (used server-side only — the browser never calls Dify).
    dify_api_key: str = ""
    dify_base_url: str = ""

    # Auth / JWT. Override JWT_SECRET in .env for any real deployment.
    jwt_secret: str = "dev-insecure-change-me"
    jwt_expire_minutes: int = 720  # 12h, convenient for a hackathon demo

    # Yarn estimation: kg of yarn needed per metre of fabric. Used by the
    # "Check yarn" feature to convert an order (metres) into a yarn requirement
    # (kg). A simple, configurable factor — refine per fabric later if needed.
    yarn_kg_per_meter: float = 0.2

    # Low-stock threshold fallback (kg) used when a yarn row has no reorder level.
    default_reorder_level_kg: float = 100.0

    # Invoice tax rate (fraction) applied to the dispatch subtotal. Demo GST 5%.
    invoice_tax_rate: float = 0.05

    # CORS: comma-separated list of allowed frontend origins.
    cors_origins: str = "http://localhost:5173"

    app_name: str = "Everest Textile Mills API"
    app_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        # Load the repo-root .env (one level above backend/).
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
