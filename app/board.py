"""Shared Scrabble board definition used by both server and client.

Holds the static 15x15 premium-square layout and the rendering colors.
Letter tiles are intentionally left out for now.
"""

# --- Board layout ---------------------------------------------------------
# Each cell holds one of:
#   "TW" triple word, "DW" double word,
#   "TL" triple letter, "DL" double letter,
#   ""   normal, "ST" center start square.
SIZE = 15

TW, DW, TL, DL, ST = "TW", "DW", "TL", "DL", "ST"

# Official Scrabble premium-square layout (15x15).
PREMIUM = [
    [TW, "", "", DL, "", "", "", TW, "", "", "", DL, "", "", TW],
    ["", DW, "", "", "", TL, "", "", "", TL, "", "", "", DW, ""],
    ["", "", DW, "", "", "", DL, "", DL, "", "", "", DW, "", ""],
    [DL, "", "", DW, "", "", "", DL, "", "", "", DW, "", "", DL],
    ["", "", "", "", DW, "", "", "", "", "", DW, "", "", "", ""],
    ["", TL, "", "", "", TL, "", "", "", TL, "", "", "", TL, ""],
    ["", "", DL, "", "", "", DL, "", DL, "", "", "", DL, "", ""],
    [TW, "", "", DL, "", "", "", ST, "", "", "", DL, "", "", TW],
    ["", "", DL, "", "", "", DL, "", DL, "", "", "", DL, "", ""],
    ["", TL, "", "", "", TL, "", "", "", TL, "", "", "", TL, ""],
    ["", "", "", "", DW, "", "", "", "", "", DW, "", "", "", ""],
    [DL, "", "", DW, "", "", "", DL, "", "", "", DW, "", "", DL],
    ["", "", DW, "", "", "", DL, "", DL, "", "", "", DW, "", ""],
    ["", DW, "", "", "", TL, "", "", "", TL, "", "", "", DW, ""],
    [TW, "", "", DL, "", "", "", TW, "", "", "", DL, "", "", TW],
]

# --- Appearance -----------------------------------------------------------
CELL = 44            # pixel size of one square
MARGIN = 20          # border around the board
GRID = 1             # grid line thickness
WIDTH = SIZE * CELL + 2 * MARGIN
HEIGHT = WIDTH

COLORS = {
    TW: (211, 72, 54),    # red
    DW: (240, 160, 168),  # pink
    TL: (58, 124, 165),   # dark blue
    DL: (152, 200, 226),  # light blue
    ST: (240, 160, 168),  # pink (center)
    "": (224, 220, 206),  # board beige
}

LABELS = {TW: "TW", DW: "DW", TL: "TL", DL: "DL"}

BACKGROUND = (40, 36, 32)
GRID_COLOR = (90, 84, 76)
TEXT_COLOR = (30, 30, 30)
STAR_COLOR = (140, 60, 70)

# Marks placed by players (placeholder for real tiles). Player number -> color.
PLAYER_COLORS = {
    1: (60, 110, 60),     # green
    2: (150, 90, 30),     # brown/orange
}


def cell_at_pixel(px, py):
    """Return (row, col) for a pixel position, or None if outside the grid."""
    col = (px - MARGIN) // CELL
    row = (py - MARGIN) // CELL
    if 0 <= row < SIZE and 0 <= col < SIZE:
        return int(row), int(col)
    return None


def cell_rect(row, col):
    """Return (x, y, w, h) pixel rect for a board cell."""
    return (MARGIN + col * CELL, MARGIN + row * CELL, CELL, CELL)
