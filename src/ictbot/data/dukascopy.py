"""Dukascopy tick-data downloader (free source; spec B1 allows independent tick
sources as long as the source is documented in every report).

Dukascopy serves one LZMA-compressed ``.bi5`` file per instrument per hour:

    https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YYYY}/{MM}/{DD}/{HH}h_ticks.bi5

where ``MM`` is **0-indexed** (January = 00) and ``HH`` is 00-23 UTC. Each file
decompresses to a stream of 20-byte big-endian records:

    >IIIff  ->  (ms_from_hour, ask_pts, bid_pts, ask_vol, bid_vol)

Prices are integer "points"; divide by ``point`` (1e5 for 5-digit EURUSD).
Timestamps are UTC. Downloaded raw files are cached under ``data/raw`` so a
re-run never re-downloads.
"""
from __future__ import annotations

import lzma
import ssl
import struct
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
RECORD = struct.Struct(">IIIff")  # 20 bytes
DEFAULT_POINT = 1e5               # EURUSD: 5 decimal digits
CA_BUNDLE = "/root/.ccr/ca-bundle.crt"


def _ssl_context() -> ssl.SSLContext:
    """Default context, trusting the agent-proxy CA bundle when present."""
    if Path(CA_BUNDLE).exists():
        return ssl.create_default_context(cafile=CA_BUNDLE)
    return ssl.create_default_context()


def hour_url(symbol: str, dt: datetime) -> str:
    return (
        f"{BASE_URL}/{symbol}/{dt.year:04d}/{dt.month - 1:02d}/"
        f"{dt.day:02d}/{dt.hour:02d}h_ticks.bi5"
    )


def _fetch(url: str, retries: int = 4, timeout: int = 30) -> bytes:
    """GET with exponential backoff on network errors. 404 -> b'' (no ticks)."""
    ctx = _ssl_context()
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ictbot/1.0"})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return b""  # Dukascopy has no file for closed-market hours
            last_err = e
            if e.code in (403, 407):
                raise  # egress policy denial — do not retry
        except Exception as e:  # noqa: BLE001 - network flake, retry
            last_err = e
        time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def parse_bi5(raw: bytes, hour_start: datetime, point: float = DEFAULT_POINT) -> pd.DataFrame:
    """Decompress+parse one .bi5 blob into a tick DataFrame (UTC index)."""
    if not raw:
        return pd.DataFrame(columns=["bid", "ask", "bid_vol", "ask_vol"])
    data = lzma.decompress(raw)
    n = len(data) // RECORD.size
    ts, bid, ask, bvol, avol = [], [], [], [], []
    base = hour_start.replace(tzinfo=timezone.utc)
    for i in range(n):
        ms, ask_p, bid_p, av, bv = RECORD.unpack_from(data, i * RECORD.size)
        ts.append(base + timedelta(milliseconds=ms))
        ask.append(ask_p / point)
        bid.append(bid_p / point)
        avol.append(av)
        bvol.append(bv)
    df = pd.DataFrame(
        {"bid": bid, "ask": ask, "bid_vol": bvol, "ask_vol": avol},
        index=pd.DatetimeIndex(ts, name="time"),
    )
    return df


def download_hour(
    symbol: str,
    dt: datetime,
    cache_dir: str | Path = "data/raw",
    point: float = DEFAULT_POINT,
) -> pd.DataFrame:
    """Fetch (or load cached) one hour of ticks for ``symbol``."""
    cache_dir = Path(cache_dir)
    cache = cache_dir / symbol / f"{dt:%Y-%m-%d}" / f"{dt.hour:02d}h.bi5"
    if cache.exists():
        raw = cache.read_bytes()
    else:
        raw = _fetch(hour_url(symbol, dt))
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
    return parse_bi5(raw, dt, point)


def download_range(
    symbol: str,
    start: datetime,
    end: datetime,
    cache_dir: str | Path = "data/raw",
    point: float = DEFAULT_POINT,
) -> pd.DataFrame:
    """Download all ticks in [start, end) hour by hour (UTC). Concatenated."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    frames, cur = [], start.replace(minute=0, second=0, microsecond=0)
    while cur < end:
        df = download_hour(symbol, cur, cache_dir, point)
        if not df.empty:
            frames.append(df)
        cur += timedelta(hours=1)
    if not frames:
        return pd.DataFrame(columns=["bid", "ask", "bid_vol", "ask_vol"])
    out = pd.concat(frames)
    out.index = out.index.tz_localize("UTC") if out.index.tz is None else out.index
    return out.sort_index()
