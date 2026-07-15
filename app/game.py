"""Authoritative stock-Scrabble game state, ported from the original TCP
socket server to be async/WebSocket-friendly and to support many concurrent
games ("rooms") instead of exactly one global game.

Game logic (rules, scoring, dictionary, bag/rack management) is unchanged
from the original project -- only the transport layer changed:
  socket + threading.Lock + protocol.py  -->  WebSocket + asyncio.Lock + JSON

Wire protocol (unchanged from the original, still one JSON object per message):

Server -> client:
  {"type": "WELCOME", "player": 1}
  {"type": "STATE", ...}                  full game snapshot (see snapshot_for)
  {"type": "ERROR", "msg": "..."}
  {"type": "INFO",  "msg": "..."}

Client -> server:
  {"type": "SUBMIT", "moves": [{"rack_index": i, "row": r, "col": c,
                                 "blank_letter": "A"}, ...]}
  {"type": "SWAP", "indices": [0, 2, 5]}
  {"type": "PASS"}
  {"type": "PAUSE"}
  {"type": "RESUME"}
  {"type": "SURRENDER"}
  {"type": "NEWGAME"}
"""

import asyncio
import random
import time

from . import dictionary
from . import rules
from .stocks import all_letter_tiles

MAX_PLAYERS = 2
RACK_SIZE = 7
TURN_SECONDS = 180  # per-turn time limit (3 min); expiry auto-passes


def tile_to_dict(tile):
    """Serialize a LetterTile for the wire."""
    return {
        "letter": tile.letter,
        "points": tile.points,
        "ticker": tile.ticker,
        "name": tile.name,
    }


class _DictWrapper:
    """Adapts the dictionary module to the .is_word interface rules expects."""

    @staticmethod
    def is_word(w):
        return dictionary.is_word(w)


