# Demand checks before pricing (#122), 2026-11-17

Prepared for the owner's pricing decision. Part 1 (prices and unit economics) is desk research and
arithmetic, done now. Parts 2 and 3 (X3, X4) are run by the owner; their results get added here. The audit's
experiments are in `docs/reviews/anti-scope-creep-product-audit-2026-11-16.md`, section I.

## 1. Price corridor

All pages checked 2026-11-17. **UNVERIFIED** = seen only in a directory or search snippet, or the vendor
page did not load. Many competitors are small indie products launched in 2026; their prices move.

### Direct AI contract checkers

| Product | Free | Paid | Behind the paywall | Source |
|---|---|---|---|---|
| ClauseCheck | 5 scans/month | $3.99/month; $39 lifetime (first 500) | negotiation email, DOCX redlines, PDF export, unlimited scans | clause-check.app |
| ClearTerm | 5/month with an account | $9 for 20 scans, about 1 year | negotiation email, archive | clearterm.app |
| Lexitize | 3/month, top 3 red flags only | $6.99 for 5 reviews (no expiry); $12.99-79.99/month | suggestions, PDF export, volume | lexitize.com/pricing |
| ClauseShield | 3/month | $15/month (15); $29/month unlimited | volume only | clauseshield.app |
| VeriClause | 1 analysis, lifetime | S$9/month; S$29/month | | vericlause.vercel.app/pricing |
| ContractGuard (pages.dev) | 3/month | price not shown | volume | contractguard.pages.dev/pricing |
| ContractGuard (BYO key) | own API key, about $0.05 | $2.99 PDF report | report | Product Hunt, UNVERIFIED |
| ContractReview | 3/month | $9.99/month, $79/year | tracked-changes DOCX | UNVERIFIED |
| ClauseCatch | explainer | $39 per review | full review | UNVERIFIED |
| ClauseGuard AI, ClauseShift, ContractScan AI | 3/month | $7/month; $9-29/month; $19-49/month | | UNVERIFIED |

### Broader tools and the human alternative

| Option | Price | Source |
|---|---|---|
| Rocket Lawyer | $149/year or $34.99/month, **unlimited AI red-flag reviews on every plan**; attorney $149 per 30 min | rocketlawyer.com/pricing |
| LegalZoom Business Attorney Plan | $469/year ($39/month), attorney review of a document up to 10 pages | legalzoom.com |
| Fiverr contract review | $100-400 typical, $50 at the low end | UNVERIFIED |
| US lawyer, simple review | $300-1,000 flat, $200-500/hour | UNVERIFIED |
| UK solicitor, basic review | £200-500 fixed | UNVERIFIED |
| Freelancer tools in general | median entry price $18/month (Fastlancer, 636 tools, Sep 2026); Bonsai from $9-15/month | fastlancer.org, hellobonsai.com |

### What it says

- **Floor: free.** Every direct competitor has a free tier of 3-5 scans a month, and Rocket Lawyer bundles
  unlimited AI reviews. Charging for the first look does not work.
- **Paid AI checkers sit at $4-15.** Subscriptions at $4-15/month, packs at $7-9 for 5-20 contracts. Packs
  and lifetime deals are common because people sign contracts rarely.
- **Ceiling: a human, $100-600 per contract.** The only bounded human option near our range is LegalZoom at
  $39/month.
