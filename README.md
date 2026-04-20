# Market Screener — Parrit.ai

MVP d'un screener financier : recherche d'entreprise par nom ou ticker, analyse financière historique + projections, comparaison peers, avis analystes, playground de valorisation (DCF + multiples EBITDA).

## Lancer en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Sources

Yahoo Finance via `yfinance` (data delayed 15-20 min). V2 : Financial Modeling Prep pour data fiable et historiques profonds.

## Stack

- Streamlit (UI)
- yfinance (data)
- Plotly (charts)
- Pandas (calc)

Built by [Parrit.ai](https://parrit.ai).
