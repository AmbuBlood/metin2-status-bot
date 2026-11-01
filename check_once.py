"""O singura verificare: citeste g-status, anunta si actualizeaza mesajele live."""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from monitor import format_board, format_line, parse_page, step

URL = "https://www.g-status.com/en-gb/game/metin2"
API = "https://discord.com/api/v10"
BASE = Path(__file__).parent
STATE_FILE = BASE / "state.json"
BOARD_FILE = BASE / "board.json"
CHANNELS_FILE = BASE / "channels.json"
GREEN = 0x2ECC71
RED = 0xE74C3C

TOKEN = os.environ["DISCORD_TOKEN"]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_servers():
    request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        servers = parse_page(response.read().decode("utf-8"))
    if not servers:
        raise ValueError("nu am gasit servere in pagina")
    return servers


def discord_call(method, path, payload=None):
    request = urllib.request.Request(
        f"{API}{path}",
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        method=method,
        headers={
            "Authorization": f"Bot {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com, 1.0)",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def embed(title, text, color=GREEN):
    return {"embeds": [{"title": title, "description": text, "color": color}]}


def update_board(channel_id, board, text):
    """Editeaza mesajul live doar cand s-a schimbat ceva, sau il recreeaza daca a fost sters."""
    payload = embed("⚔️ Status servere Metin2", text, RED if "🔴" in text else GREEN)
    message = None
    if board.get("message_id"):
        try:
            path = f"/channels/{channel_id}/messages/{board['message_id']}"
            if board.get("text") == text:
                discord_call("GET", path)
                return board
            payload["content"] = None
            message = discord_call("PATCH", path, payload)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
    if message is None:
        payload.pop("content", None)
        message = discord_call("POST", f"/channels/{channel_id}/messages", payload)
    return {"message_id": message["id"], "text": text}


def main():
    channels = json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
    # Un token gresit trebuie sa pice rularea, nu abia la urmatoarea mentenanta.
    discord_call("GET", "/users/@me")
    servers = fetch_servers()
    state, finished = step(read_json(STATE_FILE), servers, time.time())
    failures = 0

    if finished:
        lines = "\n".join(format_line(name, info) for name, info in finished)
        delivered = 0
        for channel_id in channels:
            try:
                discord_call(
                    "POST",
                    f"/channels/{channel_id}/messages",
                    embed("✅ Mentenanta s-a terminat!", lines),
                )
                delivered += 1
            except urllib.error.URLError as error:
                print(f"Anunt esuat in canalul {channel_id}: {error}")
                failures += 1
        # Salvam abia dupa trimitere, ca un anunt esuat peste tot sa fie reincercat.
        if not delivered:
            sys.exit(1)
    write_json(STATE_FILE, state)

    boards = read_json(BOARD_FILE)
    if "message_id" in boards:
        boards = {channels[0]: boards}
    text = format_board(servers, state)
    for channel_id in channels:
        try:
            boards[channel_id] = update_board(channel_id, boards.get(channel_id, {}), text)
        except urllib.error.URLError as error:
            print(f"Mesaj live esuat in canalul {channel_id}: {error}")
            failures += 1
    write_json(BOARD_FILE, boards)

    print(f"OK: {len(servers)} servere, {len(finished)} anunturi, {failures} erori")
    # Un canal cu probleme apare ca rulare esuata, dar nu le blocheaza pe celelalte.
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
