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

_EMPTY = {
    "visits": [],
    "demo_logins": [],
    "demo_messages": [],
    "demo_exhausted": [],
    "login_attempts": [],
    "chat_messages": [],
    "pdf_opens": [],
    "company_selects": [],
    "logouts": [],
    "errors": [],
}
# event type (singular) -> storage bucket (plural)
_BUCKET = {
    "visit": "visits",
    "demo_login": "demo_logins",
    "demo_message": "demo_messages",
    "demo_exhausted": "demo_exhausted",
    "login_attempt": "login_attempts",
    "chat_message": "chat_messages",
    "pdf_open": "pdf_opens",
    "company_select": "company_selects",
    "logout": "logouts",
    "error": "errors",
}
# Only these keys are ever copied out of a client-supplied `meta` dict, so a
# crafted /api/track call cannot stuff arbitrary keys (or a huge payload) into
# the analytics file.
_META_FIELDS = (
    "ok", "email", "question", "company", "year", "sector", "page", "report",
    "latency_ms", "sources", "chars", "scope", "error", "path", "count",
    "screen", "lang", "referrer", "kind", "session",
)
_META_MAX_LEN = 240
# Free-text fields that get hard-truncated. Everything else is a short enum or
# number and is left as-is.
_META_TEXT = ("question", "error", "report", "company", "path", "referrer")
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


def _detect_browser(ua: str) -> str:
    """Coarse browser family. Order matters: Edge and Opera both claim to be
    Chrome, and Chrome claims to be Safari, so the most specific token wins."""
    u = ua.lower()
    if not u:
        return "unknown"
    for needle, name in (
        ("edg/", "Edge"),
        ("opr/", "Opera"),
        ("opera", "Opera"),
        ("samsungbrowser", "Samsung"),
        ("firefox", "Firefox"),
        ("chrome", "Chrome"),
        ("safari", "Safari"),
        ("curl", "curl"),
        ("python-requests", "python-requests"),
        ("wget", "Wget"),
    ):
        if needle in u:
            return name
    return "other"


def _detect_os(ua: str) -> str:
    u = ua.lower()
    if not u:
        return "unknown"
    for needle, name in (
        ("windows nt 10", "Windows 10/11"),
        ("windows nt", "Windows"),
        ("android", "Android"),
        ("iphone", "iOS"),
        ("ipad", "iPadOS"),
        ("mac os x", "macOS"),
        ("cros", "ChromeOS"),
        ("linux", "Linux"),
    ):
        if needle in u:
            return name
    return "unknown"


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


def _clean_meta(meta: dict | None) -> dict:
    if not isinstance(meta, dict):
        return {}
    out: dict = {}
    for field in _META_FIELDS:
        if field not in meta:
            continue
        value = meta[field]
        if value is None:
            continue
        if isinstance(value, bool) or isinstance(value, (int, float)):
            out[field] = value
            continue
        text = str(value).strip()
        if not text:
            continue
        if field in _META_TEXT and len(text) > _META_MAX_LEN:
            text = text[:_META_MAX_LEN] + "…"
        out[field] = text
    return out


def _event_record(ua: str, ip: str, role: str, meta: dict | None = None) -> dict:
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
    if ua:
        record["browser"] = _detect_browser(ua)
        record["os"] = _detect_os(ua)
    extra = _clean_meta(meta)
    if extra:
        record["meta"] = extra
    return record


