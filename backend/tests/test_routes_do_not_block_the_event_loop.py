"""No route may hold the event loop while it talks to the database.

Every `Session` in this codebase is SQLAlchemy's SYNCHRONOUS one, so every
query is a blocking socket read. FastAPI runs a route declared `async def`
directly on the event loop and a route declared `def` in a worker threadpool.
An `async def` route that takes `db: Session = Depends(get_db)` therefore
blocks the whole server for the duration of each of its queries -- nothing
else, on any connection, makes progress meanwhile.

Live effect this was found through: the founder dashboard fires six requests
in parallel on mount (services/dashboard.js's loadDashboard) and they were
executing strictly one after another, because /dashboard/overview alone runs
eight sequential queries on the loop. The fix is one word per handler -- drop
`async` -- and this test is what stops it being typed back in. `async def` is
still correct for a route that genuinely awaits something (an upload, an LLM
call), so this test only flags handlers that await NOTHING -- for those,
`async` buys nothing at all and costs the whole server's concurrency.

Six handlers do both (`upload_avatar`, the two `submit_answer`s,
`upload_territory_image`, `read_first_impression`, `ask`, the Razorpay
webhook): they genuinely await, and they also run sync queries on the loop
while doing it. Fixing those means pushing their DB work through
`run_in_threadpool`, which is a real change to each one rather than a
keyword, so they are deliberately out of this test's scope.
"""

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _is_route(fn: ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr in _HTTP_METHODS:
            base = target.value
            name = getattr(base, "id", None) or getattr(base, "attr", None)
            if name and "router" in name.lower():
                return True
    return False


def _awaits_something(fn: ast.AsyncFunctionDef) -> bool:
    """True when the body really uses `await` (ignoring nested async defs)."""
    for node in ast.walk(fn):
        if isinstance(node, (ast.Await, ast.AsyncWith, ast.AsyncFor)):
            return True
        if isinstance(node, ast.AsyncFunctionDef) and node is not fn:
            return True
    return False


def _takes_db(fn: ast.AsyncFunctionDef, source: str) -> bool:
    """True when get_db appears in the signature (not the body)."""
    segment = ast.get_source_segment(source, fn) or ""
    return "get_db" in segment.split("):")[0]


def test_no_async_route_depends_on_the_synchronous_session():
    offenders = []
    for path in APP.rglob("*.py"):
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if (
                isinstance(node, ast.AsyncFunctionDef)
                and _is_route(node)
                and _takes_db(node, source)
                and not _awaits_something(node)
            ):
                offenders.append(f"{path.relative_to(APP.parent)}:{node.lineno} {node.name}")

    assert not offenders, (
        "These routes are `async def` and take the synchronous `db: Session`, so "
        "every query they run blocks the event loop for the whole process. "
        "Declare them `def` -- FastAPI will run them in the threadpool:\n  "
        + "\n  ".join(offenders)
    )
