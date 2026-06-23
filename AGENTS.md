# KSPL Development Guide for AI Agents

## Project Overview
KSPL is a KConfig GUI for Software Product Lines (SPL) with multiple variants.
It's built on Python 3.10+ with CustomTkinter for GUI, kconfiglib for parsing, and py-app-dev for CLI/MVP architecture.

## Architecture & Key Components

### Core Structure
- **Main entry**: `src/kspl/main.py` - CLI with commands: `view`, `generate`, `edit`
- **KConfig handling**: `src/kspl/kconfig.py` - Wraps kconfiglib for SPL-specific needs
- **GUI**: `src/kspl/gui.py` - CustomTkinter-based MVP pattern with EventManager
- **Data layer**: `src/kspl/config_slurper.py` - Manages variants and configuration data

### MVP Pattern
The GUI follows MVP (Model-View-Presenter) pattern from `py_app_dev.mvp`:
- Views inherit from `CTkView` and handle UI rendering
- Presenters manage business logic and coordinate between Model/View
- EventManager handles communication with events like `KSplEvents.EDIT`, `KSplEvents.REFRESH`

### SPL Concepts
- **KConfig model**: Single `KConfig` file defines configuration structure
- **Variants**: Multiple `.config` files representing different product configurations
- **Elements**: Configuration items with types (BOOL, STRING, INT, HEX, MENU, TRISTATE)

## Development Guidelines

### ⚠️ MANDATORY: Plan Before Execution

**NEVER start making changes without presenting a plan first.** This is a critical rule.

1. **Create an implementation plan** documenting:
   - What files will be modified, created, or deleted
   - What changes will be made and why
   - How the changes will be verified
2. **Present the plan for user review** — output it as text and wait for the user's response
3. **Wait for explicit approval** before proceeding with any file modifications
4. **Only after approval**, begin execution

Skipping this step is unacceptable.

### ⚠️ MANDATORY: Never Change the Plan Without Approval

