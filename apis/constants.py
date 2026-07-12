"""Shared constants for the apis app.

The whole API reports in IST; every schema module used to declare its own
``kolkata = timezone("Asia/Kolkata")`` copy. This is the single home for it.
"""
from datetime import datetime

from pytz import timezone

KOLKATA_TZ = timezone("Asia/Kolkata")


def now_ist():
    """Current timezone-aware datetime in Asia/Kolkata."""
    return datetime.now(tz=KOLKATA_TZ)


def today_ist():
    """Current date in Asia/Kolkata."""
    return now_ist().date()
