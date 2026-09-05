"""Admin & Operations.

Everything here is the real, DB-backed Admin Panel -- `panel_service.py` (RBAC,
users, credits, subscriptions, privacy requests, feedback, dashboard insights,
health), `rbac.py` (PanelRole/Capability), `panel_audit.py` (persistent audit
log), `users_db_repository.py`, `broadcasts.py`, `feature_flags.py`,
`conversations.py`, `insights.py`, `health.py`.

The Phase 12 module that used to live here -- AdminService, an in-memory
AdminRepository/AnnouncementRepository/AuditRepository, AdminUser/AdminRole --
was a separate, parallel admin backend that returned placeholder data (nothing
in it was DB-backed, so nothing it showed ever reflected reality) and every one
of its capabilities was superseded by the panel above (see the Admin Panel
Proposal's Phase 5). Removed entirely rather than left dead: the frontend
(frontend/src/services/admin.js) never called any of its endpoints, confirmed
before deletion.

Nothing imports the bare `app.admin` package -- every real caller imports the
specific submodule it needs (`app.admin.panel_service`, `app.admin.rbac`,
etc.), so this file re-exports nothing.
"""
