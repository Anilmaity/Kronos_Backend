"""
Chart candles, served live from the OANDA REST API (mid prices).

This used to time_bucket the `ltp` hypertable on TigerData TimescaleDB, but
that service was decommissioned (hostname NXDOMAIN) and the tick collectors
that fed it no longer exist, so candles now come straight from OANDA —
mirroring KronosStrategies/strategies/shared/tsdb_reader.py, which is how
every live runner already gets its bars. A short TTL cache keeps request
volume low while the chart page polls.
"""

import logging
import os
import re
import threading
import time as _time
from datetime import datetime, timezone

import graphene
import requests
from graphql import GraphQLError

logger = logging.getLogger(__name__)

# interval -> (OANDA granularity, source bars folded per bucket, bucket seconds)
# OANDA has no M3 granularity, so 3m is aggregated from M1.
INTERVAL_MAP = {
    "5s":  ("S5",  1, 5),
    "15s": ("S15", 1, 15),
    "30s": ("S30", 1, 30),
    "1m":  ("M1",  1, 60),
    "3m":  ("M1",  3, 180),
    "5m":  ("M5",  1, 300),
    "15m": ("M15", 1, 900),
    "30m": ("M30", 1, 1800),
    "1h":  ("H1",  1, 3600),
    "4h":  ("H4",  1, 14400),
    "1d":  ("D",   1, 86400),
}

_OANDA_API_KEY = os.getenv("OANDA_API_KEY", "").strip()
_OANDA_PRACTICE = os.getenv("OANDA_PRACTICE", "true").strip().lower() not in ("false", "0", "no")
_OANDA_BASE = "https://api-fxpractice.oanda.com/v3" if _OANDA_PRACTICE else "https://api-fxtrade.oanda.com/v3"
_HTTP_TIMEOUT = int(os.getenv("OANDA_HTTP_TIMEOUT", "15"))
_MAX_COUNT = 5000  # OANDA hard cap per request

_session = requests.Session()
_session.headers.update({
    "Authorization": f"Bearer {_OANDA_API_KEY}",
    "Accept-Datetime-Format": "RFC3339",
})

_TTL = float(os.getenv("CANDLES_CACHE_TTL_SEC", "5"))
_CACHE = {}  # (symbol, interval, limit) -> (fetched_at, [CandleType])
_CACHE_LOCK = threading.Lock()

_SYMBOL_RE = re.compile(r"^[A-Z0-9_]{3,20}$")


def _parse_time(rfc3339):
    # e.g. "2026-08-01T05:00:00.000000000Z" — second precision is enough
    return int(
        datetime.strptime(rfc3339[:19], "%Y-%m-%dT%H:%M:%S")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


class CandleType(graphene.ObjectType):
    time = graphene.Int()
    open = graphene.Float()
    high = graphene.Float()
    low = graphene.Float()
    close = graphene.Float()


def _fetch_oanda(symbol, granularity, count):
    resp = _session.get(
        f"{_OANDA_BASE}/instruments/{symbol}/candles",
        params={"granularity": granularity, "count": count, "price": "M"},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    out = []
    for c in resp.json().get("candles", []):
        mid = c.get("mid") or {}
        out.append((
            _parse_time(c["time"]),
            float(mid["o"]), float(mid["h"]), float(mid["l"]), float(mid["c"]),
        ))
    return out


def _aggregate(bars, bucket_secs):
    """Fold (time, o, h, l, c) source bars into bucket_secs-aligned buckets."""
    buckets = []
    for t, o, h, low, c in bars:
        b = t - (t % bucket_secs)
        if buckets and buckets[-1][0] == b:
            prev = buckets[-1]
            buckets[-1] = (b, prev[1], max(prev[2], h), min(prev[3], low), c)
        else:
            buckets.append((b, o, h, low, c))
    return buckets


class GetCandles(graphene.ObjectType):
    candles = graphene.List(
        CandleType,
        symbol=graphene.String(default_value="XAU_USD"),
        interval=graphene.String(default_value="5m"),
        limit=graphene.Int(default_value=500),
    )

    def resolve_candles(self, info, symbol, interval, limit):
        if interval not in INTERVAL_MAP:
            raise GraphQLError(
                f"Unknown interval '{interval}'. Valid: {list(INTERVAL_MAP)}"
            )
        if not _SYMBOL_RE.match(symbol or ""):
            raise GraphQLError(f"Invalid symbol '{symbol}'")

        granularity, fold, bucket_secs = INTERVAL_MAP[interval]
        limit = max(1, min(int(limit), _MAX_COUNT))

        key = (symbol, interval, limit)
        now = _time.monotonic()
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
            if hit and now - hit[0] < _TTL:
                return hit[1]

        count = min(limit * fold, _MAX_COUNT)
        try:
            bars = _fetch_oanda(symbol, granularity, count)
        except Exception as exc:
            logger.exception("candles query failed (symbol=%s interval=%s)", symbol, interval)
            raise GraphQLError(f"candles query failed: {exc}")

        if fold > 1:
            bars = _aggregate(bars, bucket_secs)
        bars = bars[-limit:]

        result = [
            CandleType(time=t, open=o, high=h, low=low, close=c)
            for t, o, h, low, c in bars
        ]
        with _CACHE_LOCK:
            _CACHE[key] = (now, result)
        return result
