"""Citeste pagina g-status si decide cand s-a terminat mentenanta (fara Discord)."""
import re
from datetime import datetime

# Cat asteptam dupa ce Login revine ca Channel 2 sa primeasca ora noua.
CH2_WAIT_SECONDS = 15 * 60

NAME_RE = re.compile(r'class="server_name">(.*?)</div>', re.S)
STATUS_RE = re.compile(r'class="status \w+">\s*(.*?)\s*<', re.S)
DATE_RE = re.compile(r'class="last_offline_date">\s*(.*?)\s*<', re.S)


def parse_page(html):
    """Intoarce {server: {"login": status, "ch2": status, "ch2_date": data}}."""
    servers = {}
    for row in html.split("<!-- Server Wrapper Start -->")[1:]:
        name = NAME_RE.search(row)
        status = STATUS_RE.search(row)
        if not name or not status:
            continue
        server, _, kind = name.group(1).strip().rpartition(" - ")
        date = DATE_RE.search(row)
        status = status.group(1).upper()
        if kind == "Login":
            servers.setdefault(server, {})["login"] = status
        elif kind == "Channel 2":
            info = servers.setdefault(server, {})
            info["ch2"] = status
            info["ch2_date"] = date.group(1) if date else None
    # Fara rand de Login nu stim statusul serverului.
    return {name: info for name, info in servers.items() if "login" in info}


def format_line(server, info):
    """🟢 **Server** · Spawn Ch1: `minut±1` · par/impar"""
    if info["login"] != "ONLINE":
        return f"🔴 **{server}** · {info['login']}"
    line = f"🟢 **{server}** · Spawn Ch1: "
    try:
        date = datetime.strptime(info.get("ch2_date") or "", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return line + "necunoscut"
    # Regula ceruta: ora divizibila cu 2 inseamna impar, altfel par.
    parity = "impar" if date.hour % 2 == 0 else "par"
    return f"{line}`{date.minute:02d}±1` · {parity}"


def format_board(servers, state):
    """Mesajul live: spawn-ul pentru serverele online, doar statusul pentru restul."""
    lines = []
    for name, info in servers.items():
        if name in state or info.get("ch2") != "ONLINE":
            # Ora de la Channel 2 nu e inca valabila.
            lines.append(format_line(name, {**info, "ch2_date": None}))
        else:
            lines.append(format_line(name, info))
    return "\n".join(lines)


def step(state, servers, now):
    """Compara pagina cu starea salvata. Intoarce (stare noua, servere terminate)."""
    state = {name: dict(entry) for name, entry in state.items()}
    finished = []
    for name, info in servers.items():
        entry = state.get(name)
        if info["login"] != "ONLINE":
            if entry is None:
                state[name] = {"ch2_before": info.get("ch2_date"), "login_back_at": None}
            else:
                entry["login_back_at"] = None
        elif entry is not None:
            if entry["login_back_at"] is None:
                entry["login_back_at"] = now
            ch2_ready = (
                info.get("ch2") == "ONLINE"
                and info.get("ch2_date") != entry["ch2_before"]
            )
            if ch2_ready or now - entry["login_back_at"] >= CH2_WAIT_SECONDS:
                # Ora veche nu mai e valabila dupa mentenanta.
                if not ch2_ready:
                    info = {**info, "ch2_date": None}
                finished.append((name, info))
                del state[name]
    return state, finished
