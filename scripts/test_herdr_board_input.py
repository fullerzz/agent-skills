"""Exercise board input with a controlled clock, without live Herdr state."""

import unittest
from unittest.mock import patch

import test_herdr_plugin as fixtures


class BoardInputTests(unittest.TestCase):
    def run_input(self, chunks: list[tuple[float, bytes]]) -> tuple[list[str], list[float]]:
        now = 0.0
        events = []
        for delay, data in chunks:
            now += delay
            events.append((now, data))
        events.append((now, b""))
        now = 0.0
        keys = []
        stamps = []

        class Board:
            def refresh(self) -> None:
                pass

            def draw(self) -> None:
                pass

            def key(self, char: str) -> bool:
                keys.append(char)
                stamps.append(now)
                return char not in ("q", "\x04")

        def select_input(
            readers: list[int], writers: list[int], errors: list[int], timeout: float
        ) -> tuple[list[int], list[int], list[int]]:
            nonlocal now
            if events[0][0] <= now + timeout:
                now = max(now, events[0][0])
                return readers, [], []
            now += timeout
            return [], [], []

        with (
            patch.object(fixtures.pl.time, "monotonic", side_effect=lambda: now),
            patch.object(fixtures.pl.select, "select", side_effect=select_input),
            patch.object(fixtures.pl.os, "read", side_effect=lambda *_: events.pop(0)[1]),
        ):
            self.assertEqual(fixtures.pl.run_board(Board(), 123, interval=60), 0)
        return keys, stamps

    def test_complete_sequences_and_normal_keys(self) -> None:
        keys, _ = self.run_input([(0, b"1\x1b[A\x1b[B\x1b[C\x1b[D\x1b[3~\x1b[6~\x1bOA+r\rq")])
        self.assertEqual(keys, ["1", "up", "down", "up", "+", "r", "\r", "q"])

    def test_split_sequences(self) -> None:
        keys, _ = self.run_input(
            [(0, b"1\x1b"), (0.01, b"["), (0.07, b"3"), (0.01, b"~\x1bO"), (0.01, b"A\x1b[6"), (0.01, b"~q")]
        )
        self.assertEqual(keys, ["1", "up", "q"])

    def test_standalone_escape_is_prompt(self) -> None:
        keys, stamps = self.run_input([(0, b"1\x1b"), (0.2, b"q")])
        self.assertEqual(keys, ["1", "\x1b", "q"])
        self.assertAlmostEqual(stamps[1], 0.05)

    def test_escape_before_normal_key_and_eof(self) -> None:
        keys, _ = self.run_input([(0, b"\x1b2")])
        self.assertEqual(keys, ["\x1b", "2"])
        keys, _ = self.run_input([(0, b"\x04")])
        self.assertEqual(keys, ["\x04"])

    def test_incomplete_prefixes_expire_before_later_keys(self) -> None:
        for prefix in (b"\x1b[", b"\x1b[3", b"\x1bO"):
            for key in (b"2", b"+", b"-", b"q"):
                with self.subTest(prefix=prefix, key=key):
                    keys, _ = self.run_input([(0, prefix), (0.11, key), (0, b"q")])
                    expected = [key.decode()]
                    if key != b"q":
                        expected.append("q")
                    self.assertEqual(keys, expected)

    def test_prefix_deadline_renews_for_each_byte(self) -> None:
        keys, _ = self.run_input([(0, b"\x1b["), (0.07, b"1"), (0.07, b";"), (0.07, b"2"), (0.07, b"Aq")])
        self.assertEqual(keys, ["q"])
