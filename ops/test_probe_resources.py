"""Ownership regressions; system commands are mocked, no server or DB is used."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "infrastructure_probe", Path(__file__).with_name("verify-infrastructure.py")
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeOwnershipTests(unittest.TestCase):
    def test_start_conflict_preserves_foreign_file_and_does_not_stop_unit(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            foreign = base / "infra_probe.py"
            foreign.write_text("foreign content")
            with patch.object(
                probe,
                "run",
                side_effect=subprocess.CalledProcessError(1, "systemd-run"),
            ) as command:
                with self.assertRaises(subprocess.CalledProcessError):
                    with probe.probe_service(base):
                        self.fail("failed start must not yield")
            self.assertEqual(command.call_count, 1)
            self.assertEqual(foreign.read_text(), "foreign content")
            self.assertEqual(list(base.iterdir()), [foreign])

    def test_body_failure_stops_only_started_unit_and_cleans_owned_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with patch.object(probe, "run") as command:
                with self.assertRaisesRegex(RuntimeError, "smoke failure"):
                    with probe.probe_service(base):
                        unit = next(base.iterdir()).name
                        raise RuntimeError("smoke failure")
                self.assertEqual(
                    command.call_args_list[-1].args, ("systemctl", "stop", unit)
                )
                self.assertEqual(command.call_count, 2)
            self.assertEqual(list(base.iterdir()), [])

    def test_overlapping_runs_have_distinct_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with patch.object(probe, "run") as command:
                with probe.probe_service(base):
                    first = next(base.iterdir())
                    with probe.probe_service(base):
                        self.assertEqual(len(list(base.iterdir())), 2)
                    self.assertTrue((first / "infra_probe.py").exists())
                stops = [
                    c.args[-1]
                    for c in command.call_args_list
                    if c.args[0] == "systemctl"
                ]
                self.assertEqual(len(set(stops)), 2)
            self.assertEqual(list(base.iterdir()), [])

    def test_failed_stop_preserves_owned_files_for_diagnosis(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with patch.object(
                probe,
                "run",
                side_effect=[None, subprocess.CalledProcessError(1, "systemctl")],
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    with probe.probe_service(base):
                        owned = next(base.iterdir())
            self.assertTrue((owned / "infra_probe.py").exists())


if __name__ == "__main__":
    unittest.main()
