"""Runnable jobs, for a scheduler to invoke as a process.

Everything in here is a `python -m app.jobs.<name>` entrypoint: it opens its own
database session, does one unit of work, logs what it did, and exits 0 on success
or non-zero on failure. Nothing here is imported by the API.

WHY THESE EXIST SEPARATELY FROM /internal/jobs/*. The HTTP sweeps are the right
shape when something already has an authenticated caller and wants a response.
A scheduler does not: it wants a process it can run, whose exit code means
something, and whose failure shows up as a failed task rather than a 200 with a
sad JSON body. Handing EventBridge a Python one-liner instead is fragile in a way
that only reveals itself at 3am, so the entrypoint lives here where it can be
tested.

Both routes call the same underlying function, so neither is a second
implementation of the work.
"""
