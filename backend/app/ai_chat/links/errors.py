"""Link errors (Phase 6, Milestone 4)."""

from app.ai_chat.errors import ChatError


class LinkError(ChatError):
    """Base for link failures."""


class InvalidLinkError(LinkError):
    def __init__(self, url: str):
        super().__init__(f"'{url}' is not a valid http(s) URL.", status_code=422)
