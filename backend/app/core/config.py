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

    # Infer the founder's lifecycle stage from their diagnosis answers when
    # founders.stage_id is NULL. Off => the stage stays unknown, which is
    # today's behaviour and is NOT neutral: DefaultInterventionRelevance reads
    # an unknown stage as "every intervention is relevant", so a founder who
    # shipped a year ago can be handed ideation-stage advice, and the
    # Confidence Model loses its stage-adjusted root-cause priors entirely.
    #
    # Worth a flag rather than always-on because it adds one LLM call to the
    # reasoning pipeline and, unlike the archetype seam, it changes what the
    # founder is RECOMMENDED rather than how they are described. Measured on
    # the live founders table when this was written: stage_id was NULL for 27
    # of 45 founders, so this is the majority path, not an edge case.
    #
    # A declared stage is never overridden -- see stage_detection_llm.py.
    STAGE_INFERENCE_LLM: bool = False

    # Write a recommendation when the curated intervention library covers none of
    # a detected root cause. Off => that cause yields nothing, silently, which is
    # the behaviour this replaces. Its own flag, not a shared diagnosis one: this
    # produces advice with no reviewed intervention behind it and should be
    # switchable on its own.
    RECOMMENDATION_FALLBACK_LLM: bool = False

    # Complete the free report's 3+3 action plan when the curated library fills
    # only one half of it. Off => the report ships whatever the library gave,
    # which for a single diagnosed root cause is all-confirm or all-solve and
    # never both (see engines/action_plan_llm.py for why the engine cannot
    # produce the doc's shape). Reproduced live: three confirm lines, zero solve
    # lines, with nothing on the page saying half the plan was missing.
    #
    # Its own flag, not folded into RECOMMENDATION_FALLBACK_LLM, and off by
    # default for the same reason that one is: it puts founder-facing advice on
    # the page with no reviewed intervention behind it. Curated lines are never
    # replaced -- only the shortfall is authored.
    ACTION_PLAN_BALANCE_LLM: bool = False

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
    # 16 = the agreed 14-question base journey (one per dimension: the doc's
    # thirteen plus EQ, with the last doubling as the "wow close") plus up to
    # 2 adaptive follow-ups for dimensions a founder answered vaguely.
    #
    # The follow-up headroom is deliberate and small. A fixed 14-and-done was
    # considered and is what the product decision specifies for the BASE, but
    # leaving zero recovery room was live-observed to ship thin dimensions
    # straight to the dashboard: in an end-to-end run the advisor left
    # decision_style and energy_patterns unresolved after one answer each,
    # and a founder's card read "Yeah, that's something I think about
    # sometimes." Two spare slots cost ~2 minutes worst case and only fire
    # when the advisor judges a dimension genuinely unresolved.
    #
    # Sized against the WHOLE journey: 16 x ~75s is ~20 min, leaving ~20 min
    # for the 30-question business diagnosis inside the ~40-minute ceiling.
    #
    # History: 18 -> 9 -> 12 -> 16 -> 17 as the base journey grew from 6 asked
    # dimensions to 14. At 9 the ceiling sat below base+close and the
    # follow-up pool could never fire at all -- verified live.
    #
    # 17, because the CLOSE IS CHARGED TO THIS BUDGET TOO. The "two spare slots"
    # above were counted as 16 - 14 base, but one of the two is always spent on
    # the closing question, so only ONE follow-up could ever fire -- half the
    # stated intent. Measured live at 16: the authored follow-up for
    # energy_patterns (arc 92) was unreachable no matter how unresolved the
    # dimension was, and the phase closed at 12/14. At 17 the same run reaches
    # 13/14. So: 14 base + 2 follow-ups + 1 close = 17.
    #
    # Raising this was only safe once select_next_question() made the close
    # TERMINAL. Ordering previously fell out of budget exhaustion, which held
    # only while the ceiling was exactly base + 1 + close; the first attempt at
    # 17 (before that fix) put the close at Q16 and a follow-up at Q17, after
    # it. Do not raise this further without re-checking that the close is still
    # last.
    #
    # Still inside the ceiling: 17 x ~75s is ~21 min, leaving ~19 min for the
    # 30-question business diagnosis inside the ~40-minute whole-journey budget.
    #
    # Note this cannot reach 14/14 on its own: 10 of the 14 dimensions have no
    # follow-up question authored at all (core_values among them), so they are
    # one-shot regardless of budget. If the advisor cannot resolve one of those
    # from a single answer, no ceiling helps -- that needs content, not config.
    MAX_FOUNDER_DNA_QUESTIONS: int = 17
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
    # The report PDF is rendered from the report document for screen parity.
    # When the service is unreachable, export returns 503 and queues a backfill
    # rather than substituting a different-looking document.
    #
    # DEPLOYMENT: this must point at a running Gotenberg. On ECS Fargate it is a
    # second container in the SAME task definition (image gotenberg/gotenberg:8,
    # port 3000), which is why localhost works -- containers in one task share a
    # network namespace. Without that sidecar every PDF download 503s forever.
    GOTENBERG_URL: str = "http://localhost:3000"

    # Public origin used to build shareable links. Empty falls back to the
    # request's own base URL, which behind the Vercel proxy is the API host --
    # correct but wrong-looking in a link a founder sends to an investor. Set
    # this to the site people actually visit (e.g. https://goxlally.ai).
    PUBLIC_APP_URL: str = ""

    # --- Google Calendar sync (per-founder, Plan Your Day) ---
    # Separate from GOOGLE_CALENDAR_* above: those are a SERVICE ACCOUNT on
    # GoXL's own calendar for discovery-call booking. These are a normal OAuth
    # client used to reach each founder's OWN calendar, which they connect
    # explicitly -- login is email-only, so Ally never has a Google token
    # otherwise. Unset means the feature is simply unavailable; Plan Your Day
    # keeps working without it.
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    # Must match a redirect URI registered on the OAuth client exactly.
    GOOGLE_OAUTH_REDIRECT_URI: str = ""
    # Fernet key encrypting stored access/refresh tokens. No default on purpose:
    # see app/calendar_sync/crypto.py -- a missing key disables the feature
    # rather than falling back to storing tokens in plaintext.
    CALENDAR_TOKEN_KEY: str = ""
    # Minutes before an event that the popup reminder fires. 30 was the team's
    # choice; it only means anything on a TIMED event, which is why tasks carry
    # an optional due_time and dateless-time tasks fall back to the hour below.
    CALENDAR_REMINDER_MINUTES_BEFORE: int = 30
    # The hour a task with a date but no time is scheduled at, so the reminder
    # above lands in the morning rather than at 23:30 the previous night.
    CALENDAR_DEFAULT_TASK_HOUR: int = 9
    # How long a synced task event occupies on the calendar. Short on purpose:
    # a task is a prompt, not a meeting, and hour-long blocks for every to-do
    # would make a founder's calendar unreadable.
    CALENDAR_EVENT_DURATION_MINUTES: int = 30

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

    # How many diagnosis ANSWERS to classify concurrently.
    #
    # DiagnosticEngine.classify_answers awaited one LLM call per answer in a
    # plain for-loop, so a 30-answer session spent 30 x ~5s in series. Profiled
    # on a real session: the `diagnosis` stage was 161s of a 203s pipeline --
    # 79% of the founder's wait on the final answer. Every answer is classified
    # independently, so the serialisation bought nothing.
    #
    # 6, not "all 30": each one is a provider call, and firing thirty at once is
    # how a burst rate limit gets hit -- and this runs while the founder is
    # waiting, so a 429 storm is the worst possible trade. 6 turns 30 serial
    # calls into 5 waves. Set to 1 to restore the strictly-sequential behaviour.
    DIAGNOSIS_CLASSIFY_CONCURRENCY: int = 6

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

    # Chat attachment blobs. Empty bucket (the default) keeps file bytes
    # inline in file_uploads.content, which is what local dev and CI run on --
    # no AWS access needed for attachments to work or be tested. Set the
    # bucket in production and new uploads go to S3 instead; rows written
    # before that keep resolving from Postgres, so there is no backfill or
    # flag day. Credentials are NOT read from here: boto3 resolves them from
    # the standard chain (ECS task role in production), so no secret for this
    # ever lives in config.
    ATTACHMENT_S3_BUCKET: str = ""
    ATTACHMENT_S3_REGION: str = ""
    # Only for S3-compatible stores (MinIO/LocalStack); empty means real AWS.
    ATTACHMENT_S3_ENDPOINT_URL: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def diagnosis_scoring_configured(self) -> bool:
        """Will any answer in a diagnosis actually get a Green/Amber/Red band?

        Two independent flags decide this, and with both at their defaults the
        answer is no -- which silently emptied every report. ADAPTIVE_QUESTIONS
        is the only thing that writes answers.score_label (the submit-time
        advisor, DiagnosisService._apply_insight); ANSWER_CLASSIFIER="llm" is the
        only thing that derives a band at report time. Neither on means every
        answer arrives at the reasoning pipeline unscored, every one is skipped
        as unclassifiable, and the diagnosis yields a report with no evidence
        behind it.

        A named predicate rather than the expression inlined at its one call
        site: this coupling is not deducible from either flag's own
        documentation, it is the direct cause of a P0, and it deserves to be
        stated once, in the same place the flags are defined.
        """
        return self.ADAPTIVE_QUESTIONS or self.ANSWER_CLASSIFIER == "llm"


settings = Settings()
