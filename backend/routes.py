import json
import os
import re
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from .auth import admin_required, auth_bp, login_required
from .database import (
    delete_analysis,
    get_admin_overview,
    get_analysis,
    get_any_analysis_owner,
    get_user_by_id,
    list_all_analyses,
    list_analyses,
    list_users,
    save_analysis,
    update_user,
)
from .detector import analyze_text, contextual_ai_score
from .extractor import extract_from_upload, extract_latex_prose
from .humanizer import humanize_text_with_report


page_bp = Blueprint("pages", __name__)
api_bp = Blueprint("api", __name__)


@page_bp.route("/", methods=["GET"])
def home():
    return render_template("index.html")


def _process_and_store(source_text: str, source_name: str, source_type: str) -> dict:
    before_report = analyze_text(source_text)
    api_key = current_app.config.get("GEMINI_API_KEY", "")
    model = current_app.config.get("GEMINI_MODEL", "gemini-2.0-flash")
    heuristic_only = request.form.get("heuristic_only") == "true"
    if heuristic_only:
        api_key = ""
    model_used = False
    if api_key:
        contextual = contextual_ai_score(source_text, api_key, model)
        if contextual:
            before_report.ai_score, before_report.contextual_note = contextual
            before_report.classification = _classification(before_report.ai_score)
            model_used = True

    humanized = humanize_text_with_report(source_text, api_key=api_key, model=model)
    model_used = model_used or any(change.change_type == "gemini_rewrite" for change in humanized.changes)
    after_report = analyze_text(humanized.text)
    if api_key:
        contextual = contextual_ai_score(humanized.text, api_key, model)
        if contextual:
            after_report.ai_score, after_report.contextual_note = contextual
            after_report.classification = _classification(after_report.ai_score)
            model_used = True

    word_count = len(re.findall(r"[A-Za-z0-9']+", source_text))
    record = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source_name": source_name,
        "source_type": source_type,
        "word_count": word_count,
        "before_score": before_report.ai_score,
        "before_label": before_report.classification,
        "after_score": after_report.ai_score,
        "after_label": after_report.classification,
        "total_changes": humanized.total_changes,
        "change_percentage": humanized.change_percentage,
        "changed_sentences": humanized.changed_sentences,
        "total_sentences": humanized.total_sentences,
        "engine_mode": "gemini" if model_used else "heuristic",
        "original_text": source_text,
        "humanized_text": humanized.text,
        "changes": [asdict(c) for c in humanized.changes],
        "cliche_hits": before_report.cliche_hits,
        "before_metrics": asdict(before_report),
        "after_metrics": asdict(after_report),
    }
    record_id = save_analysis(record, request.user["id"])
    saved = get_analysis(record_id, request.user["id"])
    return saved


def _classification(score: float) -> str:
    if score >= 65:
        return "High AI-Pattern Likelihood"
    if score >= 35:
        return "Mixed / Moderate AI-Pattern Likelihood"
    return "Low AI-Pattern Likelihood (More Human-Like)"


def _owned_or_admin_analysis(analysis_id: int) -> tuple[dict | None, tuple | None]:
    owner_id = get_any_analysis_owner(analysis_id)
    if owner_id is None:
        return None, (jsonify({"error": "Analysis not found."}), 404)
    if owner_id != request.user["id"] and request.user["role"] != "admin":
        return None, (jsonify({"error": "You do not have access to this analysis."}), 403)
    item = get_analysis(analysis_id, owner_id)
    return item, None


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "VeriTone Studio"})


