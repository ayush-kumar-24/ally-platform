# Security and data-flow evidence

What the Privacy Policy's security section and the DPDP review's questions about
vendors and cross-border transfer are actually based on. Everything here was
read out of production by the AWS team on **23 September 2026**; nothing is
inferred from the code.

This file exists because the policy previously claimed "TLS 1.3", "AES-256
encryption at rest" and "regular security audits and vulnerability assessments"
with nothing behind them. Two of those three now have evidence and are stated
again, more precisely. The third does not, and is not claimed.

## Transport encryption

| Where | Setting | Value |
|---|---|---|
| CloudFront (`api.goxlally.ai`) | Security policy | `TLSv1.2_2021` |
| Application Load Balancer (`ally-backend-alb`, :443) | SSL policy | `ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09` |

**Minimum accepted version: TLS 1.2 at both.** TLS 1.3 is supported; TLS 1.0 and
1.1 are refused.

The policy now says "TLS 1.2 as the minimum accepted version and TLS 1.3
supported" rather than the flat "TLS 1.3" it used to. The old wording was both
unevidenced and, as it turns out, wrong in the direction that matters: it
described a floor we do not actually enforce.

## Encryption at rest

| Item | Value |
|---|---|
| Instance | `ally-postgres` (RDS) |
| Encryption at rest | Enabled |
| KMS key | `11ca1c2e-2a52-4de8-9f10-bca1fbfedea0` |
| Automated backup retention | 7 days |
| Backup window | 20:58–21:28 UTC |

The policy says "encrypted at rest under a key held in AWS Key Management
Service", which is what the console shows.

> **If a specific cipher is wanted in the policy**, AWS publishes that RDS
> encryption at rest uses AES-256 — but that comes from AWS's documentation of
> its own implementation, not from anything in our console. Cite the AWS page as
> the source if the figure goes back in, rather than asserting it as something
> we configured.

## External AI providers

Read from `model_task_routing` on production, plus the ECS task definition.

| Provider | Model | Tasks |
|---|---|---|
| **Anthropic** | `claude-sonnet-5` | answer consistency, answer interpretation, archetype assignment, diagnosis reasoning, distress detection, first impression, Founder DNA dimension resolution, next-question selection, report narrative, support answering, support routing |
| **OpenAI** | `gpt-5.4-nano` | daily quote selection |

**That is the complete list, and it is complete for a reason worth stating.**
Every one of the twelve tasks in `LLMTask.ALL` has an active routing row, so the
`LLM_PROVIDER` / `LLM_MODEL` environment fallback is never reached — and those
variables are not set in the task definition, ECS secrets or any env file. A
task added later without a routing row would fail closed with
`LLMConfigurationError` rather than quietly picking a provider nobody chose.

**No embedding provider receives anything.** `RETRIEVAL_ENABLED` defaults to
false and is not overridden, and `EMBEDDING_PROVIDER` is unset, so no text is
sent for embedding at all. Gemini adapters exist in the codebase and are
**not in use**.

### Cross-border

| Provider | Endpoint | Location |
|---|---|---|
| Anthropic | `api.anthropic.com` | Outside India |
| OpenAI | `api.openai.com` | Outside India |

Everything else — application, database, backups — is in **AWS `ap-south-1`
(Mumbai)**. The Privacy Policy already discloses the LLM step as a cross-border
transfer rather than leaving it implied.

## Not claimed, because there is no evidence

**Independent security audit or penetration test.** None has been carried out,
so the policy does not mention one. It commits to naming a specific audit if one
ever happens rather than gesturing at "regular assessments" — which is what the
previous wording did.

## Refreshing this

These are console settings and they drift. Re-read them before any compliance
submission, and change both this file and the policy's Section 8 together when
they move — a policy that quotes a figure this file no longer supports is back
to the problem it was written to fix.
