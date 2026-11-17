-- Demand check X3 (issue #122): is usage frequent enough for a subscription?
-- Aggregates only: no emails, IDs, titles or contract text in the output.
-- An analysis is one row of analysis_starts (upload or retry, deleted contracts included);
-- the table exists since migration 0003, so earlier analyses are not counted.
-- Read-only. Usage: psql "$DATABASE_URL" -f scripts/demand.sql
-- Decision rule (product audit, X3): at least 20% returning: a subscription is plausible;
-- below 5%: price per contract or packs; in between: no decision from this check alone.

-- 1. Return rate: accounts with analyses on 2 or more distinct UTC days within 30 days of sign-up.
--    Only accounts with a full 30-day window and at least one analysis in it.
WITH window_days AS (
    SELECT u.id, COUNT(DISTINCT (s.started_at AT TIME ZONE 'UTC')::date) AS active_days
    FROM users u
    JOIN analysis_starts s
      ON s.user_id = u.id
     AND s.started_at < u.created_at + interval '30 days'
    WHERE u.created_at <= now() - interval '30 days'
    GROUP BY u.id
)
SELECT COUNT(*)                                            AS accounts_with_full_window,
       COUNT(*) FILTER (WHERE active_days >= 2)            AS returned_on_2_plus_days,
       ROUND(100.0 * COUNT(*) FILTER (WHERE active_days >= 2) / NULLIF(COUNT(*), 0), 1)
                                                           AS return_rate_pct
FROM window_days;

-- 2. Analyses per account, all time, every account (0 = signed up, never analyzed).
WITH per_account AS (
    SELECT u.id, COUNT(s.id) AS analyses
    FROM users u
    LEFT JOIN analysis_starts s ON s.user_id = u.id
    GROUP BY u.id
)
SELECT CASE WHEN analyses = 0 THEN '0'
            WHEN analyses = 1 THEN '1'
            WHEN analyses = 2 THEN '2'
            WHEN analyses <= 5 THEN '3-5'
            WHEN analyses <= 10 THEN '6-10'
            ELSE '11+' END                                 AS analyses,
       COUNT(*)                                            AS accounts
FROM per_account
GROUP BY 1
ORDER BY MIN(analyses);

-- 3. Totals behind the numbers above, and the waitlist size that decides whether X4 can work
--    (the audit rule needs 30 or more waitlist members for the email to say anything).
SELECT (SELECT COUNT(*) FROM users)                                        AS accounts,
       (SELECT COUNT(DISTINCT user_id) FROM analysis_starts)               AS accounts_with_analyses,
       (SELECT COUNT(*) FROM analysis_starts)                              AS analyses,
       (SELECT MIN(started_at)::date FROM analysis_starts)                 AS counted_since,
       (SELECT COUNT(DISTINCT distinct_id) FROM events
         WHERE event = 'pro_waitlist_joined')                             AS waitlist_accounts;