@api_bp.route("/analyze", methods=["POST"])
@login_required
def analyze():
    latex_mode = request.form.get("latex_mode") == "true"
    raw_input = (request.form.get("raw_text") or "").strip()
    uploaded_file = request.files.get("file")

    if uploaded_file and uploaded_file.filename:
        if uploaded_file.filename.rsplit(".", 1)[-1].lower() not in {"txt", "md", "tex", "pdf"}:
            return jsonify({"error": "Supported files are .txt, .md, .tex, and .pdf."}), 400
        source_text, source_name, source_type = extract_from_upload(
            uploaded_file, latex_mode=latex_mode
        )
    elif raw_input:
        source_text = extract_latex_prose(raw_input) if latex_mode else raw_input
        source_name = "pasted_input.txt"
        source_type = "latex" if latex_mode else "text"
    else:
        return jsonify({"error": "Upload a file (.txt, .md, .tex, .pdf) or paste text."}), 400

    if not source_text.strip():
        return jsonify({"error": "No extractable text found in the provided input."}), 400

    result = _process_and_store(source_text, source_name, source_type)
    return jsonify(result), 201


@api_bp.route("/analyses", methods=["GET"])
@login_required
def get_all():
    return jsonify(list_analyses(request.user["id"], limit=200))


@api_bp.route("/analyses/<int:analysis_id>", methods=["GET"])
@login_required
def get_one(analysis_id: int):
    item, error = _owned_or_admin_analysis(analysis_id)
    if error:
        return error
    return jsonify(item)


@api_bp.route("/analyses/<int:analysis_id>", methods=["DELETE"])
@login_required
def remove_one(analysis_id: int):
    owner_id = get_any_analysis_owner(analysis_id)
    if owner_id is None:
        return jsonify({"error": "Analysis not found."}), 404
    if owner_id != request.user["id"]:
        return jsonify({"error": "You do not have access to this analysis."}), 403
    deleted = delete_analysis(analysis_id, request.user["id"])
    if not deleted:
        return jsonify({"error": "Analysis not found."}), 404
    return jsonify({"deleted": True, "id": analysis_id})


@api_bp.route("/analyses/<int:analysis_id>/download/<kind>", methods=["GET"])
@login_required
def download(analysis_id: int, kind: str):
    item, error = _owned_or_admin_analysis(analysis_id)
    if error:
        return error

    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        if kind == "humanized":
            tmp.write(item["humanized_text"])
            out_name = f"veritone_humanized_{analysis_id}.txt"
            mime = "text/plain"
        elif kind == "report":
            tmp.write(json.dumps(item, indent=2))
            out_name = f"veritone_report_{analysis_id}.json"
            mime = "application/json"
        else:
            return jsonify({"error": "Unsupported download format."}), 400
        tmp_path = tmp.name

    response = send_file(tmp_path, as_attachment=True, download_name=out_name, mimetype=mime)
    response.call_on_close(lambda: os.unlink(tmp_path) if os.path.exists(tmp_path) else None)
    return response


@api_bp.get("/admin/overview")
@admin_required
def admin_overview():
    return jsonify(get_admin_overview())


@api_bp.get("/admin/users")
@admin_required
def admin_users():
    return jsonify(list_users())


@api_bp.patch("/admin/users/<int:user_id>")
@admin_required
def admin_update_user(user_id: int):
    target = get_user_by_id(user_id)
    if not target:
        return jsonify({"error": "User not found."}), 404
    payload = request.get_json(silent=True) or {}
    role = payload.get("role", target["role"])
    is_active = payload.get("is_active", bool(target["is_active"]))
    if role not in {"user", "admin"} or not isinstance(is_active, bool):
        return jsonify({"error": "Role or active status is invalid."}), 400
    if user_id == request.user["id"] and (role != "admin" or not is_active):
        return jsonify({"error": "You cannot disable or demote your own account."}), 400
    update_user(user_id, role, is_active)
    return jsonify({"updated": True, "user_id": user_id})


@api_bp.get("/admin/analyses")
@admin_required
def admin_analyses():
    return jsonify(list_all_analyses())


@api_bp.get("/admin/analyses/<int:analysis_id>")
@admin_required
def admin_analysis(analysis_id: int):
    owner_id = get_any_analysis_owner(analysis_id)
    if owner_id is None:
        return jsonify({"error": "Analysis not found."}), 404
    return jsonify(get_analysis(analysis_id, owner_id))