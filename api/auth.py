"""User accounts: signup, login, session tokens, daily message quota.

Passwords are never stored or logged in plaintext — only a PBKDF2-SHA256
hash is saved. The daily quota is enforced server-side (atomic increment)
so clearing localStorage cannot extend the 5-messages-per-day limit.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import date as date_cls
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from db.models import ChatHistory, User

DAILY_QUOTA = 5
PASSWORD_MIN_LEN = 8
_TOKEN_LEN = 64
_PBKDF2_ITERATIONS = 210_000

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Well-known disposable / temporary-mail providers. Any provider used in
# Morocco (gmail, outlook/hotmail/live, yahoo, menara.ma, mediasuites, ...)
# is accepted — only throwaway inboxes are rejected.
_DISPOSABLE_DOMAINS = {
    "mailinator.com", "mailinator.net", "mailinator.org",
    "guerrillamail.com", "guerrillamail.org", "guerrillamail.net",
    "guerrillamail.de", "grr.la", "pokemail.net", "spam4.me",
    "yopmail.com", "yopmail.fr", "yopmail.net", "yopmail.org",
    "temp-mail.org", "temp-mail.com", "temp-mail.net", "temp-mail.io",
    "tempmail.com", "tempmail.net", "tempmailo.com", "tempmail.dev",
    "tempinbox.com", "temporary-mail.net", "tempr.email",
    "10minutemail.com", "10minutemail.net", "10minutemail.org",
    "10mail.org", "10minut.net", "minutesmail.com",
    "trashmail.com", "trashmail.de", "trashmail.net", "trashmails.com",
    "throwawaymail.com", "throwawayemail.com", "throwaway.de",
    "maildrop.cc", "mailnesia.com", "dispostable.com", "spamgourmet.com",
    "mailcatch.com", "emailfake.com", "fakemail.net", "fakemailgenerator.com",
    "getairmail.com", "mailtemp.net", "emailondeck.com", "mytemp.email",
    "luxusmail.org", "fammail.xyz", "einrot.com", "noesdon.fun",
    "mytemp-mail.com", "maileater.com", "cellurl.com", "mail-eater.com",
    "jetable.org", "jetable.net", "meltmail.com", "deponi.online",
    "emailtemporario.com.br", "tmailweb.com", "tmpmail.org", "tmpmail.net",
    "0-mail.com", "0815.ru", "copy.sh", "kurzepost.de", "sellbe.com",
    "shitmail.de", "slopsbox.com", "sofort-mail.de", "mailimouse.com",
    "wikmailbox.com", "boun.cr", "mintemail.com", "nwytg.net",
    "spam.care", "moakt.com", "mailnox.com", "acme.com", "bumpylips.com",
    "dadamailservice.com", "fidmail.com", "figjs.com", "gawab.com",
}
# Family suffixes: block subdomains/hosts of the biggest temp-mail brands.
_DISPOSABLE_FAMILIES = (
    "mailinator", "guerrillamail", "yopmail", "10minutemail", "tempmail",
    "temp-mail", "trashmail", "throwaway", "emailfake", "fakemail",
    "maildrop", "mailnesia", "dispostable", "mailcatch", "jetable",
)


class AuthError(Exception):
    """Raised with a user-facing (French) message on validation/login failure."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class QuotaExceeded(Exception):
    pass


# ── Password hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest, expected)


# ── Validation ───────────────────────────────────────────────────────────────

