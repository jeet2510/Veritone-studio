import json
import re
import statistics
from dataclasses import dataclass, field
from typing import List


AI_CLICHE_PHRASES = [
    r"\bmoreover\b",
    r"\bfurthermore\b",
    r"\bin conclusion\b",
    r"\bit is important to note that\b",
    r"\bit is worth noting that\b",
    r"\bdelve\b",
    r"\btapestry\b",
    r"\blandscape\b",
    r"\bpivotal\b",
    r"\bcrucial\b",
    r"\btestament to\b",
    r"\bin today's fast-paced\b",
    r"\bunderscores the importance\b",
    r"\bnavigating the complexities\b",
]


@dataclass
class DetectionReport:
    ai_score: float
    classification: str
    avg_sentence_len: float
    sentence_len_stdev: float
    lexical_diversity: float = 0.0
    burstiness: float = 0.0
    cliche_hits: List[str] = field(default_factory=list)
    flagged_sentences: List[str] = field(default_factory=list)
    contextual_note: str = ""


def split_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if p.strip()]


def tokenize_words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text.lower())


def analyze_text(text: str) -> DetectionReport:
    sentences = split_sentences(text)
    words = tokenize_words(text)

    if not sentences or not words:
        return DetectionReport(
            ai_score=0.0,
            classification="Insufficient Text",
            avg_sentence_len=0.0,
            sentence_len_stdev=0.0,
            lexical_diversity=0.0,
            burstiness=0.0,
        )

    lengths = [len(tokenize_words(s)) for s in sentences]
    avg_len = statistics.mean(lengths)
    stdev_len = statistics.stdev(lengths) if len(lengths) > 1 else 0.0

    burstiness_ratio = min(stdev_len / max(avg_len, 1.0), 1.0)
    uniformity_risk = (1.0 - burstiness_ratio) * 35.0

    unique_ratio = len(set(words)) / len(words)
    low_diversity_risk = max(0.0, (0.65 - unique_ratio)) * 50.0

    cliche_hits: List[str] = []
    for pattern in AI_CLICHE_PHRASES:
        matches = re.findall(pattern, text.lower())
        if matches:
            cliche_hits.extend(matches)

    cliche_risk = min(len(cliche_hits) * 9.0, 35.0)

    flagged_sentences: List[str] = []
    for s in sentences:
        s_lower = s.lower()
        has_cliche = any(re.search(p, s_lower) for p in AI_CLICHE_PHRASES)
        is_long_and_flat = len(tokenize_words(s)) > 26 and not any(
            sep in s for sep in ["—", " - ", ":", ";", "(", ")"]
        )
        if has_cliche or is_long_and_flat:
            flagged_sentences.append(s)

    raw_score = uniformity_risk + low_diversity_risk + cliche_risk
    ai_score = round(min(max(raw_score, 0.0), 100.0), 1)

    if ai_score >= 65.0:
        classification = "High AI-Pattern Likelihood"
    elif ai_score >= 35.0:
        classification = "Mixed / Moderate AI-Pattern Likelihood"
    else:
        classification = "Low AI-Pattern Likelihood (More Human-Like)"

    return DetectionReport(
        ai_score=ai_score,
        classification=classification,
        avg_sentence_len=round(avg_len, 1),
        sentence_len_stdev=round(stdev_len, 1),
        lexical_diversity=round(unique_ratio, 3),
        burstiness=round(burstiness_ratio, 3),
        cliche_hits=cliche_hits,
        flagged_sentences=flagged_sentences,
    )


def contextual_ai_score(text: str, api_key: str, model: str) -> tuple[float, str] | None:
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=(
                "Assess linguistic patterns in the text, not its author or provenance. "
                "Return only JSON with ai_pattern_score (number 0-100) and note (one concise sentence). "
                "Consider formulaic phrasing, predictability, variation, and context. "
                "Do not infer that a score proves AI authorship.\n\nTEXT:\n" + text
            ),
            config={"response_mime_type": "application/json", "temperature": 0.1},
        )
        result = json.loads(response.text or "{}")
        score = float(result["ai_pattern_score"])
        return round(min(max(score, 0), 100), 1), str(result.get("note", ""))[:300]
    except Exception:
        return None