"""Deterministic text features for novelty and editorial diversity."""

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence


def normalize_words(text: str) -> str:
    return " ".join(tokenize_words(text))


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold())


def char_trigrams(text: str) -> frozenset[str]:
    value = normalize_words(text)
    return frozenset(value[i : i + 3] for i in range(max(0, len(value) - 2)))


def trigram_jaccard(a: str, b: str) -> float:
    left, right = char_trigrams(a), char_trigrams(b)
    return len(left & right) / len(left | right) if left or right else 0.0


def extract_keywords(text: str, *, limit: int = 12) -> list[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "has",
        "have",
        "into",
        "not",
        "can",
        "but",
    }
    return [
        word for word, _ in Counter(w for w in tokenize_words(text) if len(w) > 2 and w not in stop).most_common(limit)
    ]


def count_repeated_phrases(
    texts: Sequence[str], *, min_words: int = 3, max_words: int = 5, min_count: int = 3, limit: int = 20
) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for text in texts:
        words = tokenize_words(text)
        counts.update(
            {
                " ".join(words[i : i + size])
                for size in range(min_words, max_words + 1)
                for i in range(len(words) - size + 1)
            }
        )
    return sorted(((p, n) for p, n in counts.items() if n >= min_count), key=lambda item: (-item[1], item[0]))[:limit]


def opening_sentence(text: str, *, max_chars: int = 500) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return re.split(r"(?<=[.!?])\s+", " ".join(lines), maxsplit=1)[0][:max_chars] if lines else ""
