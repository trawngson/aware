"""Check an on-device benchmark run against the iPhone XR limits.

The app's benchmark mode (awareapp/Benchmark) records the raw duration of every
frame's inference plus 1-second device samples. This module checks that a run
followed records/device-benchmark-protocol-v1.yaml and computes the
SPECIFICATION.md 5.1.1 gate metrics. It never repairs a run: an unusable run is
INVALID, and a run that misses a limit is FAIL.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


THERMAL_STATES = ("nominal", "fair", "serious", "critical")
RUN_SETTINGS = (
    "duration_seconds",
    "sample_interval_seconds",
    "screen_brightness",
    "confidence_threshold",
    "session_preset",
    "camera_position",
)
INVALIDATING_EVENTS = ("resign_active",)


@dataclass(frozen=True)
class Gate:
    name: str
    value: float
    limit: float
    at_most: bool
    unit: str

    @property
    def passed(self) -> bool:
        return self.value <= self.limit if self.at_most else self.value >= self.limit

    def render(self) -> str:
        sign = "<=" if self.at_most else ">="
        return (
            f"{'PASS' if self.passed else 'FAIL'} {self.name}: "
            f"{_format(self.value)} {self.unit} (limit {sign} {_format(self.limit)})"
        )


@dataclass(frozen=True)
class BenchmarkReport:
    model_version: str | None
    issues: tuple[str, ...]
    notes: tuple[str, ...]
    metrics: Mapping[str, Any]
    gates: tuple[Gate, ...]

    @property
    def verdict(self) -> str:
        if self.issues:
            return "INVALID"
        return "PASS" if all(gate.passed for gate in self.gates) else "FAIL"

    def render(self) -> str:
        lines = [f"model: {self.model_version or 'unknown'}"]
        lines.extend(gate.render() for gate in self.gates)
        lines.extend(f"INVALID: {issue}" for issue in self.issues)
        lines.extend(f"note: {note}" for note in self.notes)
        lines.append(f"VERDICT: {self.verdict}")
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "model_version": self.model_version,
            "issues": list(self.issues),
            "notes": list(self.notes),
            "metrics": dict(self.metrics),
            "gates": [
                {
                    "name": gate.name,
                    "value": gate.value,
                    "limit": gate.limit,
                    "comparison": "<=" if gate.at_most else ">=",
                    "unit": gate.unit,
                    "passed": gate.passed,
                }
                for gate in self.gates
            ],
        }


def percentile_nearest_rank(values: Sequence[float], percent: float) -> float:
    if not values:
        raise ValueError("percentile of an empty sequence")
    ordered = sorted(values)
    rank = max(1, math.ceil(percent / 100 * len(ordered)))
    return ordered[rank - 1]


def evaluate_run(run: Mapping[str, Any], protocol: Mapping[str, Any]) -> BenchmarkReport:
    """Validate one run file and compute its metrics and gates."""

    issues: list[str] = []
    notes: list[str] = []
    settings = protocol["run"]
    limits = protocol["limits"]

    if run.get("schema_version") != "1.0" or run.get("benchmark") != protocol["benchmark_id"]:
        issues.append(
            f"not a {protocol['benchmark_id']} file "
            f"(benchmark={run.get('benchmark')!r}, schema={run.get('schema_version')!r})"
        )
    if run.get("status") != "completed":
        issues.append(f"run status is {run.get('status')!r} (reason: {run.get('stop_reason')})")
    if run.get("app", {}).get("configuration") != "Release":
        issues.append(f"build configuration is {run.get('app', {}).get('configuration')!r}, not Release")
    for key in RUN_SETTINGS:
        actual = run.get("settings", {}).get(key)
        if not _same_setting(actual, settings[key]):
            issues.append(f"setting {key} is {actual!r}, protocol requires {settings[key]!r}")
    health = run.get("operator_input", {}).get("battery_health_percent")
    if not isinstance(health, int) or not 1 <= health <= 100:
        issues.append(f"battery health {health!r} is not a percentage")

    weight = run.get("model", {}).get("weight_sha256")
    model = next((m for m in protocol["models"] if m["weight_sha256"] == weight), None)
    if model is None:
        issues.append(f"model weight hash {weight!r} is not a protocol model")

    device = run.get("device", {})
    expected = protocol["gate_device"]
    if device.get("machine") != expected["machine"] or _major(device.get("system_version")) != expected["os_major"]:
        issues.append(
            f"device is {device.get('machine')} on {device.get('system_name')} {device.get('system_version')}, "
            f"not the {expected['name']} ({expected['machine']}) on iOS {expected['os_major']}"
        )

    frames = run.get("frames", {})
    starts = list(frames.get("start_seconds", []))
    durations = list(frames.get("duration_ms", []))
    samples = list(run.get("samples", []))
    model_version = model["model_version"] if model else None
    structural = _frame_issues(starts, durations) + ([] if samples else ["no device samples recorded"])
    if structural:
        return BenchmarkReport(model_version, tuple(issues + structural), tuple(notes), {}, ())
    issues.extend(_sample_issues(samples, run.get("events", []), settings))

    warmup = settings["warmup_seconds"]
    window = settings["window_seconds"]
    windows = [
        (start, start + window)
        for start in _frange(warmup, settings["duration_seconds"], window)
    ]
    measured = [d for s, d in zip(starts, durations) if warmup <= s < settings["duration_seconds"]]
    by_window = [[d for s, d in zip(starts, durations) if lo <= s < hi] for lo, hi in windows]
    if any(not frames_in for frames_in in by_window):
        issues.append("at least one measured window has no frames")
        return BenchmarkReport(model_version, tuple(issues), tuple(notes), {}, ())

    window_fps = [len(frames_in) / window for frames_in in by_window]
    window_median = [statistics.median(frames_in) for frames_in in by_window]
    baseline = window_median[0]
    degradation = max(window_median[1:]) / baseline - 1 if len(window_median) > 1 else 0.0

    footprints = [s["phys_footprint_bytes"] for s in samples if s.get("phys_footprint_bytes") is not None]
    thermal_events = [
        THERMAL_STATES.index(event["detail"])
        for event in run.get("events", [])
        if event.get("kind") == "thermal_state" and event.get("detail") in THERMAL_STATES
    ]
    thermal = max([sample["thermal_state"] for sample in samples] + thermal_events)
    levels = [s["battery_level"] for s in samples]
    battery_drop = round((levels[0] - levels[-1]) * 100, 1)
    coarse = all(abs(level * 20 - round(level * 20)) < 1e-6 for level in levels)
    last = samples[-1]
    detection_rate = last["results_with_detection"] / last["results"] if last.get("results") else 0.0

    metrics: dict[str, Any] = {
        "frames_total": len(starts),
        "frames_measured": len(measured),
        "mean_fps_measured": round(len(measured) / (window * len(windows)), 2),
        "window_fps": [round(v, 2) for v in window_fps],
        "latency_ms": {
            "p50": round(statistics.median(measured), 2),
            "p95": round(percentile_nearest_rank(measured, 95), 2),
            "p99": round(percentile_nearest_rank(measured, 99), 2),
            "max": round(max(measured), 2),
        },
        "window_median_latency_ms": [round(v, 2) for v in window_median],
        "latency_degradation": round(degradation, 4),
        "peak_phys_footprint_bytes": max(footprints) if footprints else None,
        "max_thermal_state": THERMAL_STATES[thermal] if 0 <= thermal < len(THERMAL_STATES) else str(thermal),
        "battery_start_percent": round(levels[0] * 100, 1),
        "battery_end_percent": round(levels[-1] * 100, 1),
        "battery_drop_points": battery_drop,
        "battery_resolution_points": 5 if coarse else 1,
        "memory_warnings": sum(1 for e in run.get("events", []) if e.get("kind") == "memory_warning"),
        "detection_rate": round(detection_rate, 3),
        "compiled_model_bytes": run.get("model", {}).get("compiled_bytes"),
    }
    if not footprints:
        issues.append("no memory reading in any sample")
    if coarse:
        notes.append("battery level was reported in 5-point steps; the true drop is within about 5 points of the value")
    if detection_rate == 0:
        notes.append("no frame had a detection above the confidence threshold; check that the scene was in view")

    gates = (
        Gate("package_size", model["package_bytes"] if model else math.inf, limits["package_bytes_max"], True, "bytes"),
        Gate("sustained_fps", min(window_fps), limits["sustained_fps_min"], False, "fps"),
        Gate("p95_latency", metrics["latency_ms"]["p95"], limits["p95_latency_ms_max"], True, "ms"),
        Gate(
            "peak_memory",
            max(footprints) if footprints else math.inf,
            limits["peak_memory_bytes_max"],
            True,
            "bytes",
        ),
        Gate(
            "thermal_state",
            thermal,
            THERMAL_STATES.index(limits["thermal_state_max"]),
            True,
            "level (0 nominal, 1 fair, 2 serious, 3 critical)",
        ),
        Gate("latency_degradation", round(degradation, 4), limits["latency_degradation_max"], True, "fraction"),
        Gate("battery_drop", battery_drop, limits["battery_drop_points_max"], True, "points"),
    )
    return BenchmarkReport(model_version, tuple(issues), tuple(notes), metrics, gates)


def _frame_issues(starts: Sequence[float], durations: Sequence[float]) -> list[str]:
    if not starts:
        return ["no frames recorded"]
    if len(starts) != len(durations):
        return [f"{len(starts)} frame start times but {len(durations)} durations"]
    issues = []
    if any(later < earlier for earlier, later in zip(starts, starts[1:])):
        issues.append("frame start times are not in order")
    if any(not math.isfinite(d) or d <= 0 for d in durations):
        issues.append("a frame duration is not a positive number")
    return issues


def _sample_issues(
    samples: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    settings: Mapping[str, Any],
) -> list[str]:
    issues = []
    first = samples[0]
    if first.get("thermal_state") != 0:
        issues.append(f"run started with thermal state {first.get('thermal_state')}, not nominal")
    if first.get("battery_level", -1) < settings["min_start_battery"]:
        issues.append(f"run started with battery level {first.get('battery_level')}")
    if any(s.get("battery_state") != "unplugged" for s in samples):
        issues.append("the phone was not unplugged for the whole run")
    if any(s.get("low_power_mode") for s in samples):
        issues.append("Low Power Mode was on during the run")
    if any(abs(s.get("screen_brightness", -1) - settings["screen_brightness"]) > 0.01 for s in samples):
        issues.append("screen brightness changed during the run")
    times = [s.get("t", 0) for s in samples]
    gap = max((b - a for a, b in zip(times, times[1:])), default=0)
    if gap > settings["max_sample_gap_seconds"]:
        issues.append(f"a {gap:.1f} s gap between device samples")
    if times[-1] < settings["duration_seconds"] - settings["max_sample_gap_seconds"]:
        issues.append(f"samples end at {times[-1]:.1f} s, before the {settings['duration_seconds']} s run length")
    for event in events:
        if event.get("kind") in INVALIDATING_EVENTS:
            issues.append(f"app resigned active at {event.get('t')} s (touch, call, or Control Center)")
    return issues


def _same_setting(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)) and not isinstance(actual, bool):
        return math.isclose(actual, expected, rel_tol=1e-6)
    return actual == expected


def _major(version: Any) -> int | None:
    try:
        return int(str(version).split(".")[0])
    except ValueError:
        return None


def _frange(start: float, stop: float, step: float) -> list[float]:
    count = int(round((stop - start) / step))
    return [start + index * step for index in range(count)]


def _format(value: float) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.4g}" if abs(value) < 1 else f"{value:,.2f}"
    return f"{int(value):,}" if math.isfinite(value) else str(value)
