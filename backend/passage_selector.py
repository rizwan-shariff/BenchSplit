import re
from dataclasses import dataclass
from typing import Optional

STATUTE_PATTERNS = {
    "NI_ACT_S138": re.compile(
        r"(?:section\s*138\s*(?:of|under)?\s*(?:the\s+)?(?:negotiable\s+instruments|n\.?\s*i\.?\s*act)"
        r"|(?:negotiable\s+instruments|n\.?\s*i\.?\s*act).*?section\s*138"
        r"|(?:negotiable\s+instruments|n\.?\s*i\.?\s*act)\s*(?:act\s*)?138)",
        re.IGNORECASE,
    ),
    "ARB_ACT_S11": re.compile(
        r"(?:section\s*11(?:\s*\(\s*6\s*\))?\s*(?:of|under)?\s*(?:the\s+)?"
        r"(?:arbitration|conciliation)|(?:arbitration|conciliation).*?section\s*11"
        r"|arbitration\s*(?:and\s*conciliation\s*)?act\s*11)",
        re.IGNORECASE,
    ),
    "CRPC_S482": re.compile(
        r"(?:section\s*482\s*(?:of|under)?\s*(?:the\s+)?"
        r"(?:code\s+of\s+criminal\s+procedure|cr\.?\s*p\.?\s*c\.?)|"
        r"(?:code\s+of\s+criminal\s+procedure|cr\.?\s*p\.?\s*c\.?).*?section\s*482"
        r"|cr\.?\s*p\.?\s*c\.?\s*482)",
        re.IGNORECASE,
    ),
}
PARAGRAPH_BREAK = re.compile(r"(?:\n\s*\n|\n\s*(?=\d{1,4}[.)]\s+))")


@dataclass(frozen=True)
class Passage:
    statute_key: str
    page_num: int
    page_char_offset: int
    text: str
    page_text: str


def select_passages(
    pages: list[str], statute_key: Optional[str] = None, max_chars: int = 1800
) -> list[Passage]:
    keys = [statute_key] if statute_key else list(STATUTE_PATTERNS)
    if any(key not in STATUTE_PATTERNS for key in keys):
        raise ValueError(f"Unsupported statute key: {statute_key}")
    selected: list[Passage] = []
    for page_number, page_text in enumerate(pages, start=1):
        matches: dict[str, list[int]] = {key: [] for key in keys}
        paragraphs: list[tuple[int, int, str]] = []
        cursor = 0
        for separator in PARAGRAPH_BREAK.finditer(page_text):
            part = page_text[cursor:separator.start()]
            if part.strip():
                left = cursor + len(part) - len(part.lstrip())
                right = cursor + len(part.rstrip())
                paragraphs.append((left, right, page_text[left:right]))
            cursor = separator.end()
        tail = page_text[cursor:]
        if tail.strip():
            left = cursor + len(tail) - len(tail.lstrip())
            right = cursor + len(tail.rstrip())
            paragraphs.append((left, right, page_text[left:right]))
        for paragraph_index, (_, _, paragraph) in enumerate(paragraphs):
            for key in keys:
                if STATUTE_PATTERNS[key].search(paragraph):
                    matches[key].append(paragraph_index)
        for key in keys:
            seen_ranges: set[tuple[int, int]] = set()
            for match_index in matches[key]:
                first = max(0, match_index - 1)
                last = min(len(paragraphs), match_index + 2)
                if (first, last) in seen_ranges:
                    continue
                seen_ranges.add((first, last))
                start = paragraphs[first][0]
                end = paragraphs[last - 1][1]
                text = page_text[start:end]
                if len(text) > max_chars:
                    match_position = paragraphs[match_index][0]
                    local = match_position - start
                    window_start = max(0, min(len(text) - max_chars, local - max_chars // 2))
                    start += window_start
                    text = text[window_start:window_start + max_chars]
                selected.append(Passage(key, page_number, start, text, page_text))
    return selected
