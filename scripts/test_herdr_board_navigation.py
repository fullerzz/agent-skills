"""Board navigation with temporary records and a fake Herdr server."""

from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

import test_herdr_plugin as fixtures
from test_herdr_plugin import BASE, Fixture, hr, pl, raw_snapshot, tree


class NavigationTests(Fixture):
    board = fixtures.PluginTests.board
    worker_run = fixtures.PluginTests.worker_run
    fake_snapshot = fixtures.PluginTests.fake_snapshot

    def setUp(self) -> None:
        super().setUp()
        self.calls: list[tuple[str, ...]] = []
        self.raw = copy.deepcopy(BASE)
        for fake in (
            patch.object(hr, "live_snapshot", self.fake_snapshot),
            patch.object(pl, "herdr", self.fake_herdr),
        ):
            fake.start()
            self.addCleanup(fake.stop)

    def test_select_detail_enter_focus_and_escape(self) -> None:
        self.worker_run()
        before = tree(self.root)
        board = self.board()
        board.refresh()
        self.calls.clear()
        board.key("1")
        self.assertEqual(board.selected_task, "t1")
        self.assertEqual(self.calls, [])
        board.key("\r")
        self.assertIn(("agent", "focus", "w1:p2"), self.calls)
        board.key("c")
        self.assertIn(("agent", "focus", "w1:p1"), self.calls)
        board.key("+")
        board.key("\x1b")
        self.assertIsNone(board.selected_task)
        self.assertEqual(board.offset, 0)
        self.assertEqual(tree(self.root), before)
        self.assertFalse(board.key("q"))

    def test_row_keys_change_selection_without_focus(self) -> None:
        path = self.worker_run()
        for index in range(2, 12):
            self.cli("task", "add", str(path), f"t{index}")
        board = self.board()
        board.refresh()
        board.key("a")
        self.assertEqual(board.selected_task, "t10")
        self.calls.clear()
        board.key("1")
        self.assertEqual(board.selected_task, "t1")
        board.key("b")
        self.assertEqual(board.selected_task, "t11")
        self.assertEqual(self.calls, [])

    def test_selection_survives_reorder_and_stale_read_then_removed_task_returns(self) -> None:
        path = self.worker_run()
        self.cli("task", "add", str(path), "t2")
        board = self.board()
        board.refresh()
        board.key("1")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tasks"].reverse()
        path.write_text(json.dumps(data), encoding="utf-8")
        board.key("r")
        self.assertEqual(board.selected_task, "t1")
        self.raw = None
        board.refresh()
        self.assertEqual(board.selected_task, "t1")
        self.assertIn("server_not_running", board.stale)
        self.calls.clear()
        board.key("\n")
        self.assertIn("focus refused", board.notice)
        self.assertEqual(self.calls, [])
        self.raw = copy.deepcopy(BASE)
        data["tasks"] = [task for task in data["tasks"] if task["id"] != "t1"]
        path.write_text(json.dumps(data), encoding="utf-8")
        board.offset, board.inspector_offset = 4, 7
        board.active_region = "inspector"
        board.refresh()
        self.assertEqual(board.inspector_offset, 0)
        self.assertEqual(board.active_region, "tasks")
        self.assertIsNone(board.selected_task)
        self.assertIn("t1 is no longer", board.notice)
        self.assertEqual(board.offset, 0)

    def test_enter_revalidates_identity_without_a_board_refresh(self) -> None:
        self.worker_run()
        board = self.board()
        board.refresh()
        board.key("1")
        self.raw = raw_snapshot(("w1:p2", "term_worker", "codex", "replacement-session", None))
        self.calls.clear()
        board.key("\r")
        self.assertIn("focus refused", board.notice)
        self.assertEqual(self.calls, [])

    def test_scroll_is_clamped_by_the_rendered_frame(self) -> None:
        self.worker_run()
        board = self.board()
        board.refresh()
        board.key("-")
        self.assertEqual(board.offset, 0)
        board.key("+")
        self.assertEqual(board.offset, 1)
        board.console.height = 8
        board.console.width = 80
        board.key("1")
        board.key("\t")
        board.key("+")
        self.assertEqual(board.inspector_offset, 1)
        board.inspector_offset = 10000
        board.offset = 10000
        board.draw()
        self.assertGreaterEqual(board.offset, 0)
        self.assertLess(board.offset, 10000)
        self.assertLess(board.inspector_offset, 10000)
        board.key("\x1b")
        self.assertEqual(board.active_region, "tasks")
        self.assertEqual(board.inspector_offset, 0)

    def test_every_task_is_reachable_beyond_shortcut_keys(self) -> None:
        path = self.worker_run()
        for index in range(len(pl.SELECT) + 2):
            self.cli("task", "add", str(path), f"extra{index}")
        board = self.board()
        board.refresh()
        self.calls.clear()
        visited = set()
        for _ in board.view["tasks"]:
            board.key("down")
            visited.add(board.selected_task)
        self.assertEqual(visited, {task["id"] for task in board.view["tasks"]})
        board.key("]")
        self.assertEqual(board.selected_task, "t1")
        board.key("up")
        self.assertEqual(board.selected_task, board.view["tasks"][-1]["id"])
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
