# Catalyst International Trader — System Analysis

**Name of Application:** Catalyst Trading System
**Name of file:** catalyst-intl-trader-analysis-2026-10-14.md
**Date:** 2026-10-14
**Scope:** `catalyst-international/` (HKEX, Moomoo paper trading) on the intl droplet
**Method:** Code review of the files each container runs, plus Docker logs, port state and daily reports. The only system change was binding the local Postgres container to localhost (see 2.3).
**Related:** `Documentation/Implementation/Catalyst-Intl-Droplet-Hardening-Checklist.md`

---

## Executive summary

The trader has been effectively down since **2026-06-03 11:36 HKT**. The coordinator (the brain) froze mid-cycle on an MCP call with no timeout. It has made no decisions for over four months. Meanwhile:

- the organ containers still report "healthy";
- the daily report script kept generating reports;
- the position monitor keeps raising EXIT recommendations that nothing acts on.

Stop-losses are agent-managed only, so losing positions are well past their stops: 2382 is at −30% and 1800 at −22%.

The three MCP services and Postgres were reachable from the internet. ufw now covers the MCP ports; Postgres was rebound to localhost on 2026-10-14. Scanners repeatedly enumerated the MCP tools. **No unauthorised trade was found.** The only external tool calls were six failed attempts at a non-existent `execute_sql` tool.

---

## 1. Where the code is

- **Repo:** `Elimelech70/catalyst-trading-system` (local clone: `/root/Catalyst-Trading-System-International`)
- **Trader:** the `catalyst-international/` folder, run from `catalyst-international/docker-compose.yml`

| Component | Container | Entry point | Role |
|---|---|---|---|
| Brain | `catalyst-coordinator` | `agents/coordinator/coordinator.py` | Claude Sonnet 4.5 tool-use loop, every 30 min during HKEX hours. Uses `health.py` (Survival Pulse), `discipline.py` (Discipline Gate) and `system_prompt.py`. |
| Hands | `catalyst-trade-executor` | `agents/trade-executor/mcp_server.py` | Orders, position writes (single writer), `check_risk` via `safety.py`, signals |
| Eyes | `catalyst-market-scanner` | `agents/market-scanner/mcp_server.py` | Scan, quotes, technicals, patterns, news via `data/market.py`, `data/news.py`, `data/patterns.py` |
| Exit watcher | `catalyst-position-monitor` | `agents/position-monitor/monitor.py` + `mcp_server.py` | Checks open positions every 5 min; asks Claude Haiku 4.5 on borderline cases |
| Shared | — | `brokers/moomoo.py`, `data/database.py`, `cerebellum.py`, `tools.py` | Broker client, DB, ONNX inference, the tool schemas Claude sees |

**Not run by any container (legacy):** `unified_agent.py`, `tool_executor.py`, `position_monitor_service.py`, `signals.py.bak.*`, `config/settings.yaml`.

**⚠️ `data/` is not in git.** The root `.gitignore` excludes `data/`, so `market.py`, `database.py`, `news.py` and `patterns.py` exist only on the droplet. The market-scanner, position-monitor and trade-executor Dockerfiles `COPY data/`, so **the trader cannot be rebuilt from GitHub.**

---

## 2. Critical findings

### 2.1 Coordinator frozen since 2026-06-03

- The last log line is `mcp.client.sse: Error in post_writer … httpx.ReadError` during `get_quote("2020")`.
- **Cause:** `coordinator.py:146`. `await self.session.call_tool(...)` has no timeout. The SSE transport died and the await never returned, so the retry/reconnect logic at lines 155–160 (which only runs on an exception) never ran.
- The coordinator has no Docker healthcheck, and there is no external watchdog. This is the third instance of the "detection without response" pattern recorded in `catalyst-international/CLAUDE.md`.

### 2.2 Positions unmanaged; stops are software-only

Position monitor output, 2026-10-14 11:55 HKT:

| Symbol | P&L | Monitor recommendation |
|---|---|---|
| 2382 | −30.0% | EXIT |
| 1800 | −22.5% | EXIT |
| 939 | +14.8% | EXIT |
| 1398 | +12.5% | EXIT |
| 3988 | +17.1% | EXIT |
| 386 | +4.0% | HOLD (Haiku) |

- Stops and targets are only logged (`brokers/moomoo.py:855-858`). Nothing is placed at the broker, so an inactive brain means no exits.
- The monitor ignores each trade's `stop_loss`/`take_profit`. It uses fixed thresholds instead (−3% / +8%, `monitor.py:48-51`, applied at `monitor.py:83-99`).
- **772 is held at the broker but not in the DB's open positions**, so it isn't monitored. Broker/DB sync only runs at coordinator start.
- Portfolio on 2026-10-13: total assets HKD 962,818, cash 872,126, unrealised P&L −3,396, total return −3.72%. There have been 7 positions since 2026-06-04.
- Haiku is still being called every 5 minutes during market hours, which is small but ongoing API spend.

### 2.3 Internet exposure

