import unittest

from monitor import CH2_WAIT_SECONDS, format_board, format_line, parse_page, step


def row(name, status, date):
    return (
        f'<!-- Server Wrapper Start --><div class="server_name">{name}</div>'
        f'<div class="last_offline_date">{date}</div>'
        f'<div class="status {status.lower()}">{status}</div>'
    )


OLD = "2026-10-29 06:11:18"
NEW = "2026-11-05 07:00:30"


def info(login, ch2, date):
    return {"X": {"login": login, "ch2": ch2, "ch2_date": date}}


class FormatTest(unittest.TestCase):
    def line(self, date):
        return format_line("X", {"login": "ONLINE", "ch2_date": date})

    def test_even_hour_is_impar(self):
        self.assertEqual(self.line(OLD), "🟢 **X** · Spawn Ch1: `11±1` · impar")

    def test_odd_hour_is_par(self):
        self.assertEqual(self.line(NEW), "🟢 **X** · Spawn Ch1: `00±1` · par")

    def test_missing_date(self):
        self.assertEqual(self.line(None), "🟢 **X** · Spawn Ch1: necunoscut")


class BoardTest(unittest.TestCase):
    def test_online_shows_spawn_offline_hides_it(self):
        servers = {
            "A": {"login": "ONLINE", "ch2": "ONLINE", "ch2_date": OLD},
            "B": {"login": "OFFLINE", "ch2": "OFFLINE", "ch2_date": OLD},
            "C": {"login": "ONLINE", "ch2": "ONLINE", "ch2_date": OLD},
        }
        lines = format_board(servers, {"C": {}}).splitlines()
        self.assertEqual(lines[0], "🟢 **A** · Spawn Ch1: `11±1` · impar")
        self.assertEqual(lines[1], "🔴 **B** · OFFLINE")
        self.assertEqual(lines[2], "🟢 **C** · Spawn Ch1: necunoscut")


class PossibleSpawnTest(unittest.TestCase):
    def line(self, ch2, date):
        servers = {"X": {"login": "OFFLINE", "ch2": ch2, "ch2_date": date}}
        return format_board(servers, {"X": {"ch2_before": OLD}})

    def test_channels_back_before_login(self):
        self.assertEqual(self.line("ONLINE", NEW), "🔴 **X** · OFFLINE · Spawn posibil: `00±1` · par")

    def test_old_date_is_hidden(self):
        self.assertEqual(self.line("ONLINE", OLD), "🔴 **X** · OFFLINE")

    def test_channel_still_down(self):
        self.assertEqual(self.line("OFFLINE", NEW), "🔴 **X** · OFFLINE")


class ParseTest(unittest.TestCase):
    def test_login_and_channel_2(self):
        html = row("[RUBY] A - Login", "OFFLINE", OLD) + row("[RUBY] A - Channel 1", "ONLINE", NEW)
        html += row("[RUBY] A - Channel 2", "ONLINE", OLD)
        self.assertEqual(
            parse_page(html),
            {"[RUBY] A": {"login": "OFFLINE", "ch2": "ONLINE", "ch2_date": OLD}},
        )


class StepTest(unittest.TestCase):
    def test_no_announcement_without_maintenance(self):
        self.assertEqual(step({}, info("ONLINE", "ONLINE", OLD), 0), ({}, []))

    def test_waits_for_new_channel_2_date(self):
        state, done = step({}, info("OFFLINE", "OFFLINE", OLD), 0)
        self.assertEqual(done, [])
        state, done = step(state, info("ONLINE", "OFFLINE", OLD), 60)
        self.assertEqual(done, [])
        state, done = step(state, info("ONLINE", "ONLINE", NEW), 120)
        self.assertEqual(state, {})
        self.assertEqual(done[0][1]["ch2_date"], NEW)

    def test_timeout_drops_stale_date(self):
        state, _ = step({}, info("OFFLINE", "OFFLINE", OLD), 0)
        state, _ = step(state, info("ONLINE", "ONLINE", OLD), 60)
        state, done = step(state, info("ONLINE", "ONLINE", OLD), 60 + CH2_WAIT_SECONDS)
        self.assertEqual(state, {})
        self.assertIsNone(done[0][1]["ch2_date"])


if __name__ == "__main__":
    unittest.main()
