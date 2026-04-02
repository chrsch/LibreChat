"""
Number and date formatting utilities for the Collmex API.
"""

import re
from datetime import date, timedelta


def to_comma_float(value: float) -> str:
    """Convert a number to German comma-decimal format: 100.00 → '100,00'."""
    return f"{value:.2f}".replace(".", ",")


def to_collmex_upload_date(iso_date: str) -> str:
    """Parse YYYY-MM-DD to DD.MM.YYYY for CMXLRN upload."""
    parts = iso_date.split("-")
    if len(parts) != 3:
        return iso_date
    return f"{parts[2]}.{parts[1]}.{parts[0]}"


def to_collmex_query_date(iso_date: str) -> str:
    """Parse YYYY-MM-DD to YYYYMMDD for ACCDOC_GET queries."""
    return iso_date.replace("-", "")


def today_yyyymmdd() -> str:
    """Get today's date in YYYYMMDD format."""
    return date.today().strftime("%Y%m%d")


def years_ago_yyyymmdd(n: int) -> str:
    """Get a date N years ago in YYYYMMDD format."""
    d = date.today()
    try:
        d = d.replace(year=d.year - n)
    except ValueError:
        # Handle Feb 29 → Feb 28
        d = d.replace(month=2, day=28, year=d.year - n)
    return d.strftime("%Y%m%d")


def clean_text(text: str) -> str:
    """Clean text: remove backslashes, normalize whitespace."""
    text = text.replace("\\", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()
