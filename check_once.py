"""O singura verificare: citeste g-status, anunta si actualizeaza mesajul live."""
import json
import os
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
GREEN = 0x2ECC71
RED = 0xE74C3C

TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]


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


def update_board(text):
    """Editeaza mesajul live doar cand s-a schimbat ceva, sau il recreeaza daca a fost sters."""
    board = read_json(BOARD_FILE)
    payload = embed("⚔️ Status servere Metin2", text, RED if "🔴" in text else GREEN)
    message = None
    if board.get("message_id"):
        try:
            path = f"/channels/{CHANNEL_ID}/messages/{board['message_id']}"
            if board.get("text") == text:
                discord_call("GET", path)
                return
            payload["content"] = None
            message = discord_call("PATCH", path, payload)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
    if message is None:
        payload.pop("content", None)
        message = discord_call("POST", f"/channels/{CHANNEL_ID}/messages", payload)
    write_json(BOARD_FILE, {"message_id": message["id"], "text": text})


def main():
    # Un token gresit trebuie sa pice rularea, nu abia la urmatoarea mentenanta.
    discord_call("GET", f"/channels/{CHANNEL_ID}")
    servers = fetch_servers()
    state, finished = step(read_json(STATE_FILE), servers, time.time())
    if finished:
        lines = "\n".join(format_line(name, info) for name, info in finished)
        discord_call(
            "POST",
            f"/channels/{CHANNEL_ID}/messages",
            embed("✅ Mentenanta s-a terminat!", lines),
        )
    # Salvam abia dupa trimitere, ca un mesaj esuat sa fie reincercat.
    write_json(STATE_FILE, state)
    update_board(format_board(servers, state))
    print(f"OK: {len(servers)} servere, {len(finished)} anunturi")


if __name__ == "__main__":
    main()
