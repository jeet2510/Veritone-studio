import difflib
import re
from dataclasses import dataclass, field
from typing import Dict, List


DIRECT_REPLACEMENTS: Dict[str, str] = {
    r"\butilize\b": "use",
    r"\butilizing\b": "using",
    r"\bfacilitate\b": "help",
    r"\bdemonstrate\b": "show",
    r"\bdemonstrates\b": "shows",
    r"\bnumerous\b": "many",
    r"\badditionally\b": "also",
    r"\bconsequently\b": "as a result",
    r"\bprior to\b": "before",
    r"\bsubsequent to\b": "after",
    r"\bin order to\b": "to",
    r"\bdue to the fact that\b": "because",
    r"\ba wide range of\b": "many",
    r"\bplay a vital role\b": "matter",
    r"\bplays a vital role\b": "matters",
}

LEAD_IN_STRIP_PATTERNS: List[str] = [
    r"^(In conclusion,?\s*)",
    r"^(Moreover,?\s*)",
    r"^(Furthermore,?\s*)",
    r"^(It is important to note that\s*)",
    r"^(It is worth noting that\s*)",
]


@dataclass
class ChangeRecord:
    change_type: str
    before: str
    after: str
    sentence_index: int


@dataclass
class HumanizeResult:
    text: str
    total_changes: int
    change_percentage: float
    changed_sentences: int
    total_sentences: int
    changes: List[ChangeRecord] = field(default_factory=list)


def _count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def _match_case(replacement: str, original: str) -> str:
    if original.istitle():
        return replacement.capitalize()
    if original.isupper():
        return replacement.upper()
    return replacement


def humanize_sentence(
    sentence: str,
    sentence_index: int,
    changes: List[ChangeRecord],
) -> str:
    updated = sentence.strip()
    sentence_changed = False

    for pat in LEAD_IN_STRIP_PATTERNS:
        match = re.search(pat, updated, flags=re.IGNORECASE)
        if match:
            removed_str = match.group(0).strip()
            updated = re.sub(pat, "", updated, flags=re.IGNORECASE).strip()
            changes.append(
                ChangeRecord(
                    change_type="lead_in_removed",
                    before=removed_str,
                    after="(removed)",
                    sentence_index=sentence_index,
                )
            )
            sentence_changed = True
            break

    if updated and updated[0].islower():
        before_char = updated[0]
        updated = updated[0].upper() + updated[1:]
        if not sentence_changed:
            changes.append(
                ChangeRecord(
                    change_type="capitalization",
                    before=before_char,
                    after=updated[0],
                    sentence_index=sentence_index,
                )
            )

    for pattern, plain in DIRECT_REPLACEMENTS.items():
        def _sub(match: re.Match) -> str:
            original_phrase = match.group(0)
            replacement_phrase = _match_case(plain, original_phrase)
            if original_phrase != replacement_phrase:
                changes.append(
                    ChangeRecord(
                        change_type="phrase_replaced",
                        before=original_phrase,
                        after=replacement_phrase,
                        sentence_index=sentence_index,
                    )
                )
            return replacement_phrase

        updated = re.sub(pattern, _sub, updated, flags=re.IGNORECASE)

    def _split_which(match: re.Match) -> str:
        full_match = match.group(0)
        clause_tail = match.group(1).strip()
        replacement_split = f". That {clause_tail}"
        changes.append(
            ChangeRecord(
                change_type="clause_split",
                before=full_match.strip(),
                after=replacement_split.strip(),
                sentence_index=sentence_index,
            )
        )
        return replacement_split

    updated = re.sub(
        r",\s+which\s+([a-z]+s?\s+[^.!?]+)",
        _split_which,
        updated,
    )

    return updated.strip()


def humanize_text_with_report(
    text: str, api_key: str = "", model: str = "gemini-2.0-flash"
) -> HumanizeResult:
    if api_key:
        model_result = _humanize_with_gemini(text, api_key, model)
        if model_result is not None:
            return model_result

    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    output_paragraphs: List[str] = []
    changes: List[ChangeRecord] = []

    original_word_count = max(_count_words(text), 1)
    sentence_counter = 0
    changed_sentence_count = 0

    for para in paragraphs:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
        rewritten_sentences: List[str] = []

        for s in sentences:
            sentence_counter += 1
            before_count = len(changes)
            new_s = humanize_sentence(s, sentence_counter, changes)
            if len(changes) > before_count or new_s != s:
                changed_sentence_count += 1
            rewritten_sentences.append(new_s)

        output_paragraphs.append(" ".join(rewritten_sentences))

    final_text = "\n\n".join(output_paragraphs)
    total_changes = len(changes)

    estimated_changed_words = min(
        sum(max(_count_words(c.before), 1) for c in changes),
        original_word_count,
    )
    change_percentage = round((estimated_changed_words / original_word_count) * 100.0, 1)

    return HumanizeResult(
        text=final_text,
        total_changes=total_changes,
        change_percentage=change_percentage,
        changed_sentences=changed_sentence_count,
        total_sentences=sentence_counter,
        changes=changes,
    )


def _humanize_with_gemini(text: str, api_key: str, model: str) -> HumanizeResult | None:
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=(
                "Edit the prose below to sound clear, specific, and naturally varied while "
                "preserving every claim, qualification, citation, technical term, number, "
                "LaTeX command, and equation exactly in meaning. Do not invent details or "
                "add a preface. Return only the revised text.\n\nTEXT:\n" + text
            ),
            config={"temperature": 0.35},
        )
        rewritten = (response.text or "").strip()
        rewritten = re.sub(r"\A```(?:text|markdown)?\s*|\s*```\Z", "", rewritten).strip()
        if not rewritten:
            return None
    except Exception:
        return None

    original_sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    rewritten_sentences = [s for s in re.split(r"(?<=[.!?])\s+", rewritten) if s]
    changes: List[ChangeRecord] = []
    changed_sentences = 0
    modified_words = 0
    matcher = difflib.SequenceMatcher(a=original_sentences, b=rewritten_sentences, autojunk=False)
    for tag, start, end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        before = " ".join(original_sentences[start:end])
        after = " ".join(rewritten_sentences[new_start:new_end])
        changes.append(
            ChangeRecord(
                change_type="gemini_rewrite",
                before=before,
                after=after or "(removed)",
                sentence_index=start + 1,
            )
        )
        changed_sentences += max(end - start, 1)
        modified_words += len(re.findall(r"[A-Za-z0-9']+", before))

    word_count = max(_count_words(text), 1)
    return HumanizeResult(
        text=rewritten,
        total_changes=len(changes),
        change_percentage=round(min(modified_words, word_count) / word_count * 100, 1),
        changed_sentences=min(changed_sentences, len(original_sentences)),
        total_sentences=len(original_sentences),
        changes=changes,
    )