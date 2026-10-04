_default:
    @just --list

# build the plugin
build:
    uv run scripts/package_plugin.py

# bump the shared plugin version: minor or patch
bump part:
    uv run scripts/bump_version.py {{part}}

# lint python files with ruff
lint-python:
    uv run ruff check --fix .

# format python files with ruff
format-python:
    uv run ruff format .

# type-check all project Python scripts
mypy:
    uv run --with mypy --with rich --with pyyaml --with types-pyyaml mypy

# lint and format python files
check:
    @just format-python
    @just lint-python

# refresh local codex plugin installation
refresh-codex-plugin:
    git pull --ff-only
    @just build
    codex plugin remove zstack@zstack-local
    codex plugin add zstack@zstack-local
