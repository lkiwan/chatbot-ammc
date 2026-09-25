import hashlib
import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

_LOCK = threading.Lock()
_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "analytics.json"

_EMPTY = {"visits": [], "demo_logins": [], "demo_messages": [], "demo_exhausted": []}


def _detect_device(ua: str) -> str:
    ua_lower = ua.lower()
    if "ipad" in ua_lower or "tablet" in ua_lower:
        return "tablet"
    if any(k in ua_lower for k in ("mobile", "android", "iphone", "ipod", "windows phone")):
        return "mobile"
    return "desktop"


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:8]


def load_analytics() -> dict:
    try:
        if _DATA_FILE.exists():
            return json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {k: list(v) for k, v in _EMPTY.items()}


def _save(data: dict) -> None:
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_event(event_type: str, ua: str = "", ip: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        data = load_analytics()
        if event_type == "visit":
            data["visits"].append({"ts": now, "device": _detect_device(ua), "ip_hash": _hash_ip(ip)})
        elif event_type == "demo_login":
            data["demo_logins"].append({"ts": now, "device": _detect_device(ua)})
        elif event_type == "demo_message":
            data["demo_messages"].append({"ts": now})
        elif event_type == "demo_exhausted":
            data.setdefault("demo_exhausted", []).append({"ts": now, "device": _detect_device(ua)})
        _save(data)


def get_summary() -> dict:
    data = load_analytics()
    now = datetime.now(timezone.utc)
    cutoff_30d = (now - timedelta(days=30)).isoformat()

    visits = data.get("visits", [])
    demo_logins = data.get("demo_logins", [])
    demo_messages = data.get("demo_messages", [])
    demo_exhausted = data.get("demo_exhausted", [])

    # Unique visitors (by ip_hash) in last 30 days
    recent_visits = [v for v in visits if v.get("ts", "") >= cutoff_30d]
    unique_ips = len({v.get("ip_hash") for v in recent_visits if v.get("ip_hash")})

    # Device breakdown across all visits
    device_counts: dict[str, int] = {"desktop": 0, "mobile": 0, "tablet": 0}
    for v in visits:
        d = v.get("device", "desktop")
        device_counts[d] = device_counts.get(d, 0) + 1

    # Visits per day for last 7 days
    days_7: list[dict] = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        label = day.strftime("%a")
        prefix = day.date().isoformat()
        count = sum(1 for v in visits if v.get("ts", "").startswith(prefix))
        days_7.append({"day": label, "date": prefix, "count": count})

    # Demo logins per day for last 7 days
    demo_days_7: list[dict] = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        label = day.strftime("%a")
        prefix = day.date().isoformat()
        count = sum(1 for v in demo_logins if v.get("ts", "").startswith(prefix))
        demo_days_7.append({"day": label, "date": prefix, "count": count})

    # Demo exhausted per day for last 7 days
    exhausted_days_7: list[dict] = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        label = day.strftime("%a")
        prefix = day.date().isoformat()
        count = sum(1 for v in demo_exhausted if v.get("ts", "").startswith(prefix))
        exhausted_days_7.append({"day": label, "date": prefix, "count": count})

    return {
        "total_visits": len(visits),
        "unique_visitors_30d": unique_ips,
        "total_demo_logins": len(demo_logins),
        "total_demo_messages": len(demo_messages),
        "total_demo_exhausted": len(demo_exhausted),
        "device_breakdown": device_counts,
        "visits_per_day": days_7,
        "demo_logins_per_day": demo_days_7,
        "demo_exhausted_per_day": exhausted_days_7,
    }
