"""Conservative QQ chat chunking and timing; no model round trips.

Split on conversational boundaries, not blindly at every comma/period.
Code, markdown, links and structured data remain a single message.
"""

from __future__ import annotations

import re


_UNSAFE_MARKUP = re.compile(
    r"(?:\x60){3}|https?://|\b(?:[A-Za-z]:\\|/[\w.-]+/)|^\s*(?:[-*+] |\d+[.)] |#{1,6} |>)",
    re.MULTILINE,
)
_SENTENCES = re.compile(r"(?<=[。！？!?])\s*|\n{2,}")


def split_for_qq(text: str, *, max_parts: int = 3, min_chars: int = 11) -> list[str]:
    """Return 1–3 intact chunks, or one original message for technical content.

    Do not reword, paraphrase, or duplicate text. Never drop content.
    Newlines inside technical/list/quote messages are significant.
    """
    text = text.strip()
    if not text:
        return []
    if max_parts < 2 or _UNSAFE_MARKUP.search(text) or text.startswith(("{", "[")):
        return [text]
    if len(text) < max(min_chars * 2, 26):
        return [text]
    raw = [t.strip() for t in _SENTENCES.split(text) if t.strip()]
    if len(raw) < 2:
        return [text]
    chunks: list[str] = []
    current = ""
    for clause in raw:
        if not current:
            current = clause
        elif len(current) < min_chars:
            current += clause
        elif len(chunks) < max_parts - 1:
            chunks.append(current)
            current = clause
        else:
            current += clause
    if current:
        chunks.append(current)
    if len(chunks) < 2 or any(len(x) < 3 for x in chunks):
        return [text]
    if re.sub(r"\s+", "", "".join(chunks)) != re.sub(r"\s+", "", text):
        return [text]
    return chunks[:max_parts]
