---
name: python-best-practices
description: Python best practices for writing or reviewing Python source, scripts, and packages with uv, Ruff, mypy, type hints, and Pydantic boundary validation.
disable-model-invocation: true
---

# Python best practices

Apply [type system discipline](../principle-type-system-discipline/SKILL.md) and [boundary discipline](../principle-boundary-discipline/SKILL.md) when they change a decision. Python annotations are checked by mypy; they do not enforce runtime invariants.

| Rule | Guidance |
| --- | --- |
| uv for Python operations | Use `uv` whenever it supports the operation: initialization, Python installation, dependencies, environments, execution, tests, tools, and builds. Use `uv python install`, not `uv install python`. If uv cannot support a required operation, explain the limitation before using a fallback. |
| Scripts and packages | Start standalone scripts with `uv init --script`; declare dependencies with `uv add --script`. Start installable projects with `uv init --package`; use `uv add` and `uv add --dev`. Respect the supported Python version and existing layout. |
| Environments and execution | Use `uv venv` for explicit environments and `uv run` for Python, scripts, tests, and checks. Project runs normally manage their own environment. Use `uv tool install` for persistent standalone Python CLIs, not project dependencies. |
| Reproducibility | Keep dependency metadata and lockfiles consistent through uv. Use `uv sync --locked` in project CI. Do not silently migrate an existing project's packaging or upgrade unrelated dependencies. |
| Ruff formatter and linter | Format all Python source, including scripts and tests, with `uv run ruff format`; lint with `uv run ruff check`. In verification/CI, use `ruff format --check`. Both checks are required; formatting does not replace linting. Keep edits scoped rather than reformatting unrelated files. |
| mypy | Type-check Python source with `uv run mypy` using the repository's configuration and targets. Start new projects with strict checking. For existing projects, preserve stricter settings and improve touched code without blanket ignores or disabling diagnostics to get a pass. |
| Extensive type hints | Annotate parameters, return values (including `None`), model fields, and ambiguous collections. Use precise unions, generics, `Protocol`, and collection interfaces where needed. Let obvious local values be inferred. Match syntax to the supported Python version. |
| Honest types | Use `object` for unvalidated Python values instead of spreading `Any`. Narrow or parse before use. `cast`, `NewType`, `TypedDict`, and annotations do not validate data. Avoid unchecked casts and broad `type: ignore`; any unavoidable suppression needs a specific error code and reason. |
| Pydantic at boundaries | Validate external payloads, JSON, configuration, and other untrusted data with Pydantic models or `TypeAdapter`. Reuse the model as the typed contract instead of maintaining a duplicate dictionary schema and hand-written validator. Add Pydantic with uv when required. |
| Explicit validation semantics | Choose coercion, extra-field handling, and constraints to match the boundary contract. Use strict validation where coercion would hide bad data. Handle `ValidationError` at the boundary without leaking raw sensitive input. Do not use `model_construct` for untrusted data. |
| Domain modeling | Prefer explicit variants over bags of optional fields. Use dataclasses for internal records that need no external parsing, and `NewType` when semantic primitives must be distinguished. Strengthen types only where it prevents real invalid states or partial operations. |
| Verification | Test accepted and rejected boundary data and domain behavior. Ruff and mypy complement runtime tests; passing static checks does not prove runtime validation. Report the checks actually run and any gaps. |

Read [examples and setup](references/patterns.md) for uv commands, Ruff/mypy configuration, and typed Pydantic/domain patterns.
