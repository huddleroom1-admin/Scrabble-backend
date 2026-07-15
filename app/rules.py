"""Scrabble move validation and scoring (pure logic, no networking).

A move is a set of placements: {(row, col): letter_tile_info}. The board's
existing tiles are passed in as {(row, col): info}. validate_move checks full
Scrabble legality and returns the words formed plus the score, or an error.

Tile info is a dict with at least: {"letter": "A", "points": 4}. Board
premiums come from board.PREMIUM; premiums only apply to NEWLY placed tiles.
"""

from . import board

# Premium multipliers per square: (letter_mult, word_mult).
LETTER_MULT = {board.DL: 2, board.TL: 3}
WORD_MULT = {board.DW: 2, board.TW: 3, board.ST: 2}

CENTER = (board.SIZE // 2, board.SIZE // 2)   # (7, 7)


class MoveError(Exception):
    """Raised when a move is illegal; message is player-facing."""


def _line_of(placements):
    """Return 'row', 'col', or 'single' for the orientation of placements.

    Raises MoveError if the new tiles are not all in one row or one column.
    """
    rows = {r for (r, c) in placements}
    cols = {c for (r, c) in placements}
    if len(placements) == 1:
        return "single"
    if len(rows) == 1:
        return "row"
    if len(cols) == 1:
        return "col"
    raise MoveError("Tiles must be in a single row or column.")


def _collect_word(board_tiles, start, step):
    """Walk from `start` backward then forward along `step` over occupied cells.

    Returns (cells, letters, points) for the maximal contiguous run that
    includes `start`. `board_tiles` maps (r,c) -> info for ALL tiles (existing
    plus the move's new ones).
    """
    sr, sc = start
    dr, dc = step
    # Back up to the first cell of the run.
    r, c = sr, sc
    while (r - dr, c - dc) in board_tiles:
        r, c = r - dr, c - dc
    # Walk forward collecting cells.
    cells = []
    while (r, c) in board_tiles:
        cells.append((r, c))
        r, c = r + dr, c + dc
    letters = "".join(board_tiles[cell]["letter"] for cell in cells)
    return cells, letters


MIN_WORD_LEN = 3          # words must be at least 3 letters (2 is invalid)
LENGTH_BONUS_LEN = 7      # a word this long or longer scores double
LENGTH_BONUS_MULT = 2


def _score_word(cells, new_cells, board_tiles):
    """Score one word. Premiums apply only to cells in `new_cells` (this turn).

    A word of LENGTH_BONUS_LEN (7) or more letters has its score doubled.
    """
    total = 0
    word_mult = 1
    for cell in cells:
        info = board_tiles[cell]
        pts = info["points"]
        if cell in new_cells:
            kind = board.PREMIUM[cell[0]][cell[1]]
            pts *= LETTER_MULT.get(kind, 1)
            word_mult *= WORD_MULT.get(kind, 1)
        total += pts
    score = total * word_mult
    # Length bonus: 7+ letter words score double.
    if len(cells) >= LENGTH_BONUS_LEN:
        score *= LENGTH_BONUS_MULT
    return score


def validate_move(existing, placements, dictionary, allow_short=False):
    """Validate a full move and return (words, score).

    existing    : {(r,c): info} tiles already on the board (before this move)
    placements  : {(r,c): info} new tiles this turn
    dictionary  : object with .is_word(str) -> bool
    allow_short : end-game relief valve. When True (e.g. the bag is empty),
                  the 3+ letter main-word requirement is waived, so a 2-letter
                  word is a legal play. Words must still be in the dictionary.

    Raises MoveError on any rule violation.
    Returns (list_of_(word, points), total_score).
    """
    if not placements:
        raise MoveError("No tiles placed.")

    # 1. No overlap with existing tiles; all in bounds.
    for (r, c) in placements:
        if not (0 <= r < board.SIZE and 0 <= c < board.SIZE):
            raise MoveError("Tile out of bounds.")
        if (r, c) in existing:
            raise MoveError("Square already occupied.")

    new_cells = set(placements)
    all_tiles = {**existing, **placements}
    orient = _line_of(placements)

    # 2. The new tiles plus any tiles between them must be contiguous.
    if orient in ("row", "col"):
        if orient == "row":
            row = next(iter(placements))[0]
            cols = sorted(c for (_, c) in placements)
            span = [(row, c) for c in range(cols[0], cols[-1] + 1)]
        else:
            col = next(iter(placements))[1]
            rows = sorted(r for (r, _) in placements)
            span = [(r, col) for r in range(rows[0], rows[-1] + 1)]
        for cell in span:
            if cell not in all_tiles:
                raise MoveError("Placed tiles must be contiguous.")

    # 3. Connection rule: first move must cover center; later moves must touch
    #    at least one existing tile.
    if not existing:
        if CENTER not in placements:
            raise MoveError("First move must cover the center square.")
    else:
        touches = False
        for (r, c) in placements:
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (r + dr, c + dc) in existing:
                    touches = True
        if not touches:
            raise MoveError("New word must connect to existing tiles.")

    # 4. Collect every word formed: the main word + perpendicular cross-words.
    words = []          # (cells, letters)
    seen = set()

    def add_word(cells, letters):
        key = tuple(cells)
        if len(cells) >= 2 and key not in seen:
            seen.add(key)
            words.append((cells, letters))

    # Main word: along the move's orientation (use any placed cell as anchor).
    any_cell = next(iter(placements))
    if orient == "row" or (orient == "single"):
        cells, letters = _collect_word(all_tiles, any_cell, (0, 1))
        add_word(cells, letters)
    if orient == "col" or (orient == "single"):
        cells, letters = _collect_word(all_tiles, any_cell, (1, 0))
        add_word(cells, letters)

    # Cross-words: for each newly placed tile, the perpendicular run.
    for cell in placements:
        if orient == "row":
            cells, letters = _collect_word(all_tiles, cell, (1, 0))
        elif orient == "col":
            cells, letters = _collect_word(all_tiles, cell, (0, 1))
        else:  # single tile already handled both directions above
            continue
        add_word(cells, letters)

    if not words:
        raise MoveError(f"A move must form a word of at least {MIN_WORD_LEN} letters.")

    # 5a. Minimum length: the play must form at least ONE word of MIN_WORD_LEN
    #     (3) letters. Shorter cross-words (2 letters) formed incidentally
    #     alongside a valid main word are allowed -- but a play that ONLY makes
    #     2-letter words is invalid.
    #     Exception: `allow_short` (end-game, bag empty) waives this entirely,
    #     so a 2-letter word becomes a legal play on its own.
    if not allow_short and not any(len(cells) >= MIN_WORD_LEN
                                   for cells, _ in words):
        shortest = min(words, key=lambda w: len(w[0]))
        raise MoveError(
            f"'{shortest[1]}' is too short - your play must make a "
            f"{MIN_WORD_LEN}+ letter word.")

    # 5b. Every formed word must be in the dictionary.
    for cells, letters in words:
        if not dictionary.is_word(letters):
            raise MoveError(f"'{letters}' is not a valid word.")

    # 6. Score every formed word (7+ letter words are doubled in _score_word).
    total = sum(_score_word(cells, new_cells, all_tiles) for cells, _ in words)

    return [(letters, _score_word(cells, new_cells, all_tiles))
            for cells, letters in words], total
