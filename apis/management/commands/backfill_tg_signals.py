"""Backfill StrategySignal rows from historical telegram copy-trade positions.

The telegram copy-trader writes apis_position rows (dashboard PnL) but never
wrote StrategySignal rows, so the frontend "Signals" tab showed no telegram
signals. This one-time backfill creates one PLACED StrategySignal per existing
telegram position so past signals appear immediately. Going forward the bot
records signals live (apis_persist.record_signal).

Idempotent: a position that already has a linked StrategySignal is skipped, so
re-running is safe. Dry-run by default.

  python manage.py backfill_tg_signals            # dry-run (counts only)
  python manage.py backfill_tg_signals --commit   # write
  python manage.py backfill_tg_signals --name "Neymar" --commit
"""
from django.core.management.base import BaseCommand

from apis.models import UserStrategy, Position, StrategySignal


class Command(BaseCommand):
    help = "Backfill StrategySignal rows from historical telegram copy-trade positions."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true",
                            help="Persist rows (default is a dry-run).")
        parser.add_argument("--name", default="Neymar",
                            help="Strategy name substring to match (default: Neymar).")

    def handle(self, *args, **opts):
        commit = opts["commit"]
        name = opts["name"]
        uss = list(
            UserStrategy.objects.select_related("strategy")
            .filter(strategy__name__icontains=name)
        )
        if not uss:
            self.stdout.write(self.style.WARNING(f"No UserStrategy matches name~='{name}'"))
            return

        created = skipped = 0
        for us in uss:
            strat = us.strategy
            positions = Position.objects.filter(user_strategy_id=us.id).order_by("created_at")
            for p in positions:
                if p.strategy_signals.exists():
                    skipped += 1
                    continue
                is_long = float(p.total_buy_quantity or 0) > 0
                entry = p.avg_buy_price if is_long else p.avg_sell_price
                ss = StrategySignal(
                    strategy=strat,
                    symbol=p.symbol,
                    side="BUY" if is_long else "SELL",
                    entry_price=entry or 0,
                    stop_loss=None,
                    take_profit=None,
                    reason="TG copy (backfilled from position)",
                    status="PLACED",
                    signal_at=p.created_at,
                    position=p,
                )
                if commit:
                    ss.save()
                created += 1
            self.stdout.write(f"  {strat.name}: {positions.count()} positions")

        verb = "Created" if commit else "Would create"
        self.stdout.write(self.style.SUCCESS(
            f"{'COMMITTED' if commit else 'DRY-RUN'}: {verb} {created} StrategySignal "
            f"row(s); skipped {skipped} (already linked)."))
