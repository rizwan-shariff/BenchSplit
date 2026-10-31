import re
import string
from dataclasses import dataclass
from typing import Optional

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None

_SMART_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "‚": "'"})
_EDGE_PUNCTUATION = string.punctuation + "“”‘’"


@dataclass(frozen=True)
class VerificationResult:
    status: str
    score: float
    quote: str
    char_start: int
    char_end: int
    error_msg: Optional[str] = None


def normalize_with_index(text: str) -> tuple[str, list[int]]:
    mapped = text.translate(_SMART_QUOTES)
    chars: list[str] = []
    offsets: list[int] = []
    source_indices = [i for i in range(len(text))]
    for index, character in enumerate(mapped):
        if character.isspace():
            if not chars or chars[-1] == " ":
                continue
            chars.append(" ")
            offsets.append(source_indices[index])
        else:
            chars.append(character)
            offsets.append(source_indices[index])
    normalized = "".join(chars).strip()
    if normalized:
        leading = len("".join(chars)) - len("".join(chars).lstrip())
        offsets = offsets[leading:leading + len(normalized)]
    else:
        offsets = []
    start = 0
    end = len(normalized)
    while start < end and normalized[start] in _EDGE_PUNCTUATION:
        start += 1
    while end > start and normalized[end - 1] in _EDGE_PUNCTUATION:
        end -= 1
    return normalized[start:end], offsets[start:end]


def normalize_quote(text: str) -> str:
    return normalize_with_index(text)[0]


def verify_quote(
    passage_text: str,
    page_char_offset: int,
    llm_quote: str,
    *,
    page_text: Optional[str] = None,
) -> VerificationResult:
    normalized_quote, _ = normalize_with_index(llm_quote)
    normalized_passage, passage_offsets = normalize_with_index(passage_text)
    page_text = page_text if page_text is not None else passage_text
    if not normalized_quote:
        return VerificationResult("FAILED", 0.0, llm_quote, -1, -1,
                                  "Quote not found verbatim in source passage. Copy an exact contiguous sentence from the text.")
    exact_index = normalized_passage.find(normalized_quote)
    if exact_index >= 0:
        end_index = exact_index + len(normalized_quote) - 1
        start = page_char_offset + passage_offsets[exact_index]
        end = page_char_offset + passage_offsets[end_index] + 1
        return VerificationResult("VERIFIED_EXACT", 100.0, page_text[start:end], start, end)

    alignment = None
    if fuzz is not None:
        alignment = fuzz.partial_ratio_alignment(normalized_quote, normalized_passage)
        score = float(alignment.score)
        if score >= 92.0 and alignment.dest_start < alignment.dest_end:
            start = page_char_offset + passage_offsets[alignment.dest_start]
            end = page_char_offset + passage_offsets[alignment.dest_end - 1] + 1
            return VerificationResult("VERIFIED_FUZZY", score, page_text[start:end], start, end)
    else:
        from difflib import SequenceMatcher

        matcher = SequenceMatcher(None, normalized_passage, normalized_quote, autojunk=False)
        block = matcher.find_longest_match(0, len(normalized_passage), 0, len(normalized_quote))
        score = 200.0 * block.size / (len(normalized_passage) + len(normalized_quote))
        if score >= 92.0 and block.size:
            first = block.a
            last = block.a + block.size - 1
            start = page_char_offset + passage_offsets[first]
            end = page_char_offset + passage_offsets[last] + 1
            return VerificationResult("VERIFIED_FUZZY", score, page_text[start:end], start, end)

    return VerificationResult(
        "FAILED",
        score if "score" in locals() else 0.0,
        llm_quote,
        -1,
        -1,
        "Quote not found verbatim in source passage. Copy an exact contiguous sentence from the text.",
    )
