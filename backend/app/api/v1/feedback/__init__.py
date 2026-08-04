"""Founder feedback: stars, and words if they have any.

The founder_feedback table has existed since the schema was laid down --
migrated, indexed, constrained to a 1-5 rating, with foreign keys to the
session and report a rating might be about. It had no write path at all, so it
was permanently empty, and the learning engine and eval harness that read from
it had nothing to work with (see backend/docs/learning_engine.md).

This is that write path. Three moments ask for it:
  diagnosis_rating  right after a diagnosis completes  -> session_id
  report_rating     once they have read the report     -> report_id
  general           whenever they want, from the dashboard
"""
