# KSPL Copilot Instructions

## Project Overview
KSPL is a KConfig GUI for Software Product Lines (SPL) with multiple variants.
It's built on Python 3.10+ with CustomTkinter for GUI, kconfiglib for parsing, and py-app-dev for CLI/MVP architecture.

## Architecture & Key Components

### Core Structure
- **Main entry**: `src/kspl/main.py` - CLI with commands: `gui`, `generate`, `edit`
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

## Development Workflow

### Build System
Uses **pypeline** (not pip/poetry directly) for orchestrated builds:
```bash
pypeline run                    # Full pipeline: venv + pre-commit + tests
pypeline run --step PyTest --single     # Run only tests
```

### VS Code Tasks
Prefer VS Code tasks over manual commands:
- "run tests" → `.venv/Scripts/pypeline run --step PyTest --single`
- "run pre-commit checks" → pre-commit with ruff, mypy, etc.
- "generate docs" → Sphinx documentation

### Package Management
- **UV** (not pip) for dependency resolution - see `uv.lock`
- Virtual env in `.venv/` created by pypeline's CreateVEnv step
- Dev dependencies in `[dependency-groups.dev]` section of `pyproject.toml`

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
Commands inherit from `py_app_dev.core.cmd_line.Command`:
```python
@register_arguments_for_config_dataclass(MyConfig)
def register_arguments(self, parser: ArgumentParser) -> None:
    # Auto-registers dataclass fields as CLI args
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

- Always include full **type hints** (functions, methods, public attrs, constants).
- Prefer **pythonic** constructs: context managers, `pathlib`, comprehensions when clear, `enumerate`, `zip`, early returns, no over-nesting.
- Follow **SOLID**: single responsibility; prefer composition; program to interfaces (`Protocol`/ABC); inject dependencies.
- **Naming**: descriptive `snake_case` vars/funcs, `PascalCase` classes, `UPPER_SNAKE_CASE` constants. Avoid single-letter identifiers (including `i`, `j`, `a`, `b`) except in tight math helpers.
- Code should be **self-documenting**. Use docstrings only for public APIs or non-obvious rationale/constraints; avoid noisy inline comments.
- Errors: raise specific exceptions; never `except:` bare; add actionable context.
- Imports: no wildcard; group stdlib/third-party/local, keep modules small and cohesive.
- Testability: pure functions where possible; pass dependencies, avoid globals/singletons.
- tests: use `pytest`; keep the tests to a minimum; use parametrized tests when possible; do no add useless comments; the tests shall be self-explanatory.
