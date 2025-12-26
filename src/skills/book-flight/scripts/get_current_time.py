#!/usr/bin/env python3
"""Get current date and time information for flight booking context."""

from datetime import datetime
import json


def get_current_time() -> dict:
    """Return current time information in multiple formats."""
    now = datetime.now()
    
    return {
        "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "timezone": "Local",
        "timestamp": int(now.timestamp()),
    }


if __name__ == "__main__":
    result = get_current_time()
    print(f"Current Date: {result['date']}")
    print(f"Current Time: {result['time']}")
    print(f"Day of Week: {result['weekday']}")
    print(f"Full Datetime: {result['current_datetime']}")
    print(f"\nJSON Output:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

