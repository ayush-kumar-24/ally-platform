# Row-level security: the five tables that had none, and one that should not exist

Supabase's own security advisor flagged six tables in `public` with RLS
disabled, while every other table in the schema has it on. RLS off means the
`anon` role — the key that ships inside every browser that loads the app — can
read **and write** every row of them.

Five are fixed by migration `c9f41b8e3a07`. The sixth is not an application
table and needs a decision from you.

## What was exposed

| Table | Rows | What anon could do |
|---|---|---|
| `support_bot_misses` | — | Read every question founders asked that Ally could not answer, with `founder_id` attached |
| `coupon_redemptions` | — | Read who redeemed what, for how much |
| `coupons` | — | Read every discount code, **and create new ones** |
| `support_bot_answers` | 300 | Rewrite the help content founders are shown |
| `notification_types` | 48 | Edit the notification catalogue |
| `_perf_baseline` | 4871 | Read raw query text — see below |

Read access is the obvious half. The write access is the half worth sitting
with: nothing stopped someone holding the public key from inserting a
100%-off coupon and redeeming it.

## Why the migration is safe to deploy

The question that matters, because enabling RLS without a matching policy is
how you take an application down.

**On Supabase.** `ally_app` does not exist and the app connects as `postgres`,
which carries `rolbypassrls` — verified live with
`select rolbypassrls from pg_roles where rolname = current_user`, not assumed.
RLS is enabled with no policies: the app is unaffected, `anon` and
`authenticated` are denied. That is the whole fix.

**On RDS.** `ally_app` exists and *is* subject to RLS, so every table gets an
explicit policy for it. Founder isolation for `coupon_redemptions` (identical
to `d91c6e4b72aa`), unrestricted access for the three global tables, and a
split pair for `support_bot_misses`.

**No browser code loses access.** The frontend uses Supabase for authentication
only — it never queries a table through `supabase-js`. Every read goes through
the backend.

## The one decision worth reviewing: `support_bot_misses`

It holds `founder_id`, so the obvious move is the ordinary founder-isolation
policy. That would be wrong in both directions.

**On writes**, the public support route answers people who are not signed in
and passes `founder_id = 0` as a sentinel
(`app/api/v1/support/public.py`). Against a
`founder_id = public.get_founder_id()` predicate that insert is refused — and
`SupportMissRepository.record` swallows every failure by design, because it
runs on the path where someone is already being told we have no answer. So the
policy would not break anything visibly. It would silently stop recording
public misses, which is a worse outcome than the gap it closed.

**On reads**, nothing in the application reads this table at all. It is written
by the bot and queried by hand when someone asks what founders are stuck on.

So it gets two policies instead: `FOR INSERT WITH CHECK (true)` and
`FOR SELECT USING (<admin context>)`. Stricter than founder isolation on reads,
and correct on writes, where founder isolation is simply false.

## `_perf_baseline` — delete it, do not secure it

Not in this schema. No migration creates it, no application code reads it. It
is a `pg_stat_statements` dump left behind by the query-performance work, and
its `q` column holds **raw query text**, which can contain literal values
lifted out of real queries — that is why the advisor flagged it and why
securing a stray artifact is the wrong instinct.

It exists only on Supabase, which is why the migration does not touch it: a
migration that dropped it would be a migration dropping a table it never
created, on one target only.

**Check what is in it first.** If `q` contains values rather than
placeholders, this has been sitting world-readable:

```sql
select q from public._perf_baseline
 where q ~ '''[^'']{6,}'''
 limit 20;
```

Then drop it:

```sql
drop table if exists public._perf_baseline;
```

If you want to keep the benchmark, re-create it from
`pg_stat_statements` with `queryid` and the timings only, and leave `q` out.

## After deploying

Confirm nothing is still exposed:

```sql
select relname
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
 where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity
 order by 1;
```

Empty is the right answer once `_perf_baseline` is gone.

And on RDS specifically, confirm the policies landed:

```sql
select tablename, policyname, cmd, roles
  from pg_policies
 where tablename in ('support_bot_misses','coupon_redemptions','coupons',
                     'support_bot_answers','notification_types')
 order by tablename, policyname;
```
