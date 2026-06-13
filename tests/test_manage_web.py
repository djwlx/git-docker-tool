import tempfile
import unittest
from pathlib import Path

from app.manage_web import (
    AppConfig,
    AppState,
    JobRunner,
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

    def test_parse_ttyd_credentials_accepts_default_credentials(self):
        self.assertEqual(parse_ttyd_credentials("admin:adminadmin"), ("admin", "adminadmin"))

    def test_find_compose_file_prefers_supported_names_in_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compose_file = root / "compose.yaml"
            compose_file.write_text("services: {}", encoding="utf-8")
            self.assertEqual(find_compose_file(root), compose_file)

    def test_find_compose_file_supports_docker_compose_yaml_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compose_file = root / "docker-compose.yaml"
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

    def test_job_runner_runs_prune_after_successful_update(self):
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
            store.save(AppState(auto_update_enabled=True, auto_prune_enabled=True, update_interval_hours=6))
            runner = RecordingJobRunner(config, store, update_result=True)

            runner.run_due_cycle()

            self.assertEqual(runner.events, ["update", "prune"])

    def test_job_runner_skips_prune_when_update_fails(self):
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
            store.save(AppState(auto_update_enabled=True, auto_prune_enabled=True, update_interval_hours=6))
            runner = RecordingJobRunner(config, store, update_result=False)

            runner.run_due_cycle()

            self.assertEqual(runner.events, ["update"])

    def test_job_runner_can_run_prune_without_update(self):
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
            store.save(AppState(auto_update_enabled=False, auto_prune_enabled=True, update_interval_hours=6))
            runner = RecordingJobRunner(config, store, update_result=True)

            runner.run_due_cycle()

            self.assertEqual(runner.events, ["prune"])


class RecordingJobRunner(JobRunner):
    def __init__(self, config, state_store, update_result):
        super().__init__(config, state_store)
        self.update_result = update_result
        self.events = []

    def _run_update_job(self):
        self.events.append("update")
        return self.update_result

    def _run_prune_job(self):
        self.events.append("prune")
        return True


if __name__ == "__main__":
    unittest.main()
