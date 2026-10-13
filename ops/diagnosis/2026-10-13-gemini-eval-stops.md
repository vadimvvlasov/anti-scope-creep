# 2026-10-13: the Gemini eval chain stopped twice, for two different reasons

| | |
|---|---|
| Severity | low: local eval tooling, not prod; no result was lost (the eval cache resumes) |
| Detected by | the eval chain itself: a non-zero exit stopped the loop; the run log in the session scratchpad |
| Investigated by | Claude Code, while running the chain, from the run log and one probe request |
| Fixed in | the run commands (an argument array); no code change |

## Symptom

A chain of six `python -m evaluation run --provider gemini ...` runs (about 430 requests,
the daily quota resets at 12:00 Yekaterinburg time) stopped twice before finishing.

## Timeline (Yekaterinburg time, UTC+5)

| Time | Event |
|---|---|
| 12:07:35 | chain started; `v4-holdout` finishes its last missing contract |
| 12:08:28 | `v4b-holdout` starts |
| 12:09:16 | stop 1: `RemoteProtocolError`, then `HTTP 429` on 5 attempts → `GroqError: Groq request failed after 5 attempts (last: HTTP 429)` |
| 12:09 | probe request with the same key and model, between the stop and the restart: `200` |
| 12:09:45 | chain restarted with a 90-second pause and up to 3 tries per run; `v4b-holdout` completes (20 of 20) |
| 12:16:33 | stop 2: `v3-holdout` fails in 1 second, three times in a row: `__main__.py: error: unrecognized arguments: --findings-prompt ../eval/prompts/findings-v3.txt` |
| 12:21:00 | restarted with the arguments passed as an array |
| 12:48:35 | chain finished: every run complete, 0 failed contracts; later `429` series were absorbed by the retries |

## Investigation

### Stop 1: `429`

```text
Groq gemini-3.5-flash-lite attempt 1 failed: RemoteProtocolError
Groq gemini-3.5-flash-lite attempt 1 failed: HTTP 429
...
Groq gemini-3.5-flash-lite attempt 5 failed: HTTP 429
app.groq_client.GroqError: Groq request failed after 5 attempts (last: HTTP 429)
```

(The client class is shared by both providers, hence "Groq" in Gemini lines.)

1. **Daily quota used up?** No. A probe request right after the stop returned `200`, and
   the restarted chain completed all remaining runs the same day.
2. **Per-minute limit?** Yes, as far as the evidence goes. The client spaces Gemini
   requests at 10 per minute (the free tier allows 15), but the provider still answered
   `429` for a short window. `v4b-holdout` started at 12:08:28 and stopped at 12:09:16,
   after 3 contracts and 5 failed attempts: all the retries fit in less than a minute.
   Without a `retry-after` value the client uses exponential backoff (2 + 4 + 8 + 16 s,
   about 30 s), which can end inside the same one-minute window.
3. **Why the provider counted more than 10 per minute is not known.** The
   `RemoteProtocolError` just before shows a dropped connection; a retried request may
   count twice on the provider side. The logs cannot confirm it.

### Stop 2: `unrecognized arguments`

The command built the optional flag as `${prompt:+--findings-prompt $prompt}`. In bash
that unquoted expansion splits into two arguments. The shell was zsh, which does not
split unquoted parameter expansions, so `argparse` received one argument,
`"--findings-prompt ../eval/prompts/findings-v3.txt"`, and rejected it. The failure was
immediate and identical on every try, which pointed at the command, not the provider:
a provider problem never fails in under a second three times in a row.

## Root cause

- Stop 1: the retry budget (about 30 s of backoff) is shorter than the provider's
  one-minute rate-limit window.
- Stop 2: a bash-only idiom in a command run under zsh.

## Fix

- The chain retries a stopped run up to 3 times with a 90-second pause; the cache makes
  every retry continue where it stopped.
- Arguments are built as an array: `args=(...); [ -n "$prompt" ] && args+=(--findings-prompt "$prompt")`,
  then `"${args[@]}"`, which behaves the same in bash and zsh.

## Prevention

- When a provider sends no `retry-after`, the backoff should cover at least one full
  rate-limit window (60 s for per-minute limits). Candidate change: a longer base delay
  or more attempts for the Gemini client in the eval; not done yet.
- Tell a provider limit from an own error by the shape of the failure: `429` after
  several seconds of retries is the provider; the same error in under a second on every
  try is the command or the code.
- Scripts that others copy from notes use arrays for optional arguments.

## Access during the investigation

The run log, the eval cache in `eval/runs/` and one probe request with the developer's
Gemini key, read from a local file into an environment variable and never printed.
No prod system was involved.
