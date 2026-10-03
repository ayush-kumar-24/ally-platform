# Data Lifecycle and Raw Chat Contract

Part of the Day 1 security design package. Tags `[CODE]`, `[DECISION]`, `[UNKNOWN]` and `[PRODUCT/LEGAL DECISION]` are defined in [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md).

## 1. Lifecycle per layer

| Layer | Created by `[CODE]` | States | Ends by |
|---|---|---|---|
| L1 Account | `create_founder_on_signup` (DB function) → `ensure_founder_or_waitlist` (`app/services/provisioning.py`); `PATCH /profile*` | `active`, then `deletion_pending` (`deletion_requested_at`), then `erased` (`deletion_executed_at`) | Erasure sweep ([RETENTION_AND_ERASURE_POLICY.md](RETENTION_AND_ERASURE_POLICY.md)) |
| L2 Raw chat | `ChatExecutionService.send_message` → `SqlConversationRepository.add_message` | `active`, then `archived`, then `purged` (target, see §2) | Founder delete, retention expiry, or erasure |
| L3 Memory | Target: `MemoryService` behind the contract in [MEMORY_CONTRACT.md](MEMORY_CONTRACT.md) | `proposed`, then `confirmed`, then `archived` or `deleted` | Founder action, kind expiry, source deletion, or erasure |
| L4 Diagnosis | `DiagnosisService.start_session` / `submit_answer`; `ReasoningService._persist` | session: `in_progress`, then `completed` / `abandoned`. Report: a new version row; the previous row gets `is_active=false` | Erasure only (no founder delete, D-41) |

## 2. Raw chat contract (L2)

| # | Topic | Contract | Today |
|---|---|---|---|
| RC-1 | **Retention** | `[DECISION D-20]` Raw chat (`conversations`, `messages`, `file_uploads` + S3 objects) is purged `RAW_CHAT_RETENTION_DAYS` after the conversation's `last_message_at`. Purge is a hard delete run by a new internal job, `purge-raw-chat`, under `/api/v1/internal/jobs/`. The **value** is `[PRODUCT/LEGAL DECISION]`; the engineering default proposal is **90 days**, configurable. `0` means "never purge" and is refused in production. | `[CODE]` No TTL. Chat is kept until account erasure. |
| RC-2 | **Delete is hard** | `[DECISION D-21]` `DELETE /chat/conversations/{id}?mode=delete` must, inside one transaction: hard-delete the `messages`, the `file_uploads` rows and the `conversations` row; delete the `founder_memory` rows whose `source_conversation_id` matches and whose `status` is `proposed`; and write one `founder_memory_events` / audit event with no content. S3 objects are deleted synchronously, best effort. Any failure goes onto a `pending_object_deletions` retry list, which the purge job drains. The API answers `204` only after the DB commit. | `[CODE]` Soft delete (`status='deleted'`, `conversation.py:213`). Messages, memory and attachments are kept. |
| RC-3 | **Archive stays reversible** | `[DECISION D-22]` `mode=archive` keeps today's behaviour: hidden from the list, restorable through `/restore`, still subject to RC-1 retention. | `[CODE]` Same today. |
| RC-4 | **No restore after delete** | `[DECISION D-23]` A deleted conversation can never be restored. `POST /chat/conversations/{id}/restore` applies only to `archived`. `ConversationStatus.DELETED` is removed from the reachable states. An existing `deleted` row is purged by a one-off backfill under RC-2 semantics. | `[CODE]` `/restore` revives deleted conversations (`chat/router.py:388-396`). |
| RC-5 | **Deleted chat must not influence AI** | `[DECISION D-24]` After RC-2: no message, title, attachment text or `proposed` memory from that conversation reaches any prompt. A `confirmed` memory whose source is the deleted conversation survives, because the founder adopted it; it then has `source_conversation_id = NULL`. | `[CODE]` Raw WORKING memory copies are injected into other conversations for about 7 days. |
| RC-6 | **Attachments** | `[DECISION D-25]` Attachments follow their conversation: same retention, same hard delete, S3 object deleted. `DELETE /chat/attachments/{id}` becomes a hard delete; the archive behaviour moves to an explicit `?mode=archive`. Extracted text is never persisted (keeps `[CODE]` `context_window.py`). Attachments are never embedded and never become memory. | `[CODE]` Attachment delete only archives; S3 is never deleted (`chat/router.py:449-457`). |
| RC-7 | **Conversation titles** | `[DECISION D-26]` A title is raw chat: app-encrypted, purged with the conversation. The dashboard (`dashboard/repository.py:recent_conversations`) and admin timeline (`app/admin/insights.py`) list only `status='active'`. An auto-title is never sent to any LLM other than the conversation's own. | `[CODE]` The title is the first 60 characters of the first message, plaintext, listed regardless of status. |
| RC-8 | **In-conversation context** | `[DECISION D-27]` The prompt for a turn may include only messages of **the same conversation** (keep the last-20 rule in `ConversationService.build_context`) plus confirmed memories ([MEMORY_CONTRACT.md](MEMORY_CONTRACT.md)). No message from any other conversation, active or not. | `[CODE]` Same conversation plus raw memory from any conversation. |
| RC-9 | **"Don't Remember This"** | `[DECISION D-28]` See the table below. | `[CODE]` Does not exist. |
| RC-10 | **Admin access** | `[DECISION D-29]` See "Admin access to raw chat" below. | `[CODE]` support and super_admin can read every conversation, including deleted ones; reads are not audited. |
| RC-11 | **Memory write on chat** | `[DECISION D-30]` A chat turn never writes raw message text to `founder_memory`. The only path from chat to memory is extraction under [MEMORY_CONTRACT.md](MEMORY_CONTRACT.md) §6. | `[CODE]` Every turn writes WORKING memory (`chat_execution.py:215-226`). |
| RC-12 | **Processing restriction** | `[DECISION D-32]` `require_ai_processing_allowed_for_id` also guards `POST /chat/attachments` and the extraction job. | `[CODE]` It guards only `/chat/message` and `/chat/stream`. |

