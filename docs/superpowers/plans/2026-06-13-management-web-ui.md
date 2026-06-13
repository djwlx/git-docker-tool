# Management Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a password-protected management page that shares ttyd credentials and controls automatic Docker Compose updates and Docker image pruning.

**Architecture:** Add a small Python standard-library web app that serves the management page, persists state in `/workspace`, and runs background scheduler threads for the two jobs. Update the container entrypoint to launch both the management app and ttyd with shared credentials defined by environment variables.

**Tech Stack:** Alpine, Python 3 standard library, shell entrypoint, Docker CLI, unittest

---

### Task 1: Add failing tests for app utilities

**Files:**
- Create: `tests/test_manage_web.py`
- Test: `tests/test_manage_web.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile
import unittest
from pathlib import Path

from app.manage_web import (
    AppConfig,
    StateStore,
    backoff_delay_seconds,
    find_compose_file,
    parse_ttyd_credentials,
)


class ManageWebTests(unittest.TestCase):
    def test_parse_ttyd_credentials_returns_username_and_password(self):
        self.assertEqual(parse_ttyd_credentials("admin:secret"), ("admin", "secret"))

    def test_parse_ttyd_credentials_rejects_missing_separator(self):
        with self.assertRaises(ValueError):
            parse_ttyd_credentials("admin")

    def test_find_compose_file_prefers_supported_names_in_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compose_file = root / "compose.yaml"
            compose_file.write_text("services: {}", encoding="utf-8")
            self.assertEqual(find_compose_file(root), compose_file)

    def test_find_compose_file_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertIsNone(find_compose_file(Path(temp_dir)))

    def test_backoff_delay_seconds_doubles_until_fifth_attempt(self):
        self.assertEqual([backoff_delay_seconds(i) for i in range(1, 6)], [1, 2, 4, 8, 16])

    def test_state_store_loads_defaults_when_file_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = AppConfig(
                ttyd_credentials="admin:adminadmin",
                compose_root=Path(temp_dir),
                state_file=Path(temp_dir) / "state.json",
                host="0.0.0.0",
                port=7680,
                prune_interval_hours=24,
            )
            store = StateStore(config)
            self.assertFalse(store.load().auto_update_enabled)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_manage_web.py -v`
Expected: FAIL with `ModuleNotFoundError` for `app.manage_web`

- [ ] **Step 3: Write minimal implementation**

```python
# Placeholder module with the required exports so the first test can progress.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_manage_web.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_manage_web.py app/manage_web.py
git commit -m "test: cover management app utilities"
```

### Task 2: Implement the management app and scheduler

**Files:**
- Create: `app/manage_web.py`
- Modify: `tests/test_manage_web.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_state_store_persists_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = AppConfig(
                ttyd_credentials="admin:adminadmin",
                compose_root=Path(temp_dir),
                state_file=Path(temp_dir) / "state.json",
                host="0.0.0.0",
                port=7680,
                prune_interval_hours=24,
            )
            store = StateStore(config)
            state = store.load()
            state.auto_update_enabled = True
            state.update_interval_hours = 6
            store.save(state)
            reloaded = store.load()
            self.assertTrue(reloaded.auto_update_enabled)
            self.assertEqual(reloaded.update_interval_hours, 6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_manage_web.py -v`
Expected: FAIL because `StateStore.save` or persistence behavior is missing

- [ ] **Step 3: Write minimal implementation**

```python
# Implement config parsing, state dataclass, JSON persistence,
# HTTP basic auth, HTML form rendering, and scheduler loops.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_manage_web.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/manage_web.py tests/test_manage_web.py
git commit -m "feat: add docker management web app"
```

### Task 3: Wire container startup and environment variables

**Files:**
- Modify: `Dockerfile`
- Modify: `entrypoint.sh`

- [ ] **Step 1: Write the failing test**

```python
    def test_parse_ttyd_credentials_accepts_default_credentials(self):
        self.assertEqual(parse_ttyd_credentials("admin:adminadmin"), ("admin", "adminadmin"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_manage_web.py -v`
Expected: FAIL if credential parsing or defaults are inconsistent

- [ ] **Step 3: Write minimal implementation**

```sh
# Install python3, copy the app, expose the management port,
# and start the app before exec'ing ttyd with the same credentials.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_manage_web.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Dockerfile entrypoint.sh
git commit -m "feat: wire management app into container startup"
```

### Task 4: Document runtime configuration and usage

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

```python
    def test_find_compose_file_supports_docker_compose_yaml_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compose_file = root / "docker-compose.yaml"
            compose_file.write_text("services: {}", encoding="utf-8")
            self.assertEqual(find_compose_file(root), compose_file)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_manage_web.py -v`
Expected: FAIL until supported file names and docs are aligned

- [ ] **Step 3: Write minimal implementation**

```markdown
# Document management page port, shared credentials, COMPOSE_ROOT,
# update interval control, prune behavior, and retry strategy.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_manage_web.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_manage_web.py
git commit -m "docs: describe management page configuration"
```
