"""Market Screener — Parrit.ai
Tape un nom d'entreprise (LVMH, Apple, Nvidia…) ou un ticker.
Sources: Yahoo Finance via yfinance + API search.
"""
import re

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

st.set_page_config(page_title="Market Screener — Parrit", layout="wide", page_icon="📊")


# ═══════════════════════ HELPERS ═══════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def search_yahoo(query: str):
    try:
        r = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 8, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=6,
        )
        r.raise_for_status()
        out = []
        for q in r.json().get("quotes", []):
            if q.get("quoteType") not in ("EQUITY", "ETF"):
                continue
            sym = q.get("symbol")
            if not sym:
                continue
            name = q.get("longname") or q.get("shortname") or sym
            exch = q.get("exchDisp") or q.get("exchange") or ""
            out.append((sym, name, exch))
        return out
    except Exception:
        return []


@st.cache_resource(show_spinner=False)
def load_ticker(t: str):
    tk = yf.Ticker(t)
    try:
        info = tk.info
    except Exception:
        info = {}
    return tk, info


def fmt_b(v, suffix=""):
    """Format en millions/milliards lisible."""
    if v is None or pd.isna(v):
        return "n/a"
    if abs(v) >= 1e9:
        return f"{v/1e9:,.2f} B{suffix}"
    if abs(v) >= 1e6:
        return f"{v/1e6:,.1f} M{suffix}"
    return f"{v:,.0f}{suffix}"


def pct(v, digits=1):
    """Convertit un ratio décimal (ex: 0.25) en pourcentage (25.0%).
    Pour les valeurs déjà en pourcentage (ex: dividendYield), utiliser pct_raw."""
    if v is None or pd.isna(v):
        return "n/a"
    return f"{v*100:.{digits}f}%"


def pct_raw(v, digits=2):
    """Pour les valeurs déjà exprimées en % par Yahoo (ex: dividendYield)."""
    if v is None or pd.isna(v):
        return "n/a"
    return f"{v:.{digits}f}%"


def cagr(start, end, years):
    if start and end and start > 0 and years > 0:
        return (end / start) ** (1 / years) - 1
    return None


# ═══════════════════════ HEADER + RECHERCHE ═══════════════════════

st.markdown("## 📊 Market Screener")
st.caption("Parrit.ai · MVP prototype · Sources : Yahoo Finance")

query = st.text_input(
    "Entreprise ou ticker",
    value="LVMH",
    placeholder="LVMH, Apple, Nvidia, TotalEnergies, AAPL, MC.PA...",
)

if not query or not query.strip():
    st.info("Tape le nom d'une entreprise (LVMH, Apple…) ou un ticker (AAPL, MC.PA…).")
    st.stop()

query = query.strip()

# On recherche toujours via Yahoo, sauf si le ticker a un suffixe bourse explicite
# (ex: MC.PA, SAP.DE) — dans ce cas on peut l'utiliser direct.
has_bourse_suffix = bool(re.fullmatch(r"[A-Za-z0-9]{1,6}\.[A-Z]{1,3}", query))

if has_bourse_suffix:
    ticker_input = query.upper()
else:
    matches = search_yahoo(query)
    if not matches:
        st.error(f"Aucun résultat pour « {query} ». Saisis un ticker (ex: MC.PA).")
        st.stop()
    # Auto-sélection si le top match correspond exactement au query (cas "AAPL")
    top_symbol = matches[0][0]
    if top_symbol.upper() == query.upper():
        ticker_input = top_symbol
        st.caption(f"→ Ticker : **{ticker_input}** ({matches[0][1]})")
    else:
        labels = [f"{sym} — {name} ({exch})" for sym, name, exch in matches]
        sel = st.selectbox("Résultats (le 1er est le match le plus probable) :", labels, index=0)
        ticker_input = matches[labels.index(sel)][0]
        st.caption(f"→ Ticker sélectionné : **{ticker_input}**")

tk, info = load_ticker(ticker_input)

