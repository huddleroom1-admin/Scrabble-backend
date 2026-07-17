"""A simple heuristic Scrabble AI (no lookahead), used to drive the second
player in "vs AI" rooms.

Design: rules.validate_move is already a complete, battle-tested legality +
scoring oracle (it's the exact function that checks every human move too).
So this module's only job is to propose candidate tile placements for
validate_move to check, then keep the highest-scoring one that comes back
legal. That split keeps the AI simple *and* guarantees it can never submit
an illegal move -- the worst it can do is miss a good play, never make a
bad one.

Search strategy: for every empty square adjacent to an existing tile (an
"anchor" -- or the center square on an empty board), try placing runs of
rack tiles through that square, in both directions, at every offset that
still covers the anchor. Rack-tile arrangements are precomputed once per
turn and reused across all anchors, and the whole search is capped by
SEARCH_BUDGET so a single AI turn can't run away on a crowded board.

Known limitation (v1): the AI never plays a blank tile -- it only searches
using its non-blank rack tiles, so blanks just sit unused in its rack. A
good follow-up: try each blank as every letter A-Z (large search-space
increase, so left out of the first version deliberately).
"""

import itertools

from . import rules
from .board import SIZE

SEARCH_BUDGET = 15000  # max validate_move attempts per AI turn


def _anchors(existing):
    """Empty cells worth trying a word through: adjacent to an existing
    tile, or the center square if the board is empty."""
    if not existing:
        return [(SIZE // 2, SIZE // 2)]
    anchors = set()
    for (r, c) in existing:
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < SIZE and 0 <= nc < SIZE and (nr, nc) not in existing:
                anchors.add((nr, nc))
    return anchors


def _empty_run(existing, row, col, dr, dc):
    """Maximal run of empty cells through (row, col) along (dr, dc),
    bounded by the board edge or an occupied cell on either side."""
    r, c = row, col
    while 0 <= r - dr < SIZE and 0 <= c - dc < SIZE and (r - dr, c - dc) not in existing:
        r, c = r - dr, c - dc
    cells = []
    while 0 <= r < SIZE and 0 <= c < SIZE and (r, c) not in existing:
        cells.append((r, c))
        r, c = r + dr, c + dc
    return cells


def _rack_permutations(available):
    """available: [(rack_index, letter, points), ...], no blanks.

    Returns {length: [(indices_tuple, letters_tuple, points_tuple), ...]},
    deduped by letters_tuple -- two tiles with the same letter are
    interchangeable for word-forming purposes, so trying both wastes a
    validate_move call for an identical result.
    """
    n = len(available)
    perms_by_len = {}
    for length in range(1, n + 1):
        seen = set()
        entries = []
        for combo in itertools.permutations(range(n), length):
            letters = tuple(available[i][1] for i in combo)
            if letters in seen:
                continue
            seen.add(letters)
            indices = tuple(available[i][0] for i in combo)
            points = tuple(available[i][2] for i in combo)
            entries.append((indices, letters, points))
        perms_by_len[length] = entries
    return perms_by_len


def choose_move(existing, rack, dict_wrapper, allow_short, bag_size):
    """existing    : {(r,c): info} current board tiles
    rack        : list of tiles in rack order; each needs .letter, .points
                  (letter == "" marks an unassigned blank, skipped -- see
                  module docstring)
    dict_wrapper: object with .is_word(str) -> bool
    allow_short : passed straight through to rules.validate_move
    bag_size    : tiles remaining, used to decide if a swap is possible

    Returns one of:
      {"action": "submit", "moves": [{"rack_index": i, "row": r, "col": c}, ...]}
      {"action": "swap", "indices": [...]}
      {"action": "pass"}
    """
    available = [(i, t.letter, t.points) for i, t in enumerate(rack) if t.letter]

    best = None  # (score, moves)
    attempts = 0

    if available:
        perms_by_len = _rack_permutations(available)
        anchors = _anchors(existing)

        def budget_left():
            return attempts < SEARCH_BUDGET

        for anchor in anchors:
            if not budget_left():
                break
            for dr, dc in ((0, 1), (1, 0)):
                if not budget_left():
                    break
                run = _empty_run(existing, anchor[0], anchor[1], dr, dc)
                if anchor not in run:
                    continue
                anchor_idx = run.index(anchor)
                run_len = len(run)
                for length, entries in perms_by_len.items():
                    if not budget_left():
                        break
                    if length > run_len:
                        continue
                    lo = max(0, anchor_idx - length + 1)
                    hi = min(anchor_idx, run_len - length)
                    for start in range(lo, hi + 1):
                        if not budget_left():
                            break
                        span = run[start:start + length]
                        for indices, letters, points in entries:
                            if not budget_left():
                                break
                            attempts += 1
                            placements = {
                                span[k]: {"letter": letters[k], "points": points[k]}
                                for k in range(length)
                            }
                            try:
                                _, score = rules.validate_move(
                                    existing, placements, dict_wrapper, allow_short
                                )
                            except rules.MoveError:
                                continue
                            if best is None or score > best[0]:
                                moves = [
                                    {
                                        "rack_index": indices[k],
                                        "row": span[k][0],
                                        "col": span[k][1],
                                    }
                                    for k in range(length)
                                ]
                                best = (score, moves)

    if best is not None:
        return {"action": "submit", "moves": best[1]}

    non_blank_indices = [i for i, t in enumerate(rack) if t.letter]
    if non_blank_indices and bag_size >= len(non_blank_indices):
        return {"action": "swap", "indices": non_blank_indices}

    return {"action": "pass"}
