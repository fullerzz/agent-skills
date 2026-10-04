_default:
    @just --list

# build the plugin
build:
    uv run scripts/package_plugin.py

# lint python files with ruff
lint-python:
    uv run ruff check --fix .

# format python files with ruff
format-python:
    uv run ruff format .

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
