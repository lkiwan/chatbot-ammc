import hashlib
import hmac
import ipaddress
import json
import os
import threading
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

_LOCK = threading.Lock()
_ROOT = Path(__file__).resolve().parent.parent
_DATA_FILE = Path(
    os.environ.get("ANALYTICS_FILE") or (_ROOT / "data" / "analytics.json")
)
_GEO_FILE = _DATA_FILE.with_name(f"{_DATA_FILE.stem}_geo.json")
_SALT = (
    os.environ.get("ANALYTICS_SALT")
    or os.environ.get("API_TOKEN")
    or "ammc-local-dev"
).encode()

_EMPTY = {"visits": [], "demo_logins": [], "demo_messages": [], "demo_exhausted": []}
# event type (singular) -> storage bucket (plural)
_BUCKET = {
    "visit": "visits",
    "demo_login": "demo_logins",
    "demo_message": "demo_messages",
    "demo_exhausted": "demo_exhausted",
}
_GEO_FIELDS = ("city", "country", "country_code", "isp")
_LOCAL_GEO = {"city": "Local", "country": "Private Network", "country_code": "", "isp": ""}
_NO_GEO = {"city": "", "country": "", "country_code": "", "isp": ""}

_GEO_CACHE: dict[str, dict] = {}
_GEO_LOCK = threading.Lock()
# ip-api.com's free tier is 45 req/min, so the cache is the only thing keeping
# us under that limit once the demo gets real traffic. The disk mirror below
# makes the cache survive restarts.
_GEO_CACHE_MAX = 5000


def is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_unspecified
    except ValueError:
        return False


def _normalize_ip(ip: str) -> str:
    """Collapse IPv4-mapped IPv6 (::ffff:1.2.3.4) to plain IPv4.

    Uvicorn reports IPv4 peers in the mapped form, so without this the same
    visitor hashes and geolocates as two different people.
    """
    raw = (ip or "").strip()
    if not raw:
        return ""
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return raw
    if addr.version == 6 and addr.ipv4_mapped:
        return str(addr.ipv4_mapped)
    return str(addr)


def _load_geo_disk() -> dict:
    try:
        if _GEO_FILE.exists():
            data = json.loads(_GEO_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {
                    k: v for k, v in data.items()
                    if isinstance(v, dict) and not is_private_ip(k)
                }
    except Exception:
        pass
    return {}


def _save_geo_disk(cache: dict) -> None:
    try:
        _GEO_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _GEO_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_GEO_FILE)
    except Exception:
        # the geo cache is an optimisation, never a hard dependency
        pass


