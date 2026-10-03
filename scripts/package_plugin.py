# /// script
# requires-python = ">=3.11"
# ///
"""Stage only bundled plugin resources for the local Codex marketplace."""

import os
import shutil
from pathlib import Path


RESOURCES = (".codex-plugin", "LICENSE", "skills", "hooks")
IGNORED = {
    ".git", "node_modules", "__pycache__", ".cache", ".venv", ".agent-work",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store",
}


def ignored(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED or name.endswith((".pyc", ".pyo", ".log"))}


def package(root: Path) -> Path:
    root = root.resolve()
    destination = root / "dist" / "zstack"
    if (root / "dist").is_symlink() or destination.is_symlink():
        raise ValueError("Refusing to replace a symlinked dist/zstack directory")
    for name in RESOURCES:
        source = root / name
        if not source.exists() or source.is_symlink():
            raise ValueError(f"Missing or symlinked plugin resource: {name}")
        if not source.is_dir():
            continue
        for directory, directories, files in os.walk(source):
            directories[:] = [entry for entry in directories if entry not in ignored(directory, directories)]
            for entry in directories + files:
                path = Path(directory) / entry
                if entry in ignored(directory, [entry]) or not path.is_symlink():
                    continue
                target = path.resolve()
                if (
                    Path(os.readlink(path)).is_absolute()
                    or not target.exists()
                    or not any(target.is_relative_to(root / resource) for resource in RESOURCES)
                    or any(part in IGNORED for part in target.relative_to(root).parts)
                    or bool(ignored(str(target.parent), [target.name]))
                ):
                    raise ValueError(f"Plugin symlink escapes packaged resources: {path.relative_to(root)}")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name in RESOURCES:
        source = root / name
        if source.is_dir():
            shutil.copytree(source, destination / name, symlinks=True, ignore=ignored)
        else:
            shutil.copy2(source, destination / name)
    return destination


if __name__ == "__main__":
    print(package(Path(__file__).resolve().parent.parent))
