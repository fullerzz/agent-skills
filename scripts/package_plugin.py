# /// script
# requires-python = ">=3.11"
# ///
"""Stage tracked plugin resources, using their current working-tree contents."""

import os
import shutil
import subprocess
from pathlib import Path

RESOURCES = (".codex-plugin", "LICENSE", "skills", "hooks")
IGNORED = {
    ".git",
    "node_modules",
    "__pycache__",
    ".cache",
    ".venv",
    ".agent-work",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
}


def excluded(path: Path) -> bool:
    return any(part in IGNORED for part in path.parts) or path.name.endswith((".pyc", ".pyo", ".log"))


def git_output(root: Path, *arguments: str) -> bytes:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("Git is required to package tracked plugin resources")
    result = subprocess.run(  # noqa: S603 - Fixed Git inventory command; no shell.
        [executable, "-C", str(root), *arguments],
        capture_output=True,
        check=True,
    )
    return result.stdout


def tracked_resources(root: Path) -> set[Path]:
    if Path(os.fsdecode(git_output(root, "rev-parse", "--show-toplevel")).strip()).resolve() != root:
        raise ValueError("Packaging requires the Git repository root")
    inventory = git_output(root, "ls-files", "-z", "--", *RESOURCES)
    ignored = git_output(root, "ls-files", "-z", "--cached", "--ignored", "--exclude-standard", "--", *RESOURCES)
    files = {Path(os.fsdecode(name)) for name in set(inventory.split(b"\0")) - set(ignored.split(b"\0")) if name}
    files = {path for path in files if not excluded(path)}
    if not files:
        raise ValueError("No tracked plugin resources; run from the Git checkout")
    return files


def validate_link(root: Path, path: Path, included: set[Path]) -> None:
    link = (root / path).readlink()
    if link.is_absolute() or excluded(link):
        raise ValueError(f"Plugin symlink escapes packaged resources: {path}")
    current = path.parent
    for index, part in enumerate(link.parts):
        current = current.parent if part == ".." else current / part
        if current not in included or (index < len(link.parts) - 1 and (root / current).is_symlink()):
            raise ValueError(f"Plugin symlink traverses an omitted or indirect resource: {path}")
    resolved = (root / path).resolve().relative_to(root)
    if resolved not in included:
        raise ValueError(f"Plugin symlink escapes packaged resources: {path}")


def validate_resources(root: Path, files: set[Path]) -> None:
    for name in RESOURCES:
        source = root / name
        correct_type = source.is_file() if name == "LICENSE" else source.is_dir()
        tracked = any(path.is_relative_to(name) for path in files)
        if source.is_symlink() or not correct_type or not tracked:
            raise ValueError(f"Missing or wrong-type plugin resource: {name}")
    included = files | {parent for path in files for parent in path.parents}
    for path in sorted(files):
        source = root / path
        if any((root / parent).is_symlink() for parent in path.parents):
            raise ValueError(f"Plugin resource has a symlinked parent: {path}")
        if source.is_symlink():
            validate_link(root, path, included)
        elif not source.is_file():
            raise ValueError(f"Tracked plugin resource is missing or not a file: {path}")


def package(root: Path) -> Path:
    root = root.resolve()
    destination = root / "dist" / "zstack"
    if (root / "dist").is_symlink() or destination.is_symlink():
        raise ValueError("Refusing to replace a symlinked dist/zstack directory")
    files = tracked_resources(root)
    validate_resources(root, files)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for path in sorted(files):
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / path, target, follow_symlinks=False)
    return destination


if __name__ == "__main__":
    print(package(Path(__file__).resolve().parent.parent))
