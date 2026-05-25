from datetime import datetime, timezone
from typing import Optional


def utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    """Normaliza datetimes aware a UTC naive para columnas timestamp sin zona."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
