"""Reports API response models. The owner view carries facts; the shared view is a
strict subset -- prose only, no facts, no IDs, no reasoning internals."""

from datetime import datetime

from pydantic import BaseModel


class SectionOut(BaseModel):
    key: str
    heading: str
    prose: str
    facts: dict = {}


class ReportView(BaseModel):
    """Owner view -- full report."""

    report_id: int
    variant: str
    tone_persona: str | None = None
    generated_at: datetime | None = None
    exposes_numeric_scores: bool = True
    sections: list[SectionOut]
    unpopulated_sections: list[str] = []


class SectionSlice(BaseModel):
    """A single-section endpoint (founder-dna / business-dna / recommendations)."""

    report_id: int
    section: SectionOut | None


class InsightsView(BaseModel):
    report_id: int
    variant: str
    sections: list[SectionOut]


class SharedSection(BaseModel):
    heading: str
    prose: str


class SharedReportView(BaseModel):
    """Public, token-scoped. Strictly less than the owner view: prose + headings
    only. No facts, no scores internals, no intervention IDs, no reasoning."""

    variant: str
    sections: list[SharedSection]


class ShareCreated(BaseModel):
    share_token: str
    share_url: str
    expires_at: datetime