def append_event(
    event_type: str,
    ua: str = "",
    ip: str = "",
    role: str = "",
    meta: dict | None = None,
) -> None:
    bucket = _BUCKET.get(event_type)
    if bucket is None:
        return
    record = _event_record(ua, _normalize_ip(ip), role, meta)
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
                    "browser": ev.get("browser", "unknown"),
                    "os": ev.get("os", "unknown"),
                    "role": ev.get("role", ""),
                    "first_seen": ev.get("ts", ""),
                    "last_seen": ev.get("ts", ""),
                }
                # one counter per bucket, so a new event type is counted
                # automatically instead of needing a new key here
                row.update({b: 0 for b in _EMPTY})
                row["_companies"] = set()
                row["_latencies"] = []
                row["_logins_ok"] = 0
                row["_logins_fail"] = 0
                row["_sessions"] = set()
            ts = ev.get("ts", "")
            if ts < row["first_seen"]:
                row["first_seen"] = ts
            if ts > row["last_seen"]:
                # the most recent event carries the freshest geo, since an
                # ISP can be reassigned to the same address over time
                row["last_seen"] = ts
                for field in ("ip", "city", "country", "country_code", "isp",
                              "device", "browser", "os"):
                    if ev.get(field):
                        row[field] = ev[field]
            row[bucket] += 1
            if ev.get("role") == "demo":
                row["role"] = "demo"
            elif ev.get("role") == "admin":
                row["role"] = "admin"

            meta = ev.get("meta") or {}
            company = meta.get("company", "")
            if company:
                row["_companies"].add(company)
            latency = meta.get("latency_ms")
            if isinstance(latency, (int, float)) and latency >= 0:
                row["_latencies"].append(float(latency))
            if bucket == "login_attempts":
                row["_sessions"].add(meta.get("session", "") or ts)
                if meta.get("ok"):
                    row["_logins_ok"] += 1
                else:
                    row["_logins_fail"] += 1

    rows = sorted(by_key.values(), key=lambda r: r["last_seen"], reverse=True)
    for row in rows:
        row["total_events"] = sum(row[b] for b in _EMPTY)
        row["location"] = _format_location(row)
        row["companies_explored"] = len(row.pop("_companies"))
        latencies = sorted(row.pop("_latencies"))
        row["sessions"] = len(row.pop("_sessions"))
        row["logins_ok"] = row.pop("_logins_ok")
        row["logins_fail"] = row.pop("_logins_fail")
        row["questions"] = row["chat_messages"]
        if latencies:
            row["avg_latency_ms"] = int(sum(latencies) / len(latencies))
            row["max_latency_ms"] = int(latencies[-1])
        else:
            row["avg_latency_ms"] = None
            row["max_latency_ms"] = None
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


# ── Deep analytics ────────────────────────────────────────────────────────────
# Everything below is derived on read from the same event log, so there is no
# second source of truth to keep in sync and no extra file to migrate.


def _meta_of(ev: dict) -> dict:
    meta = ev.get("meta")
    return meta if isinstance(meta, dict) else {}