class Room:
    """One live game (2 players). Equivalent to the original GameState, but
    scoped to a room code so a single server process can host many games,
    and guarded by an asyncio.Lock so it plays nicely with WebSocket handlers.
    """

    def __init__(self, code):
        self.code = code
        self.lock = asyncio.Lock()
        self.clients = {}  # player -> WebSocket
        self.placed = {}  # "row,col" -> tile dict (with owner)
        self.racks = {1: [], 2: []}
        self.scores = {1: 0, 2: 0}
        self.turn = 1
        self.dict = _DictWrapper()

        self.bag = all_letter_tiles()
        random.shuffle(self.bag)

        self.history = []
        self.last_play = None

        self.turn_deadline = None  # time.monotonic() instant, or None
        self.paused = False
        self.paused_remaining = None
        self.paused_by = None

        self.consecutive_passes = 0
        self.game_over = False
        self.final = None

        self.timer_task = None  # asyncio.Task, started once the room is full

    # ---- bookkeeping (mirrors the original GameState) ---------------------

    def add_history(self, entry):
        self.history.append(entry)

    def start_turn_clock(self):
        if self.game_over:
            self.turn_deadline = None
        else:
            self.turn_deadline = time.monotonic() + TURN_SECONDS

    def seconds_left(self):
        if self.paused:
            return self.paused_remaining
        if self.turn_deadline is None:
            return None
        return max(0, int(round(self.turn_deadline - time.monotonic())))

    def next_turn(self):
        self.turn = 2 if self.turn == 1 else 1
        self.start_turn_clock()

    def rack_points(self, player):
        return sum(t.points for t in self.racks.get(player, []))

    def draw_tiles(self, n):
        drawn = []
        for _ in range(n):
            if not self.bag:
                break
            drawn.append(self.bag.pop())
        return drawn

    def deal_rack(self, player):
        rack = self.racks[player]
        rack.extend(self.draw_tiles(RACK_SIZE - len(rack)))

    def existing_for_rules(self):
        out = {}
        for key, info in self.placed.items():
            r, c = map(int, key.split(","))
            out[(r, c)] = info
        return out

    def snapshot_for(self, player):
        return {
            "type": "STATE",
            "placed": self.placed,
            "turn": self.turn,
            "players": len(self.clients),
            "scores": self.scores,
            "bag": len(self.bag),
            "your_rack": [tile_to_dict(t) for t in self.racks.get(player, [])],
            "history": self.history,
            "last_play": self.last_play,
            "turn_seconds_left": self.seconds_left(),
            "turn_limit": TURN_SECONDS,
            "paused": self.paused,
            "paused_by": self.paused_by,
            "game_over": self.game_over,
            "final": self.final,
        }

    # ---- state transitions (call while holding self.lock) -----------------

    async def broadcast(self):
        stale = []
        for p, ws in list(self.clients.items()):
            try:
                await ws.send_json(self.snapshot_for(p))
            except Exception:
                stale.append(p)
        for p in stale:
            self.clients.pop(p, None)

    async def pause(self, player):
        if self.paused or self.game_over or len(self.clients) < MAX_PLAYERS:
            return
        self.paused_remaining = self.seconds_left()
        self.paused = True
        self.paused_by = player
        self.turn_deadline = None
        await self.broadcast()

    async def resume(self):
        if not self.paused:
            return
        remaining = (
            self.paused_remaining if self.paused_remaining is not None else TURN_SECONDS
        )
        self.turn_deadline = time.monotonic() + remaining
        self.paused = False
        self.paused_remaining = None
        self.paused_by = None
        await self.broadcast()

    def check_endgame(self, player_just_moved=None):
        if self.game_over:
            return
        out = (
            player_just_moved is not None
            and not self.racks[player_just_moved]
            and not self.bag
        )
        deadlock = self.consecutive_passes >= MAX_PLAYERS
        if out or deadlock:
            self.finalize(finisher=player_just_moved if out else None)

    def finalize(self, finisher=None):
        leftovers = {p: self.rack_points(p) for p in (1, 2)}
        for p in (1, 2):
            self.scores[p] -= leftovers[p]
        if finisher is not None:
            self.scores[finisher] += sum(
                leftovers[p] for p in (1, 2) if p != finisher
            )

        s1, s2 = self.scores[1], self.scores[2]
        winner = 0 if s1 == s2 else (1 if s1 > s2 else 2)
        self.game_over = True
        self.turn_deadline = None
        self.final = {
            "scores": dict(self.scores),
            "leftovers": leftovers,
            "winner": winner,
            "finisher": finisher,
        }

    async def surrender(self, player):
        if self.game_over or len(self.clients) < MAX_PLAYERS:
            return
        opponent = 2 if player == 1 else 1
        self.game_over = True
        self.paused = False
        self.turn_deadline = None
        self.add_history(
            {
                "player": player,
                "kind": "surrender",
                "text": "surrendered",
                "points": 0,
                "anchor": None,
            }
        )
        self.final = {
            "scores": dict(self.scores),
            "leftovers": {1: self.rack_points(1), 2: self.rack_points(2)},
            "winner": opponent,
            "finisher": None,
            "surrendered_by": player,
        }
        await self.broadcast()

    async def reset(self):
        self.placed = {}
        self.scores = {1: 0, 2: 0}
        self.turn = 1
        self.history = []
        self.last_play = None
        self.consecutive_passes = 0
        self.game_over = False
        self.final = None
        self.paused = False
        self.paused_remaining = None
        self.paused_by = None
        self.bag = all_letter_tiles()
        random.shuffle(self.bag)
        self.racks = {1: [], 2: []}
        for p in list(self.clients):
            self.deal_rack(p)
        if len(self.clients) == MAX_PLAYERS:
            self.start_turn_clock()
        else:
            self.turn_deadline = None
        await self.broadcast()


# ---- move handlers (module-level, same shape as the original server) ------


