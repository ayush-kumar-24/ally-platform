from pydantic import BaseModel


class FieldStatus(BaseModel):
    field: str
    label: str
    section: str
    required: bool
    filled: bool


class ProgressResponse(BaseModel):
    fields: list[FieldStatus]
    filled: int
    total: int
    percent: int
    required_filled: int
    required_total: int
    profile_completed: bool


class MissingField(BaseModel):
    field: str
    label: str
    section: str


class ValidationResponse(BaseModel):
    valid: bool
    missing: list[MissingField]
