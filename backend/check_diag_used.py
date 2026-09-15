import os
import sqlalchemy as sa

eng = sa.create_engine(os.environ["E2E_DB"])
ids = (3704, 3705, 3706, 7575, 7930, 11491)
with eng.connect() as conn:
    rows = conn.execute(sa.text(
        "select founder_id, stage_id, diagnosis_used from founders where founder_id = any(:ids)"
    ), {"ids": list(ids)}).all()
    for r in sorted(rows, key=lambda r: r.founder_id):
        print(f"  founder_id={r.founder_id}  stage_id={r.stage_id}  diagnosis_used={r.diagnosis_used}")