# Si le ticker ne renvoie rien, on arrête net avec un message clair
if not info or not (info.get("longName") or info.get("shortName") or info.get("currentPrice") or info.get("regularMarketPrice")):
    st.error(
        f"❌ Ticker `{ticker_input}` introuvable ou data indisponible sur Yahoo. "
        "Retape le nom de l'entreprise (ex: LVMH, Apple) pour utiliser le sélecteur."
    )
    st.stop()
name = info.get("longName") or info.get("shortName") or ticker_input
sector = info.get("sector", "n/a")
industry = info.get("industry", "n/a")
currency = info.get("currency", "USD")
country = info.get("country", "n/a")

st.markdown(f"### {name} `{ticker_input}`")
st.caption(f"{sector} · {industry} · {country} · devise {currency}")

# ═══════════════════════ KPI HEADER ═══════════════════════

price = info.get("currentPrice") or info.get("regularMarketPrice")
mcap = info.get("marketCap")
ebitda = info.get("ebitda")
fcf = info.get("freeCashflow")
net_debt = (info.get("totalDebt") or 0) - (info.get("totalCash") or 0)
ev = (mcap or 0) + net_debt

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Cours", f"{price:,.2f} {currency}" if price else "n/a")
k2.metric("Market Cap", fmt_b(mcap))
k3.metric("PER TTM", f"{info.get('trailingPE'):.1f}" if info.get("trailingPE") else "n/a")
k4.metric("PER fwd", f"{info.get('forwardPE'):.1f}" if info.get("forwardPE") else "n/a")
k5.metric("EV/EBITDA", f"{ev/ebitda:.1f}" if ebitda and ebitda > 0 else "n/a")
k6.metric("FCF yield", f"{(fcf/mcap)*100:.2f}%" if fcf and mcap else "n/a")

k7, k8, k9, k10, k11, k12 = st.columns(6)
k7.metric("ROE", pct(info.get("returnOnEquity")))
k8.metric("Marge nette", pct(info.get("profitMargins")))
k9.metric("Marge op.", pct(info.get("operatingMargins")))
k10.metric("Croissance CA YoY", pct(info.get("revenueGrowth")))
k11.metric("Div yield", pct_raw(info.get("dividendYield")))
k12.metric("Beta", f"{info.get('beta'):.2f}" if info.get("beta") else "n/a")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Analyse financière", "🌐 Marché & concurrents", "👔 Avis analystes", "🧮 Valorisation"]
)

# ═══════════════════════ TAB 1 — FINANCE ═══════════════════════

