# Catalyst Intl Droplet — Hardening & Clean-up Checklist

**Created:** 14/10/2026 **Droplet:** catalyst-trading-system-international (209.38.87.27) **Repo on droplet:** `~/Catalyst-Trading-System-International` **Remote (assumed, verify with `git remote -v`):** github.com/Elimelech70/Catalyst-Trading-System-International **Mode:** Moomoo paper trading (HKEX), Docker, host networking

---

## Done (14/10/2026)

- [x] SSH key login from laptop confirmed working (no password needed)  
- [x] Claude Code on droplet authenticated with Anthropic API key (`~/.bashrc`)  
- [x] Config mapped by Claude Code (see summary)  
- [x] Found ports 8001–8003 listening on `0.0.0.0` (OpenD correctly on `127.0.0.1`)  
- [x] ufw enabled: deny incoming, allow outgoing, OpenSSH only  
- [x] External test from laptop: port 8003 times out (blocked)

---

## 1\. Security — finish now

- [ ] **Confirm password SSH is off**

```sh
sshd -T | grep passwordauthentication   # expect: no
```

- [ ] **Remove API key from shell history** (if it was ever typed at the prompt)

```sh
grep -n ANTHROPIC ~/.bash_history
# if found: nano ~/.bash_history, delete lines, then: history -c
```

- [ ] **Lock down `.bashrc`**: `chmod 600 ~/.bashrc`

- [ ] **Check for past outside access to services**

```sh
for c in catalyst-trade-executor catalyst-position-monitor catalyst-market-scanner; do
  echo "== $c"; docker logs $c 2>&1 | grep -v 127.0.0.1 | grep -iE "POST|GET|request" | tail -20
done
```

      Unknown IPs → investigate what endpoints they hit before moving on.

- [ ] **Bind services to localhost (second layer behind ufw).** Claude Code prompt:

      > In this repo, find where the market scanner (:8002), position monitor (:8001) and trade executor (:8003) bind to 0.0.0.0 and change them to 127.0.0.1. Show the diff before rebuilding.

      Then rebuild/restart and confirm:

```sh
ss -tlnp | grep -E '8001|8002|8003'   # expect 127.0.0.1 only
```

- [ ] **Optional:** attach a DigitalOcean Cloud Firewall (SSH only) as a network-level layer.

## 2\. Cost control

- [ ] Set a monthly spend limit in the Anthropic Console (Limits). The YAML's \$5 daily budget is **not enforced** by code.  
- [ ] Decide whether to implement a real daily budget in the coordinator.

## 3\. Code & config integrity

- [ ] **Uncommitted production changes** — `cerebellum.py`, `model_version.json`

```sh
cd ~/Catalyst-Trading-System-International
git status
git diff
```

      Decide: commit (with message describing the live model state) or discard.

- [ ] Confirm the droplet is on the expected branch and in sync: `git branch -vv`, `git fetch && git status`.  
- [ ] **Config drift:** archive/delete `config/settings.yaml` (legacy IBKR/Sonnet 4); strip unused keys from `config/intl_claude_config.yaml` or wire them into code. One source of truth.  
- [ ] Note in README: `account_type: paper` in YAML does nothing; paper mode is hardcoded (`agents/trade-executor/mcp_server.py:73`). **Keep it hardcoded.**

## 4\. Models

- [ ] Check deprecation status of pinned models:  
      - Coordinator: `claude-sonnet-4-5-20250929` (`agents/coordinator/coordinator.py:70-74`)  
      - Position monitor: `claude-haiku-4-5-20251001` (`agents/position-monitor/monitor.py:33-35`)  
- [ ] Decide on upgrade path; move model IDs to env vars so changes don't need code edits.

## 5\. Risk limits (`safety.py` RiskLimits)

- [ ] Reconcile: 15 positions × 20% max each \= 300% of portfolio. Pick consistent values.  
- [ ] Confirm HK\$10,000 per-position cap (`max_position_value_hkd`) is the intended binding constraint.  
- [ ] Review 25 trades/day max against strategy intent.

## 6\. Operations

- [ ] Remove or fix inactive `catalyst.service` systemd unit (containers survive via `restart: unless-stopped`).  
- [ ] Confirm Docker starts on boot: `systemctl is-enabled docker`.  
- [ ] Containers up 4–6 months: plan OS updates (`apt update && apt upgrade`) and a controlled restart window outside HKEX hours.  
- [ ] After any change: check `docker logs --tail 50 catalyst-coordinator` for healthy cycles.

---

## Reference: useful commands

| Purpose | Command |
| :---- | :---- |
| Firewall status | `ufw status verbose` |
| Listening ports | `ss -tlnp` |
| Containers | `docker ps` |
| Coordinator logs | `docker logs --tail 50 catalyst-coordinator` |
| External port test (from laptop) | `nc -zv -w 3 209.38.87.27 8003` |
| API key length check | `echo ${#ANTHROPIC_API_KEY}` |

&nbsp;