"""Native Hermes lifecycle adapter; model and tool payloads never become stored state."""

import logging
import threading
from collections.abc import Callable
from typing import Protocol

from . import session_start

LOGGER = logging.getLogger(__name__)


class HookRegistry(Protocol):
    def register_hook(self, name: str, callback: Callable[..., object]) -> object: ...


def data_directory() -> str:
    # This documented API follows the active Hermes profile on every call.
    from plugins.plugin_storage import plugin_data_dir  # type: ignore[import-not-found]

    return str(plugin_data_dir("zstack"))


class HermesHooks:
    def __init__(self, directory: Callable[[], str] = data_directory) -> None:
        self.directory = directory
        self._pending_resets: set[tuple[str, str]] = set()
        self._lock = threading.RLock()

    def pre_llm_call(self, session_id: object = None, **kwargs: object) -> dict[str, str]:
        """Refresh controls on each turn, including resumed and compacted conversations."""
        try:
            if not isinstance(session_id, str):
                raise ValueError("Missing native session identity")
            directory = self.directory()
            session_start.state_path(directory, session_id)
            key = (directory, session_id)
            with self._lock:
                source = "startup" if kwargs.get("is_first_turn") is True else "resume"
                if key in self._pending_resets:
                    source = "clear"
                context, warning = session_start.build_context("hermes", session_id, directory, source)
                if warning is None:
                    self._pending_resets.discard(key)
            return {"context": context}
        except Exception:  # noqa: BLE001 - Context failure must not prevent the user's turn.
            LOGGER.warning("zstack: Hermes session controls unavailable")
            return {
                "context": (
                    "zstack could not establish this Hermes session's controls. Do not run inherited "
                    "controls or infer stored activation. Follow the user's explicit mode selection "
                    "or opt-out conversationally and preserve it in resume notes."
                )
            }

    def on_session_reset(self, session_id: object = None, **kwargs: object) -> None:
        """Hermes supplies the replacement ID; never erase the outgoing chat's state."""
        try:
            if not isinstance(session_id, str):
                raise ValueError("Missing native session identity")
            directory = self.directory()
            path = session_start.state_path(directory, session_id)
            key = (directory, session_id)
            with self._lock:
                self._pending_resets.add(key)
                session_start.set_active(path, False)
                self._pending_resets.discard(key)
        except Exception:  # noqa: BLE001 - Keep a failed clear inactive and retry at the next turn.
            LOGGER.warning("zstack: Hermes reset state could not be cleared")


def register_hooks(ctx: HookRegistry) -> None:
    hooks = HermesHooks()
    ctx.register_hook("pre_llm_call", hooks.pre_llm_call)
    ctx.register_hook("on_session_reset", hooks.on_session_reset)
