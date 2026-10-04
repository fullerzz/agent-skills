"""Native Hermes plugin: expose the shared skills without activating a workflow."""

# ruff: noqa: N999 -- Hermes loads this directory entrypoint under its own module name.

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from hooks.hermes import HookRegistry, register_hooks
else:
    from .hooks.hermes import HookRegistry, register_hooks


class SkillRegistry(HookRegistry, Protocol):
    """The documented Hermes context surface this plugin needs."""

    def register_skill(self, name: str, path: Path) -> object: ...


def register(ctx: SkillRegistry) -> None:
    """Hermes owns namespacing, opt-in loading, and registration cleanup."""
    skills_dir = Path(__file__).resolve().parent / "skills"
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.is_file():
            ctx.register_skill(child.name, skill_md)
    register_hooks(ctx)
