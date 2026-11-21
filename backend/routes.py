import json
import re
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request, send_file

from .database import delete_analysis, get_analysis, list_analyses, save_analysis
from .detector import analyze_text
from .extractor import extract_from_upload, extract_latex_prose
from .humanizer import humanize_text_with_report


page_bp = Blueprint("pages", __name__)
api_bp = Blueprint("api", __name__)


@page_bp.route("/", methods=["GET"])
def home():
    return render_template("index.html")


def _process_and_store(source_text: str, source_name: str, source_type: str) -> dict:
    before_report = analyze_text(source_text)
    humanized = humanize_text_with_report(source_text)
    after_report = analyze_text(humanized.text)

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
        "original_text": source_text,
        "humanized_text": humanized.text,
        "changes": [asdict(c) for c in humanized.changes],
        "cliche_hits": before_report.cliche_hits,
    }
    record_id = save_analysis(record)
    saved = get_analysis(record_id)
    saved["before_metrics"] = asdict(before_report)
    saved["after_metrics"] = asdict(after_report)
    return saved


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "VeriTone Studio"})


@api_bp.route("/analyze", methods=["POST"])
def analyze():
    latex_mode = request.form.get("latex_mode") == "true"
    raw_input = (request.form.get("raw_text") or "").strip()
    uploaded_file = request.files.get("file")

    if uploaded_file and uploaded_file.filename:
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
def get_all():
    return jsonify(list_analyses(limit=100))


@api_bp.route("/analyses/<int:analysis_id>", methods=["GET"])
def get_one(analysis_id: int):
    item = get_analysis(analysis_id)
    if not item:
        return jsonify({"error": "Analysis not found."}), 404
    return jsonify(item)


@api_bp.route("/analyses/<int:analysis_id>", methods=["DELETE"])
def remove_one(analysis_id: int):
    deleted = delete_analysis(analysis_id)
    if not deleted:
        return jsonify({"error": "Analysis not found."}), 404
    return jsonify({"deleted": True, "id": analysis_id})


@api_bp.route("/analyses/<int:analysis_id>/download/<kind>", methods=["GET"])
def download(analysis_id: int, kind: str):
    item = get_analysis(analysis_id)
    if not item:
        return jsonify({"error": "Analysis not found."}), 404

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

    return send_file(tmp_path, as_attachment=True, download_name=out_name, mimetype=mime)