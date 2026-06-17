"""
Position PnL maths — pure (no Django imports) so it is unit-testable and shared
by PositionType and UserStrategyType, keeping the row totals and the strategy
total in agreement.

Direction matters: a position is LONG when avg_buy_price > 0 and SHORT when
avg_sell_price > 0 (the writer sets only the side it opened; the other stays 0).
The old long-only formula (ltp - avg_buy_price) * qty computed a short's PnL
against avg_buy_price == 0, so it returned ~ ltp * qty * contract ≈ the entry
price (the "4K" bug) with the wrong sign.

Stored realized_profit_loss and the prices are in "price x lots" units; the
contract size (1 XAU lot = 100 oz) converts to account currency at the edge.
"""

CONTRACT_SIZE = 100  # XAUUSD: 1 lot = 100 oz. Move onto CurrencyPair for non-gold.


def _unrealized(ltp: float, quantity: float, avg_buy_price: float,
                avg_sell_price: float) -> float:
    """Directional unrealized PnL in price-x-lots units (0 for a flat position)."""
    if avg_buy_price > 0:        # long
        return (ltp - avg_buy_price) * quantity
    if avg_sell_price > 0:       # short
        return (avg_sell_price - ltp) * quantity
    return 0.0                   # no entry on either side (e.g. cancelled)


def position_pnl(realized_profit_loss, ltp, quantity,
                 avg_buy_price, avg_sell_price, contract_size=CONTRACT_SIZE) -> float:
    """Realized + directional unrealized PnL, in account currency, rounded to 2dp."""
    realized = float(realized_profit_loss)
    unreal = _unrealized(float(ltp), float(quantity),
                         float(avg_buy_price), float(avg_sell_price))
    return round((realized + unreal) * contract_size, 2)


def position_notional(quantity, avg_buy_price, avg_sell_price,
                      contract_size=CONTRACT_SIZE) -> float:
    """Position value at entry (whichever side was opened), in account currency."""
    buy, sell = float(avg_buy_price), float(avg_sell_price)
    entry = buy if buy > 0 else sell
    return round(entry * float(quantity) * contract_size, 2)


def position_pnl_pct(realized_profit_loss, ltp, quantity,
                     avg_buy_price, avg_sell_price, contract_size=CONTRACT_SIZE) -> float:
    """PnL as a % of notional. 0 when there is no notional (avoids /0 on shorts)."""
    notional = position_notional(quantity, avg_buy_price, avg_sell_price, contract_size)
    if not notional:
        return 0.0
    pnl = position_pnl(realized_profit_loss, ltp, quantity,
                       avg_buy_price, avg_sell_price, contract_size)
    return round(pnl / notional * 100, 2)