with tab1:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("#### Cours — historique 5 ans")
        hist = tk.history(period="5y")
        if not hist.empty:
            fig = go.Figure(go.Scatter(x=hist.index, y=hist["Close"], mode="lines", line=dict(color="#1e88e5")))
            fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Pas d'historique de cours.")
    with c2:
        st.markdown("#### Range 52 sem.")
        h52 = info.get("fiftyTwoWeekHigh")
        l52 = info.get("fiftyTwoWeekLow")
        if h52 and l52 and price:
            st.metric("Haut 52 sem.", f"{h52:,.2f}", f"{(price/h52-1)*100:+.1f}%")
            st.metric("Bas 52 sem.", f"{l52:,.2f}", f"{(price/l52-1)*100:+.1f}%")

    st.markdown("#### Agrégats annuels historiques")
    try:
        fin = tk.income_stmt
        cf = tk.cashflow
        rows = {}
        if fin is not None and not fin.empty:
            mapping = [
                ("Revenue", "Total Revenue"),
                ("EBITDA", "EBITDA"),
                ("EBIT", "Operating Income"),
                ("Net Income", "Net Income"),
            ]
            for label, key in mapping:
                if key in fin.index:
                    rows[label] = fin.loc[key]
        if cf is not None and not cf.empty and "Free Cash Flow" in cf.index:
            rows["Free Cash Flow"] = cf.loc["Free Cash Flow"]

        if rows:
            df = pd.DataFrame(rows).T
            df = df.apply(lambda s: s / 1e6)
            df.columns = [c.strftime("%Y") if hasattr(c, "strftime") else str(c) for c in df.columns]
            df = df.iloc[:, ::-1]  # chronologique

            # Marges
            if "Revenue" in df.index:
                if "EBITDA" in df.index:
                    df.loc["Marge EBITDA %"] = (df.loc["EBITDA"] / df.loc["Revenue"]) * 100
                if "Net Income" in df.index:
                    df.loc["Marge nette %"] = (df.loc["Net Income"] / df.loc["Revenue"]) * 100

            st.dataframe(df.style.format("{:,.1f}", na_rep="n/a"), use_container_width=True)

            # Charts : 2x2 grid
            cc1, cc2 = st.columns(2)
            years = df.columns.tolist()
            with cc1:
                if "Revenue" in df.index and "EBITDA" in df.index:
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_bar(x=years, y=df.loc["Revenue"].values, name="Revenue", marker_color="#1e88e5")
                    fig.add_scatter(x=years, y=df.loc["EBITDA"].values, name="EBITDA", line=dict(color="#ff6f00"), mode="lines+markers")
                    fig.update_layout(title="Revenue vs EBITDA (M)", height=280, margin=dict(l=0, r=0, t=40, b=0))
                    st.plotly_chart(fig, use_container_width=True)
            with cc2:
                if "Free Cash Flow" in df.index and "Net Income" in df.index:
                    fig = go.Figure()
                    fig.add_bar(x=years, y=df.loc["Net Income"].values, name="Net Income", marker_color="#43a047")
                    fig.add_bar(x=years, y=df.loc["Free Cash Flow"].values, name="FCF", marker_color="#8e24aa")
                    fig.update_layout(title="Net Income vs FCF (M)", height=280, margin=dict(l=0, r=0, t=40, b=0), barmode="group")
                    st.plotly_chart(fig, use_container_width=True)

            # Projections CAGR
            st.markdown("#### 📐 Projections 1-5 ans (CAGR historique)")
            st.caption("Projection mécanique basée sur le CAGR des 3-4 dernières années. À confronter avec les projections analystes ci-dessous.")
            proj_rows = {}
            num_years = min(5, len(years) - 1) if len(years) >= 2 else 0
            if num_years >= 2:
                for label in ["Revenue", "EBITDA", "Free Cash Flow", "Net Income"]:
                    if label not in df.index:
                        continue
                    series = df.loc[label].dropna()
                    if len(series) < 2:
                        continue
                    start = series.iloc[0]
                    end = series.iloc[-1]
                    c = cagr(start, end, num_years)
                    if c is None:
                        continue
                    last = end
                    future = [last * (1 + c) ** i for i in range(1, 6)]
                    proj_rows[label] = {"CAGR historique": pct(c)}
                    for i, val in enumerate(future, 1):
                        proj_rows[label][f"N+{i}"] = f"{val:,.0f}"
                if proj_rows:
                    st.dataframe(pd.DataFrame(proj_rows).T, use_container_width=True)
        else:
            st.warning("Pas de données financières annuelles.")
    except Exception as e:
        st.warning(f"Erreur chargement états financiers : {e}")

    # Projections analystes (consensus)
    st.markdown("#### 👥 Projections consensus analystes")
    try:
        est = tk.earnings_estimate
        rev = tk.revenue_estimate
        ccol1, ccol2 = st.columns(2)
        with ccol1:
            st.caption("EPS estimate")
            if est is not None and not est.empty:
                st.dataframe(est, use_container_width=True)
            else:
                st.info("n/a")
        with ccol2:
            st.caption("Revenue estimate")
            if rev is not None and not rev.empty:
                st.dataframe(rev, use_container_width=True)
            else:
                st.info("n/a")
        st.caption("⚠️ Yahoo free : consensus limité à 1-2 ans forward. Pour 3-5 ans, bascule sur Financial Modeling Prep.")
    except Exception as e:
        st.info(f"Estimations indisponibles : {e}")


# ═══════════════════════ TAB 2 — MARKET ═══════════════════════

