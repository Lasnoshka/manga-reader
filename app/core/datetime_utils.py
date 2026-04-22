from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC datetime — замена устаревшему datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
