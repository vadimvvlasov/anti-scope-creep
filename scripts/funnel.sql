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