with tab2:
    mcol1, mcol2 = st.columns([1, 2])
    with mcol1:
        st.markdown("#### Profil")
        st.markdown(f"**Secteur** : {sector}")
        st.markdown(f"**Industrie** : {industry}")
        st.markdown(f"**Pays** : {country}")
        emp = info.get("fullTimeEmployees")
        if emp:
            st.markdown(f"**Employés** : {emp:,}")
        website = info.get("website")
        if website:
            st.markdown(f"**Site** : {website}")
    with mcol2:
        summary = info.get("longBusinessSummary", "")
        if summary:
            st.markdown("#### Activité")
            with st.expander("Voir la description", expanded=True):
                st.write(summary)

    st.markdown("#### 🆚 Comparables (même industrie)")
    st.caption("Saisis 2-5 tickers concurrents. Les lignes se classent par market cap décroissante.")
    default_peers = {"MC.PA": "KER.PA,CFR.SW,HESAY", "AAPL": "MSFT,GOOGL,NVDA,META", "NVDA": "AMD,AVGO,INTC,TSM"}.get(ticker_input, "")
    peers_input = st.text_input(
        "Tickers concurrents (virgule)",
        value=default_peers,
        placeholder="Ex: KER.PA, CFR.SW, HESAY",
    )
    if peers_input:
        peers = [p.strip().upper() for p in peers_input.split(",") if p.strip()]
        rows = []
        for p in [ticker_input] + peers:
            try:
                pi = yf.Ticker(p).info
                pmc = pi.get("marketCap") or 0
                pebitda = pi.get("ebitda") or 0
                pnd = (pi.get("totalDebt") or 0) - (pi.get("totalCash") or 0)
                pev = pmc + pnd
                prev = pi.get("totalRevenue") or 0
                rows.append({
                    "Ticker": p,
                    "Nom": (pi.get("shortName") or "?")[:30],
                    "Market Cap (B)": round(pmc / 1e9, 2) if pmc else None,
                    "PER TTM": round(pi.get("trailingPE") or 0, 1) or None,
                    "PER fwd": round(pi.get("forwardPE") or 0, 1) or None,
                    "EV/EBITDA": round(pev / pebitda, 1) if pebitda > 0 else None,
                    "EV/Sales": round(pev / prev, 2) if prev > 0 else None,
                    "ROE %": round((pi.get("returnOnEquity") or 0) * 100, 1),
                    "Marge nette %": round((pi.get("profitMargins") or 0) * 100, 1),
                    "Croiss. CA YoY %": round((pi.get("revenueGrowth") or 0) * 100, 1),
                    "Div yield %": round((pi.get("dividendYield") or 0), 2),
                })
            except Exception:
                rows.append({"Ticker": p, "Nom": "ERREUR"})
        peers_df = pd.DataFrame(rows)
        if "Market Cap (B)" in peers_df.columns:
            peers_df = peers_df.sort_values("Market Cap (B)", ascending=False, na_position="last")
        st.dataframe(peers_df, use_container_width=True, hide_index=True)

    st.info(
        "💡 **Analyse marché / TAM / croissance sectorielle** : non couvert dans ce MVP "
        "(nécessite sources tierces type Statista, IBISWorld, ou analyse LLM). "
        "Approche V2 : brancher un node Claude qui résume le marché à partir du sector/industry + web search."
    )


# ═══════════════════════ TAB 3 — ANALYSTES ═══════════════════════

