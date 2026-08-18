from typing import Literal

from pydantic import BaseModel

# Where the recording came from. Gating differs by context: diagnosis and
# founder_dna are free for every plan; chat requires a paid plan (see
# errors.VoiceUpgradeRequiredError).
#
# founder_dna was missing here until 2026-08-18 even though FounderDnaChat.jsx
# has always sent it -- so every voice recording on that page 422'd on the
# Literal and voice simply never worked there. It shares VOICE_DIAGNOSIS
# rather than getting its own feature: the phase is a mandatory step before
# the diagnosis, so gating it behind a paid plan would wall free founders out
# of a step they cannot skip.
VoiceContext = Literal["diagnosis", "chat", "founder_dna"]


class TranscriptionResponse(BaseModel):
    text: str
