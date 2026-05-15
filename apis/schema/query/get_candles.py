import graphene
from django.db import connections
from graphql import GraphQLError


INTERVAL_MAP = {
    "5s":  ("5 seconds",  5),
    "15s": ("15 seconds", 15),
    "30s": ("30 seconds", 30),
    "1m":  ("1 minute",   60),
    "3m":  ("3 minutes",  180),
    "5m":  ("5 minutes",  300),
    "15m": ("15 minutes", 900),
    "30m": ("30 minutes", 1800),
    "1h":  ("1 hour",     3600),
    "4h":  ("4 hours",    14400),
    "1d":  ("1 day",      86400),
}


class CandleType(graphene.ObjectType):
    time = graphene.Int()
    open = graphene.Float()
    high = graphene.Float()
    low = graphene.Float()
    close = graphene.Float()


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
        tsdb_alias = "tsdb" if "tsdb" in connections.databases else "default"

        bucket_sql, bucket_secs = INTERVAL_MAP[interval]
        limit = max(1, min(int(limit), 5000))
        history_secs = bucket_secs * limit * 3

        sql = """
            SELECT bucket, open, high, low, close FROM (
                SELECT time_bucket(%s::interval, time) AS bucket,
                       first(ltp::float8, time) AS open,
                       max(ltp::float8)         AS high,
                       min(ltp::float8)         AS low,
                       last(ltp::float8, time)  AS close
                FROM   ltp
                WHERE  symbol = %s
                  AND  time  >= NOW() - (%s || ' seconds')::interval
                GROUP BY bucket
                ORDER  BY bucket DESC
                LIMIT  %s
            ) sub
            ORDER BY bucket ASC;
        """

        try:
            with connections[tsdb_alias].cursor() as cur:
                cur.execute(sql, [bucket_sql, symbol, history_secs, limit])
                rows = cur.fetchall()
        except Exception as exc:
            raise GraphQLError(f"candles query failed: {exc}")

        return [
            CandleType(
                time=int(r[0].timestamp()),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
            )
            for r in rows
        ]
