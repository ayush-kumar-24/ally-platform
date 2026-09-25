from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import ENV_FILE


class Settings(BaseSettings):
    # ENV_FILE is absolute. With the bare relative ".env" this used to
    # carry, pydantic resolved it against the working directory -- so this
    # and load_dotenv() in app.main could read two different files, or
    # neither. See app/core/paths.py.
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

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
    # Keep session mode even when DATABASE_URL points at the Supabase pooler on
    # 5432. Off, because session mode is what dropped three of ten end-to-end
    # runs mid-request: app/db/session.py moves a pooler URL to 6543 for the
    # runtime engine and says so in the log. Migrations are never moved --
    # alembic reads DATABASE_URL as written, which is what Supabase wants for
    # DDL. Set this true only to run the app itself on session mode deliberately.
    DB_SESSION_POOLER_OK: bool = False

    # --- Auth ---
    # "dev"      = temporary local stand-in for testing, never used in production.
    # "supabase" = verify the JWT the frontend gets from Supabase Auth.
    # "cognito"  = verify the Cognito ID token used to establish an Ally session.
    AUTH_PROVIDER: str = "dev"

    # Amazon Cognito user-pool identity provider.
    # These identifiers are not secrets and may be overridden by environment.
    COGNITO_REGION: str = "ap-south-1"
    COGNITO_USER_POOL_ID: str = "ap-south-1_QideRXCEN"
    COGNITO_CLIENT_ID: str = "31ql28tvmbl66c6lun5fkdn2it"

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

    # The Supabase SERVICE ROLE key. Used for exactly one thing: creating the
    # auth.users row when an admin approves a waitlist registration (see
    # app/services/supabase_admin.py). Sign-ups are switched off at the project
    # level, so approval is the ONLY way an identity comes into existence, and
    # that call needs an admin credential -- the anon key cannot do it.
    #
    # This key bypasses RLS entirely and can read or write every table in the
    # project. Treat it like the database password it effectively is: Secrets
    # Manager, never a plain environment variable, never anywhere near the
    # frontend. It is deliberately NOT wired into the auth provider, the ORM
    # session, or any request path a founder can reach; the one module that
    # reads it is the only module that should ever read it.
    #
    # Empty means the approve endpoint refuses rather than half-approving: a
    # registration marked approved with no identity behind it is a founder
    # who has been told they are in and cannot log in.
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # How many founders the platform is being opened to in this phase. Counted
    # against approvals, not registrations -- the queue is allowed to grow past
    # it, and that backlog is the demand signal. A super admin can approve past
    # the cap deliberately (see app/services/waitlist.py); everyone else is
    # refused with the count in the message.
    WAITLIST_APPROVAL_CAP: int = 300

    # Exempts ONE known caller -- the landing site's server-to-server forward
    # (app/lib/ally-waitlist.ts over there) -- from the public waitlist
    # endpoint's per-IP rate limit.
    #
    # That endpoint is unauthenticated by design (see app/api/v1/waitlist/
    # public.py), so this is not an auth token; it changes nothing about who
    # may call it. What it fixes: the landing site forwards EVERY registration
    # from one small pool of serverless egress IPs, which is indistinguishable
    # from a single caller hammering the endpoint to a per-IP limiter -- so the
    # 6th founder to register within five minutes was rate-limited into a
    # dropped registration, silently, on both sides. A real per-visitor abuse
    # limit has to key on the visitor, which only the landing site can see;
    # this lets that site enforce its OWN limit (already does, see its
    # RATE_LIMIT/RATE_WINDOW_MS) instead of being throttled a second time by
    # an IP the limit was never meant to describe.
    #
    # Empty means the exemption is never available -- same fail-closed rule as
    # INTERNAL_JOBS_SECRET below: a header nobody can produce, not "open by
    # default" if this is forgotten.
    WAITLIST_FORWARD_SECRET: str = ""

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

    # --- Public launch -------------------------------------------------------
    # Nothing is free once we launch. Until then Free carries almost the whole
    # product, because the people using it are our own testers and gating them
    # out mid-test would be worse than leaving it open.
    #
    # Flipping this to True empties the Free tier: a founder without a paid plan
    # gets no product features and is sent to the plans page to choose one. It is
    # a switch rather than a code change so launch day is a deploy setting, not a
    # release, and so it can be put back inside a minute if something is wrong.
    #
    # BEFORE FLIPPING IT: move the existing testers onto a real plan, or they
    # lose access at the same moment everyone else does. One UPDATE on
    # founders.plan_type -- see docs/PUBLIC-LAUNCH-CHECKLIST.md.
    PUBLIC_LAUNCH: bool = False

    # Founder-archetype assignment via LLM. Off => the deterministic lexical
    # match, which its own docstring calls a heuristic. The LLM chooses from the
    # same seeded catalogue and falls back to the lexical engine on any failure.
    ARCHETYPE_LLM: bool = False

    # Short bullet previews of the founder's own Founder DNA answers, shown on
    # the cards with the whole answer behind "Read more". Off => the cards show
    # the answers themselves, which is today's behaviour and is a wall of prose
    # for any founder who wrote at length.
    #
    # Worth a flag because it is the only LLM call on a page that otherwise just
    # reads stored text. It is cheap -- ONE call per report, not per view, and
    # not per dimension: the result is cached on the report (see
    # reports/dna_summaries.py), so a founder who opens the page fifty times
    # pays for it once. It fails to the un-summarised cards on any error.
    FOUNDER_DNA_SUMMARY_LLM: bool = False

    # Let a model choose each founder's two dashboard lines from the shortlist
    # the catalogue and their profile produce. Off => the deterministic pick,
    # which is still per-founder and still stage-filtered -- the model is
    # buying judgement about WHICH of forty relevant lines lands best, not the
    # personalisation itself. A founder cannot tell which one chose, so watch
    # the job's by_fallback count rather than the page.
    #
    # One call per founder per NIGHT, never per page view. See quotes/jobs.py.
    DAILY_QUOTES_LLM: bool = False

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
    #
    # CORRECTION (2026-08-27): the "27 of 45" above counted raw NULLs and was
    # misleading. 26 of those 27 rows are empty test accounts that never began
    # onboarding -- no industry, no problem, no goal, nothing. Every founder who
    # actually completed onboarding has a stage, and the values vary properly
    # (Ideation 11, Validation 2, Prototype 2, Early Traction 1, Growth 2).
    # So this is the EXCEPTION path, not the majority one: it earns its keep for
    # founders whose profile was populated outside onboarding, not as a routine
    # substitute for a stage nobody recorded.
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

    # Fewest answers a readiness pillar needs before it gets a score and a band
    # rather than being reported as not assessed.
    #
    # Each answer is 0, 1 or 2 (green/amber/red) and a pillar's score is the mean
    # inverted onto 0-100, so the number of answers IS the resolution of the
    # score. One answer can only ever produce 0, 50 or 100 -- three bands with
    # nothing in between -- and the founder is shown a band, not a sample size,
    # so "Critical Gap" off a single amber reads exactly like "Critical Gap" off
    # eight. Three is the floor because it is the first count whose scale has
    # more steps than the band table has bands.
    #
    # A pillar below the floor is reported the same way as one never asked
    # (score None, no band, no red flag) and is excluded from the overall
    # weighted score, which renormalises over what remains. The two are still
    # distinguishable downstream: assessed_question_count is 0 for never-asked
    # and 1-2 for below-floor.
    MIN_ANSWERS_PER_PILLAR_SCORE: int = 3

    # How many questions written for the founder's OWN industry open the
    # diagnosis, before pillar coverage takes over. Keyed by
    # founder_stages.stage_order.
    #
    # Set per stage rather than as a fraction because the right number is a
    # product judgement about how much of a stage is industry-shaped, and that
    # is not linear in the budget: an Ideation founder has almost nothing built,
    # so what industry they are in is most of what distinguishes them from any
    # other Ideation founder, while a Maturity founder has years of their own
    # evidence to be asked about.
    #
    #     1  Ideation          6 of 14      5  Growth / Scaling  12 of 30
    #     2  Validation        8 of 20      6  Expansion         13 of 32
    #     3  Prototype / MVP  10 of 24      7  Maturity          14 of 32
    #     4  Early Traction   12 of 30      8  Exit              14 of 30
    #
    # Stages 3, 6 and 8 were not specified and are interpolated between their
    # neighbours; change them freely, they carry no more authority than that.
    #
    # Data, not behaviour: editable in production like
    # founder_stages.question_budget. An empty dict, or a stage missing from it,
    # falls back to INDUSTRY_OPENING_SHARE below. Zero for a stage disables the
    # block at that stage.
    #
    # Every value here is still bounded at runtime by `opening_block_size` --
    # see INDUSTRY_OPENING_SHARE for the measurements behind that bound, and
    # note that at Ideation and Validation these numbers sit exactly ON it.
    INDUSTRY_OPENING_QUESTIONS: dict[int, int] = {
        1: 6, 2: 8, 3: 10, 4: 12, 5: 12, 6: 13, 7: 14, 8: 14,
    }

    # Fallback share of the budget, used only for a stage absent from
    # INDUSTRY_OPENING_QUESTIONS above (including an unknown stage).
    #
    # WHY AN OPENING BLOCK AND NOT JUST A RANKING PREFERENCE. As a tie-break
    # (industry_scope's relevance rank) industry is too quiet to be felt: it
    # only separates questions the coverage terms have already tied, so a
    # founder can answer ten questions before meeting one written for their
    # industry. The diagnosis should read as theirs from the start.
    #
    # WHY IT IS CAPPED, AND WHY AT ROUGHLY A THIRD. The industry banks do NOT
    # cover the six pillars, measured on the seeded data:
    #
    #   SaaS,          Stage 0->1   20 questions: 19 Product & Execution,
    #                               1 Team & Leadership. Nothing at all for
    #                               Founder Readiness, Market Clarity,
    #                               Revenue Maturity or Strategic Clarity.
    #   Manufacturing, Stage 1->10+ 25 questions: 21 Revenue Maturity,
    #                               4 Product & Execution. Four pillars absent.
    #
    # And the bank is large against the budget -- 15 questions at Ideation
    # (budget 14), 20 at Validation (budget 20), 25 at Growth (budget 30). So
    # an uncapped industry-first pass would spend an Ideation founder's ENTIRE
    # diagnosis inside two or three pillars, and Founder Readiness and
    # Strategic Clarity -- motivation clarity, idea conviction, delegation
    # anxiety, leadership identity -- would go unasked at every stage in every
    # industry. Those pillars are scored and reported, and a pillar with no
    # answers renders as not assessed.
    #
    # A third leaves twice the budget for coverage, which at every stage is
    # more than two questions per in-scope pillar:
    #
    #   Ideation 14 -> 4 industry, 10 coverage   Growth     30 -> 10, 20
    #   Validation 20 -> 6, 14                   Expansion  32 -> 10, 22
    #   Early Traction 30 -> 10, 20
    #
    # Data, not behaviour: tune it in production like founder_stages
    # .question_budget. 0.0 disables the block entirely and returns selection
    # to the ranking preference alone.
    INDUSTRY_OPENING_SHARE: float = 1 / 3

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
    # Note this cannot reach 15/15 on its own: 10 of the dimensions have no
    # follow-up question authored at all (core_values among them), so they are
    # one-shot regardless of budget. If the advisor cannot resolve one of those
    # from a single answer, no ceiling helps -- that needs content, not config.
    #
    # 2026-09-02: 17 -> 18, for RISK_APPETITE as the fifteenth dimension. The
    # formula is unchanged and is the whole reason this moved: 15 base + 2
    # follow-ups + 1 close = 18. Leaving it at 17 would not have dropped the
    # new dimension -- base questions are asked before follow-ups -- it would
    # have eaten a follow-up slot instead, reintroducing at 15 dimensions the
    # exact "only one follow-up can ever fire" bug the 16 -> 17 change fixed at
    # 14, and just as invisibly.
    #
    # Still safe on ordering: the close is TERMINAL by construction, not by
    # budget exhaustion -- FounderDnaEngine.select_next_question pulls
    # `is_closing` out of the candidate list and holds it back until the base
    # journey is done (engine.py, `closing = next(... if q.is_closing)`). That
    # is what the warning above asks to re-check, and it still holds.
    #
    # Timing: 18 x ~75s is ~22 min. The whole-journey budget is unchanged, but
    # the diagnosis half is no longer a flat 30 -- per-stage budgets (8f3a1c92d7b4)
    # put Ideation at 14 and Validation at 20, so the combined journey is
    # shorter than it was at 17 + 30 for most founders, not longer.
    MAX_FOUNDER_DNA_QUESTIONS: int = 18
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
    DISCOVERY_CALL_DURATION_MINUTES: int = 30
    DISCOVERY_TIMEZONE: str = "Asia/Kolkata"
    # Which midnight ends a founder's metered day (plans/usage.py).
    #
    # Its own setting rather than reusing DISCOVERY_TIMEZONE: that one decides
    # when call slots are offered, and someone changing booking hours must not
    # silently move every founder's token allowance with it.
    #
    # UTC was the previous behaviour and was wrong for this audience -- founders
    # are in India, so a day that rolls over at 00:00 UTC hands back their
    # allowance at 05:30 IST. A tester who ran out at 9pm was told to wait for
    # "midnight" and then found nothing there until dawn.
    USAGE_RESET_TIMEZONE: str = "Asia/Kolkata"
    # Personal Gmail calendars can't invite attendees via a service account
    # ("forbiddenForServiceAccounts"); only turn this on with a Google Workspace
    # calendar + domain-wide delegation. When off, the booking is created without
    # attendees and the app delivers the meeting link to the founder itself.
    GOOGLE_CALENDAR_INVITE_ATTENDEES: bool = False
    # Minutes before the call that Google Calendar emails a reminder, and pops
    # one up. Set on the event rather than left to each person's own defaults:
    # without this Google uses whatever the attendee happens to have configured,
    # which for most people is a 10-minute popup and no email at all.
    #
    # These reach the FOUNDER only when they are an attendee -- i.e. only with
    # GOOGLE_CALENDAR_INVITE_ATTENDEES on. Until then they apply to the host
    # calendar alone, which is harmless.
    #
    # Separate from the app's own 1-hour reminder email
    # (app/jobs/discovery_reminders.py). That one always works; these need
    # Workspace.
    GOOGLE_CALENDAR_REMINDER_EMAIL_MINUTES: int = 30
    GOOGLE_CALENDAR_REMINDER_POPUP_MINUTES: int = 10
    # Auto-generating a Google Meet link also needs Workspace -- personal Gmail
    # rejects it ("Invalid conference type value"). When off, the booking is a
    # plain event and the meeting link comes from GOXL_MEETING_URL.
    # The Workspace user the service account acts AS, e.g. calls@goxl.in.
    #
    # A bare service account has its own empty calendar. It can write to a
    # calendar shared with it, but it CANNOT create a Meet conference or invite
    # attendees -- both need a real Workspace identity. Setting this makes the
    # client impersonate that user (domain-wide delegation).
    #
    # Requires a Workspace admin to authorise the service account's client ID
    # for https://www.googleapis.com/auth/calendar in
    # Admin console > Security > API controls > Domain-wide delegation.
    #
    # Leave empty and everything still works, minus per-call Meet links and
    # attendee invites -- the shared GOXL_MEETING_URL room is used instead.
    GOOGLE_CALENDAR_DELEGATED_USER: str = ""

    GOOGLE_CALENDAR_CREATE_MEET: bool = False
    # A permanent video-room link (Google Meet / Zoom) used for every discovery
    # call when auto-Meet is off. Recommended for the personal-Gmail setup.
    GOXL_MEETING_URL: str = ""

    # --- Discovery calls: open or not ---
    # False until Google Workspace domain verification lands (30-48h as of
    # 2026-09-08). Booking is built and works, but a confirmed call needs a
    # joining link we cannot mint yet, so /book refuses and /slots returns
    # nothing rather than confirming calls nobody can host.
    #
    # The page has its own COMING_SOON flag showing the feature behind a
    # banner. That one hides the button; this one is the actual lock. Turn both
    # off together.
    DISCOVERY_CALLS_ENABLED: bool = False

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
    #: The SAME address founders write back to -- decided 2026-09-07.
    #:
    #: The root goxlally.ai is already verified for sending, on the Resend
    #: account Supabase uses for login codes, and its MX already points at
    #: Hostinger for receiving. So one address does both, with no DNS work and
    #: nothing for a founder to notice: mail arrives from the address they can
    #: reply to.
    #:
    #: THIS MEANS EMAIL_PASSWORD MUST BE A KEY FROM THAT ACCOUNT. A key from
    #: the other team cannot send as this domain and every send is rejected.
    #:
    #: The cost of merging them is a shared free-tier ceiling (100/day, 3,000/
    #: month) with login codes -- and running out of login codes locks every
    #: founder out, while running out of notifications merely delays one. Watch
    #: that account's volume, and pay for it before it is close.
    EMAIL_FROM: str = "Ally by GoXL <info@goxlally.ai>"
    EMAIL_USE_TLS: bool = True
    #: Where a founder's reply actually lands.
    #:
    #: EMAIL_FROM is a no-reply address, but the discovery-call emails invite
    #: a founder to reply to reschedule -- so without this their reply bounces
    #: or vanishes, which is worse than never having offered. Set this to a
    #: mailbox a person actually reads.
    #: goxlally.ai, not goxl.in -- agreed 2026-09-07. The mailbox must exist
    #: and be read by a person: the discovery-call emails invite a reply.
    EMAIL_REPLY_TO: str = "info@goxlally.ai"

    @property
    def email_enabled(self) -> bool:
        return bool(self.EMAIL_HOST)

    # Admin Panel Phase 3: who gets paged when the health check turns red.
    # Comma-separated, same shape as CORS_ORIGINS below -- deliberately not
    # GOXL_ADMIN_PANEL_USERS (panel *access* and *who gets alerted* are
    # different questions; an on-call inbox may not be a panel login at all).
    HEALTH_ALERT_EMAILS: str = ""

    @property
    def health_alert_emails(self) -> list[str]:
        return [e.strip() for e in self.HEALTH_ALERT_EMAILS.split(",") if e.strip()]

    #: Who is told when a Privacy Center request lands on the review queue.
    #:
    #: Separate from HEALTH_ALERT_EMAILS on purpose: that is an on-call/ops
    #: inbox for "the system is red", this is whoever handles founder requests
    #: and DSARs. The same person may read both; they are not the same question.
    #:
    #: Unset is NOT silence -- privacy_notifications falls back to
    #: EMAIL_REPLY_TO, because a request nobody is told about is the exact
    #: defect that feature exists to remove.
    PRIVACY_ALERT_EMAILS: str = ""

    @property
    def privacy_alert_emails(self) -> list[str]:
        return [e.strip() for e in self.PRIVACY_ALERT_EMAILS.split(",") if e.strip()]

    #: Who is told when a founder writes to us -- Help & Support, the help
    #: widget, or the Feedback page.
    #:
    #: Falls back to PRIVACY_ALERT_EMAILS and then EMAIL_REPLY_TO, so this can
    #: stay unset until the team wants support mail split out. It must never
    #: resolve to nobody: the product tells the founder a person will reply.
    SUPPORT_ALERT_EMAILS: str = ""

    @property
    def support_alert_emails(self) -> list[str]:
        return [e.strip() for e in self.SUPPORT_ALERT_EMAILS.split(",") if e.strip()]

    #: The team's own accounts, which always hold every feature.
    #:
    #: These are the people who build and test Ally. They sign in with ordinary
    #: accounts on whatever tier those accounts happen to carry, which meant a
    #: developer testing Vision, voice chat or email reminders hit the same
    #: paywall a Starter founder would -- and a feature nobody on the team can
    #: reach is a feature nobody on the team is testing.
    #:
    #: Listed by EMAIL rather than founder_id on purpose: ids differ between
    #: environments and are assigned at signup, so an id list would be wrong in
    #: staging and stale the moment someone re-registers. Email is what the
    #: person actually is.
    #:
    #: Matching is case-insensitive and whitespace-tolerant (see the property
    #: below) -- "Info@GoXL.in " and "info@goxl.in" are one person, and a list
    #: this long is edited by hand.
    #:
    #: This grants the PRO feature set, which is every feature there is. It does
    #: NOT lift the daily token ceiling (8,000 on Pro) or the one-per-account
    #: diagnosis cap; those are separate limits with separate reasons, and the
    #: admin panel already has a diagnosis reset for the second.
    TEAM_FULL_ACCESS_EMAILS: str = (
        "14aarush9@gmail.com,"
        "aniketkumarshawtech@gmail.com,"
        "aaryakapoor14@gmail.com,"
        "aarya.goxl@gmail.com,"
        "ayushray2403@gmail.com,"
        "ayushkumar20060324@gmail.com,"
        "ayushgoxl@gmail.com,"
        "ayush2403kumar@gmail.com,"
        "d.viraj2@gmail.com,"
        "goxloffice@gmail.com,"
        "goxlmarketing@gmail.com,"
        "goxl.work@gmail.com,"
        "godblesspower7@gmail.com,"
        "pranjalsavantsavant@gmail.com,"
        "pranjalmaheshsavant@gmail.com,"
        "info@goxl.in,"
        "sumitgoxlofficial@gmail.com,"
        "sumitsuman4411@gmail.com"
    )

    @property
    def team_full_access_emails(self) -> frozenset[str]:
        """Normalised for comparison: lowercased, stripped, blanks dropped."""
        return frozenset(
            e.strip().lower()
            for e in self.TEAM_FULL_ACCESS_EMAILS.split(",")
            if e.strip()
        )

    #: The Ally mark shown in the header band of every email.
    #:
    #: A HOSTED URL, not an attachment and not a data: URI -- Gmail blocks data
    #: URIs outright, and a CID attachment would force every sender to build a
    #: multipart/related message. The mark already ships to S3 with the frontend
    #: (frontend/public/ally-logo-mark-on-dark.png), so this needs nothing new
    #: deployed to be reachable.
    #:
    #: Hardcoded to app.goxlally.ai rather than derived from the app-URL setting
    #: above, for the reason documented there: production has that pointed at the
    #: marketing site, which would make this a broken image in every inbox.
    #:
    #: An unreachable value is not fatal. Clients block images by default anyway,
    #: so the header is designed to read correctly without it -- the alt text is
    #: the word "Ally" on the green band.
    EMAIL_LOGO_URL: str = "https://app.goxlally.ai/ally-logo-mark-on-dark.png"

    # --- CORS ---
    # Comma-separated. PRODUCTION MUST INCLUDE THE MARKETING SITE as well as
    # the app: the landing page's help widget calls /support/public/ask from
    # goxlally.ai, and a missing origin here fails as a browser CORS block --
    # no server error, no log line, the widget just quietly falls back to its
    # nine offline answers. Both the apex and www, because the site is reachable
    # at both:
    #   https://app.goxlally.ai,https://goxlally.ai,https://www.goxlally.ai
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

    # Where the FOUNDER-FACING APP lives. MUST be https://app.goxlally.ai.
    #
    # Used to send a founder back into the app after an external redirect that
    # cannot carry a session -- today the Google Calendar OAuth callback, which
    # lands on this API and has to bounce to /app/plan.
    #
    # PRODUCTION HAS THIS SET TO THE MARKETING SITE (https://goxlally.ai) AND
    # THAT IS A LIVE BUG. goxlally.ai has no /app/* routes, so every founder who
    # connects a calendar is redirected to a 404 -- the connection saves first,
    # so it "works" while looking broken at the last step. Verified:
    #   goxlally.ai/app/plan     -> 404
    #   app.goxlally.ai/app/plan -> 200
    #
    # It also used to build share links, which is how one wrong value broke two
    # unrelated features. Shares no longer read it; see SHARE_LINK_BASE_URL.
    PUBLIC_APP_URL: str = ""

    # This API's own public origin, e.g. https://api.goxlally.ai.
    #
    # Only needed to build absolute links back to this API from inside it, share
    # links being the one that matters. Empty falls back to the origin the
    # request arrived on -- right when the API is reached directly, wrong behind
    # a proxy that rewrites Host without forwarding it, which is exactly the
    # Vercel /api/* rewrite this app sits behind.
    PUBLIC_API_URL: str = ""

    # OPT-IN pretty share links: https://<this>/r/<token>.
    #
    # SET THIS TO https://app.goxlally.ai IN PRODUCTION. The rewrite genuinely
    # exists there (frontend/vercel.json maps /r/:token to this API's
    # /reports/shared/{token}/view), and it is verified working -- requesting
    # app.goxlally.ai/r/<garbage> returns this API's own error, not the SPA.
    #
    # Empty means share links use the direct API URL: longer, and it resolves
    # with no rewrite at all.
    #
    # Opt-in rather than inferred because the failure mode is silent. A base URL
    # whose rewrite is missing produces links that look perfect and 404, and
    # nothing here can detect the difference.
    SHARE_LINK_BASE_URL: str = ""

    # --- Payments (Razorpay) ---
    # Until both key settings are set, app.payments refuses to create a real
    # order rather than simulating one -- unlike email/PDF rendering, a stub
    # "success" here would hand out a paid plan for nothing. See
    # app/payments/gateway.py.
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    # Separate from the key secret: this signs webhook deliveries specifically
    # (set on the Razorpay dashboard's own webhook config), not the same value
    # used to sign the checkout-callback or to authenticate API calls.
    RAZORPAY_WEBHOOK_SECRET: str = ""

    @property
    def payments_enabled(self) -> bool:
        return bool(self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET)

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

    # --- Task reminders by email ---
    # Minutes before a task is due that the reminder email is sent. Mirrors
    # CALENDAR_REMINDER_MINUTES_BEFORE deliberately: a founder with a calendar
    # connected and one without should be nudged at the same moment, or the
    # same task nags twice at two different times.
    TASK_REMINDER_MINUTES_BEFORE: int = 30
    # How late a reminder may be delivered, measured from the TASK's moment and
    # not from the row's. A reminder is worth sending while it is still ahead
    # of the thing it warns about, whatever offset the founder picked; past
    # that it is a nag about something already missed, so it is dropped (marked
    # sent, not retried forever). The grace covers the "at the time" offset,
    # where the reminder moment IS the task's and every sweep runs after it.
    TASK_REMINDER_GRACE_MINUTES: int = 10

    # --- Notification emails ---
    # Per founder, per run. A safety valve, not a policy: the dedup keys already
    # decide how often each notification may recur, so a founder hitting this
    # means something upstream is generating far more than expected -- and the
    # cap turns "a founder wakes to sixty emails" into "the logs show a capped
    # run". Anything over the cap is not lost; it goes out on the next run.
    NOTIFICATION_EMAIL_MAX_PER_RUN: int = 10
    # A notification that sat unsent this long is not worth an email. Same
    # reasoning as TASK_REMINDER_GRACE_MINUTES: after an outage, "here is
    # everything you missed" is how a founder learns to filter us.
    NOTIFICATION_EMAIL_MAX_AGE_HOURS: int = 24

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

    #: Cosine DISTANCE below which a diagnosis candidate counts as re-asking
    #: something this session already asked, and is dropped from selection.
    #: 0 disables the filter entirely.
    #:
    #: The catalogue carries rephrasings of one question inside a single
    #: category, and they share almost no words -- "could you say whose job it
    #: was", "is there any system for tracking who owns what", "a mistake
    #: because two people assumed the other was handling it" have four, seven
    #: and ten content words with no overlap at all. So this cannot be done
    #: lexically; it is done on the embeddings `questions` already carries,
    #: over the HNSW cosine index already built for them.
    #:
    #: 0.10 is deliberately tight. A false positive costs the founder a
    #: question they should have been asked, which is worse and less visible
    #: than the repeat it prevents, so this starts conservative and is meant to
    #: be tuned against real sessions rather than guessed upward.
    DIAGNOSIS_REPEAT_MAX_DISTANCE: float = 0.10

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

    def question_budget(self, stage_budget: int | None) -> int:
        """How many questions a diagnosis may ask, given the founder's stage.

        MAX_DIAGNOSIS_QUESTIONS is the fallback, not the answer: the real number
        lives on founder_stages.question_budget so it can differ per stage (an
        idea-stage founder needs far fewer than a scaling one). NULL there means
        "not decided for this stage", which is how the column ships.

        This lives here, beside the setting it falls back to, because TWO
        callers need the identical number and must never disagree:

          * DiagnosisService._attach_question -- the completion CEILING.
          * WeightedConfidenceModel -- the coverage DENOMINATOR, 25% of the
            confidence score.

        If the ceiling exceeded the denominator a founder could answer past 100%
        coverage; if it fell short they could never reach it and would never
        finish early. Two copies of `max(1, x or DEFAULT)` in two packages is
        exactly how those drift, so there is one copy and it is here.

        A non-positive stage budget is treated as UNSET, not clamped. Clamping
        was the first cut and it was worse than the bug it guarded: `max(1, -1)`
        is 1, so a stage that somehow held -1 would end every diagnosis after a
        single question. Falling back to the global default is the only safe
        reading of a number that cannot mean what it says.

        A CHECK constraint refuses a non-positive value at the database. This
        refuses one that arrives anyway, because the column is edited by hand in
        production and 0 is what a half-finished edit leaves behind. The final
        max() covers a misconfigured constant, so the return can never be 0 --
        it is a divisor, and a ZeroDivisionError here would take out the
        confidence score and the whole report with it.
        """
        if stage_budget is not None and stage_budget > 0:
            return stage_budget
        return max(1, self.MAX_DIAGNOSIS_QUESTIONS)


settings = Settings()
