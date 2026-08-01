"""
Tests for the OANDA-backed candles resolver (chart data source).

The TigerData TimescaleDB that used to back this query was decommissioned
(hostname NXDOMAIN, tick collectors removed), so candles are now fetched
live from the OANDA REST instruments endpoint, mirroring the pattern in
KronosStrategies/strategies/shared/tsdb_reader.py.

All OANDA HTTP is mocked — no network, no credentials needed.
"""

from unittest import mock

from django.test import TestCase
from graphql import GraphQLError

from apis.schema.query import get_candles as gc


def _oanda_payload(times_prices):
    """Build an OANDA candles JSON payload from [(epoch, o, h, l, c), ...]."""
    from datetime import datetime, timezone

    candles = []
    for t, o, h, low, c in times_prices:
        iso = datetime.fromtimestamp(t, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000000000Z"
        )
        candles.append(
            {
                "time": iso,
                "complete": True,
                "mid": {"o": str(o), "h": str(h), "l": str(low), "c": str(c)},
            }
        )
    return {"candles": candles}


class GetCandlesOandaTests(TestCase):
    def setUp(self):
        gc._CACHE.clear()

    def _resolve(self, payload, symbol="XAU_USD", interval="5m", limit=500):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = payload
        resp.raise_for_status.return_value = None
        with mock.patch.object(gc._session, "get", return_value=resp) as m:
            out = gc.GetCandles.resolve_candles(
                None, None, symbol=symbol, interval=interval, limit=limit
            )
        return out, m

    def test_native_interval_maps_to_oanda_granularity(self):
        payload = _oanda_payload([(600, 1, 2, 0.5, 1.5), (900, 1.5, 3, 1, 2)])
        out, m = self._resolve(payload, interval="5m", limit=10)
        url = m.call_args[0][0]
        params = m.call_args[1]["params"]
        self.assertIn("/instruments/XAU_USD/candles", url)
        self.assertEqual(params["granularity"], "M5")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].time, 600)
        self.assertEqual(out[1].close, 2.0)

    def test_5s_uses_S5(self):
        out, m = self._resolve(_oanda_payload([(5, 1, 1, 1, 1)]), interval="5s")
        self.assertEqual(m.call_args[1]["params"]["granularity"], "S5")

    def test_3m_aggregates_M1_buckets(self):
        # six M1 bars -> two 3m buckets, OHLC folded correctly
        bars = [
            (0, 10, 12, 9, 11),
            (60, 11, 15, 11, 14),
            (120, 14, 14, 8, 9),
            (180, 9, 10, 9, 10),
            (240, 10, 11, 7, 8),
            (300, 8, 9, 8, 9),
        ]
        out, m = self._resolve(_oanda_payload(bars), interval="3m", limit=10)
        self.assertEqual(m.call_args[1]["params"]["granularity"], "M1")
        self.assertEqual(len(out), 2)
        b0, b1 = out
        self.assertEqual((b0.time, b0.open, b0.high, b0.low, b0.close), (0, 10, 15, 8, 9))
        self.assertEqual((b1.time, b1.open, b1.high, b1.low, b1.close), (180, 9, 11, 7, 9))

    def test_limit_trims_to_most_recent(self):
        bars = [(i * 300, i, i, i, i) for i in range(10)]
        out, _ = self._resolve(_oanda_payload(bars), interval="5m", limit=3)
        self.assertEqual(len(out), 3)
        self.assertEqual(out[-1].time, 9 * 300)
        self.assertEqual(out[0].time, 7 * 300)

    def test_unknown_interval_raises(self):
        with self.assertRaises(GraphQLError):
            gc.GetCandles.resolve_candles(None, None, "XAU_USD", "7m", 10)

    def test_oanda_failure_raises_graphql_error(self):
        with mock.patch.object(gc._session, "get", side_effect=OSError("boom")):
            with self.assertRaises(GraphQLError):
                gc.GetCandles.resolve_candles(None, None, "XAU_USD", "5m", 10)

    def test_ttl_cache_prevents_second_fetch(self):
        payload = _oanda_payload([(0, 1, 1, 1, 1)])
        resp = mock.Mock(status_code=200)
        resp.json.return_value = payload
        resp.raise_for_status.return_value = None
        with mock.patch.object(gc._session, "get", return_value=resp) as m:
            gc.GetCandles.resolve_candles(None, None, "XAU_USD", "5m", 10)
            gc.GetCandles.resolve_candles(None, None, "XAU_USD", "5m", 10)
        self.assertEqual(m.call_count, 1)
