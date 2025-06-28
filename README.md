# SPL KConfig GUI

<p align="center">
  <a href="https://github.com/cuinixam/kspl/actions/workflows/ci.yml?query=branch%3Amain">
    <img src="https://img.shields.io/github/actions/workflow/status/cuinixam/kspl/ci.yml?branch=main&label=CI&logo=github&style=flat-square" alt="CI Status" >
  </a>
  <a href="https://codecov.io/gh/cuinixam/kspl">
    <img src="https://img.shields.io/codecov/c/github/cuinixam/kspl.svg?logo=codecov&logoColor=fff&style=flat-square" alt="Test coverage percentage">
  </a>
</p>
<p align="center">
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff">
  </a>
  <a href="https://github.com/cuinixam/pypeline">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cuinixam/pypeline/refs/heads/main/assets/badge/v0.json" alt="pypeline">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat-square" alt="pre-commit">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/kspl/">
    <img src="https://img.shields.io/pypi/v/kspl.svg?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/kspl.svg?style=flat-square&logo=python&amp;logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/kspl.svg?style=flat-square" alt="License">
</p>

---

**Source Code**: <a href="https://github.com/cuinixam/kspl" target="_blank">https://github.com/cuinixam/kspl </a>

---

KConfig GUI for Software Product Lines with multiple variants.

## How to use it

Use pipx (or your favorite package manager) to install and run it in an isolated environment:

```shell
pipx install kspl
```

This will install the `kspl` command globally, which you can use to open/edit the KConfig configuration in your SPL.

```shell
kspl view --project-dir /path/to/your/spl
```

For more information on the available commands, run:

```shell
kspl --help
```

## Start developing

The project uses UV for dependencies management and packaging and the [pypeline](https://github.com/cuinixam/pypeline) for streamlining the development workflow.
Use pipx (or your favorite package manager) to install the `pypeline` in an isolated environment:

```shell
pipx install pypeline-runner
```

To bootstrap the project and run all the steps configured in the `pypeline.yaml` file, execute the following command:

```shell
pypeline run
```

For those using [VS Code](https://code.visualstudio.com/) there are tasks defined for the most common commands:

- run tests
- run pre-commit checks (linters, formatters, etc.)
- generate documentation

See the `.vscode/tasks.json` for more details.

## Committing changes

This repository uses [commitlint](https://github.com/conventional-changelog/commitlint) for checking if the commit message meets the [conventional commit format](https://www.conventionalcommits.org/en).

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- prettier-ignore-start -->
<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- markdownlint-disable -->
<!-- markdownlint-enable -->
<!-- ALL-CONTRIBUTORS-LIST:END -->
<!-- prettier-ignore-end -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!

## Credits

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)

This package was created with
[Copier](https://copier.readthedocs.io/) and the
[browniebroke/pypackage-template](https://github.com/browniebroke/pypackage-template)
project template.
