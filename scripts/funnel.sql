-- Product funnel by acquisition channel, last 14 days (docs/analytics.md).
-- Each visitor is one person: anonymous IDs are mapped to the account through `identify`.
-- The channel is the visitor's first utm_source, else referrer_host, else 'direct'.
-- Read-only. Usage: psql "$DATABASE_URL" -f scripts/funnel.sql

WITH recent AS (
    SELECT * FROM events WHERE received_at >= now() - interval '14 days'
),
links AS (
    SELECT DISTINCT properties->>'anon_id' AS anon_id, distinct_id AS account_id
    FROM recent
    WHERE event = 'identify'
),
people AS (
    SELECT e.received_at, e.event, e.properties,
           COALESCE(l.account_id, e.distinct_id) AS person
    FROM recent e
    LEFT JOIN links l ON l.anon_id = e.distinct_id
),
channel AS (
    SELECT DISTINCT ON (person) person,
           COALESCE(properties->>'utm_source', properties->>'referrer_host', 'direct') AS source
    FROM people
    ORDER BY person, received_at
)
SELECT c.source,
       COUNT(DISTINCT p.person) FILTER (WHERE p.event = 'pageview')            AS visitors,
       COUNT(DISTINCT p.person) FILTER (WHERE p.event = 'signup_completed')    AS signups,
       COUNT(DISTINCT p.person) FILTER (WHERE p.event = 'analysis_started')    AS analyzed,
       COUNT(DISTINCT p.person) FILTER (WHERE p.event = 'report_exported')     AS exported,
       COUNT(DISTINCT p.person) FILTER (WHERE p.event = 'pro_cta_clicked')     AS pro_clicked,
       COUNT(DISTINCT p.person) FILTER (WHERE p.event = 'pro_waitlist_joined') AS waitlist
FROM people p
JOIN channel c USING (person)
GROUP BY c.source
ORDER BY visitors DESC;

-- X1 (guest sample, issue #125): visitors split by whether they opened /sample/* before signing up
-- (or at all, for those who never signed up), with the same 14-day window and person mapping.
WITH recent AS (
    SELECT * FROM events WHERE received_at >= now() - interval '14 days'
),
links AS (
    SELECT DISTINCT properties->>'anon_id' AS anon_id, distinct_id AS account_id
    FROM recent
    WHERE event = 'identify'
),
people AS (
    SELECT e.received_at, e.event, e.properties,
           COALESCE(l.account_id, e.distinct_id) AS person
    FROM recent e
    LEFT JOIN links l ON l.anon_id = e.distinct_id
),
per_person AS (
    SELECT person,
           MIN(received_at) FILTER (WHERE event = 'pageview' AND properties->>'path' LIKE '/sample/%') AS sample_at,
           MIN(received_at) FILTER (WHERE event = 'signup_completed')                                 AS signup_at,
           BOOL_OR(event = 'analysis_started')                                                       AS analyzed
    FROM people
    GROUP BY person
)
SELECT sample_at IS NOT NULL AND (signup_at IS NULL OR sample_at < signup_at) AS saw_sample_first,
       COUNT(*)                                                               AS visitors,
       COUNT(*) FILTER (WHERE signup_at IS NOT NULL)                          AS signups,
       COUNT(*) FILTER (WHERE analyzed)                                       AS analyzed
FROM per_person
GROUP BY 1
ORDER BY 1;
