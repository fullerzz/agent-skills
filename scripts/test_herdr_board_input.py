"""Exercise board input through real pipes, without live Herdr state."""

import os
import threading
import time
import unittest

import test_herdr_plugin as fixtures


class BoardInputTests(unittest.TestCase):
    def run_input(self, chunks: list[tuple[float, bytes]]) -> tuple[list[str], list[float]]:
        read, write = os.pipe()
        keys = []
        stamps = []

        class Board:
            def refresh(self) -> None:
                pass

            def draw(self) -> None:
                pass

            def key(self, char: str) -> bool:
                keys.append(char)
                stamps.append(time.monotonic())
                return char not in ("q", "\x04")

        def feed() -> None:
            try:
                for delay, data in chunks:
                    time.sleep(delay)
                    os.write(write, data)
            finally:
                os.close(write)

        thread = threading.Thread(target=feed)
        start = time.monotonic()
        thread.start()
        try:
            self.assertEqual(fixtures.pl.run_board(Board(), read, interval=60), 0)
        finally:
            thread.join()
            os.close(read)
        return keys, [stamp - start for stamp in stamps]

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
        self.assertGreaterEqual(stamps[1], 0.04)
        self.assertLess(stamps[1], 0.15)

    def test_escape_before_normal_key_and_eof(self) -> None:
        keys, _ = self.run_input([(0, b"\x1b2")])
        self.assertEqual(keys, ["\x1b", "2"])
        keys, _ = self.run_input([(0, b"\x04")])
        self.assertEqual(keys, ["\x04"])
