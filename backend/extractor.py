import re
import tempfile
from pathlib import Path
from pypdf import PdfReader


def extract_latex_prose(tex_source: str) -> str:
    body_match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", tex_source, flags=re.DOTALL)
    text = body_match.group(1) if body_match else tex_source

    for env in ["lstlisting", "verbatim", "equation", "align", "tabular", "tabularx", "tikzpicture"]:
        text = re.sub(rf"\\begin\{{{env}\*?\}}.*?\\end\{{{env}\*?\}}", "\n\n", text, flags=re.DOTALL)

    text = re.sub(r"(?<!\\)%[^\n]*", "", text)
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(
        r"\\(?:section|subsection|subsubsection|caption|label|ref|eqref|cite|texttt|emph|textbf|path)\{([^{}]*)\}",
        r"\1",
        text,
    )
    text = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_from_upload(file_storage, latex_mode: bool = False) -> tuple[str, str, str]:
    filename = file_storage.filename or "uploaded_file"
    suffix = Path(filename).suffix.lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        while True:
            chunk = file_storage.stream.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    try:
        if suffix == ".pdf":
            reader = PdfReader(str(tmp_path))
            pages = [page.extract_text() or "" for page in reader.pages]
            extracted = "\n\n".join(p.strip() for p in pages if p.strip())
            return extracted, filename, "pdf"

        raw_text = tmp_path.read_text(encoding="utf-8", errors="replace")
        if latex_mode or suffix == ".tex":
            return extract_latex_prose(raw_text), filename, "latex"
        return raw_text, filename, "text"
    finally:
        tmp_path.unlink(missing_ok=True)