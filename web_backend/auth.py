"""
Authentication and role-based access control.

Uses a simple JSON file to store user -> role mappings.
First user to register gets 'admin' role automatically.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel

log = logging.getLogger(__name__)

USERS_FILE = Path(__file__).parent / "users.json"

VALID_ROLES = {"admin", "engineer", "viewer"}


class UserInfo(BaseModel):
    email: str
    name: Optional[str] = None
    image: Optional[str] = None
    role: str = "viewer"


# --- User store ---

def _load_users() -> dict:
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def register_user(email: str, name: str = None, image: str = None, provider: str = None) -> dict:
    """Register or return existing user. First user gets admin."""
    users = _load_users()

    if email in users:
        # Update name/image if changed
        users[email]["name"] = name or users[email].get("name")
        users[email]["image"] = image or users[email].get("image")
        _save_users(users)
        return users[email]

    # New user — first one gets admin
    role = "admin" if len(users) == 0 else "viewer"

    users[email] = {
        "email": email,
        "name": name,
        "image": image,
        "role": role,
        "provider": provider,
    }
    _save_users(users)
    log.info("Registered new user: %s (role=%s)", email, role)
    return users[email]


def get_user(email: str) -> Optional[dict]:
    users = _load_users()
    return users.get(email)


def set_user_role(email: str, role: str) -> dict:
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")
    users = _load_users()
    if email not in users:
        raise KeyError(f"User not found: {email}")
    users[email]["role"] = role
    _save_users(users)
    return users[email]


def list_users() -> list[dict]:
    users = _load_users()
    return list(users.values())


# --- FastAPI dependency ---

def get_current_user(request: Request) -> UserInfo:
    """Extract user from request headers set by the frontend.
    
    The NextAuth middleware on the frontend ensures only authenticated
    users can reach the app. The frontend passes user info via headers.
    """
    email = request.headers.get("X-User-Email", "")
    role = request.headers.get("X-User-Role", "viewer")

    if not email:
        raise HTTPException(401, "Not authenticated")

    # Verify against our user store
    user = get_user(email)
    if user:
        role = user.get("role", "viewer")

    return UserInfo(email=email, role=role)


def require_role(*allowed_roles: str):
    """Factory for role-checking dependencies."""
    def checker(request: Request) -> UserInfo:
        user = get_current_user(request)
        if user.role not in allowed_roles:
            raise HTTPException(
                403,
                f"Insufficient permissions. Required: {allowed_roles}, have: {user.role}"
            )
        return user
    return checker