- **What others charge for is what we have:** the negotiation email, export (PDF, DOCX redlines), volume.
- **Open gaps:** no competitor found claims to check its quotes against the contract text. Privacy is a
  common claim (no storage, no training, parsing in the browser), but only one pre-launch open-source project
  claims fully local processing. The local model (#121) would make "the text never leaves our server" true.
- **The current fake door is above the market and sells the wrong thing.** $19/month for more analyses per
  day is the median price of a whole freelancer tool, while checkers that already include the email charge
  $4-10/month. Undercutting is not a lever: the floor is free. The levers are the result (email, export) and
  verifiable, private output.

## 2. Unit economics (estimate)

| Item | Per contract | Basis |
|---|---|---|
| GPU time | 2-4 min | eval: 123 s on freelance contracts, about 240 s on the CUAD held-out (#121) |
| Electricity | under $0.01 | about 350 W x 4 min = 0.023 kWh; at $0.10-0.30/kWh, $0.002-0.007 |
| Server, disk, network | 0 extra | the home server is already paid for (`docs/self-host.md`) |
| Payment fee | the main cost | Paddle (merchant of record) 5% + $0.50; Stripe Managed Payments about +3.5% on top of card fees; Lemon Squeezy takes no new sign-ups |

The fee per sale for a merchant of record (taxes and VAT handled for us), Paddle as the example:

| Price | Fee | Kept | Fee share |
|---|---|---|---|
| $3 (one contract) | $0.65 | $2.35 | 22% |
| $9 (pack) | $0.95 | $8.05 | 11% |
| $19 | $1.45 | $17.55 | 8% |
| $39 (year or lifetime) | $2.45 | $36.55 | 6% |

- The variable cost is close to zero at any price. Small tickets lose most to the payment fee: below about
  $9 a single sale is inefficient, so packs or annual prices beat a $3 single contract.
- The real limits are not money:
  - **Capacity.** One slot at 2-4 min is 15-30 contracts an hour when the GPU is free, and the GPU is shared.
  - **The owner's time.** Support, refunds and account recovery (#128).
  - **Paid-promise risk.** Availability of a single home server (#130); legal framing (`docs/spec.md`, Legal
    positioning).
- Break-even is fixed costs only: the payment provider has no monthly fee, and the domain and server already
  exist. A handful of sales a month covers the cash costs; what the owner's time is worth decides whether it
  is worth doing.

## 3. X3: how often do people come back

`scripts/demand.sql`, read-only, aggregates only. The owner runs it on prod:

```bash
psql "$DATABASE_URL" -f scripts/demand.sql     # plain postgresql:// form, prod connection string
```

It prints:

1. The share of accounts that analyzed contracts on 2 or more distinct days within 30 days of sign-up. Only
   accounts whose 30-day window has closed are counted.
2. Analyses per account, in buckets.
3. Totals and the waitlist size.

Analyses are counted from `analysis_starts`, so only since migration 0003. The owner's own and test accounts
are included; note how many there are and subtract them.

| Return rate | Reading (audit rule) |
|---|---|
| at least 20% | a subscription is plausible |
| 5-20% | no decision from X3 alone |
| below 5% | price per contract or packs |

With few accounts (under about 30 with a full window), read the counts, not the percentage.

Results (to be filled in by the owner): *not run yet.*

## 4. X4: ask the waitlist

Only to accounts that joined the Pro waitlist: they asked to hear about Pro, and registration has no email
verification, so other accounts may not be real addresses. Get the list as `analytics.md` describes: join
`pro_waitlist_joined.distinct_id` with `users.id`. If the waitlist has fewer than 30 people, the audit rule
cannot give a "kill" signal; send anyway, treat replies as interviews, and add 5-10 freelancer interviews
around the guest sample (X5).

Draft (plain text, from the owner's own address, no tracking):

```text
Subject: Quick question about Anti-Scope Creep Pro

Hi,

You joined the waitlist for Anti-Scope Creep Pro, so I'd like to ask three short questions before I decide
what Pro should be. A one-line reply is plenty.

1. How many client contracts do you sign or review in a year?
2. What would you pay to have one contract checked, with the risky clauses, suggested replacement wording
   and a ready email to the client? A number is perfect, "nothing" is a useful answer too.
3. Do you ever check contracts for someone else (clients, a team, other freelancers)?

Pro is not available yet and nothing will be charged without asking you first.

Thanks,
<your name>
```

| Replies | Reading (audit rule) |
|---|---|
| at least 5 replies that name a price | demand is real enough to design billing |
| fewer than 3 replies from 30 or more sent | too weak to build billing |

Record counts and anonymized quotes only, no names or emails.

Results (to be filled in by the owner): *not sent yet.*

## 5. Preliminary direction (for the owner to decide after X3 and X4)

- Keep a free tier that shows the findings, as every competitor does. That is the free entry, not "5 a day".
- Charge for the result: the negotiation email and the PDF/DOCX export with suggested wording (#123).
- If X3 shows rare use, which is the likely case: a **pack that does not expire** (about 5 contracts for
  $9-15) or a **low annual price** ($39-59). Not $19/month.
- If X3 shows 20% or more coming back: a monthly plan at about $5-10, in line with checkers that include the
  email.
- Lead with what competitors don't claim: quotes checked against the contract, and the text processed on our
  own server (after #121).
- Billing waits for #128-#130 in any case.
