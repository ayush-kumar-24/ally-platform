"""Report generation for the reasoning pipeline.

`ReportGenerator` assembles typed report DTOs (presentation only, no
recomputation); renderers project them to markdown / dict / (future) PDF.
"""

from app.api.v1.reasoning.reporting.generator import ReportGenerator
from app.api.v1.reasoning.reporting.renderers import (
    DictReportRenderer,
    MarkdownReportRenderer,
    ReportRenderer,
)
from app.api.v1.reasoning.reporting.schemas import (
    BusinessProfile,
    FounderProfile,
    FounderReport,
    InternalReport,
    ReasoningBundle,
)

__all__ = [
    "ReportGenerator",
    "DictReportRenderer",
    "MarkdownReportRenderer",
    "ReportRenderer",
    "ReasoningBundle",
    "FounderProfile",
    "BusinessProfile",
    "FounderReport",
    "InternalReport",
]