def _bucket_counts(rows: list[dict], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for ev in rows:
        value = _meta_of(ev).get(field, "")
        if not value:
            continue
        key = str(value)
        out[key] = out.get(key, 0) + 1
    return out


def get_login_funnel() -> dict:
    """Every sign-in attempt, per credential tried, with pass/fail split.

    This is the table that answers "who tried to get in, and how often".
    """
    data = load_analytics()
    attempts = data.get("login_attempts", [])
    by_email: dict[str, dict] = {}
    for ev in attempts:
        meta = _meta_of(ev)
        email = (meta.get("email") or "").lower() or "(vide)"
        row = by_email.setdefault(email, {
            "email": email,
            "attempts": 0,
            "success": 0,
            "failed": 0,
            "ips": set(),
            "first_seen": ev.get("ts", ""),
            "last_seen": ev.get("ts", ""),
        })
        ok = bool(meta.get("ok"))
        row["attempts"] += 1
        row["success" if ok else "failed"] += 1
        if ev.get("ip_hash"):
            row["ips"].add(ev["ip_hash"])
        ts = ev.get("ts", "")
        if ts < row["first_seen"]:
            row["first_seen"] = ts
        if ts > row["last_seen"]:
            row["last_seen"] = ts

    rows = []
    for row in by_email.values():
        row["unique_ips"] = len(row.pop("ips"))
        row["success_rate"] = (
            round(row["success"] / row["attempts"] * 100) if row["attempts"] else 0
        )
        rows.append(row)
    rows.sort(key=lambda r: (-r["attempts"], r["email"]))

    failed_ips: dict[str, dict] = {}
    for ev in attempts:
        if _meta_of(ev).get("ok") or not ev.get("ip_hash"):
            continue
        key = ev["ip_hash"]
        entry = failed_ips.setdefault(key, {
            "ip_hash": key, "ip": ev.get("ip", ""),
            "location": _format_location(ev), "failed": 0, "last_seen": ev.get("ts", ""),
        })
        entry["failed"] += 1
        if ev.get("ts", "") > entry["last_seen"]:
            entry["last_seen"] = ev["ts"]

    total = len(attempts)
    success = sum(1 for ev in attempts if _meta_of(ev).get("ok"))
    return {
        "total_attempts": total,
        "total_success": success,
        "total_failed": total - success,
        "success_rate": round(success / total * 100) if total else 0,
        "by_email": rows,
        "top_bruteforce": sorted(
            failed_ips.values(), key=lambda r: -r["failed"]
        )[:10],
    }


def get_chat_stats(limit: int = 40) -> dict:
    """Question-level usage: volume, latency, top questions, coverage."""
    data = load_analytics()
    msgs = data.get("chat_messages", [])
    latencies = sorted(
        float(m["latency_ms"])
        for m in (_meta_of(e) for e in msgs)
        if isinstance(m.get("latency_ms"), (int, float)) and m["latency_ms"] >= 0
    )
    errored = sum(1 for m in (_meta_of(e) for e in msgs) if m.get("error"))
    with_sources = sum(
        1 for m in (_meta_of(e) for e in msgs)
        if isinstance(m.get("sources"), (int, float)) and m["sources"] > 0
    )
    unique_askers = len({e.get("ip_hash") for e in msgs if e.get("ip_hash")})
    total = len(msgs)

    def pct(p: float) -> int:
        return int(latencies[min(len(latencies) - 1, int(len(latencies) * p))]) if latencies else 0

    per_day: list[dict] = []
    now = datetime.now(timezone.utc)
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        prefix = day.date().isoformat()
        per_day.append({
            "day": day.strftime("%a"),
            "date": prefix,
            "count": sum(1 for m in msgs if m.get("ts", "").startswith(prefix)),
        })

    return {
        "total_questions": total,
        "unique_askers": unique_askers,
        "questions_per_asker": round(total / unique_askers, 2) if unique_askers else 0,
        "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else None,
        "p50_latency_ms": pct(0.50),
        "p95_latency_ms": pct(0.95),
        "max_latency_ms": int(latencies[-1]) if latencies else None,
        "error_rate": round(errored / total * 100, 1) if total else 0,
        "source_rate": round(with_sources / total * 100, 1) if total else 0,
        "questions_per_day": per_day,
        "top_companies": sorted(
            _bucket_counts(msgs, "company").items(), key=lambda kv: -kv[1]
        )[:limit],
        "top_years": sorted(
            _bucket_counts(msgs, "year").items(), key=lambda kv: -kv[1]
        )[:20],
        "top_sectors": sorted(
            _bucket_counts(msgs, "sector").items(), key=lambda kv: -kv[1]
        )[:20],
        "top_reports": sorted(
            _bucket_counts(msgs, "report").items(), key=lambda kv: -kv[1]
        )[:20],
    }


def get_recent_questions(limit: int = 60) -> list[dict]:
    """The raw question log, newest first — what each visitor actually asked."""
    data = load_analytics()
    out: list[dict] = []
    for ev in reversed(data.get("chat_messages", [])):
        meta = _meta_of(ev)
        out.append({
            "ts": ev.get("ts", ""),
            "ip": ev.get("ip", ""),
            "ip_hash": ev.get("ip_hash", ""),
            "location": _format_location(ev),
            "country_code": ev.get("country_code", ""),
            "device": ev.get("device", ""),
            "role": ev.get("role", ""),
            "question": meta.get("question", ""),
            "company": meta.get("company", ""),
            "year": meta.get("year", ""),
            "sector": meta.get("sector", ""),
            "scope": meta.get("scope", ""),
            "latency_ms": meta.get("latency_ms"),
            "sources": meta.get("sources"),
            "error": meta.get("error", ""),
        })
        if len(out) >= limit:
            break
    return out


def get_recent_logins(limit: int = 60) -> list[dict]:
    data = load_analytics()
    out: list[dict] = []
    for ev in reversed(data.get("login_attempts", [])):
        meta = _meta_of(ev)
        out.append({
            "ts": ev.get("ts", ""),
            "ip": ev.get("ip", ""),
            "location": _format_location(ev),
            "country_code": ev.get("country_code", ""),
            "email": meta.get("email", ""),
            "ok": bool(meta.get("ok")),
            "kind": meta.get("kind", ""),
        })
        if len(out) >= limit:
            break
    return out


def _hour_histogram(rows: list[dict]) -> list[int]:
    hours = [0] * 24
    for ev in rows:
        try:
            hours[datetime.fromisoformat(ev.get("ts", "")).hour] += 1
        except ValueError:
            continue
    return hours


def get_activity_hours() -> dict:
    """Visits / questions / failed logins bucketed by hour of day (UTC)."""
    data = load_analytics()
    failed = [e for e in data.get("login_attempts", []) if not _meta_of(e).get("ok")]
    return {
        "visits": _hour_histogram(data.get("visits", [])),
        "questions": _hour_histogram(data.get("chat_messages", [])),
        "failed_logins": _hour_histogram(failed),
    }


def get_browsers() -> dict:
    """Browser / OS / device mix over every event, not just page views."""
    data = load_analytics()
    browsers: dict[str, int] = {}
    systems: dict[str, int] = {}
    devices: dict[str, int] = {}
    for bucket in _EMPTY:
        for ev in data.get(bucket, []):
            b = ev.get("browser", "")
            if b and b != "unknown":
                browsers[b] = browsers.get(b, 0) + 1
            o = ev.get("os", "")
            if o and o != "unknown":
                systems[o] = systems.get(o, 0) + 1
            d = ev.get("device", "")
            if d:
                devices[d] = devices.get(d, 0) + 1

    def top(d: dict[str, int], n: int = 10) -> list[dict]:
        return sorted(
            ({"name": k, "count": v} for k, v in d.items()),
            key=lambda x: -x["count"],
        )[:n]

    return {"browsers": top(browsers), "systems": top(systems), "devices": top(devices)}


def get_timeline(days: int = 30) -> list[dict]:
    """One point per day: visits, questions, logins, errors."""
    data = load_analytics()
    now = datetime.now(timezone.utc)
    out: list[dict] = []
    for i in range(days - 1, -1, -1):
        day = now - timedelta(days=i)
        prefix = day.date().isoformat()

        def count(rows: list[dict]) -> int:
            return sum(1 for r in rows if r.get("ts", "").startswith(prefix))

        out.append({
            "date": prefix,
            "day": day.strftime("%a"),
            "visits": count(data.get("visits", [])),
            "questions": count(data.get("chat_messages", [])),
            "logins": count(data.get("login_attempts", [])),
            "errors": count(data.get("errors", [])),
            "pdf_opens": count(data.get("pdf_opens", [])),
        })
    return out


def get_usage() -> dict:
    """What visitors browsed: companies picked, PDFs opened, errors hit."""
    data = load_analytics()
    errors: dict[str, int] = {}
    for ev in data.get("errors", []):
        kind = _meta_of(ev).get("kind") or ev.get("path") or "unknown"
        errors[str(kind)] = errors.get(str(kind), 0) + 1
    return {
        "pdf_opens": len(data.get("pdf_opens", [])),
        "company_selects": len(data.get("company_selects", [])),
        "logouts": len(data.get("logouts", [])),
        "errors": len(data.get("errors", [])),
        "top_companies_viewed": sorted(
            _bucket_counts(data.get("company_selects", []), "company").items(),
            key=lambda kv: -kv[1],
        )[:20],
        "top_pdfs_opened": sorted(
            _bucket_counts(data.get("pdf_opens", []), "report").items(),
            key=lambda kv: -kv[1]
        )[:20],
        # [name, count] pairs, not dicts: the dashboard renders every "top X"
        # list with the same shape, so mixing the two crashed the render.
        "error_kinds": sorted(
            ((k, v) for k, v in errors.items()),
            key=lambda kv: -kv[1]
        )[:20],
    }


def get_deep(visitor_limit: int = 300) -> dict:
    """Everything the dashboard needs, in one response."""
    return {
        "summary": get_summary(),
        "logins": get_login_funnel(),
        "chat": get_chat_stats(),
        "questions": get_recent_questions(),
        "login_log": get_recent_logins(),
        "usage": get_usage(),
        "clients": get_browsers(),
        "hours": get_activity_hours(),
        "timeline": get_timeline(),
        "visitors": get_visitors(visitor_limit),
    }
