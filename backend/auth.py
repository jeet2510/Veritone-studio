import re
from functools import wraps
from typing import Any, Callable

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .database import create_user, get_user_by_id, get_user_by_username


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "is_active": bool(user["is_active"]),
    }


def current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id")
    if user_id is None:
        return None
    user = get_user_by_id(int(user_id))
    if not user or not user["is_active"]:
        session.clear()
        return None
    return user


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        user = current_user()
        if not user:
            return jsonify({"error": "Sign in to continue."}), 401
        request.user = user
        return view(*args, **kwargs)

    return wrapped


def admin_required(view: Callable) -> Callable:
    @wraps(view)
    @login_required
    def wrapped(*args: Any, **kwargs: Any):
        if request.user["role"] != "admin":
            return jsonify({"error": "Administrator access is required."}), 403
        return view(*args, **kwargs)

    return wrapped


@auth_bp.get("/me")
def me():
    user = current_user()
    return jsonify({"user": public_user(user) if user else None})


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        return jsonify({"error": "Username must be 3-32 characters using letters, numbers, dots, underscores, or hyphens."}), 400
    if len(password) < 10:
        return jsonify({"error": "Password must be at least 10 characters."}), 400
    if get_user_by_username(username):
        return jsonify({"error": "That username is already in use."}), 409
    user_id = create_user(username, generate_password_hash(password))
    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    return jsonify({"user": public_user(get_user_by_id(user_id))}), 201


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    user = get_user_by_username(str(payload.get("username", "")).strip())
    password = str(payload.get("password", ""))
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Incorrect username or password."}), 401
    if not user["is_active"]:
        return jsonify({"error": "This account is disabled."}), 403
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"user": public_user(user)})


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"signed_out": True})