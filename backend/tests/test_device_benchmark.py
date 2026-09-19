from __future__ import annotations

import copy
import unittest
from pathlib import Path

from src.device_benchmark import evaluate_run, percentile_nearest_rank
from src.metadata_validation import load_yaml_mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = load_yaml_mapping(PROJECT_ROOT / "records" / "device-benchmark-protocol-v1.yaml")
YOLO26N = PROTOCOL["models"][0]


def synthetic_run(*, fps: int = 15, latency_ms: float = 20.0, **overrides) -> dict:
    """A clean, passing XR run: fixed frame rate and latency, 1 Hz samples."""

    run_settings = PROTOCOL["run"]
    duration = run_settings["duration_seconds"]
    count = duration * fps
    run = {
        "schema_version": "1.0",
        "benchmark": PROTOCOL["benchmark_id"],
        "run_id": "00000000-0000-0000-0000-000000000000",
        "status": "completed",
        "stop_reason": None,
        "device": {"machine": "iPhone11,8", "system_name": "iOS", "system_version": "18.6.2"},
        "app": {"version": "1.0", "build": "1", "configuration": "Release"},
        "model": {"resource": "aware", "weight_sha256": YOLO26N["weight_sha256"], "compiled_bytes": 4_900_000},
        "operator_input": {"battery_health_percent": 84, "room_temperature_c": 27.0, "notes": ""},
        "settings": {key: run_settings[key] for key in (
            "duration_seconds", "sample_interval_seconds", "screen_brightness",
            "confidence_threshold", "session_preset", "camera_position",
        )},
        "frames": {
            "start_seconds": [index / fps for index in range(count)],
            "duration_ms": [latency_ms] * count,
        },
        "samples": [
            {
                "t": float(second),
                "phys_footprint_bytes": 180_000_000,
                "thermal_state": 0,
                "battery_level": 0.9 - 0.03 * second / duration,
                "battery_state": "unplugged",
                "low_power_mode": False,
                "screen_brightness": 0.5,
                "results": second * fps,
                "results_with_detection": second * fps // 2,
            }
            for second in range(duration + 1)
        ],
        "events": [],
    }
    run.update(overrides)
    return run


def gate(report, name):
    return next(g for g in report.gates if g.name == name)