- Ports 8001–8003 bind to `0.0.0.0` (`uvicorn.run(host="0.0.0.0")` at the end of each `mcp_server.py`) and have no authentication. They were reachable until ufw was enabled on 2026-10-14.
- The logs show tens of thousands of external requests. Scanners from many IPs opened `/sse` sessions roughly weekly from April 2026, which is enough to fetch the tool list (`execute_trade`, `close_all`, …).
- **External tool calls:** 6 in total, all `execute_sql` (an unknown tool, which errored), on 2026-09-12 across all three services.
- **Trades:** executor `Executing trade` counts match coordinator `execute_trade` calls 1:1 for 2026-06-01 to 06-03. There were no executor trades after the freeze and no `close_all` ever. Executor logs from before 2026-05-31 can't be cross-checked because the coordinator's logs only begin then.
- **Postgres (fixed 2026-10-14):** `docker-compose.yml` published `"5432:5432"`. Docker's own firewall rules are evaluated before ufw's, so ufw did not block it, and the checklist's external test (port 8003 only) missed it. This local container is not in the trading path: the trader uses the managed DigitalOcean DB, and the container had no client connections. **Fix applied:** the binding is now `"127.0.0.1:5432:5432"` and only the Postgres container was recreated. Verified: it listens on `127.0.0.1` only, and a connection to the public IP on 5432 is refused.
- **Follow-up:** the local container was initialised with the same `DB_USER`/`DB_PASSWORD` as the managed DB and was internet-reachable. Consider rotating the managed-DB password.

---

## 3. Risk and logic findings

| # | Finding | Location |
|---|---|---|
| 1 | `execute_trade` never calls the safety validator. Calling `check_risk` first is only a prompt instruction. | `agents/trade-executor/mcp_server.py:289-411`; `system_prompt.py` (CRITICAL RULES) |
| 2 | The HKD 10k cap can be exceeded. `max((max_qty // lot_size) * lot_size, lot_size)` forces at least one lot even when one lot costs more than 10k. There is no per-symbol cap: 2382 was bought 3× (≈ HKD 25.6k), and 1398 and 3988 were stacked too. | `mcp_server.py:320-326` |
| 3 | Partial fills are recorded with the requested `quantity`, not `filled_qty`. | `mcp_server.py:359-364` |
| 4 | `safety.py` limits are non-binding on a ≈HKD 960k portfolio. 20% per position = 192k; 1% trade risk = 9.6k; 2% daily loss = ≈19k (the prompt says HKD 2,000); 15 × 20% = 300%. The `max_daily_trades` counter is in memory and resets on restart. In practice the 10k cap is the only binding constraint. | `safety.py:34-46` |
| 5 | Tier sizing (Tier 2 7k / Tier 3 5k) appears only in the prompt. `catalyst-international/CLAUDE.md` wrongly says it is "ENFORCED in trade-executor". | `system_prompt.py`; `CLAUDE.md` |
| 6 | The design pushes the AI to act: the identity prompt says "I am a trader. I trade.", and the Discipline Gate demands a trade after 3 idle days. This produced repeated "DEGRADED MODE TIER 3" buys on 2026-06-03. | `discipline.py`; `system_prompt.py` |
| 7 | The neural model is never queried. The cerebellum is loaded (and re-instantiated every cycle), but the brain only receives a fixed string. The market-scanner image doesn't include `cerebellum.py`. | `coordinator.py:558-570, 630-636` |
| 8 | In an AI consultation, a CLOSE decision returns `"closed"` without checking the close result. | `coordinator.py:479-486` |
| 9 | The holiday calendar covers 2026 only. From 2027 the coordinator will treat HKEX holidays as trading days, and `safety.is_market_open` has no holidays at all. | `coordinator.py:47-67`; `safety.py:74-107` |
| 10 | Model IDs: the coordinator already honours `CLAUDE_MODEL` (env, set in compose); the position monitor's Haiku ID is hardcoded. | `coordinator.py:73`; `monitor.py:35` |
| 11 | Paper mode is hardcoded (correct — keep it). | `trade-executor/mcp_server.py:73`; `moomoo.py:266` |
| 12 | The tool list Claude sees (`tools.py`) and the coordinator's MCP routing map differ. For example, `get_exit_recommendations` and `sync_positions` are routable but not offered to Claude. | `tools.py`; `coordinator.py:202-226` |

---

## 4. Recommended actions (priority order)

1. ~~**Close Postgres to the internet.**~~ Done 2026-10-14 (see 2.3). Still recommended: rotate the managed-DB password, and add a DigitalOcean Cloud Firewall as a network-level layer.
2. **Decide on the 5 EXIT-flagged positions** before restarting the coordinator. A restart during market hours will act on the monitor's recommendations.
3. **Put `data/` under version control** (narrow the `.gitignore` rule to runtime state such as `data/*.db`).
4. **Fix the freeze:** wrap MCP calls in `asyncio.wait_for`, add a coordinator heartbeat and healthcheck, and add out-of-band alerting when no cycle completes during market hours.
5. **Enforce risk in the executor:** run `validate_trade` inside `execute_trade`, add per-symbol exposure and tier caps, and fix the one-lot override and partial-fill quantity.
6. **Make the monitor use per-trade stops**, and place broker-side stop orders where Moomoo supports them.
7. **Bind the MCP services to `127.0.0.1`** and consider authentication, per the hardening checklist.
8. **Reconcile `RiskLimits`** with the HKD 10k cap and the prompt's HKD 2,000 daily loss; add the 2027 holiday calendar; move the Haiku model ID to an environment variable.

---

*Prepared by Claude (Opus 5.5) for Craig — 2026-10-14*
