"""Native Hermes lifecycle adapter; model and tool payloads never become stored state."""

import logging
import os
import threading
from collections.abc import Callable
from functools import partial
from typing import Protocol

from . import session_start, xray

LOGGER = logging.getLogger(__name__)
OBSERVER_HOOKS = (
    "on_session_start",
    "on_session_end",
    "on_session_finalize",
    "post_llm_call",
    "pre_tool_call",
    "post_tool_call",
    "subagent_start",
    "subagent_stop",
    "pre_auxiliary_call",
    "post_auxiliary_call",
)


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
            xray.record_internal(
                "hermes",
                session_id,
                directory,
                "session_start",
                "clear_state_failed" if warning else "context_emitted",
                source=source,
            )
            self.observe("pre_llm_call", session_id=session_id, **kwargs)
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
        self.observe("on_session_reset", session_id=session_id, **kwargs)

    def observe(self, hook: str, **kwargs: object) -> None:
        # In particular pre_tool_call must never raise or return a policy directive:
        # Hermes treats failing policy callbacks as a reason to block execution.
        if os.environ.get("ZSTACK_XRAY") != "1":
            return
        if hook in {"pre_auxiliary_call", "post_auxiliary_call"} and kwargs.get("aux_task") != "compression":
            return
        try:
            xray.record_hermes(hook, kwargs, self.directory())
        except Exception:  # noqa: BLE001 - Optional observer cannot affect tool dispatch.
            LOGGER.warning("zstack: Hermes xray metadata capture unavailable")


def register_hooks(ctx: HookRegistry) -> None:
    hooks = HermesHooks()
    ctx.register_hook("pre_llm_call", hooks.pre_llm_call)
    ctx.register_hook("on_session_reset", hooks.on_session_reset)
    for name in OBSERVER_HOOKS:
        ctx.register_hook(name, partial(hooks.observe, name))
