import os
import sqlalchemy as sa

eng = sa.create_engine(os.environ["E2E_DB"])
with eng.connect() as conn:
    rows = conn.execute(sa.text("""
        select f.founder_id, f.profile_completed, f.stage_id,
               exists(select 1 from founder_consents c where c.founder_id = f.founder_id) as has_consent
        from founders f
        order by f.founder_id
    """)).all()
    print(f"{len(rows)} founder(s) total")
    ready = [r for r in rows if r.profile_completed and r.has_consent]
    print(f"{len(ready)} fully onboarded (profile complete + consent given):")
    for r in ready:
        print(f"  founder_id={r.founder_id}  stage_id={r.stage_id}")
