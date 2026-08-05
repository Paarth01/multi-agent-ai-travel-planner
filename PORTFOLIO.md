# TripSync AI — Portfolio Writeup

Different lengths for different places. Pick what fits.

---

## Live links

- **Live demo:** https://multi-agent-ai-travel-planner-rho.vercel.app
- **GitHub:** https://github.com/Paarth01/multi-agent-ai-travel-planner
- **API (backend, for reference — not meant to be browsed directly):** https://tripsync-api-f3gb.onrender.com
- **Data service (backend, for reference):** https://tripsync-data-service.onrender.com

Note: the backend services are on Render's free tier and spin down
after 15 minutes of inactivity — the first request after idle time can
take 30-60s to wake up. Worth a one-line heads-up if you're sending
this link to someone ("first load might be slow, it's a free-tier
cold start, not a bug").

---

## GitHub repo setup

**Repo name:** `multi-agent-ai-travel-planner`
(keyword-first for GitHub search/discovery; keep "TripSync AI" as the
project's display name in the README's H1, not the repo name itself)

**Description** (GitHub "About" field):
> Multi-agent AI travel planner built with LangGraph — 4 specialized agents (flight, hotel, activity, pricing) coordinate in real time via a budget negotiation loop. FastAPI + SSE backend, React/TypeScript frontend, real Indian travel pricing datasets, 126 tests. Live demo: multi-agent-ai-travel-planner-rho.vercel.app

**Topics** (add via the gear icon next to "About"):
```
langgraph
multi-agent-systems
ai-agents
llm-orchestration
fastapi
react
typescript
python
server-sent-events
redis
docker
pytest
tailwindcss
travel-planner
real-time
```

---

## Resume bullet points (pick 2-3, not all)

- Built a multi-agent AI travel planner using **LangGraph**, orchestrating 4 specialized agents (flight, hotel, activity, pricing) with **parallel execution** and a **cross-agent budget negotiation loop** that reallocates ceilings and re-runs only the affected agent — not a full restart — when a trip exceeds budget
- Designed a 3-tier data-sourcing strategy (self-hosted real datasets → third-party APIs → synthetic fallback) so the system degrades gracefully instead of failing when any single data provider is unavailable, rate-limited, or unconfigured
- Sourced and aggregated a 300K-row real-world flight pricing dataset and a 134K-row hotel booking dataset into a self-hosted FastAPI microservice, reducing external API dependency to zero for the primary demo path
- Implemented a Redis-backed caching layer (with automatic in-memory fallback) across all live data sources, using cache keys scoped to search parameters rather than budget state — so repeated queries during the negotiation loop are served from cache without going stale on price changes
- Built the full stack: FastAPI + Server-Sent Events streaming backend, React/TypeScript/Tailwind frontend consuming the live event stream, 126 automated tests across unit, integration, and API layers

---

## One-line pitch (LinkedIn headline / GitHub repo description)

> Multi-agent AI travel planner (LangGraph) that negotiates flight/hotel/activity budgets across specialized agents in real time — built on real Indian travel pricing data, not just mocked responses.

---

## GitHub README hero paragraph

TripSync AI plans a complete trip — flights, hotels, day-by-day
activities — from a budget, destination, and dates. Under the hood,
four specialized agents (flight, hotel, activity, pricing) run in
parallel under a LangGraph orchestrator. When the combined cost exceeds
budget, a negotiation loop kicks in: the pricing agent identifies which
single category is most over its allocation, shrinks that ceiling, and
re-invokes only that one agent — not the whole plan — before
re-checking the total. This repeats up to a capped number of rounds,
then ships a "best effort" itinerary if it still doesn't fit, rather
than failing outright.

Rather than relying entirely on third-party APIs, the flight and hotel
agents are backed by a self-hosted data service built on real datasets
— 300K+ real 2022 Indian domestic flight fares and 134K+ real hotel
booking records — so the demo runs on genuine pricing statistics with
zero external dependency. Amadeus and Google Places APIs are wired in
as a broader-coverage fallback tier, with mock data as the final
safety net, so the system never fails a trip plan just because one
upstream provider is down or unconfigured.

---

## Interview talking points (STAR-style, for when someone asks "walk me through a project")

**The architecture decision I'd lead with:** the negotiation loop.
Most "multi-agent" demos are just a router calling different tools —
this one has actual agent-to-agent coordination through shared
LangGraph state, where agents don't call each other directly, they
negotiate through a mediator (the pricing agent) that decides which
single agent to re-invoke and with what new constraint. That's a
meaningfully different pattern from simple task delegation, and it's
the piece worth explaining in depth if asked to go deeper.

**A real bug I'd mention if asked "what went wrong along the way":**
the mock price generators originally scaled proportionally to the
budget ceiling — meaning a tiny budget always "fit" itself, since the
fake price shrank right along with it. That made the negotiation loop
undemonstrable; a $10 budget for a flight looked exactly as affordable
as a $10,000 one. Fixed by adding an absolute price floor, mirroring
how real flights/hotels have a floor cost regardless of budget — a
good example of a subtle correctness bug that only shows up when you
actually try to demo the "interesting" failure path, not the happy path.

**A design tradeoff I'd defend if pushed:** caching by search
parameters (route/city/dates), not by budget ceiling. This means a
reallocation round re-querying the same route during negotiation hits
cache instead of re-fetching from a rate-limited provider — realistic
behavior, since real APIs would be queried by route/date regardless of
what budget filtering happens downstream. The alternative (caching the
final filtered pick) would be simpler but wouldn't reflect how real
travel APIs are actually queried.

**If asked about testing:** 126 tests, deliberately including tests
that caught real bugs during development — not just tests written to
pass. Two examples: a test asserting "every category respects its own
ceiling" caught an edge case where ceilings had drifted after prior
reallocation rounds and no longer summed to the total budget; a test
on the live-API fallback logic caught a bug where a data source was
marked "live" before confirming the live call actually returned
results, so an empty response silently reported the wrong source.

**The strongest story, if there's time for it — a real production
debugging session during deployment:** after deploying to Render, live
testing showed the negotiation loop burning all 3 rounds on a hotel
search even though the real hotel price never changed between rounds.
Root cause: neither the self-hosted data service nor Amadeus accept a
price ceiling as a search parameter — they only take city/dates — so
shrinking the ceiling and re-querying returned the exact same
"cheapest available" result every time. Fixed it by having each agent
flag when its cheapest available option is already at its real-data
floor, so the pricing agent can recognize a category has no cheaper
option to find and skip straight to a "best effort" itinerary instead
of wasting rounds and duplicate network calls.

The interesting part for an interview isn't the fix itself, though —
it's what happened *verifying* it. The first "confirmation" test still
showed the old 3-round behavior after redeploying. Rather than assume
the fix was wrong, the deploy pipeline was checked directly (diffing
GitHub's actual file contents against the intended fix) — which
revealed an AI coding assistant (Copilot) had applied the described
change to the *wrong* return block: it added the new field to the
exception-handling path instead of the success path, and even
introduced a latent `NameError` in the process by swapping `None` for
a variable that didn't exist in that scope. The bug was invisible from
reading the diff casually — it only showed up by diffing actual
deployed file content byte-for-byte against intent, and by reproducing
the exact scenario locally with `graph.stream()` tracing to watch
state field-by-field. That's a genuinely good story about not trusting
"looks right" and verifying against ground truth instead — especially
relevant now that AI-assisted coding is common and can introduce
subtle, syntactically-valid-but-semantically-wrong changes.

---

## What NOT to claim

Worth being precise about, since overclaiming is easy to get caught out
on in an interview:

- The flight/hotel data is real but *not live* — it's real historical
  statistics sampled at request time, not current market prices.
- The activity/attraction fee data is real but hand-curated from ~15
  sources, not bulk-aggregated like the flight/hotel data — a
  meaningfully smaller and more manual effort, worth describing
  accurately rather than implying it's the same kind of dataset.
- Coverage is narrow by design: 6 cities for flights, 4 for hotels, 4
  cities/2 categories for activities. It's honest, not misleading, but
  worth knowing cold so you're not caught flat-footed if someone tries
  a route outside that coverage during a live demo.
