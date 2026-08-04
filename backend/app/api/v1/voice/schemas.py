from typing import Literal

from pydantic import BaseModel

# Where the recording came from. Gating differs by context: diagnosis is free
# for every plan; chat requires a paid plan (see errors.VoiceUpgradeRequiredError).
VoiceContext = Literal["diagnosis", "chat"]


class TranscriptionResponse(BaseModel):
    text: str
