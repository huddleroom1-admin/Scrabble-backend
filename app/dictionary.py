"""Word dictionary for move validation.

Loads the cached word list (assets/words.txt, ENABLE list) into a set for
O(1) lookups. If the file is missing, run fetch_words.py (or see its note)
to download it.
"""

import os

WORDS_PATH = os.path.join(os.path.dirname(__file__), "assets", "words.txt")

_words = None


def load():
    """Load and cache the word set. Returns the set (possibly empty)."""
    global _words
    if _words is not None:
        return _words
    _words = set()
    if os.path.exists(WORDS_PATH):
        with open(WORDS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                w = line.strip().upper()
                if w:
                    _words.add(w)
    return _words


def is_word(word):
    """True if `word` (any case) is in the dictionary. Words must be >= 2 chars."""
    w = word.upper()
    if len(w) < 2:
        return False
    return w in load()


if __name__ == "__main__":
    words = load()
    print(f"Loaded {len(words)} words from {WORDS_PATH}")
    for w in ("CAT", "QI", "ZZZ", "STOCK", "AAPL"):
        print(f"  {w}: {is_word(w)}")