async def handle_submit(room: Room, player, moves):
    """Validate and apply a SUBMIT move. Returns (error_or_None, info_or_None)."""
    if not isinstance(moves, list) or not moves:
        return "No tiles placed.", None

    async with room.lock:
        if room.game_over:
            return "Game over.", None
        if room.paused:
            return "Game is paused.", None
        if len(room.clients) < MAX_PLAYERS:
            return "Waiting for opponent.", None
        if player != room.turn:
            return "Not your turn.", None

        rack = room.racks[player]
        used_indices = set()
        placements = {}
        for m in moves:
            try:
                idx = int(m["rack_index"])
                r = int(m["row"])
                c = int(m["col"])
            except (KeyError, TypeError, ValueError):
                return "Malformed move.", None
            if idx in used_indices:
                return "Same rack tile used twice.", None
            if not (0 <= idx < len(rack)):
                return "No such tile in your rack.", None
            if (r, c) in placements:
                return "Two tiles on the same square.", None
            used_indices.add(idx)
            tile = rack[idx]
            info = {**tile_to_dict(tile), "owner": player}
            if getattr(tile, "neutral", False) and not tile.letter:
                chosen_letter = str(m.get("blank_letter", "")).upper()
                if len(chosen_letter) != 1 or not chosen_letter.isalpha():
                    return "Pick a letter for the blank tile.", None
                info["letter"] = chosen_letter
                info["blank"] = True
                info["points"] = 0
            placements[(r, c)] = info

        try:
            words, gained = rules.validate_move(
                room.existing_for_rules(),
                placements,
                room.dict,
                allow_short=(len(room.bag) == 0),
            )
        except rules.MoveError as exc:
            return str(exc), None

        for (r, c), info in placements.items():
            room.placed[f"{r},{c}"] = info
        for idx in sorted(used_indices, reverse=True):
            rack.pop(idx)
        room.scores[player] += gained
        room.deal_rack(player)
        room.consecutive_passes = 0
        room.next_turn()

        summary = ", ".join(f"{w} (+{p})" for w, p in words)
        word_text = ", ".join(w for w, _ in words)
        anchor = sorted(placements.keys())[0]
        room.add_history(
            {
                "player": player,
                "kind": "play",
                "text": word_text,
                "points": gained,
                "anchor": [anchor[0], anchor[1]],
            }
        )
        room.last_play = {
            "player": player,
            "word": word_text,
            "points": gained,
            "seq": len(room.history),
        }

        room.check_endgame(player_just_moved=player)
        await room.broadcast()
        return None, summary


async def handle_swap(room: Room, player, indices):
    if not isinstance(indices, list) or not indices:
        return "No tiles selected to swap.", None

    async with room.lock:
        if room.game_over:
            return "Game over.", None
        if room.paused:
            return "Game is paused.", None
        if len(room.clients) < MAX_PLAYERS:
            return "Waiting for opponent.", None
        if player != room.turn:
            return "Not your turn.", None

        rack = room.racks[player]
        idxs = sorted(set(int(i) for i in indices), reverse=True)
        if any(not (0 <= i < len(rack)) for i in idxs):
            return "Invalid tile selection.", None
        if len(room.bag) < len(idxs):
            return "Not enough tiles in the bag to swap.", None

        returned = [rack.pop(i) for i in idxs]
        drawn = room.draw_tiles(len(returned))
        rack.extend(drawn)
        room.bag.extend(returned)
        random.shuffle(room.bag)

        room.consecutive_passes += 1
        room.next_turn()
        room.add_history(
            {
                "player": player,
                "kind": "swap",
                "text": f"swapped {len(returned)}",
                "points": 0,
                "anchor": None,
            }
        )
        room.check_endgame()
        await room.broadcast()
        return None, f"Swapped {len(returned)} tile(s)"


async def _pass_locked(room: Room, player, text="passed"):
    """Caller must hold room.lock and have verified it's legal to pass."""
    room.consecutive_passes += 1
    room.next_turn()
    room.add_history(
        {"player": player, "kind": "pass", "text": text, "points": 0, "anchor": None}
    )
    room.check_endgame()
    await room.broadcast()


async def handle_pass(room: Room, player):
    async with room.lock:
        if (
            not room.game_over
            and not room.paused
            and player == room.turn
            and len(room.clients) == MAX_PLAYERS
        ):
            await _pass_locked(room, player)


async def turn_timer(room: Room):
    """Watchdog: auto-pass the active player's turn when their clock expires.
    One of these runs per room (started when the room fills up).
    """
    while not room.game_over:
        await asyncio.sleep(0.25)
        async with room.lock:
            if (
                room.game_over
                or len(room.clients) < MAX_PLAYERS
                or room.turn_deadline is None
            ):
                continue
            if room.seconds_left() <= 0:
                expired = room.turn
                await _pass_locked(room, expired, text="timed out")
