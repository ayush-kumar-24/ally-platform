"""The document versions currently in force.

Bump these when the Terms of Service or Privacy Policy materially changes. The
service compares a founder's stored record against these to answer
`needs_reconsent` -- which is how a policy update re-prompts existing users
(GDPR Art 7(3) / recital 42: consent must relate to the specific text shown).

Keep these in lockstep with the frontend's `CURRENT_VERSIONS` in
`src/services/consents.js` and the version tag rendered on the Login screen.
"""

CURRENT_TERMS_VERSION = "1.0"
CURRENT_PRIVACY_VERSION = "1.0"
