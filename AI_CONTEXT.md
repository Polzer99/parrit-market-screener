# AI_CONTEXT.md — parrit-market-screener
> First reflex every session: read this first. Doctrine: Parrit AI Playbook (REGLES-DOR §33).

## 1. Architecture state
Single-file Streamlit prototype (`app.py`, ~543 lines) — a financial screener: search a company by name/ticker, view historical financials + CAGR projections, peer comparables, analyst consensus, and a valuation playground (3-scenario DCF + EBITDA multiples). Stack = Streamlit (UI) · yfinance (data) · Plotly (charts) · pandas (calc); deps pinned in `requirements.txt`. Entry point is `app.py` run via `streamlit run app.py` — there is **no backend, no database, no API server, no auth**. All data is fetched read-only at runtime from public Yahoo Finance (`query2.finance.yahoo.com` search + `yfinance.Ticker`), cached in-process via `@st.cache_data`/`@st.cache_resource`. Data flow: `search_yahoo()` → `load_ticker()` → `info`/`history`/`income_stmt`/`cashflow`/`recommendations` → tabs render.

## 2. Risk zones — DO NOT TOUCH without care
This repo is **clean** (audit: 3 raw findings, 0 real blocker, 0 real high). No secrets, no auth surface, no data-loss path, no `strict` flags (Python). The real traps are different from the other repos:
- **Silent `except Exception` swallows** — the genuine debt class here. `search_yahoo` (`app.py:40-41`) returns `[]` on any failure; `load_ticker` (`app.py:49-51`) swallows to `info={}`; per-peer fetch in Tab 2 (`app.py:350-351`) writes `"Nom": "ERREUR"`; the DCF `last_fcf` fetch (`app.py:439-440`) does a bare `pass`. These hide upstream outages (Yahoo rate-limiting / schema drift) as "no data". Log-and-continue rather than fully swallow if you touch them.
- **Live dependency on an undocumented Yahoo endpoint** — `app.py:22-28` calls `query2.finance.yahoo.com/v1/finance/search` with a spoofed `User-Agent`; yfinance scrapes Yahoo internals. This is **mocked/best-effort financial data, not a reliable source** — the app itself flags it ("MVP prototype", "data delayed 15-20 min", `app.py:538-542`). Any number shown can be stale, partial, or wrong; never treat output as decision-grade.
- **Financial math edge cases** — DCF terminal value guards `discount_rate > growth_term` (`app.py:454-458`, else TV=0); fair price returns `None` when `sharesOutstanding` is missing (`app.py:461`). Do not "simplify" these guards away or you reintroduce divide-by-zero / nonsense valuations.
- **Yahoo field unit conventions** — `pct()` vs `pct_raw()` exist because some Yahoo fields are decimals and some are already percentages (the one historical bug, fixed: `dividendYield` was double-multiplied, commit `5a27359`). Use the right helper per field.

## 3. Established rules — what's already true
- **No secrets in the repo** — verified clean by the global audit (E5 = 0 real). The app uses zero API keys; the only network calls are unauthenticated public Yahoo endpoints. `.gitignore` already excludes `.env`, `.venv/`, `__pycache__/`, and `.streamlit/secrets.toml` — keep any future credential server-only and out of git.
- **Read-only by design** — no writes, no DB, no RLS surface, no mutating endpoint, no webhook. There is nothing to authenticate and no data to lose; that is the intended (and correct) posture for this prototype.
- **Honest self-labeling is intentional** — the in-app "MVP prototype" / "V2: Financial Modeling Prep + SEC EDGAR" disclaimers and the per-tab "non couvert dans ce MVP" notes (TAM, 3-5y consensus) are deliberate scope markers, not bugs. Keep them until the underlying source is upgraded.
- **Deps are pinned** (`requirements.txt`, `>=` floors) — install with that file; no lockfile yet.

## 4. Open debt — playbook findings still pending
Tracked in `docs/ai-playbook/audits/GLOBAL-AUDIT-2026-06-21.md` (this repo: §1 row, §3 grouped "propres, gaps docs/config uniquement", §4 themes 1-3-7). All **safe-auto / Codex**, no rotation, no security work:
- **AI_CONTEXT.md was missing (E11)** — addressed by this file (audit theme 1).
- **No CI barrier (E12)** — no `.github/workflows`; add a blocking gate (lint + `pip install -r requirements.txt` + import/smoke check) so "the CI blocks" replaces "remember to verify" (audit theme 3).
- **No Dependabot (E13)** — add `.github/dependabot.yml` for the `pip` ecosystem + github-actions (audit theme 2).
- **Silent except/pass swallows (E15)** — convert the four swallows listed in §2 to log-and-continue so Yahoo outages surface instead of silently rendering "n/a"/"ERREUR" (audit theme 7).
- **No test net / no lockfile** — no tests and no pinned lockfile; a minimal smoke test on the helpers (`fmt_b`, `pct`, `cagr`, `compute_dcf`) would anchor the CI gate above.