from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "Ally Backend API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development | staging | production

    # --- Database ---
    # Supabase today, AWS RDS later -- only this value changes when that happens.
    DATABASE_URL: str

    # --- Auth ---
    # "dev" = temporary local stand-in for testing, never used in production.
    # Set to "cognito" once the real Cognito provider is built.
    AUTH_PROVIDER: str = "dev"

    # --- Security ---
    SECRET_KEY: str

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- Observability ---
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
