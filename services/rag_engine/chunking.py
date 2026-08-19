import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Chunk:
    text: str
    page: int | None
    start_char: int
    end_char: int
    heading: str | None = None

_AR_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")
_ARABIC_NORMALIZATION = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه", "ـ": "",
})


def normalize_arabic(text: str) -> str:
    text = _AR_DIACRITICS.sub("", text or "")
    return text.translate(_ARABIC_NORMALIZATION)


def normalize_for_search(text: str) -> str:
    text = normalize_arabic(text).lower()
    text = re.sub(r"[^\w\u0600-\u06ff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u0600-\u06ff]+", normalize_for_search(text))


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    start = 0
    for m in re.finditer(r"(?<=[.!؟?؛:])\s+|\n{2,}", text):
        end = m.start()
        sentence = text[start:end].strip()
        if sentence:
            spans.append((sentence, start, end))
        start = m.end()
    tail = text[start:].strip()
    if tail:
        spans.append((tail, start, len(text)))
    return spans


def _detect_heading(sentence: str, current: str | None) -> str | None:
    stripped = sentence.strip()
    if len(stripped) <= 90 and (
        re.match(r"^(#{1,6}|[0-9]+[.)-]|[\u0660-\u0669]+[.)-])\s+", stripped)
        or stripped.endswith(":")
        or stripped.isupper()
    ):
        return stripped[:90]
    return current


def chunk_text_advanced(text: str, size: int = 900, overlap: int = 120, page_map: list[tuple[int, int, int]] | None = None) -> list[Chunk]:
    """Arabic/English sentence-aware chunking with overlap and source offsets."""
    text = re.sub(r"[ \t]+", " ", text or "").strip()
    if not text:
        return []
    size = max(240, size)
    overlap = max(0, min(overlap, size // 2))
    sentences = _split_sentences(text)
    chunks: list[Chunk] = []
    current: list[tuple[str, int, int]] = []
    current_len = 0
    heading: str | None = None

    def page_for(pos: int) -> int | None:
        if not page_map:
            return None
        for page, start, end in page_map:
            if start <= pos <= end:
                return page
        return None

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        joined = " ".join(x[0] for x in current).strip()
        chunks.append(Chunk(text=joined, page=page_for(current[0][1]), start_char=current[0][1], end_char=current[-1][2], heading=heading))
        if overlap > 0:
            tail_text = joined[-overlap:]
            tail_start = max(current[-1][1], current[-1][2] - len(tail_text))
            current = [(tail_text, tail_start, current[-1][2])]
            current_len = len(tail_text)
        else:
            current = []
            current_len = 0

    for sentence, start, end in sentences:
        heading = _detect_heading(sentence, heading)
        if len(sentence) > size:
            flush()
            step = size - overlap if overlap else size
            for sub_start in range(0, len(sentence), step):
                piece = sentence[sub_start:sub_start + size].strip()
                if piece:
                    chunks.append(Chunk(text=piece, page=page_for(start + sub_start), start_char=start + sub_start, end_char=min(end, start + sub_start + len(piece)), heading=heading))
            current = []
            current_len = 0
            continue
        if current_len + len(sentence) + 1 > size:
            flush()
        current.append((sentence, start, end))
        current_len += len(sentence) + 1
    flush()
    # remove near-empty duplicate overlap-only chunks
    clean: list[Chunk] = []
    seen = set()
    for c in chunks:
        key = normalize_for_search(c.text[:200])
        if len(c.text.strip()) < 20 or key in seen:
            continue
        seen.add(key)
        clean.append(c)
    return clean