with tab3:
    rcol1, rcol2, rcol3, rcol4 = st.columns(4)
    with rcol1:
        rec_key = info.get("recommendationKey", "n/a")
        st.metric("Consensus", rec_key.upper() if rec_key else "n/a")
    with rcol2:
        nb = info.get("numberOfAnalystOpinions")
        st.metric("Nb analystes", nb if nb else "n/a")
    with rcol3:
        pt = info.get("targetMeanPrice")
        if pt and price:
            st.metric("Target mean", f"{pt:.2f}", f"{(pt/price-1)*100:+.1f}%")
        else:
            st.metric("Target mean", f"{pt:.2f}" if pt else "n/a")
    with rcol4:
        rm = info.get("recommendationMean")
        st.metric("Score moyen (1=buy, 5=sell)", f"{rm:.2f}" if rm else "n/a")

    st.markdown("#### 📊 Évolution mensuelle des recommandations")
    try:
        recs = tk.recommendations
        if recs is not None and not recs.empty:
            period_col = "period" if "period" in recs.columns else None
            if period_col:
                # Yahoo retourne "0m", "-1m", "-2m", "-3m" — inversons pour chronologique
                recs = recs.sort_values(period_col)
            buckets = ["strongBuy", "buy", "hold", "sell", "strongSell"]
            colors = {"strongBuy": "#0d6e3c", "buy": "#43a047", "hold": "#9e9e9e", "sell": "#e57373", "strongSell": "#b71c1c"}
            labels = {"strongBuy": "Strong Buy", "buy": "Buy", "hold": "Hold", "sell": "Sell", "strongSell": "Strong Sell"}
            fig = go.Figure()
            x_labels = recs[period_col].tolist() if period_col else recs.index.tolist()
            # Rename "0m" -> "now", "-1m" -> "-1 mois", etc.
            x_labels = [
                "Maintenant" if str(x) == "0m" else f"{str(x).replace('m', ' mois').replace('-', '- ')}"
                for x in x_labels
            ]
            for b in buckets:
                if b in recs.columns:
                    fig.add_bar(x=x_labels, y=recs[b].values, name=labels[b], marker_color=colors[b])
            fig.update_layout(barmode="stack", height=340, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h"))
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("Données brutes"):
                st.dataframe(recs, use_container_width=True)
        else:
            st.info("Pas d'évolution disponible.")
    except Exception as e:
        st.info(f"Recos indisponibles : {e}")

    st.markdown("#### 🎯 Prix cibles")
    targets = [
        ("High", info.get("targetHighPrice")),
        ("Mean", info.get("targetMeanPrice")),
        ("Median", info.get("targetMedianPrice")),
        ("Low", info.get("targetLowPrice")),
    ]
    tdf = pd.DataFrame(targets, columns=["Métrique", "Prix"])
    if price:
        tdf["vs cours %"] = [round((p / price - 1) * 100, 1) if p else None for _, p in targets]
    st.dataframe(tdf, use_container_width=True, hide_index=True)


# ═══════════════════════ TAB 4 — VALO ═══════════════════════

with tab4:
    st.markdown("#### 🎯 3 scénarios DCF")
    st.caption("Projection FCF 5 ans + valeur terminale, actualisés au WACC.")

    # FCF de base
    last_fcf = None
    try:
        cf_df = tk.cashflow
        if cf_df is not None and not cf_df.empty and "Free Cash Flow" in cf_df.index:
            last_fcf = cf_df.loc["Free Cash Flow"].dropna().iloc[0] / 1e6
    except Exception:
        pass

    fcf0 = st.number_input(
        "FCF dernier exercice (M)",
        value=float(last_fcf) if last_fcf else 1000.0,
        step=100.0,
    )
    nd_m = net_debt / 1e6
    shares = info.get("sharesOutstanding")

    def compute_dcf(fcf_start, growth_short, growth_term, discount_rate, years=5):
        fcfs = [fcf_start * (1 + growth_short) ** i for i in range(1, years + 1)]
        disc = [(1 + discount_rate) ** i for i in range(1, years + 1)]
        pv_fcf = sum(f / d for f, d in zip(fcfs, disc))
        if discount_rate > growth_term:
            tv = fcfs[-1] * (1 + growth_term) / (discount_rate - growth_term)
            pv_tv = tv / disc[-1]
        else:
            tv = pv_tv = 0
        ev_local = pv_fcf + pv_tv
        equity = ev_local - nd_m
        fair = (equity * 1e6 / shares) if shares else None
        return {"EV (M)": ev_local, "Equity (M)": equity, "Prix théorique": fair, "FCFs": fcfs}

    sc_cols = st.columns(3)
    scenarios = [
        ("😕 Bear", 0.02, 0.015, 0.10, sc_cols[0]),
        ("😐 Base", 0.06, 0.02, 0.08, sc_cols[1]),
        ("😃 Bull", 0.12, 0.025, 0.07, sc_cols[2]),
    ]
    scen_results = {}
    for name_s, g_short_default, g_term_default, wacc_default, col in scenarios:
        with col:
            st.markdown(f"**{name_s}**")
            gs = st.slider(f"Croissance 5y ({name_s})", -5.0, 30.0, g_short_default * 100, 0.5, key=f"gs_{name_s}") / 100
            gt = st.slider(f"Croiss. terminale ({name_s})", 0.0, 5.0, g_term_default * 100, 0.1, key=f"gt_{name_s}") / 100
            wc = st.slider(f"WACC ({name_s})", 4.0, 15.0, wacc_default * 100, 0.1, key=f"wc_{name_s}") / 100
            res = compute_dcf(fcf0, gs, gt, wc)
            scen_results[name_s] = res
            st.metric("Prix théorique", f"{res['Prix théorique']:,.2f}" if res["Prix théorique"] else "n/a")
            if res["Prix théorique"] and price:
                st.caption(f"Upside vs cours : **{(res['Prix théorique']/price-1)*100:+.1f}%**")

    st.markdown("#### 📋 Synthèse des scénarios")
    synth = pd.DataFrame({
        name_s: {
            "Enterprise Value (M)": round(res["EV (M)"], 0),
            "Equity Value (M)": round(res["Equity (M)"], 0),
            "Prix théorique": round(res["Prix théorique"], 2) if res["Prix théorique"] else None,
            "Upside vs cours %": round((res["Prix théorique"] / price - 1) * 100, 1) if (res["Prix théorique"] and price) else None,
        }
        for name_s, res in scen_results.items()
    })
    synth["Cours actuel"] = {"Prix théorique": round(price, 2) if price else None}
    st.dataframe(synth, use_container_width=True)

    # Sensitivity heatmap WACC x terminal growth, scénario base
    st.markdown("#### 🗺️ Sensibilité — WACC × Croissance terminale (base case, croissance 5y=6%)")
    waccs = [w / 100 for w in range(5, 13)]  # 5% → 12%
    gterms = [g / 100 for g in range(0, 5)]  # 0% → 4%
    sensi = []
    for gt in gterms:
        row = []
        for w in waccs:
            r = compute_dcf(fcf0, 0.06, gt, w)
            row.append(round(r["Prix théorique"], 1) if r["Prix théorique"] else None)
        sensi.append(row)
    sensi_df = pd.DataFrame(
        sensi,
        index=[f"g_term={gt*100:.1f}%" for gt in gterms],
        columns=[f"WACC={w*100:.1f}%" for w in waccs],
    )
    st.dataframe(sensi_df.style.format("{:,.1f}", na_rep="n/a"), use_container_width=True)
    if price:
        st.caption(f"💡 Cellules où le prix théorique > cours actuel ({price:,.2f} {currency}) = upside.")

    st.divider()
    st.markdown("#### 🧮 Valo par multiples EBITDA")
    if ebitda:
        ebitda_m = ebitda / 1e6
        mcol1, mcol2 = st.columns([1, 2])
        with mcol1:
            multiple = st.slider("Multiple EBITDA cible", 3.0, 30.0, 10.0, 0.5)
        ev_mult = ebitda_m * multiple
        equity_mult = ev_mult - nd_m
        fair_mult = (equity_mult * 1e6 / shares) if shares else None
        with mcol2:
            mm1, mm2, mm3 = st.columns(3)
            mm1.metric("EV (multiples)", f"{ev_mult:,.0f} M")
            mm2.metric("Equity (multiples)", f"{equity_mult:,.0f} M")
            if fair_mult and price:
                mm3.metric("Prix théorique", f"{fair_mult:,.2f}", f"{(fair_mult/price-1)*100:+.1f}%")
            elif fair_mult:
                mm3.metric("Prix théorique", f"{fair_mult:,.2f}")
    else:
        st.info("EBITDA indisponible dans Yahoo pour ce ticker.")

st.divider()
st.caption(
    "⚠️ MVP prototype — données Yahoo Finance, retard possible et complétude variable. "
    "V2 : brancher Financial Modeling Prep pour fiabilité + SEC EDGAR pour données officielles + "
    "LLM pour résumé marché/TAM sur onglet Marché."
)
