from datetime import datetime


def format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")