> **Superseded 2026-09-22 by R-0370.** Observability is Grafana Cloud Free; see PLATFORM_BUILD.md. Kept as the record of the rejected option and its prices.

# Datadog for this app — what it costs, what to turn on

Researched 2026-09-13. List prices, annual-commit column, US region. On-demand (no commit) is
25–50% higher on most lines. Our stack: one 2 GB droplet, Docker Compose, Flask, Postgres, Caddy,
a phone-first TypeScript PWA, Anthropic calls.

## 1. Products that matter here

- **Infrastructure Monitoring** — the droplet: CPU, memory, disk, container health, Postgres integration.
- **Log Management** — backend and Caddy logs, shipped by the agent from Docker; frontend logs via the browser SDK.
- **APM (traces)** — request timing through Flask, Postgres queries, outbound HTTP.
- **Real User Monitoring** — what the phone browser actually experienced: load time, errors, routes.
- **Session Replay** — replays a user's session; the add-on to RUM.
- **Error Tracking** — groups backend and browser errors into issues; included with APM/RUM, no separate charge.
- **LLM Observability** — every Anthropic call as a span: prompt, response, tokens, cost, latency, evaluations.
- **Synthetic Monitoring** — scheduled uptime checks from outside; API tests are cheap, browser tests are not.
- **Product Analytics** — funnels, retention, heatmaps, built on the same RUM sessions.
- **Database Monitoring** — per-query Postgres detail. Priced per database host; skip it at our size.
- New in 2026: AI Credits ($500 per 500 credits) for the AI assistant, and Feature Flags (from $55/mo).
  Neither is worth it here.

## 2. List price per unit

| Line | Annual price | Free tier |
|---|---|---|
| Infrastructure Pro | $15 per host / mo | 5 hosts, 1-day metric retention, free forever |
| Log ingest | $0.10 per GB | none |
| Log indexing, 15-day retention | $1.70 per million events | none |
| Log Flex storage | $0.05 per million events stored | none |
| APM (with infra) | $31 per host / mo | none |
| RUM Measure (all sessions) | $0.15 per 1,000 sessions | none |
| RUM Investigate (the subset you keep) | $3.00 per 1,000 sessions | none |
| Session Replay | $2.50 per 1,000 sessions | none |
| Product Analytics | $1.50 per 1,000 sessions | none |
| Error Tracking | included | — |
| LLM Observability | $160 / mo for 100,000 spans (Pro) | 40,000 spans free |
| Synthetic API tests | $5 per 10,000 runs | 10,000 runs / mo free |
| Synthetic browser tests | $12 per 1,000 runs | 500 runs / mo free |

The per-span rate above the LLM Observability included tier is not published. Get it in writing before
relying on it.

## 3. Two scales, everything on

Assumes 1 host, 1 APM host, 2 GB logs a month, 4 million log events, every session investigated and replayed,
one API uptime check every 5 minutes (8,640 runs, inside the free tier).

| Line | 10 users, 300 sessions | 200 users, 6,000 sessions |
|---|---|---|
| Infrastructure | $15 | $15 |
| Log ingest 2 GB | $0.20 | $0.20 |
| Log indexing 4M events | $6.80 | $6.80 |
| APM | $31 | $31 |
| RUM Measure | $0.05 | $0.90 |
| RUM Investigate | $0.90 | $18.00 |
| Session Replay | $0.75 | $15.00 |
| Product Analytics | $0.45 | $9.00 |
| LLM Observability | $0 (under 40k spans) | $160 |
| Synthetics | $0 | $0 |
| **Total** | **about $55 / mo** | **about $256 / mo** |

The two jumps are LLM Observability crossing 40,000 spans, and APM plus Infrastructure being a flat $46
floor whether five people use the app or five hundred.

## 4. Staying under about $30 a month

Turn on now:

1. Infrastructure Monitoring, one host: $15. The baseline.
2. Logs, ingest only, with exclusion filters so health checks and static asset lines never index.
   Index only warnings and errors, roughly 200,000 events: about $0.55.
3. LLM Observability inside the free 40,000 spans. A beta of tens of users will not reach it.
   Set a monitor on span count so the $160 tier is a decision, not a surprise.
4. One synthetic API check every 5 minutes: free.
5. Browser SDK for logs and Error Tracking only, no RUM sessions billed yet.

Runs about **$16 a month**.

Add when the beta has real traffic:

- APM at $31 puts the whole bill over $30 on its own. Add it only when a latency question is costing you
  more than the money, or run traces at a 10% sample against a shorter retention.
- RUM plus Session Replay at 300 sessions is under $2 — cheap and worth it once you have users to watch.
  Investigate only sessions with an error, which keeps the blended rate near $0.75 per 1,000.
- Product Analytics after RUM, once there is enough behaviour to analyse.
- Skip Database Monitoring and browser synthetic tests entirely at this size.

## 5. Integration shape

- **Agent**: a `datadog/agent` container in the Compose file with the Docker socket and `/proc` mounted,
  `DD_LOGS_ENABLED=true` and `DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL=true`. Exclusion filters live in the
  agent config so noisy lines are dropped before ingest, not after. Enable the Postgres integration there.
- **Backend**: `ddtrace-run` in front of the Flask entrypoint, or `ddtrace.auto` imported at startup.
  Log correlation on, so a trace links to its log lines.
- **Browser**: the RUM SDK and the browser logs SDK in the PWA entry file, with the session replay option
  and a sample rate. Point both at the same service name as the backend so a slow page links to its trace.
- **Anthropic calls**: the LLM Observability SDK wraps the Anthropic client. No prompt rewriting needed;
  it records model, tokens, cost and latency per call, and it is where a bad answer gets traced back to a prompt.

## Sources

- https://www.datadoghq.com/pricing/
- https://docs.datadoghq.com/account_management/billing/pricing/
- https://docs.datadoghq.com/llm_observability/monitoring/cost/
- https://rumcost.com/datadog-rum-pricing
- https://last9.io/blog/datadog-pricing-all-your-questions-answered/
- https://cubeapm.com/pricing-calculator/datadog/
