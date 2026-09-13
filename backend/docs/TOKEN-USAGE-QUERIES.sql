-- Where are founders' daily tokens actually going?
-- Run against PRODUCTION. All read-only.

-- 1. THE DECISIVE ONE: prompt vs completion split on chat calls.
--    The founder is charged prompt_tokens + completion_tokens on every turn.
--    If input_tokens dwarfs output_tokens, the budget is being spent on the
--    prompt we assemble, not on what the founder wrote or what Ally replied.
select task,
       count(*)                              as calls,
       round(avg(input_tokens))              as avg_prompt,
       round(avg(output_tokens))             as avg_reply,
       round(avg(input_tokens + output_tokens)) as avg_charged,
       max(input_tokens + output_tokens)     as worst_turn,
       round(100.0 * avg(input_tokens)
             / nullif(avg(input_tokens + output_tokens), 0), 1) as pct_prompt
from llm_call_log
where created_at >= now() - interval '7 days'
  and status = 'success'
group by task
order by calls desc;

-- 2. How fast the day is used up, per plan.
--    "tokens run out very early" -> look at hours_to_exhaust.
select f.plan_type,
       count(distinct d.founder_id)                as founders,
       round(avg(d.tokens_used))                   as avg_daily_tokens,
       max(d.tokens_used)                          as max_daily_tokens,
       count(*) filter (where d.tokens_used >= 3500 and f.plan_type = 'starter') as plus_at_ceiling,
       count(*) filter (where d.tokens_used >= 8000 and f.plan_type = 'pro')     as pro_at_ceiling
from daily_token_usage d
join founders f on f.founder_id = d.founder_id
where d.day >= current_date - 7
  and d.source = 'chat'
group by f.plan_type
order by f.plan_type;

-- 3. Cost per message: how many messages does a founder actually get?
select f.plan_type,
       count(*)                                        as chat_calls,
       round(avg(l.input_tokens + l.output_tokens))     as avg_cost_per_message,
       case f.plan_type
         when 'starter' then 3500 when 'pro' then 8000
         when 'free' then 8000 else 0 end               as daily_limit,
       round(case f.plan_type
               when 'starter' then 3500 when 'pro' then 8000
               when 'free' then 8000 else 0 end
             / nullif(avg(l.input_tokens + l.output_tokens), 0), 1)
                                                        as messages_per_day
from llm_call_log l
join founders f on f.founder_id = l.founder_id
where l.created_at >= now() - interval '7 days'
  and l.status = 'success'
group by f.plan_type;

-- 4. Does prompt size grow through a conversation? (the 20-message history
--    plus every message ever flagged `important` is re-sent on every turn)
select width_bucket(input_tokens, 0, 12000, 12) * 1000 as prompt_token_bucket,
       count(*) as calls
from llm_call_log
where created_at >= now() - interval '7 days' and status = 'success'
group by 1 order by 1;

-- 5. Anyone charged who should not be. The Rs 199 Starter tier has a limit of
--    0 and no chat feature: any row here is a founder being metered on a plan
--    that sells them nothing to meter.
select f.plan_type, count(*) as rows_, sum(d.tokens_used) as tokens
from daily_token_usage d
join founders f on f.founder_id = d.founder_id
where f.plan_type = 'basic' and d.tokens_used > 0
group by f.plan_type;

-- 6. Meter failures — usage that happened but was never charged (or was
--    double-charged on replay). Should be empty.
select count(*) as unreconciled, coalesce(sum(tokens), 0) as tokens
from unbilled_usage where resolved = false;
