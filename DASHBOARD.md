# 📈 Daily Market Dashboard

An interactive dashboard of global and Korean economic indicators, refreshed on
demand. The data is gathered **server-side** by a GitHub Action (a static web
page can't fetch these sources directly — most block cross-origin browser
requests), and published to GitHub Pages. A **Refresh** button on the page asks
the Action to re-gather and re-publish, then reloads when it's done.

**Live page:** https://kwmski7.github.io/kwmski7/

## What it shows

| Section | Contents |
|---|---|
| **Global markets** | S&P 500, Dow, Nasdaq, Russell 2000 (7-day, rebased to 100); Dollar Index (DXY); USD/KRW, EUR/USD, USD/JPY, USD/CNY; WTI, Brent, gold, silver, copper, natural gas; 10-year government bond yields; **US Treasury yield curve** with today vs. ~1-week / ~1-month lines to show the shift |
| **Korea** | KOSPI, KOSDAQ, KOSPI 200, KOSDAQ 150 (7-day, rebased); optional **KTB yield curve** with trend (see ECOS below) |
| **Sector maps** | Treemaps of daily performance — US S&P 500 sectors (SPDR ETFs) and Korean KOSPI/KOSDAQ sectors (KODEX ETFs), colored red-up / blue-down (Korean convention) with the exact % on each tile |

Colors follow the validated, colorblind-safe blue↔red diverging pair; every
value is also labeled numerically, so meaning never rests on color alone. A
light/dark theme toggle is included.

## How it fits together

```
scripts/config.py      all tickers & instrument definitions (edit here)
scripts/fetch_data.py  gathers data -> site/data.json (+ committed data/ snapshot)
web/index.html         the dashboard (static; reads data.json, draws with Plotly)
.github/workflows/refresh.yml   installs deps, runs fetch, deploys to Pages
```

Data source: **Yahoo Finance** via `yfinance` (no API key). Any ticker that
returns no data is skipped and listed under the dashboard's **Data notes** — so
the page never breaks on a single bad symbol, and you can add speculative
tickers safely.

## One-time setup

1. **Enable GitHub Pages from Actions.** Repo → **Settings → Pages → Build and
   deployment → Source: GitHub Actions**.
2. **Run it once.** Repo → **Actions → "Refresh market data" → Run workflow**.
   This generates `data.json` and publishes the site. (Until the first run, the
   page shows a "run the workflow" message instead of data.)
3. Open the live page and confirm data appears.

## Using the Refresh button

The Refresh button triggers the Action via the GitHub API, which needs a token
(the page is static and can't hold a server secret):

1. Create a **fine-grained token**:
   [Settings → Developer settings → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
   → **Generate new token**.
2. **Repository access → Only select repositories →** this repo.
3. **Permissions → Repository → Actions → Read and write.**
4. Generate, copy, and paste it when the dashboard prompts.

The token is stored **only in your browser** (`localStorage`) and is sent only
to `api.github.com`. Use **"Forget saved token"** in the footer to remove it.
After a refresh, the button waits for the run to finish and for Pages to
re-publish (~1–2 minutes), then reloads automatically.

## Optional: Korean government bond yield curve

The KTB yield curve uses the **Bank of Korea ECOS** API. To enable it:

1. Get a free key at https://ecos.bok.or.kr (API 인증키 신청).
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**,
   named `ECOS_API_KEY`.

Without the key, that one section is simply omitted; everything else works. If
the item codes in `config.py` (`ECOS_KR_CURVE`) don't match the current ECOS
table, adjust them there.

## Re-enabling the daily 9am run

Manual-only by default. To also auto-refresh every morning at **9am KST**,
uncomment the `schedule` block in `.github/workflows/refresh.yml`:

```yaml
  schedule:
    - cron: "0 0 * * *"   # 00:00 UTC == 09:00 KST
```

## Customizing the data

All symbols live in [`scripts/config.py`](scripts/config.py) — grouped by
indices, FX, commodities, bonds, Korean indices, yield-curve points, and the US
/ Korea sector lists. Edit the lists (Yahoo Finance symbols), commit, and the
next refresh picks them up. To flip the up/down color convention to the Western
green-up/red-down, change `--up` / `--down` in the `web/index.html` palette
block.

## Local run

```bash
pip install -r requirements.txt
python scripts/fetch_data.py           # writes site/data.json
python -m http.server -d site 8000     # open http://localhost:8000
```
