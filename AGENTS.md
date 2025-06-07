# AGENTS.md

> **Scope:** Applies to *this* directory and all nested sub‑directories unless overridden by a deeper `AGENTS.md`.

---

## 🎯 Purpose

Provide **coding conventions, architectural guidelines, and procedural rules** for both humans and automated agents working on this Python codebase. The rules ensure consistency, testability, security, and maintainability.

---

## 📚 General Principles

1. **Readability > Cleverness** – prefer clear, idiomatic Python over micro‑optimisations.
2. **Single Responsibility** – each module, class, and function should serve one clear purpose.
3. **Automation First** – CI must be able to install, test, lint, and type‑check the project without manual steps.

---

## 🧑‍💻 Code Style

| Tool               | Config                                                   |
| ------------------ | -------------------------------------------------------- |
| **Formatter**      | `black --line-length 100`                                |
| **Import sorter**  | `ruff format` (or `isort` 5.x, same profile)             |
| **Linter**         | `ruff check .` with `select = ["E","F","B","I","N","D"]` |
| **Type checker**   | `mypy --strict`                                          |
| **Python version** | ≥ 3.11                                                   |

Additional rules:

* Use **type annotations** everywhere except one‑off scripts in `/scripts`.
* Variable, function, and module names: `snake_case`; class names: `PascalCase`; constants: `UPPER_SNAKE`.
* Prefer [`pathlib.Path`](https://docs.python.org/3/library/pathlib.html) to string paths.
* Avoid *relative imports* except inside tests.

---

## 🏗️ Recommended Project Layout

```text
project_root/
├── src/               # Production code (set PYTHONPATH accordingly)
│   └── package_name/
│       ├── __init__.py
│       ├── core/
│       ├── services/
│       └── ...
├── tests/             # pytest tests (mirrors src layout)
├── scripts/           # one‑off maintenance scripts
├── pyproject.toml     # build & tool configs (Poetry / Hatchling)
└── README.md
```

> **Note:** Keep `src` importable only via the package; do **not** rely on implicit local imports.

---

## 🔬 Testing

* Framework: **pytest**
* Minimum coverage: **90 %** lines, **100 %** for new/modified code.
* Use **fixtures** for external resources; no real network calls in unit tests.
* Property‑based tests encouraged with *hypothesis* where valuable.

Run locally:

```bash
pytest -q
coverage xml && coverage html
```

---

## 📦 Dependency Management

* Use **Poetry** or **Hatch** (preferred) declared in `pyproject.toml`.
* Pin direct dependencies with exact versions; use range spec only for libraries.
* Do **not** commit virtual‑envs or lock files other than `poetry.lock`.

---

## 🔄 Git & Branching

* Default branch: `main`
* Feature branches: `feat/<scope>-<short_description>`
* Hotfix branches: `fix/<issue>`

**Commit message convention** (adapted from Conventional Commits):

```text
<type>(<scope>): <subject>

<body>  # optional
```

Allowed `<type>`: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `ci`.

---

## 🚦 Pull Request Checklist

1. CI green (`black`, `ruff`, `mypy`, `pytest`).
2. PR <= **400** changed LOC (excluding generated files).
3. Linked issue or clear rationale.
4. Changelog entry added in `CHANGELOG.md`.
5. No secrets, credentials, or personal data committed.

---

## 🛡️ Security & Secrets

* **Never** hard‑code secrets. Use environment variables or a secrets manager (e.g. HashiCorp Vault).
* External calls must validate TLS certificates.
* Dependencies are scanned with [`pip-audit`](https://github.com/pypa/pip-audit) in CI.

---

## 🤖 Agent‑Specific Rules

1. For every file you modify, obey all `AGENTS.md` files whose scope includes that file.
2. If multiple `AGENTS.md` files conflict, **the deepest one wins**.
3. You **must** run all programmatic checks below before finalising a patch—even for documentation changes.
4. Direct user/developer/system instructions override this file.

---

## ✅ Programmatic Checks (CI)

```bash
# format & lint
black .
ruff check .
# type checking
mypy .
# tests & coverage
pytest --cov=src --cov-report=xml --cov-report=term
pip-audit
```

---

## 📄 Example Good PR Description

```
feat(core): add async file downloader

### What & Why
- Introduces `core.download.AsyncDownloader` with retries and back‑off.
- Replaces synchronous code that blocked the event loop (#42).

### Changes
- src/package_name/core/download.py (+120 LOC)
- tests/core/test_download.py (+220 LOC)

### Validation
- `pytest` → 125 tests passed
- Coverage 92 %
- `mypy` passes
```

---

## 🙋 Support & Maintainers

| Role             | GitHub                                              | Responsibility        |
| ---------------- | --------------------------------------------------- | --------------------- |
| Lead Maintainer  | @maintainer‑handle                                  | Code review, releases |
| Security Contact | [security@example.com](mailto:security@example.com) | Vulnerability reports |

---

> **Remember:** Follow these guidelines unless explicitly instructed otherwise by the project maintainers or an upstream `AGENTS.md`.
> These instructions take precedence over any tool default configurations.
