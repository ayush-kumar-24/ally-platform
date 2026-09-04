"""Admin HTTP API -- transport only, every rule lives in AdminPanelService (or,
for flags/broadcasts/usage, the container-composed service each endpoint calls
directly). `panel_router.py` and `panel_router_v2.py` are both mounted under
`/admin` from `app/api/v1/router.py`; import each directly.

The Phase 12 router that used to live here (`router.py`, plus its own
`dependencies.py`/`responses.py`/`schemas.py`) is gone -- see `app/admin/
__init__.py` for why.
"""
