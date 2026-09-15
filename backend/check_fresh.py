import os
import sqlalchemy as sa

eng = sa.create_engine(os.environ["E2E_DB"])
with eng.connect() as conn:
    rows = conn.execute(sa.text("""
        select f.founder_id, f.stage_id, f.plan_type,
               count(s.session_id) filter (where s.status = 'completed') as completed_sessions
        from founders f
        join founder_consents c on c.founder_id = f.founder_id
        left join sessions s on s.founder_id = f.founder_id
        where f.profile_completed = true
        group by f.founder_id, f.stage_id, f.plan_type
        having count(s.session_id) filter (where s.status = 'completed') = 0
        order by f.founder_id
    """)).all()
    print(f"{len(rows)} founder(s) genuinely never completed a diagnosis:")
    for r in rows:
        print(f"  founder_id={r.founder_id}  stage_id={r.stage_id}  plan={r.plan_type}")