def _geo_lookup(ip: str) -> dict:
    if not ip or is_private_ip(ip):
        return dict(_LOCAL_GEO)
    with _GEO_LOCK:
        cached = _GEO_CACHE.get(ip)
    if cached is not None:
        return dict(cached)
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,city,isp"
        req = urllib.request.Request(url, headers={"User-Agent": "ammc-analytics/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
        # ip-api answers 200 with status:"fail" for unknown/reserved ranges
        if data.get("status") == "success":
            result = {
                "city": data.get("city") or "",
                "country": data.get("country") or "",
                "country_code": data.get("countryCode") or "",
                "isp": data.get("isp") or "",
            }
        else:
            result = dict(_NO_GEO)
    except Exception:
        result = dict(_NO_GEO)

    # Only successful lookups are cached, otherwise a transient network error
    # would pin an IP to "unknown" for the lifetime of the process.
    if any(result.values()):
        with _GEO_LOCK:
            if len(_GEO_CACHE) >= _GEO_CACHE_MAX:
                _GEO_CACHE.clear()
            _GEO_CACHE[ip] = result
            snapshot = dict(_GEO_CACHE)
        _save_geo_disk(snapshot)
    return dict(result)


_GEO_CACHE.update(_load_geo_disk())


def _detect_device(ua: str) -> str:
    ua_lower = ua.lower()
    if "ipad" in ua_lower or "tablet" in ua_lower:
        return "tablet"
    if any(k in ua_lower for k in ("mobile", "android", "iphone", "ipod", "windows phone")):
        return "mobile"
    return "desktop"


def _hash_ip(ip: str) -> str:
    # keyed hash: a plain sha256 of an IPv4 is trivially reversible by brute force
    # 12 hex chars (48 bits) keeps the birthday bound far above any realistic
    # visitor count, so unique_visitors_30d stops silently merging people.
    return hmac.new(_SALT, ip.encode(), hashlib.sha256).hexdigest()[:12]


def load_analytics() -> dict:
    try:
        if _DATA_FILE.exists():
            data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # One malformed record must not take down the whole dashboard,
                # so anything that is not a dict is dropped on read.
                return {
                    k: [e for e in (data.get(k) or []) if isinstance(e, dict)]
                    for k in _EMPTY
                }
    except Exception:
        pass
    return {k: list(v) for k, v in _EMPTY.items()}


def _save(data: dict) -> None:
    try:
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_DATA_FILE)
    except Exception:
        # analytics must never break the app
        pass


def _event_record(ua: str, ip: str, role: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    device = _detect_device(ua)
    record: dict = {"ts": now, "device": device}
    if role:
        record["role"] = role
    if ip:
        record["ip"] = ip
        record["ip_hash"] = _hash_ip(ip)
        # Resolved before append_event takes _LOCK: the HTTP call can take 3s
        # and must not block every other analytics write while it waits.
        geo = _geo_lookup(ip)
        for field in _GEO_FIELDS:
            record[field] = geo.get(field, "")
    return record


def append_event(event_type: str, ua: str = "", ip: str = "", role: str = "") -> None:
    bucket = _BUCKET.get(event_type)
    if bucket is None:
        return
    record = _event_record(ua, _normalize_ip(ip), role)
    with _LOCK:
        data = load_analytics()
        data[bucket].append(record)
        _save(data)


def _format_location(row: dict) -> str:
    seen, parts = set(), []
    for part in (row.get("city", ""), row.get("country", "")):
        if part and part.lower() not in seen:
            seen.add(part.lower())
            parts.append(part)
    return ", ".join(parts) if parts else "Unknown"


def _visitor_rows() -> list[dict]:
    """One row per unique IP, newest activity first."""
    data = load_analytics()
    by_key: dict[str, dict] = {}

    for bucket in _EMPTY:
        for ev in data.get(bucket, []):
            key = ev.get("ip_hash") or ""
            if not key:
                continue
            row = by_key.get(key)
            if row is None:
                row = by_key[key] = {
                    "ip_hash": key,
                    "ip": ev.get("ip", ""),
                    "city": ev.get("city", ""),
                    "country": ev.get("country", ""),
                    "country_code": ev.get("country_code", ""),
                    "isp": ev.get("isp", ""),
                    "device": ev.get("device", "desktop"),
                    "role": ev.get("role", ""),
                    "first_seen": ev.get("ts", ""),
                    "last_seen": ev.get("ts", ""),
                    "visits": 0,
                    "demo_logins": 0,
                    "demo_messages": 0,
                    "demo_exhausted": 0,
                }
            ts = ev.get("ts", "")
            if ts < row["first_seen"]:
                row["first_seen"] = ts
            if ts > row["last_seen"]:
                # the most recent event carries the freshest geo, since an
                # ISP can be reassigned to the same address over time
                row["last_seen"] = ts
                for field in ("ip", "city", "country", "country_code", "isp", "device"):
                    if ev.get(field):
                        row[field] = ev[field]
            row[bucket] += 1
            if ev.get("role") == "demo":
                row["role"] = "demo"

    rows = sorted(by_key.values(), key=lambda r: r["last_seen"], reverse=True)
    for row in rows:
        row["total_events"] = sum(row[b] for b in _EMPTY)
        row["location"] = _format_location(row)
    return rows


def get_visitors(limit: int = 200) -> list[dict]:
    return _visitor_rows()[:limit]


def get_geo_summary(limit: int = 12) -> dict:
    rows = _visitor_rows()
    countries: dict[str, dict] = {}
    cities: dict[str, dict] = {}

    for row in rows:
        code = row.get("country_code") or ""
        key = code or row.get("country", "")
        if key:
            entry = countries.setdefault(key, {
                "country": row.get("country", "") or "Unknown",
                "country_code": code,
                "visitors": 0,
                "demo_visitors": 0,
            })
            entry["visitors"] += 1
            if row.get("role") == "demo":
                entry["demo_visitors"] += 1
        city = row.get("city", "")
        if city:
            city_key = f"{city}|{code}"
            entry = cities.setdefault(city_key, {
                "city": city,
                "country": row.get("country", ""),
                "country_code": code,
                "visitors": 0,
            })
            entry["visitors"] += 1

    return {
        "total_unique": len(rows),
        "located": sum(1 for r in rows if r.get("country")),
        "countries": sorted(countries.values(), key=lambda c: -c["visitors"])[:limit],
        "cities": sorted(cities.values(), key=lambda c: -c["visitors"])[:limit],
    }


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

    geo = get_geo_summary()
    demo_keys = {
        v.get("ip_hash")
        for v in data.get("demo_logins", []) + data.get("demo_exhausted", [])
        if v.get("ip_hash")
    }

    return {
        "total_visits": len(visits),
        "unique_visitors_30d": unique_ips,
        "total_demo_logins": len(demo_logins),
        "total_demo_messages": len(demo_messages),
        "total_demo_exhausted": len(demo_exhausted),
        "unique_demo_visitors": len(demo_keys),
        "device_breakdown": device_counts,
        "visits_per_day": days_7,
        "demo_logins_per_day": demo_days_7,
        "demo_exhausted_per_day": exhausted_days_7,
        "unique_visitors_all": geo["total_unique"],
        "located_visitors": geo["located"],
        "top_countries": geo["countries"],
        "top_cities": geo["cities"],
    }
