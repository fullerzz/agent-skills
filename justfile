_default:
    @just --list

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
