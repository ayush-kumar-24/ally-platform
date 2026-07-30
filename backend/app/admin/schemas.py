"""Domain input value objects for the admin module. (API request models live in
app/api/v1/admin/schemas.py.)"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnnouncementDraft:
    title: str
    body: str
    audience: str = "all"