**NEVER deviate from the approved plan without asking the user first.** If the current approach hits a blocker (e.g., a tool doesn't work, a dependency is missing, a test fails unexpectedly), you MUST:

1. **Stop** — do not attempt an alternative approach on your own
2. **Report the problem** to the user with a clear description of what went wrong
3. **Propose alternatives** if you have ideas, but do NOT implement them
4. **Wait for explicit approval** before changing direction

This applies to all scope changes: switching libraries, replacing test targets, altering architecture, or any deviation from what was agreed upon. The user decides, not the agent.

### Running Tests and Verification

The project uses `pypeline-runner` for all automation. Key commands:

```bash
# Run full pipeline (lint + tests) - this is the primary verification command
pypeline run

# Run only linting (pre-commit hooks)
pypeline run --step PreCommit

# Run only tests with specific Python version
pypeline run --step CreateVEnv --step PyTest --single --input python_version=3.13
```

### Local Development

- **VS Code tasks** (preferred over manual commands):
  - "run tests" → `.venv/Scripts/pypeline run --step PyTest --single`
  - "run pre-commit checks" → pre-commit with ruff, mypy, etc.
  - "generate docs" → Sphinx documentation
- **Package management**: UV (not pip) for dependency resolution — see `uv.lock`. The virtual env in `.venv/` is created by pypeline's `CreateVEnv` step. Dev dependencies live in the `[dependency-groups.dev]` section of `pyproject.toml`.

### CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

1. **Lint** (`PreCommit` step) - Runs ruff linting/formatting via pre-commit
2. **Commit Lint** - Enforces [conventional commits](https://www.conventionalcommits.org)
3. **Test** - Matrix: Python 3.10 & 3.13 on Ubuntu and Windows
4. **Release** - Semantic versioning with automatic PyPI publishing

### Code Quality

- **Ruff** handles linting/formatting (configured in `pyproject.toml`)
- **Pre-commit hooks** enforce code standards
- **Type hints** are required (`py.typed` marker present)
- Docstrings follow standard conventions but are not required for all functions

## Project-Specific Patterns

### Configuration Handling
```python
# Always use Path objects, not strings
project_dir = Path("/path/to/spl")
spl_data = SPLKConfigData(project_dir)  # Expects KConfig file at root

# Variant discovery pattern
variant_configs = spl_data.get_variants()  # Auto-discovers *.config files
```

### Error Handling
Uses `py_app_dev.core.exceptions.UserNotificationException` for user-facing errors:
```python
if not self.kconfig_model_file.is_file():
    raise UserNotificationException(f"File {self.kconfig_model_file} does not exist.")
```

### CLI Command Pattern
Commands inherit from `py_app_dev.core.cmd_line.Command` and register their arguments from a config dataclass:
```python
class EditCommand(Command):
    def __init__(self) -> None:
        super().__init__("edit", "Edit KConfig configuration.")

    def run(self, args: Namespace) -> int:
        config = EditCommandConfig.from_namespace(args)
        ...
        return 0

    def _register_arguments(self, parser: ArgumentParser) -> None:
        # Auto-registers the dataclass fields as CLI args
        register_arguments_for_config_dataclass(parser, EditCommandConfig)
```

### Testing Strategy
- Pytest with parametrized tests
- Test data in `tests/data/` (sample KConfig files)
- Focus on KConfig parsing, variant handling, and GUI event flows
- Use `tmp_path` fixture for file-based tests

## Critical Files for Understanding
- `src/kspl/kconfig.py` - Core KConfig abstractions and kconfiglib integration
- `src/kspl/config_slurper.py` - SPL variant management logic
- `tests/data/KConfig` - Example KConfig syntax and structure
- `pypeline.yaml` - Build pipeline definition
- `.pre-commit-config.yaml` - Code quality tools (ruff, mypy, commitlint)

## Common Gotchas
- KConfig files must be named exactly `KConfig` (no extension) at project root
- Variant files follow pattern `*.config` and are auto-discovered
- CustomTkinter has different API than standard tkinter - check existing patterns in `gui.py`
- Use `py_app_dev.core.logging.logger` (structured logging) not standard logging

## Coding Guidelines

- **Less is more** — be concise and question every implementation that looks too complicated; if there is a simpler way, use it.
- **Never nester** — maximum three indentation levels are allowed. Use early returns, guard clauses, and extraction into helper functions to keep nesting shallow. The third level should only be used when truly necessary.
- **Use dataclasses for complex data structures**: Prefer using `dataclasses` over complex standard types (e.g. `tuple[list[str] | None, dict[str, str] | None]`) for function return values or internal data exchange to improve readability and extensibility.
- Always include full **type hints** (functions, methods, public attrs, constants).
- Prefer **pythonic** constructs: context managers, `pathlib`, comprehensions when clear, `enumerate`, `zip`, early returns, no over-nesting.
- Follow **SOLID**: single responsibility; prefer composition; program to interfaces (`Protocol`/ABC); inject dependencies.
- **Naming**: descriptive `snake_case` vars/funcs, `PascalCase` classes, `UPPER_SNAKE_CASE` constants. Avoid single-letter identifiers (including `i`, `j`, `a`, `b`) except in tight math helpers.
- Code should be **self-documenting**. Use docstrings only for public APIs or non-obvious rationale/constraints; avoid noisy inline comments.
- Errors: raise specific exceptions; never `except:` bare; add actionable context.
- Imports: no wildcard; group stdlib/third-party/local, keep modules small and cohesive.
- Testability: pure functions where possible; pass dependencies, avoid globals/singletons.
- Tests: use `pytest`; keep the tests to a minimum; use parametrized tests when possible; do not add useless comments; the tests shall be self-explanatory.
- Pytest fixtures: use them to avoid code duplication; use `conftest.py` for shared fixtures. Use `tmp_path` for file system operations.
- **Never suppress linter/type-checker warnings** by adding ignore rules to `pyproject.toml` or `# noqa` / `# type: ignore` comments. Always fix the underlying code instead.

## Definition of Done

Changes are NOT complete until:

- `pypeline run` executes with **zero failures**
- **All new functionality has tests** - never skip writing tests for new code
- Test coverage includes edge cases and error conditions
</content>
</invoke>