def _is_disposable(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()
    if domain in _DISPOSABLE_DOMAINS:
        return True
    base = domain.rsplit(".", 1)[0] if "." in domain else domain
    for fam in _DISPOSABLE_FAMILIES:
        if fam in domain:
            return True
    return False


def validate_full_name(full_name: str) -> str:
    name = " ".join(full_name.strip().split())
    parts = name.split()
    if len(parts) < 2 or any(len(p) < 2 for p in parts):
        raise AuthError("Veuillez saisir votre nom complet (prénom et nom).")
    return name


def validate_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 320 or not EMAIL_RE.match(email):
        raise AuthError("Adresse email non valide.")
    if _is_disposable(email):
        raise AuthError("Les adresses email temporaires ne sont pas autorisées.")
    return email


def validate_password(password: str) -> str:
    if len(password) < PASSWORD_MIN_LEN:
        raise AuthError(f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LEN} caractères.")
    if len(password) > 128:
        raise AuthError("Mot de passe trop long.")
    return password


# ── Queries ──────────────────────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(text("lower(email) = lower(:e)")).params(e=email.strip()).first()


def get_user_by_email_exact(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_token(db: Session, token: str) -> Optional[User]:
    if not token:
        return None
    return db.query(User).filter(User.token == token).first()


def _new_token() -> str:
    return secrets.token_hex(_TOKEN_LEN // 2)


# ── Quota ────────────────────────────────────────────────────────────────────

def _today() -> date_cls:
    return date_cls.today()


def quota_reset(db: Session, user: User) -> None:
    """Roll today's counter back to 0 when the quota date is stale."""
    if user.quota_date != _today():
        user.daily_msgs_used = 0
        user.quota_date = _today()
        db.flush()


def quota_left(db: Session, user: User) -> int:
    quota_reset(db, user)
    return max(0, DAILY_QUOTA - user.daily_msgs_used)


def consume_message(db: Session, user: User) -> int:
    """Atomically consume one daily message. Raises QuotaExceeded when done.

    Returns the number of messages left for the day.
    """
    from sqlalchemy import update
    quota_reset(db, user)
    db.execute(
        update(User)
        .where(User.id == user.id)
        .values(daily_msgs_used=User.daily_msgs_used + 1)
    )
    db.flush()
    left = max(0, DAILY_QUOTA - user.daily_msgs_used)
    if left < 0 or user.daily_msgs_used > DAILY_QUOTA:
        db.execute(
            update(User)
            .where(User.id == user.id)
            .values(daily_msgs_used=User.daily_msgs_used - 1)
        )
        db.flush()
        raise QuotaExceeded()
    return left


# ── Actions ──────────────────────────────────────────────────────────────────

def signup(db: Session, full_name: str, email: str, password: str) -> User:
    name = validate_full_name(full_name)
    email = validate_email(email)
    validate_password(password)

    if get_user_by_email(db, email):
        raise AuthError("Cet email est déjà inscrit.", status=409)

    user = User(
        full_name=name,
        email=email.lower(),
        password_hash=hash_password(password),
        token=_new_token(),
        daily_msgs_used=0,
        quota_date=_today(),
    )
    db.add(user)
    db.flush()
    return user


def login(db: Session, email: str, password: str) -> User:
    email = email.strip().lower()
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Email ou mot de passe incorrect.", status=401)
    user.token = _new_token()
    db.flush()
    return user


def public_user(user: User) -> dict:
    return {
        "email": user.email,
        "full_name": user.full_name,
        "role": "user",
    }


def add_history(db: Session, user: User, question: str, answer: str,
                company: Optional[str] = None, year: Optional[str] = None,
                sources: Optional[list] = None) -> None:
    db.add(ChatHistory(
        user_id=user.id,
        question=question[:40000] if question else question,
        answer=(answer or "")[:40000],
        company_name=(company or "")[:500],
        year=(year or "")[:20],
        sources=sources,
    ))


def get_history(db: Session, user: User, limit: int = 100) -> list[dict]:
    rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )
    out = []
    for r in reversed(rows):  # newest last in the list for chronological UI order
        out.append({
            "question": r.question,
            "answer": r.answer or "",
            "companyName": r.company_name or "",
            "year": r.year or "",
            "sources": r.sources or [],
            "timestamp": int(r.created_at.timestamp() * 1000),
            "thread": [
                {"role": "user", "content": r.question, "sources": []},
                {"role": "assistant", "content": r.answer or "", "sources": r.sources or []},
            ],
        })
    return out


def admin_user_history(db: Session, user_id: int, limit: int = 100) -> dict | None:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None
    return {
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
        },
        "messages": get_history(db, user, limit),
    }


def admin_users(db: Session, limit: int = 500) -> dict:
    """Registered accounts with per-account usage for the admin dashboard.

    Message counts and last activity come from chat_history; today's quota
    consumption comes from the daily counters on the account row.
    """
    counts: dict[int, dict] = {}
    for user_id, total, last in (
        db.query(
            ChatHistory.user_id,
            func.count(ChatHistory.id),
            func.max(ChatHistory.created_at),
        )
        .group_by(ChatHistory.user_id)
        .all()
    ):
        counts[user_id] = {
            "total": int(total),
            "last": last.isoformat() if last else None,
        }

    today = date_cls.today()
    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .limit(min(limit, 2000))
        .all()
    )
    out = []
    for u in users:
        used_today = u.daily_msgs_used if u.quota_date == today else 0
        stat = counts.get(u.id, {})
        out.append({
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "messages_total": stat.get("total", 0),
            "last_message_at": stat.get("last"),
            "quota_used_today": used_today,
            "quota_left_today": max(0, DAILY_QUOTA - used_today),
            "quota_day": DAILY_QUOTA,
        })
    return {
        "total": len(out),
        "quota_day": DAILY_QUOTA,
        "users": out,
    }