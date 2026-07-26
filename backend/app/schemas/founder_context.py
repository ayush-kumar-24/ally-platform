from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Values mirror the founder_context CHECK constraints, so a bad value is a clean
# 422 at the API instead of a 500 from the database.
GeographicType = Literal["metro", "tier2", "tier3", "rural"]
EconomicBackground = Literal["business_family", "salaried", "financial_stress", "stable"]
EducationLevel = Literal["no_degree", "technical", "business", "first_gen_graduate"]
IndustryExposure = Literal["none", "adjacent", "deep_domain", "first_gen_in_sector"]
LanguageComfort = Literal["english_confident", "regional_primary", "bilingual", "technical_only"]
NetworkAccess = Literal["strong", "moderate", "limited", "none"]


class FounderContextRead(BaseModel):
    """Founder background/context ("memory"). All optional -- may be unset."""

    model_config = ConfigDict(from_attributes=True)

    geographic_type: str | None = None
    economic_background: str | None = None
    education_level: str | None = None
    industry_exposure: str | None = None
    language_comfort: str | None = None
    network_access: str | None = None
    context_notes: str | None = None
    updated_at: datetime | None = None


class FounderContextUpdate(BaseModel):
    """Upsert the founder's context; only the fields sent are written."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    geographic_type: GeographicType | None = None
    economic_background: EconomicBackground | None = None
    education_level: EducationLevel | None = None
    industry_exposure: IndustryExposure | None = None
    language_comfort: LanguageComfort | None = None
    network_access: NetworkAccess | None = None
    context_notes: str | None = Field(default=None, max_length=5000)
