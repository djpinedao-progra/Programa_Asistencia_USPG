from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def local_datetime(value, timezone_name="America/Guatemala"):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(timezone_name))


def utc_isoformat(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def local_date_utc_bounds(value, timezone_name="America/Guatemala"):
    day = date.fromisoformat(value)
    local_zone = ZoneInfo(timezone_name)
    start = datetime.combine(day, time.min, tzinfo=local_zone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=local_zone)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )