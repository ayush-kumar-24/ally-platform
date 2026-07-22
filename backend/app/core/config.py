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
    # "dev"      = temporary local stand-in for testing, never used in production.
    # "supabase" = verify the JWT the frontend gets from Supabase Auth.
    AUTH_PROVIDER: str = "dev"

    # Only needed when AUTH_PROVIDER="supabase".
    # Supabase dashboard -> Project Settings -> API -> JWT Settings -> JWT Secret.
    SUPABASE_JWT_SECRET: str = ""

    # --- Security ---
    # Signs the session tokens THIS backend issues (see below). Keep it secret.
    SECRET_KEY: str

    # --- Session tokens (minted by this backend, not by the identity provider) ---
    # The upstream IdP (Supabase Google/LinkedIn today, Cognito on AWS later) only
    # proves who the user is, once, at /auth/session. From there the backend issues
    # its own access + refresh JWTs, so the rest of the API never depends on the
    # provider's token format. Moving to AWS changes only that one verification step.
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Provisioning ---
    # OFF by default: first login does NOT write a founder row while this is false,
    # so no rows are created in the database without an explicit opt-in. Turning it
    # on also requires the create_founder_on_signup / consents bugs to be fixed.
    ENABLE_FOUNDER_PROVISIONING: bool = False

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
