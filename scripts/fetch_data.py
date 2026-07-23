"""Gather global & Korean market data and emit a single ``data.json``.

Run by the GitHub Action (manually or on demand via the dashboard's Refresh
button). Every network call is defensive: one bad ticker never aborts the
run — it is recorded in ``errors`` and surfaced on the dashboard.

Outputs (all JSON):
    site/data.json            -> served by GitHub Pages, read by the dashboard
    data/latest.json          -> committed, always the newest snapshot
    data/history/<date>.json  -> committed, a lightweight daily record

Data source: Yahoo Finance via ``yfinance`` (no API key). The Korean govt
bond curve optionally comes from Bank of Korea ECOS if ECOS_API_KEY is set.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import config

try:
    import yfinance as yf
except Exception as exc:  # pragma: no cover - import guard
    print(f"FATAL: yfinance import failed: {exc}", file=sys.stderr)
    raise

KST = timezone(timedelta(hours=9))
ERRORS: list[str] = []


def note_error(msg: str) -> None:
    print(f"  ! {msg}", file=sys.stderr)
    ERRORS.append(msg)


# --------------------------------------------------------------------------
# Download layer
# --------------------------------------------------------------------------
def download_history(tickers: list[str]) -> dict[str, pd.Series]:
    """Return {ticker: close-price Series} for every ticker that returned data.

    A single batched request is attempted first; anything that comes back
    empty is retried individually so one dead symbol does not blank a batch.
    """
    tickers = sorted(set(t for t in tickers if t))
    closes: dict[str, pd.Series] = {}
    if not tickers:
        return closes

    def extract(df: pd.DataFrame, ticker: str) -> pd.Series | None:
        try:
            if isinstance(df.columns, pd.MultiIndex):
                if ticker not in df.columns.get_level_values(0):
                    return None
                sub = df[ticker]
            else:
                sub = df
            col = "Close" if "Close" in sub.columns else ("Adj Close" if "Adj Close" in sub.columns else None)
            if col is None:
                return None
            s = pd.to_numeric(sub[col], errors="coerce").dropna()
            return s if len(s) else None
        except Exception:
            return None

    print(f"Downloading {len(tickers)} tickers (batched)...")
    try:
        batch = yf.download(
            tickers, period=config.HISTORY_PERIOD, interval="1d",
            auto_adjust=False, progress=False, threads=True, group_by="ticker",
        )
    except Exception as exc:
        note_error(f"batch download failed ({exc}); falling back to per-ticker")
        batch = None

    missing = []
    for t in tickers:
        s = extract(batch, t) if batch is not None and not batch.empty else None
        if s is None:
            missing.append(t)
        else:
            closes[t] = s

    for t in missing:
        try:
            df = yf.download(t, period=config.HISTORY_PERIOD, interval="1d",
                             auto_adjust=False, progress=False, threads=False)
            s = extract(df, t)
            if s is not None:
                closes[t] = s
            else:
                note_error(f"no data for {t}")
        except Exception as exc:
            note_error(f"download failed for {t}: {exc}")

    print(f"  got {len(closes)}/{len(tickers)} tickers")
    return closes


# --------------------------------------------------------------------------
# Transforms
# --------------------------------------------------------------------------
def pct(cur: float, prev: float) -> float | None:
    if prev in (None, 0) or cur is None:
        return None
    return round((cur - prev) / prev * 100.0, 2)


def spark(series: pd.Series, n: int = 8) -> list[float]:
    """Last ``n`` closes as plain floats for a sparkline."""
    tail = series.tail(n)
    return [round(float(v), 4) for v in tail.to_list()]


def quote(meta: dict, series: pd.Series | None) -> dict | None:
    """Build a stat-tile quote (latest value, day change, week sparkline)."""
    if series is None or len(series) == 0:
        return None
    vals = series.to_list()
    last = float(vals[-1])
    prev = float(vals[-2]) if len(vals) >= 2 else None
    week_prev = float(vals[-6]) if len(vals) >= 6 else (float(vals[0]) if vals else None)
    return {
        "label": meta["label"],
        "ticker": meta["ticker"],
        "unit": meta.get("unit", ""),
        "decimals": meta.get("decimals", 2),
        "value": round(last, 6),
        "change_pct": pct(last, prev),
        "week_pct": pct(last, week_prev),
        "spark": spark(series),
        "asof": series.index[-1].strftime("%Y-%m-%d"),
    }


def build_quotes(group: dict, closes: dict) -> dict:
    out = {}
    for key, meta in group.items():
        q = quote(meta, closes.get(meta["ticker"]))
        if q is not None:
            out[key] = q
        else:
            note_error(f"{meta['label']} ({meta['ticker']}): no data")
    return out


def build_indexed_series(group: dict, closes: dict, days: int = 7) -> dict:
    """Overlay-comparison series: each index rebased to 100 at the window start.

    Rebasing keeps everything on ONE axis (per the dataviz rule) so indices of
    wildly different absolute levels can be compared on a single chart.
    """
    frames = {}
    for meta in group.values():
        s = closes.get(meta["ticker"])
        if s is not None and len(s):
            frames[meta["label"]] = s
    if not frames:
        return {}
    df = pd.DataFrame(frames).dropna(how="all").tail(days)
    df = df.dropna(axis=1, how="all")
    if df.empty:
        return {}
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    indexed, raw = {}, {}
    for col in df.columns:
        col_s = df[col].dropna()
        if col_s.empty:
            continue
        base = float(col_s.iloc[0])
        indexed[col] = [round(float(v) / base * 100.0, 3) if pd.notna(v) else None for v in df[col]]
        raw[col] = [round(float(v), 3) if pd.notna(v) else None for v in df[col]]
    return {"dates": dates, "indexed": indexed, "raw": raw}


def normalize_yield(v: float) -> float:
    """Some Yahoo yield symbols quote percent x10 (42.5 == 4.25%)."""
    return v / 10.0 if v is not None and v > 20 else v


def value_at_offset(series: pd.Series, trading_days_ago: int) -> float | None:
    if series is None or len(series) == 0:
        return None
    idx = len(series) - 1 - trading_days_ago
    if idx < 0:
        return None
    return float(series.iloc[idx])


def build_us_curve(closes: dict) -> dict | None:
    mats, today, wk, mo = [], [], [], []
    for point in config.US_YIELD_CURVE:
        s = closes.get(point["ticker"])
        if s is None or len(s) == 0:
            continue
        mats.append(point["label"])
        today.append(round(normalize_yield(value_at_offset(s, 0)), 3))
        w = value_at_offset(s, 5)
        m = value_at_offset(s, 21)
        wk.append(round(normalize_yield(w), 3) if w is not None else None)
        mo.append(round(normalize_yield(m), 3) if m is not None else None)
    if not mats:
        note_error("US yield curve: no data")
        return None
    asof = None
    for point in config.US_YIELD_CURVE:
        s = closes.get(point["ticker"])
        if s is not None and len(s):
            asof = s.index[-1].strftime("%Y-%m-%d")
            break
    return {"maturities": mats, "today": today, "week_ago": wk, "month_ago": mo, "asof": asof}


def build_sectors(sector_list: list, closes: dict) -> list:
    out = []
    for sec in sector_list:
        s = closes.get(sec["ticker"])
        if s is None or len(s) < 2:
            note_error(f"sector {sec['name']} ({sec['ticker']}): no data")
            continue
        last = float(s.iloc[-1])
        prev = float(s.iloc[-2])
        out.append({
            "name": sec["name"],
            "ticker": sec["ticker"],
            "price": round(last, 2),
            "change_pct": pct(last, prev),
            "week_pct": pct(last, float(s.iloc[-6]) if len(s) >= 6 else float(s.iloc[0])),
        })
    return out


# --------------------------------------------------------------------------
# Korean government bond curve via Bank of Korea ECOS (optional)
# --------------------------------------------------------------------------
def build_kr_curve() -> dict | None:
    key = os.environ.get("ECOS_API_KEY", "").strip()
    if not key:
        return None
    import requests

    end = datetime.now(KST).strftime("%Y%m%d")
    start = (datetime.now(KST) - timedelta(days=45)).strftime("%Y%m%d")

    def fetch_item(item: str) -> pd.Series | None:
        url = (
            f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/100/"
            f"{config.ECOS_STAT_CODE}/D/{start}/{end}/{item}"
        )
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            rows = r.json().get("StatisticSearch", {}).get("row", [])
            pairs = [(row["TIME"], float(row["DATA_VALUE"])) for row in rows if row.get("DATA_VALUE")]
            if not pairs:
                return None
            pairs.sort()
            return pd.Series([v for _, v in pairs], index=[t for t, _ in pairs])
        except Exception as exc:
            note_error(f"ECOS item {item} failed: {exc}")
            return None

    mats, today, wk, mo = [], [], [], []
    asof = None
    for point in config.ECOS_KR_CURVE:
        s = fetch_item(point["item"])
        if s is None or len(s) == 0:
            continue
        mats.append(point["label"])
        today.append(round(float(s.iloc[-1]), 3))
        wk.append(round(float(s.iloc[-6]), 3) if len(s) >= 6 else None)
        mo.append(round(float(s.iloc[-22]), 3) if len(s) >= 22 else None)
        asof = str(s.index[-1])
    if not mats:
        note_error("Korea yield curve: ECOS returned no data")
        return None
    asof_fmt = f"{asof[:4]}-{asof[4:6]}-{asof[6:]}" if asof and len(asof) == 8 else asof
    return {"maturities": mats, "today": today, "week_ago": wk, "month_ago": mo, "asof": asof_fmt}


# --------------------------------------------------------------------------
# Assemble
# --------------------------------------------------------------------------
def main() -> int:
    all_tickers: list[str] = []
    for group in (config.GLOBAL_INDICES, config.FX_DOLLAR, config.COMMODITIES,
                  config.GLOBAL_BONDS, config.KOREA_INDICES):
        all_tickers += [m["ticker"] for m in group.values()]
    all_tickers += [p["ticker"] for p in config.US_YIELD_CURVE]
    all_tickers += [s["ticker"] for s in config.US_SECTORS]
    all_tickers += [s["ticker"] for s in config.KR_SECTORS]

    closes = download_history(all_tickers)

    quotes = {}
    quotes.update(build_quotes(config.GLOBAL_INDICES, closes))
    quotes.update(build_quotes(config.FX_DOLLAR, closes))
    quotes.update(build_quotes(config.COMMODITIES, closes))
    quotes.update(build_quotes(config.GLOBAL_BONDS, closes))
    quotes.update(build_quotes(config.KOREA_INDICES, closes))

    now = datetime.now(timezone.utc)
    data = {
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_at_kst": now.astimezone(KST).strftime("%Y-%m-%d %H:%M KST"),
        "source": "Yahoo Finance" + (" + BOK ECOS" if os.environ.get("ECOS_API_KEY") else ""),
        "quotes": quotes,
        "groups": {
            "global_indices": [k for k in config.GLOBAL_INDICES if k in quotes],
            "fx_dollar": [k for k in config.FX_DOLLAR if k in quotes],
            "commodities": [k for k in config.COMMODITIES if k in quotes],
            "global_bonds": [k for k in config.GLOBAL_BONDS if k in quotes],
            "korea_indices": [k for k in config.KOREA_INDICES if k in quotes],
        },
        "series": {
            "global_indices": build_indexed_series(config.GLOBAL_INDICES, closes),
            "korea_indices": build_indexed_series(config.KOREA_INDICES, closes),
        },
        "yield_curves": {},
        "sectors": {
            "US": build_sectors(config.US_SECTORS, closes),
            "KR": build_sectors(config.KR_SECTORS, closes),
        },
    }

    us_curve = build_us_curve(closes)
    if us_curve:
        data["yield_curves"]["US"] = us_curve
    kr_curve = build_kr_curve()
    if kr_curve:
        data["yield_curves"]["KR"] = kr_curve

    data["errors"] = ERRORS

    # Write outputs -------------------------------------------------------
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    site_dir = os.path.join(root, "site")
    data_dir = os.path.join(root, "data")
    hist_dir = os.path.join(data_dir, "history")
    os.makedirs(site_dir, exist_ok=True)
    os.makedirs(hist_dir, exist_ok=True)

    payload = json.dumps(data, ensure_ascii=False, indent=2)
    for path in (
        os.path.join(site_dir, "data.json"),
        os.path.join(data_dir, "latest.json"),
        os.path.join(hist_dir, now.astimezone(KST).strftime("%Y-%m-%d") + ".json"),
    ):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(payload)

    print(f"\nDone. quotes={len(quotes)} sectors_us={len(data['sectors']['US'])} "
          f"sectors_kr={len(data['sectors']['KR'])} curves={list(data['yield_curves'])} "
          f"errors={len(ERRORS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
