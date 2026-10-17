# Python patterns

Examples target Python 3.11+ and Pydantic 2. Match the target project's supported versions; do not upgrade it merely to copy an example.

## uv workflows

Choose the script or package workflow for the task; these are alternatives, not a mandatory setup sequence.

Standalone script with inline dependency metadata:

```sh
uv python install 3.11
uv init --script ingest.py --python 3.11
uv add --script ingest.py 'pydantic>=2,<3'
uv run ingest.py
uv run --with ruff ruff format ingest.py
uv run --with ruff ruff check ingest.py
uv run --with mypy --with 'pydantic>=2,<3' mypy --strict ingest.py
```

The mypy environment must contain the script's dependencies; a standalone mypy tool environment does not automatically read inline script dependencies.

Installable project:

```sh
uv init --package example-app
cd example-app
uv add 'pydantic>=2,<3'
uv add --dev ruff mypy pytest
uv run example-app
uv run ruff format .
uv run ruff check .
uv run mypy src tests
uv run pytest
uv build
```

Use the package's configured entry point (here `example-app`). Use the existing test runner in established projects rather than adding pytest by default.

Use `uv venv .venv` when an explicit environment is needed outside project management. Use `uv tool install ruff` for a persistent standalone CLI; prefer project dev dependencies for reproducible checks. Install uv itself with `mise` or `brew` where available. Do not substitute bare `pip`, `python`, or `venv` commands when uv supports the operation.

Project CI checks (adapt paths to the repository; include scripts and tests):

```sh
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

## Minimal checking configuration

Merge into an existing `pyproject.toml`; do not replace project settings. These are new-project defaults, not permission to weaken existing rules.

```toml
[tool.ruff.lint]
extend-select = ["I"]

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

Ruff's formatter and linter are separate commands. Review lint fixes before accepting them; do not apply unsafe fixes automatically. Run mypy in the environment containing the project's dependencies and required type stubs.

## Validate once, use typed values inside

This boundary accepts a positive integer count, rejects string-to-integer coercion, and rejects unknown fields. Those choices are appropriate for this example's contract; environment variables often need deliberate string conversion, and forward-compatible wire protocols may allow extra fields.

```python
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


class Order(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    sku: Annotated[str, Field(min_length=1)]
    quantity: Annotated[int, Field(gt=0)]


orders_adapter = TypeAdapter(list[Order])


def parse_orders(payload: object) -> list[Order]:
    return orders_adapter.validate_python(payload)


def total_quantity(orders: list[Order]) -> int:
    return sum(order.quantity for order in orders)


def test_order_boundary() -> None:
    assert total_quantity(parse_orders([{"sku": "book", "quantity": 2}])) == 2
    assert total_quantity(parse_orders([])) == 0
    for invalid in (
        [{"sku": "book", "quantity": "2"}],
        [{"sku": "book", "quantity": 0}],
        [{"sku": "book", "quantity": 2, "unexpected": True}],
    ):
        try:
            parse_orders(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError("invalid order accepted")
```

For JSON bytes/text, use `Order.model_validate_json` or the adapter's `validate_json`; for decoded values, use `model_validate` or `validate_python`. Catch validation failures at the application boundary and translate them into a useful error. Avoid logging raw payloads or full validation errors containing secrets. Frozen models prevent field reassignment, not mutation of nested mutable containers.

## Typed internal variants and semantic identifiers

Use standard dataclasses when no external validation is needed. `NewType` distinguishes identifiers for mypy but performs no runtime check; create IDs only from already validated values.

```python
from dataclasses import dataclass
from typing import NewType, assert_never

JobId = NewType("JobId", str)


@dataclass(frozen=True)
class Pending:
    job_id: JobId


@dataclass(frozen=True)
class Complete:
    job_id: JobId
    result: str


def describe(job: Pending | Complete) -> str:
    if isinstance(job, Pending):
        return f"{job.job_id}: pending"
    if isinstance(job, Complete):
        return job.result
    assert_never(job)
```

Adding a new variant to the union makes the final branch a mypy error until it is handled. Use Pydantic discriminated unions when those variants arrive as external data. Prefer keyword-only arguments when several parameters of the same type could be swapped accidentally.

## Tool references

- [uv commands](https://docs.astral.sh/uv/reference/cli/) and [script metadata](https://docs.astral.sh/uv/guides/scripts/)
- [Ruff formatter](https://docs.astral.sh/ruff/formatter/) and [linter](https://docs.astral.sh/ruff/linter/)
- [Pydantic strict validation](https://docs.pydantic.dev/latest/concepts/strict_mode/) and [mypy integration](https://docs.pydantic.dev/latest/integrations/mypy/)
