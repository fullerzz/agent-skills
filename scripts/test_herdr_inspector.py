"""Rendered pane contracts; synthetic data and no live Herdr operations."""

import io
import unittest
from typing import Any

from test_herdr_plugin import pl


def task(index: int = 0) -> dict[str, Any]:
    return {
        "id": f"task-{index}",
        "title": f"Work item {index}",
        "lifecycle": {"observed": "working"},
        "acceptance": "not recorded",
        "binding": None,
        "binding_check": {"status": "unbound"},
        "reports": [],
        "evidence": [],
        "data_gaps": [],
    }


def view(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"run_id": "inspector-test", "coordinator": {}, "tasks": tasks, "sources": {}, "data_gaps": []}


def render(data: dict[str, Any], width: int = 120, height: int = 32, **kwargs: Any) -> tuple[str, Any]:  # noqa: ANN401 - Rich frame.
    out = io.StringIO()
    console = pl.Console(file=out, width=width, height=height, color_system=None)
    frame = pl.board_frame(data, {}, width=width, **kwargs)
    console.print(frame)
    return out.getvalue(), frame


@unittest.skipUnless(pl.HAVE_RICH, "Rich is required")
class InspectorRendering(unittest.TestCase):
    def test_regions_visible_and_bounded(self) -> None:
        for width, height in ((80, 24), (120, 32), (8, 2), (1, 1)):
            result, _ = render(view([task()]), width, height, selected_task="task-0")
            self.assertLessEqual(len(result.splitlines()), height)
            self.assertTrue(all(pl.Text(line).cell_len <= width for line in result.splitlines()))
            if width >= 80:
                self.assertIn("Tasks", result)
                self.assertIn("Inspector", result)
                self.assertIn("Lifecycle", result)
                self.assertIn("Task ID", result)

    def test_no_implicit_selection(self) -> None:
        result, _ = render(view([task()]))
        self.assertIn("Select a task", result)
        self.assertNotIn("Task ID", result)

    def test_inspector_scroll_preserves_table_and_reaches_final_evidence(self) -> None:
        selected = task()
        selected["evidence"] = [{"ref": f"evidence-{i}", "revision": "a" * 40} for i in range(40)]
        initial, _ = render(view([selected]), selected_task=selected["id"])
        final, frame = render(view([selected]), selected_task=selected["id"], inspector_offset=100000)
        self.assertIn("evidence-39", final)
        self.assertEqual(
            [line.split("│")[0] for line in initial.splitlines()], [line.split("│")[0] for line in final.splitlines()]
        )
        self.assertGreater(frame.inspector_offset, 0)
        self.assertLess(frame.inspector_offset, 100000)

    def test_long_id_retained_across_inspector_scroll(self) -> None:
        selected = task()
        selected["id"] = "long-task-" + "0123456789" * 14
        data = view([selected])
        result, _ = render(data, height=100, selected_task=selected["id"])
        compact = "".join(line.split("│")[-1].strip() for line in result.splitlines())
        self.assertIn(selected["id"], compact)

    def test_reveal_selected_row_and_complete_diagnostics(self) -> None:
        tasks = [task(i) for i in range(60)]
        data = view(tasks)
        data["data_gaps"] = ["gap-" + str(i) for i in range(50)]
        result, frame = render(data, selected_task="task-59", reveal_selection=True)
        self.assertIn("task-59", result)
        self.assertGreater(frame.offset, 0)
        result, frame = render(data, offset=100000)
        self.assertIn("gap-49", result)
        self.assertLess(frame.offset, 100000)


if __name__ == "__main__":
    unittest.main()
