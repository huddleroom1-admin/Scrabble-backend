# Stock Scrabble — Backend

This is your original `scrabble` game's logic (`board.py`, `rules.py`,
`dictionary.py`, `stocks.py`) ported from a raw TCP socket server to a
**FastAPI + WebSocket** server, so it can be reached from a mobile app over
the real internet and deployed like a normal web service.

## What changed vs. the original

| Original | This version | Why |
|---|---|---|
| Raw TCP socket, custom framing (`protocol.py`) | WebSocket, JSON messages | Mobile OSes and app stores expect WebSocket/HTTP; raw sockets are painful on iOS in particular |
| One global game (exactly 2 players, ever) | Many concurrent **rooms**, each with its own 2-player game | So the server can host many simultaneous matches for real users |
| `threading.Lock` + a thread per client | `asyncio.Lock` + one FastAPI process | Matches FastAPI's async model |
| Pygame client draws everything | *(not part of this backend — that's the Flutter app, next step)* | Pygame can't run on iOS/Android |

**Not changed at all:** `board.py`, `rules.py`, `dictionary.py`, `stocks.py`
were copied over verbatim — they had no Pygame or networking dependency, so
your move validation, scoring (including the length bonus and premium
squares), and tile bag/point rules behave identically to the original.

## Project layout

```
backend/
  app/
    main.py         FastAPI app: room creation + the WebSocket endpoint
    game.py          Room (game state) + move handlers, ported from server.py
    board.py         unchanged
    rules.py         unchanged
    dictionary.py    unchanged
    stocks.py        unchanged
    assets/words.txt unchanged
  requirements.txt
```

## Run it locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health`

## Playing a game (protocol)

1. **Create a room** (or just agree on a code with your opponent — any
   string works as a room code):
   ```
   POST /rooms
   -> {"code": "AB3F9K"}
   ```
2. **Both players connect** a WebSocket to:
   ```
   ws://<host>/ws/AB3F9K
   ```
   The first player to connect becomes player 1, the second player 2. A
   third connection attempt gets `{"type": "ERROR", "msg": "Game is full."}`.
3. **Server sends** `{"type": "WELCOME", "player": 1}` immediately, then a
   `STATE` snapshot after each change. `STATE` includes the board, your own
   rack, scores, whose turn it is, the turn clock, and move history — this
   is everything a client needs to redraw the screen.
4. **Client sends** one of:
   ```json
   {"type": "SUBMIT", "moves": [{"rack_index": 0, "row": 7, "col": 7}, ...]}
   {"type": "SWAP", "indices": [0, 2, 5]}
   {"type": "PASS"}
   {"type": "PAUSE"}
   {"type": "RESUME"}
   {"type": "SURRENDER"}
   {"type": "NEWGAME"}
   ```
   For a blank tile, add `"blank_letter": "A"` to that move's entry.

Full message shapes are documented in the docstring at the top of `game.py`.

## Deploying so it's reachable from a real phone

Any host that runs a long-lived Python process with WebSocket support works.
Easiest options for a small project like this:

- **Render** — connect the GitHub repo, set the start command to
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, free tier available.
- **Railway** or **Fly.io** — similar; both support WebSockets out of the box.

Once deployed you'll have a URL like `https://your-app.onrender.com`; the
Flutter app will connect to `wss://your-app.onrender.com/ws/<code>`.

## Known gaps to revisit later

- **Rooms never expire.** A disconnected player can currently rejoin the
  same code, which is nice for dropped connections, but abandoned rooms sit
  in memory forever. Add a cleanup task before this sees real traffic.
- **No auth.** Anyone who knows a room code can join it. Fine for
  play-with-a-friend; add a real join flow if you want public matchmaking.
- **AI opponent.** Not built yet — the cleanest place to add it is as a
  third kind of "player" inside `Room` that the server drives itself
  (submits moves on its own turn), so the WebSocket protocol above doesn't
  need to change for the Flutter app.
- **CORS is wide open** (`allow_origins=["*"]`) — fine for development,
  tighten before shipping publicly.

## Next step

The Flutter app will replace `client.py`'s Pygame rendering with a real
mobile UI, using this WebSocket protocol to talk to the server. Say the
word when you're ready and I'll scaffold that project next.
