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
    # Per-process cap on connections to the Supabase pooler, which allows 15 in
    # session mode total across everything talking to it -- every API process,
    # every alembic run, every one-off script. Configurable so a multi-instance
    # deploy can be tuned without a code change: at N instances this process
    # alone can open up to N * (POOL_SIZE + POOL_MAX_OVERFLOW), and that must
    # stay comfortably under 15 with headroom for the rest. Defaults sized for
    # up to 2 instances (2*5=10) with room to spare. Running more than that
    # needs either a lower per-instance value here or -- the real fix --
    # switching DATABASE_URL to Supabase's transaction-mode pooler (port 6543),
    # which is built for many concurrent short-lived connections instead of a
    # fixed pool of long-lived ones.
    DB_POOL_SIZE: int = 2
    DB_POOL_MAX_OVERFLOW: int = 3

    # --- Auth ---
    # "dev"      = temporary local stand-in for testing, never used in production.
    # "supabase" = verify the JWT the frontend gets from Supabase Auth.
    AUTH_PROVIDER: str = "dev"

    # Only needed when AUTH_PROVIDER="supabase".
    #
    # Supabase signs user access tokens ASYMMETRICALLY (ES256) and publishes the
    # public half at {SUPABASE_URL}/auth/v1/.well-known/jwks.json. That is what
    # verifies a real founder login, so SUPABASE_URL is the setting that
    # matters in production.
    #
    # SUPABASE_JWT_SECRET is the LEGACY shared HS256 secret. It still signs the
    # anon/service keys and older projects' user tokens, so it is kept as a
    # fallback -- but a project on asymmetric signing never uses it for logins.
    # Verifying the anon key against it proves the secret is right and proves
    # nothing about user tokens; they are signed by a different key entirely.
    SUPABASE_URL: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # Shared secret Supabase sends back on its Auth webhook (configured on the
    # Supabase project's "Send webhook" auth hook). Verified against the
    # `X-Webhook-Secret` header on every inbound call -- an unauthenticated
    # caller must not be able to trigger someone else's account deletion by
    # guessing a founder's Supabase user_id. Empty means the endpoint refuses
    # every request rather than silently trusting an unsigned one.
    SUPABASE_WEBHOOK_SECRET: str = ""

    # Shared secret for internal-only endpoints with no founder in the request
    # at all (the deletion-sweep trigger an external scheduler calls). Same
    # fail-closed rule: empty means refuse, never "open by default".
    INTERNAL_JOBS_SECRET: str = ""

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

    # The refresh token used to be returned in the /auth/session and /auth/
    # resume JSON bodies, same as the access token -- which meant the only
    # place for a browser client to keep it was localStorage, fully readable
    # by any JS on the page (XSS, a compromised script, a malicious
    # extension). It is now ALSO set as an HttpOnly cookie the browser
    # handles automatically; /auth/refresh, /resume and /logout read it from
    # there first and only fall back to a body field for non-browser callers
    # that cannot use cookies (a mobile app, a script).
    #
    # REFRESH_COOKIE_SECURE must be True in production (cookie is dropped
    # entirely over plain HTTP otherwise, which is correct) -- False only
    # exists so local http://localhost dev isn't forced onto TLS.
    #
    # REFRESH_COOKIE_SAMESITE defaults to "lax": correct and simplest if the
    # frontend proxies /api to the backend (same browser-visible origin, per
    # the "Verify Vercel /api proxy to api.goxlally.ai" roadmap item -- once
    # that's confirmed, "lax" is right and nothing else here needs to
    # change). If the frontend and backend ever end up on genuinely
    # different origins with no proxy, this must become "none" (which
    # itself requires REFRESH_COOKIE_SECURE=True, the browser rejects
    # SameSite=None over plain HTTP).
    #
    # REFRESH_COOKIE_DOMAIN empty means a host-only cookie -- correct for a
    # single api.goxlally.ai host. Only set this to ".goxlally.ai" if the
    # cookie genuinely needs to be shared across multiple subdomains.
    REFRESH_COOKIE_NAME: str = "ally_refresh_token"
    REFRESH_COOKIE_SECURE: bool = True
    REFRESH_COOKIE_SAMESITE: str = "lax"
    REFRESH_COOKIE_DOMAIN: str = ""

    # --- Plan enforcement ---
    # The quota gate (daily token ceilings + credit balance). Was dormant while
    # its storage was unmigrated; daily_token_usage, plan_call_usage and the
    # credit columns all exist as of migration b8e2d4f60a19, so it can be live.
    # An explicit PLAN_ENFORCEMENT_ENABLED in the process environment still wins
    # over this, so a deploy can disable it without a code change.
    #
    # Defaults to True (changed pre-beta, 2026-08-16): with it off, chat LLM
    # usage is completely unbounded per founder -- a real cost-abuse exposure
    # flagged in the pre-beta audit. "Secure by default" here means a deploy
    # that forgets to set this env var explicitly still gets the gate, rather
    # than silently shipping unmetered LLM access. Set
    # PLAN_ENFORCEMENT_ENABLED=false explicitly (env var, not this default) if
    # a specific environment genuinely needs it off.
    PLAN_ENFORCEMENT_ENABLED: bool = True

    # Founder-archetype assignment via LLM. Off => the deterministic lexical
    # match, which its own docstring calls a heuristic. The LLM chooses from the
    # same seeded catalogue and falls back to the lexical engine on any failure.
    ARCHETYPE_LLM: bool = False

    # Write a recommendation when the curated intervention library covers none of
    # a detected root cause. Off => that cause yields nothing, silently, which is
    # the behaviour this replaces. Its own flag, not a shared diagnosis one: this
    # produces advice with no reviewed intervention behind it and should be
    # switchable on its own.
    RECOMMENDATION_FALLBACK_LLM: bool = False

    # --- Diagnosis length ---
    # Hard cap on questions in one diagnosis. A diagnosis must reach a confident
    # picture within this budget; it is not a walk through the whole bank (which
    # is 569 questions for Stage 0->1 and would never be finished by anyone).
    #
    # This is also the denominator for the confidence score's evidence-coverage
    # signal. That signal used to divide by the founder's whole in-scope bank,
    # which made the score's own target unreachable: 30/569 = 0.05 on a 25%-weight
    # input capped the total at 76, so a founder answering 30 questions perfectly
    # could never cross the 80 needed to generate a report. Coverage means "how
    # much of THIS diagnosis is done", and a diagnosis is this many questions.
    MAX_DIAGNOSIS_QUESTIONS: int = 30

    # --- Founder DNA (phase 2, adaptive) ---
    # Safety ceiling for the Founder DNA phase, which runs BEFORE the
    # diagnosis above (see founders.founder_dna_completed_at). Unlike
    # MAX_DIAGNOSIS_QUESTIONS this is not a target to reach -- the engine
    # stops earlier, per-dimension, the moment the resolution advisor judges
    # a dimension resolved.
    #
    # 9 = the 6 dimensions (the hard floor -- 6 dimensions cannot be covered
    # in fewer than 6 questions) plus 50% headroom for clarifying follow-ups
    # on vague answers. Sized against the WHOLE journey's time budget, not
    # this phase in isolation: Founder DNA + the adaptive business diagnosis
    # together must stay inside ~40 minutes of a founder's time, and the
    # business diagnosis needs the larger share of that. Was 18, which let a
    # first live run spend 12 questions here before the diagnosis had even
    # started -- too much of the budget on identity, too little left for the
    # actual problem.
    MAX_FOUNDER_DNA_QUESTIONS: int = 9
    # Minimum answers a dimension needs before the resolution advisor is
    # asked to judge it. 1, not 2: a single specific, story-based answer CAN
    # fully resolve a dimension (verified live -- the advisor correctly held
    # dimensions open on thin answers and closed them on concrete ones), and
    # requiring a second answer everywhere doubled this phase's length for
    # signal the advisor did not need. The advisor is still the one deciding
    # -- a vague first answer keeps the dimension open and earns a follow-up,
    # which is what the headroom in the ceiling above is for.
    FOUNDER_DNA_MIN_QUESTIONS_PER_DIMENSION: int = 1

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

    # --- Email (SMTP -- works with Gmail, SendGrid, SES, etc.) ---
    # Until EMAIL_HOST is set, email.py runs in stub mode (logs instead of sends)
    # so dev/tests never send real mail.
    EMAIL_HOST: str = ""
    EMAIL_PORT: int = 587
    EMAIL_USER: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_FROM: str = "GoXL <no-reply@goxl.in>"
    EMAIL_USE_TLS: bool = True

    @property
    def email_enabled(self) -> bool:
        return bool(self.EMAIL_HOST)

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- PDF rendering (Gotenberg headless-Chromium sidecar) ---
    # The report PDF is rendered from the print HTML for screen parity. When the
    # service is unreachable, export falls back to the reportlab renderer and
    # flags it via the X-PDF-Renderer response header (visible degradation).
    GOTENBERG_URL: str = "http://localhost:3000"

    # --- Observability ---
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"

    # --- Tier-1 Reasoning: answer classifier ---
    # "stored" (deterministic, reads answers.score_label) | "llm" (provider-driven)
    ANSWER_CLASSIFIER: str = "stored"
    LLM_PROVIDER: str = ""            # openai | anthropic | gemini
    LLM_MODEL: str = ""              # empty -> the adapter's default model
    LLM_CLASSIFIER_MAX_RETRIES: int = 2
    LLM_CLASSIFIER_TIMEOUT_SECONDS: float = 30.0
    LLM_CLASSIFIER_TEMPERATURE: float = 0.0

    # --- Adaptive questioning (Hybrid) ---
    # When true, the live answer-submit path asks the LLM to read the answer, score
    # it Green/Amber/Red, and re-rank the deterministic shortlist to pick the most
    # informative next question. Falls back to the deterministic pick if the LLM is
    # off, errors, or returns an out-of-shortlist id. Uses LLM_PROVIDER / LLM_MODEL.
    ADAPTIVE_QUESTIONS: bool = False
    ADAPTIVE_SHORTLIST_SIZE: int = 8
    ADAPTIVE_TIMEOUT_SECONDS: float = 20.0

    # Report narrative prose via LLM (report_narrative task). Off => deterministic
    # template. Each section degrades to the template on failure and records it
    # (narrator_provenance), so template-generated sections are never invisible.
    REPORT_NARRATIVE_LLM: bool = False

    # Answer-consistency detector (input (c) of confidence). Off => the signal stays
    # UNAVAILABLE and confidence renormalises over the other four inputs, as before.
    ANSWER_CONSISTENCY_LLM: bool = False

    # Distress LANGUAGE detection (#11). Off => the deterministic distress proxy
    # (distress-tagged Red answers). On => the LLM reads the founder's words and
    # FAILS CLOSED (a detector error routes the session to wellbeing support).
    DISTRESS_LLM: bool = False

    # --- Tier-1 Reasoning: retrieval / embeddings ---
    RETRIEVAL_ENABLED: bool = False
    EMBEDDING_PROVIDER: str = ""      # openai | gemini
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    # Stamped into the *_embedding tables' embedding_version column by the
    # migration, so every vector records which generation it belongs to.
    EMBEDDING_VERSION: str = "openai-3-small-v1"
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_MIN_SIMILARITY: float = 0.0

    # --- Provider adapters (credentials via env; never logged) ---
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_VERSION: str = "2023-06-01"
    OPENAI_BASE_URL: str = "https://api.openai.com"
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com"
    PROVIDER_TIMEOUT_SECONDS: float = 30.0
    PROVIDER_MAX_RETRIES: int = 3
    PROVIDER_BACKOFF_SECONDS: float = 0.5

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
