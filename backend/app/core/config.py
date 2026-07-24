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
    # ON: first real (Supabase) login creates the founder row via
    # create_founder_on_signup. Dev-mode identities are never provisioned (they
    # have no auth.users row for the FK), so dev stays read-only.
    ENABLE_FOUNDER_PROVISIONING: bool = True

    # Consent versions stamped onto the founder + consent records at provisioning.
    # Bump these when the policy/terms text changes.
    PRIVACY_POLICY_VERSION: str = "v1"
    TERMS_VERSION: str = "v1"

    # --- Discovery calls / Google Calendar ---
    # Both must be set for real scheduling; until then calendar.py runs in stub
    # mode (deterministic slots + placeholder meeting links) so dev/tests work.
    #   GOOGLE_CALENDAR_ID:               the host calendar shared with the service account
    # Provide the service-account key ONE of two ways (file is easier -- the key
    # is multi-line JSON, which .env cannot hold inline):
    #   GOOGLE_CALENDAR_CREDENTIALS_FILE: path to the downloaded key .json  (recommended)
    #   GOOGLE_CALENDAR_CREDENTIALS_JSON: the key JSON minified onto one line
    GOOGLE_CALENDAR_ID: str = ""
    GOOGLE_CALENDAR_CREDENTIALS_FILE: str = ""
    GOOGLE_CALENDAR_CREDENTIALS_JSON: str = ""
    DISCOVERY_CALL_DURATION_MINUTES: int = 45
    DISCOVERY_TIMEZONE: str = "Asia/Kolkata"
    # Personal Gmail calendars can't invite attendees via a service account
    # ("forbiddenForServiceAccounts"); only turn this on with a Google Workspace
    # calendar + domain-wide delegation. When off, the booking is created without
    # attendees and the app delivers the meeting link to the founder itself.
    GOOGLE_CALENDAR_INVITE_ATTENDEES: bool = False
    # Auto-generating a Google Meet link also needs Workspace -- personal Gmail
    # rejects it ("Invalid conference type value"). When off, the booking is a
    # plain event and the meeting link comes from GOXL_MEETING_URL.
    GOOGLE_CALENDAR_CREATE_MEET: bool = False
    # A permanent video-room link (Google Meet / Zoom) used for every discovery
    # call when auto-Meet is off. Recommended for the personal-Gmail setup.
    GOXL_MEETING_URL: str = ""

    @property
    def google_calendar_enabled(self) -> bool:
        return bool(
            self.GOOGLE_CALENDAR_ID
            and (self.GOOGLE_CALENDAR_CREDENTIALS_FILE or self.GOOGLE_CALENDAR_CREDENTIALS_JSON)
        )

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
