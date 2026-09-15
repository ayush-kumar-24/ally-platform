import os
os.environ.setdefault("DATABASE_URL", os.environ["E2E_DB"])
os.environ.setdefault("SECRET_KEY", "check-only-not-a-real-secret")

from app.db.session import SessionLocal
from app.models import Founder
from app.services.profile_progress import validate_profile

for fid in (7575, 7930, 11491):
    with SessionLocal() as db:
        f = db.get(Founder, fid)
        result = validate_profile(f)
        status = "READY" if result.get("valid") else "NOT READY"
        print(f"founder_id={fid}  {status}")
        if not result.get("valid"):
            missing = [m["label"] for m in result.get("missing", [])]
            print(f"    missing: {missing}")