class DeviceBenchmarkTests(unittest.TestCase):
    def test_protocol_matches_the_app_release_record(self) -> None:
        release = load_yaml_mapping(PROJECT_ROOT / "records" / "app-model-release-v1.yaml")
        self.assertEqual(YOLO26N["model_version"], release["model_version"])
        self.assertEqual(YOLO26N["package_bytes"], release["package_bytes"])
        self.assertEqual(
            YOLO26N["weight_sha256"],
            release["file_sha256"]["Data/com.apple.CoreML/weights/weight.bin"],
        )
        self.assertEqual(PROTOCOL["limits"]["package_bytes_max"], 25 * 1024 * 1024)
        self.assertEqual(PROTOCOL["run"]["duration_seconds"] - PROTOCOL["run"]["warmup_seconds"], 600)

    def test_nearest_rank_percentile(self) -> None:
        values = list(range(1, 101))
        self.assertEqual(percentile_nearest_rank(values, 95), 95)
        self.assertEqual(percentile_nearest_rank([7.0], 95), 7.0)

    def test_clean_xr_run_passes_with_exact_metrics(self) -> None:
        report = evaluate_run(synthetic_run(), PROTOCOL)

        self.assertEqual(report.verdict, "PASS", report.render())
        self.assertEqual(report.model_version, "aware-v1-yolo26n-fp16")
        self.assertEqual(report.metrics["frames_measured"], 600 * 15)
        self.assertEqual(report.metrics["window_fps"], [15.0] * 10)
        self.assertEqual(report.metrics["latency_ms"]["p95"], 20.0)
        self.assertEqual(report.metrics["battery_drop_points"], 3.0)
        self.assertEqual(report.metrics["battery_resolution_points"], 1)
        self.assertEqual(report.metrics["detection_rate"], 0.5)

    def test_slow_tail_fails_p95_but_not_the_median(self) -> None:
        run = synthetic_run()
        durations = run["frames"]["duration_ms"]
        for index in range(0, len(durations), 10):
            durations[index] = 150.0

        report = evaluate_run(run, PROTOCOL)

        self.assertEqual(report.verdict, "FAIL")
        self.assertFalse(gate(report, "p95_latency").passed)
        self.assertTrue(gate(report, "latency_degradation").passed)

    def test_one_slow_minute_fails_sustained_fps(self) -> None:
        run = synthetic_run()
        starts, durations = run["frames"]["start_seconds"], run["frames"]["duration_ms"]
        kept = [
            (s, d)
            for index, (s, d) in enumerate(zip(starts, durations))
            if not (310 <= s < 370) or index % 2 == 0
        ]
        run["frames"] = {"start_seconds": [s for s, _ in kept], "duration_ms": [d for _, d in kept]}

        report = evaluate_run(run, PROTOCOL)

        self.assertEqual(min(report.metrics["window_fps"]), 7.5)
        self.assertFalse(gate(report, "sustained_fps").passed)
        self.assertEqual(report.verdict, "FAIL")

    def test_late_slowdown_fails_degradation(self) -> None:
        run = synthetic_run()
        run["frames"]["duration_ms"] = [
            30.0 if start >= 550 else 20.0 for start in run["frames"]["start_seconds"]
        ]

        report = evaluate_run(run, PROTOCOL)

        self.assertEqual(report.metrics["latency_degradation"], 0.5)
        self.assertFalse(gate(report, "latency_degradation").passed)

    def test_serious_thermal_event_fails(self) -> None:
        run = synthetic_run(events=[{"t": 400.0, "kind": "thermal_state", "detail": "serious"}])

        report = evaluate_run(run, PROTOCOL)

        self.assertEqual(report.metrics["max_thermal_state"], "serious")
        self.assertFalse(gate(report, "thermal_state").passed)

    def test_memory_and_battery_limits(self) -> None:
        run = synthetic_run()
        run["samples"][200]["phys_footprint_bytes"] = 600_000_000
        run["samples"][-1]["battery_level"] = 0.80

        report = evaluate_run(run, PROTOCOL)

        self.assertFalse(gate(report, "peak_memory").passed)
        self.assertFalse(gate(report, "battery_drop").passed)
        self.assertEqual(report.metrics["battery_drop_points"], 10.0)

    def test_coarse_battery_readings_are_noted(self) -> None:
        run = synthetic_run()
        for sample in run["samples"]:
            sample["battery_level"] = 0.9 if sample["t"] < 300 else 0.85

        report = evaluate_run(run, PROTOCOL)

        self.assertEqual(report.metrics["battery_resolution_points"], 5)
        self.assertTrue(any("5-point" in note for note in report.notes))

    def test_protocol_breaches_make_the_run_invalid(self) -> None:
        cases = {
            "stopped": {"status": "stopped", "stop_reason": "operator_stopped"},
            "debug build": {"app": {"version": "1.0", "build": "1", "configuration": "Debug"}},
            "unknown model": {"model": {"resource": "aware", "weight_sha256": "0" * 64, "compiled_bytes": 1}},
            "no health": {"operator_input": {"battery_health_percent": None, "room_temperature_c": None, "notes": ""}},
            "resigned": {"events": [{"t": 100.0, "kind": "resign_active", "detail": ""}]},
        }
        for label, overrides in cases.items():
            with self.subTest(label):
                self.assertEqual(evaluate_run(synthetic_run(**overrides), PROTOCOL).verdict, "INVALID")

        charging = synthetic_run()
        charging["samples"][50]["battery_state"] = "charging"
        warm_start = synthetic_run()
        warm_start["samples"][0]["thermal_state"] = 1
        changed = synthetic_run()
        changed["settings"]["duration_seconds"] = 300
        gap = synthetic_run()
        del gap["samples"][100:110]
        for label, run in {"charging": charging, "warm": warm_start, "settings": changed, "gap": gap}.items():
            with self.subTest(label):
                self.assertEqual(evaluate_run(run, PROTOCOL).verdict, "INVALID")

    def test_empty_run_is_invalid_without_metrics(self) -> None:
        run = synthetic_run(status="failed", stop_reason="no_frames")
        run["frames"] = {"start_seconds": [], "duration_ms": []}

        report = evaluate_run(run, PROTOCOL)

        self.assertEqual(report.verdict, "INVALID")
        self.assertEqual(report.gates, ())
        self.assertIn("no frames recorded", report.issues)

    def test_only_the_xr_on_ios_18_counts(self) -> None:
        devices = {
            "other phone": {"machine": "iPhone15,2", "system_name": "iOS", "system_version": "18.6.2"},
            "xr on ios 17": {"machine": "iPhone11,8", "system_name": "iOS", "system_version": "17.7"},
        }
        for label, device in devices.items():
            with self.subTest(label):
                report = evaluate_run(synthetic_run(device=device), PROTOCOL)
                self.assertEqual(report.verdict, "INVALID")
                self.assertTrue(all(g.passed for g in report.gates))

    def test_report_does_not_mutate_the_run(self) -> None:
        run = synthetic_run()
        before = copy.deepcopy(run)

        evaluate_run(run, PROTOCOL)

        self.assertEqual(run, before)


class ProtocolV2Tests(unittest.TestCase):
    V2 = load_yaml_mapping(PROJECT_ROOT / "records" / "device-benchmark-protocol-v2.yaml")

    def test_v2_changes_only_the_thermal_limit(self) -> None:
        self.assertEqual(self.V2["status"], "approved")
        for section in ("run", "models", "gate_device", "validity", "benchmark_id"):
            self.assertEqual(self.V2[section], PROTOCOL[section], section)
        changed = {k for k in PROTOCOL["limits"] if PROTOCOL["limits"][k] != self.V2["limits"][k]}
        self.assertEqual(changed, {"thermal_state_max"})
        self.assertEqual(self.V2["limits"]["thermal_state_max"], "serious")

    def test_serious_passes_and_critical_fails_under_v2(self) -> None:
        serious = synthetic_run(events=[{"t": 225.0, "kind": "thermal_state", "detail": "serious"}])
        critical = synthetic_run(events=[{"t": 400.0, "kind": "thermal_state", "detail": "critical"}])

        self.assertEqual(evaluate_run(serious, PROTOCOL).verdict, "FAIL")
        self.assertEqual(evaluate_run(serious, self.V2).verdict, "PASS")
        self.assertEqual(evaluate_run(critical, self.V2).verdict, "FAIL")


if __name__ == "__main__":
    unittest.main()