### RC-9 "Don't Remember This"

Two scopes. Both are founder-controlled and both are reversible only by turning them off going forward.

| Scope | Field | Effect |
|---|---|---|
| Message | `messages.metadata.memory_opt_out = true` (set on send via `MessageRequest.remember: bool = true`, or afterwards via `POST /chat/conversations/{id}/messages/{mid}/forget`) | The message is never sent to memory extraction. Setting it afterwards deletes every `founder_memory` row whose `source_message_id` is that message (proposed **and** confirmed), and writes an audit event. The message stays in the conversation, and therefore in that conversation's own context window, until it is deleted or reaches retention. |
| Conversation | `conversations.metadata.memory_opt_out = true` (toggle on the conversation) | As above for every current and future message in the conversation. |
| Account | `founder_settings.memory_enabled = false` | Defined in the Memory Contract §5 (disable). |

"Don't Remember This" does **not** delete the message. Deleting it is RC-2.

### RC-10 Admin access to raw chat

1. **Audit every read.** Every call to `AdminPanelService.list_conversations` or `view_conversation` writes an `admin_audit_log` row: `action = chat.list` / `chat.view`, the `target_user_id`, the `conversation_id`, and a mandatory `reason` string of at least 10 characters. The request is refused if `reason` is missing.
2. **Deleted means gone.** Deleted conversations do not exist (RC-2), so admins cannot read them.
3. **Standing access versus founder grant.** Whether `support` keeps standing `VIEW_CHATS`, or only reads a conversation the founder has shared through a time-boxed support grant, is a `[PRODUCT/LEGAL DECISION]`. The engineering recommendation is a founder grant with a 7-day expiry.
4. **No admin writes.** No admin role may edit, export or bulk-download raw chat. This keeps the `[CODE]` stance in `panel_service.py`.

## 3. Report lifecycle and versioning (L4) `[DECISION D-40]`

| Rule | Contract |
|---|---|
| Version | Each `founder_reports` row is an immutable version. A new column `report_version` (int, per founder, starting at 1) is added. The most recent row stays `is_active=true` (keeps `[CODE]` semantics). |
| Immutability | After `_persist` commits, only `narrative_snapshot`, `founder_dna._summaries/_reads`, `pdf_storage_key` and `pdf_requested_at` may be written, and only once each (write-if-null). |
| Share links | A share points at **one version**. `ReasoningRepository.repoint_shares` is removed. Regenerating a report deactivates the old version's shares; the founder must create a new link. `[CODE]` today: shares are silently moved to the new report. |
| Old versions | Superseded versions remain readable by their owner. Their PDFs are kept with the row. Pruning old versions is a `[PRODUCT/LEGAL DECISION]` (proposal: keep all while the account exists). |
| Founder delete | Founders cannot delete a single report (D-41). Removal is through erasure only. `[PRODUCT/LEGAL DECISION]` whether to add it. |
| Overwritten tables | `detected_root_causes` and `internal_intelligence_reports` stay one-per-session (delete then replace, `[CODE]`). They are not versioned. |

## 4. Founder-initiated deletion matrix (target)

| Object | Founder action | Effect |
|---|---|---|
| Conversation | Delete | RC-2 hard delete |
| Attachment | Delete | Hard delete row + S3 |
| Message | Forget (RC-9) | Derived memory deleted; the message is kept |
| Memory item | Delete | Hard delete ([MEMORY_CONTRACT.md](MEMORY_CONTRACT.md)) |
| All memory | Disable + "clear" | Hard delete of all `founder_memory` rows |
| Goal, achievement, task | Delete | Hard delete (`[CODE]` already) |
| Vision image | Delete | S3 delete (`[CODE]` already) |
| Calendar | Disconnect | Revoke + delete (`[CODE]` already) |
| Report | none | Erasure only |
| Account | `DELETE /privacy/account` | Erasure sweep after the grace period |
