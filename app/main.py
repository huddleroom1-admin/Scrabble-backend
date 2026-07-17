"""FastAPI backend for stock-Scrabble.

Replaces the original raw-TCP-socket server with WebSockets, and replaces the
single global game with many concurrent "rooms" (games), each identified by
a short room code -- this is what lets many pairs of players use the same
deployed server at once, which you need for real internet multiplayer.

Run locally:
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

Client flow (two humans):
    1. POST /rooms          -> {"code": "AB3F9K"}   (or just pick your own
                                code and share it -- any string works)
    2. Connect a WebSocket to /ws/{code}
    3. First message received is {"type": "WELCOME", "player": 1 or 2}
    4. From then on, send/receive JSON messages per game.py's docstring.

Client flow (single player vs AI):
    1. POST /rooms?vs_ai=true -> {"code": "AB3F9K", "vs_ai": true}
    2. Connect a WebSocket to /ws/{code} -- you'll always be player 1.
       The game starts immediately (no waiting for a second connection);
       the AI plays player 2 automatically on its turns.
"""

import asyncio
import random
import string

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import dictionary
from .game import MAX_PLAYERS, Room, handle_pass, handle_submit, handle_swap, turn_timer

app = FastAPI(title="Stock Scrabble Backend")

# Wide open for now -- tighten this to your app's origin(s) before shipping.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms: dict[str, Room] = {}


@app.on_event("startup")
async def _load_dictionary():
    dictionary.load()


@app.get("/health")
async def health():
    return {"status": "ok", "rooms_active": len(rooms)}


@app.post("/rooms")
async def create_room(vs_ai: bool = False):
    """Generate a fresh, unused room code. Pass ?vs_ai=true to create a
    single-player room where the second slot is played by the AI --
    the game starts as soon as one human connects, no waiting required.
    """
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in rooms:
            break
    room = Room(code)
    if vs_ai:
        room.ai_player = 2
        room.deal_rack(2)
    rooms[code] = room
    return {"code": code, "vs_ai": vs_ai}


@app.websocket("/ws/{code}")
async def game_socket(websocket: WebSocket, code: str):
    code = code.upper()
    room = rooms.setdefault(code, Room(code))

    async with room.lock:
        if room.connected_count() >= MAX_PLAYERS:
            await websocket.accept()
            await websocket.send_json({"type": "ERROR", "msg": "Game is full."})
            await websocket.close()
            return
        player = 1 if 1 not in room.clients else 2
        await websocket.accept()
        room.clients[player] = websocket
        room.deal_rack(player)
        await websocket.send_json({"type": "WELCOME", "player": player})
        if room.connected_count() == MAX_PLAYERS:
            room.start_turn_clock()
            if room.timer_task is None:
                room.timer_task = asyncio.create_task(turn_timer(room))
        await room.broadcast()

    try:
        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")

            if mtype == "SUBMIT":
                err, summary = await handle_submit(room, player, msg.get("moves"))
                if err:
                    await websocket.send_json({"type": "ERROR", "msg": err})
                else:
                    await websocket.send_json(
                        {"type": "INFO", "msg": f"Played {summary}"}
                    )
            elif mtype == "SWAP":
                err, summary = await handle_swap(room, player, msg.get("indices"))
                if err:
                    await websocket.send_json({"type": "ERROR", "msg": err})
                else:
                    await websocket.send_json({"type": "INFO", "msg": summary})
            elif mtype == "PASS":
                await handle_pass(room, player)
            elif mtype == "PAUSE":
                async with room.lock:
                    await room.pause(player)
            elif mtype == "RESUME":
                async with room.lock:
                    await room.resume()
            elif mtype == "SURRENDER":
                async with room.lock:
                    await room.surrender(player)
            elif mtype == "NEWGAME":
                async with room.lock:
                    await room.reset()
    except WebSocketDisconnect:
        pass
    finally:
        async with room.lock:
            room.clients.pop(player, None)
            await room.broadcast()
        # Room (and its bag/board/history) is kept alive so a disconnected
        # player can rejoin the same code. Add cleanup/expiry here later if
        # you want abandoned rooms to be garbage-collected.
