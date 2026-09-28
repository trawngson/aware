#!/bin/bash
# Builds the app for an iOS simulator, runs RenderCheckUITests once per
# appearance, and collects the screenshots.
#
# Usage: .github/scripts/ios-render-check.sh <output-dir>
# Env:   IOS_VERSION   simulator runtime version (default 27.0)
#        DEVICE        simulator device type (default "iPhone 18 Pro")
#        SIMULATOR     "new" (default) creates a simulator and deletes it on exit;
#                      "existing" uses this machine's simulator named DEVICE on that
#                      runtime (a booted one first), creating one only if none exists
#        APPEARANCES   "light dark" (default), "light" or "dark"
#        RENDER_STEPS  steps for the UI test, e.g. "tap:Recycling Map | shot:map";
#                      empty runs the full tour (see RenderCheckUITests)
#        RECORD_VIDEO  1 to also record <appearance>.mp4
#        CACHE_DIR     keeps downloaded Swift packages here, so later runs (or CI
#                      with this directory cached) skip fetching them
#
# Output: <output-dir>/<appearance>/NN-name.png and <output-dir>/<appearance>.xcresult
# (plus <appearance>.mp4 when recording). An existing simulator gets its status
# bar and appearance back and is shut down again if the script booted it; the
# app and test runner stay installed on it.
set -euo pipefail

OUT=${1:?usage: ios-render-check.sh <output-dir>}
IOS_VERSION=${IOS_VERSION:-27.0}
DEVICE=${DEVICE:-iPhone 18 Pro}
APPEARANCES=${APPEARANCES:-light dark}
RENDER_STEPS=${RENDER_STEPS:-}
RECORD_VIDEO=${RECORD_VIDEO:-}
SIMULATOR=${SIMULATOR:-new}

cd "$(dirname "$0")/../.."
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
DERIVED=$(mktemp -d)/DerivedData

PACKAGE_FLAGS=()
if [ -n "${CACHE_DIR:-}" ]; then
    mkdir -p "$CACHE_DIR"
    PACKAGE_FLAGS=(-clonedSourcePackagesDirPath "$(cd "$CACHE_DIR" && pwd)/SourcePackages")
fi

RUNTIME=$(xcrun simctl list runtimes -j | python3 -c '
import json, sys
for runtime in json.load(sys.stdin)["runtimes"]:
    if runtime["name"].startswith("iOS") and runtime["version"] == sys.argv[1] and runtime.get("isAvailable"):
        print(runtime["identifier"])
        break
' "$IOS_VERSION")
if [ -z "$RUNTIME" ]; then
    echo "No available iOS $IOS_VERSION simulator runtime:" >&2
    xcrun simctl list runtimes >&2
    exit 1
fi

UDID=
STATE_BEFORE=
if [ "$SIMULATOR" = existing ]; then
    # A booted one first: it skips the boot entirely.
    read -r UDID STATE_BEFORE < <(xcrun simctl list devices -j available | python3 -c '
import json, sys
runtime, name = sys.argv[1:]
devices = [d for d in json.load(sys.stdin)["devices"].get(runtime, []) if d["name"] == name]
devices.sort(key=lambda d: d["state"] != "Booted")
if devices:
    print(devices[0]["udid"], devices[0]["state"])
' "$RUNTIME" "$DEVICE") || true
    if [ -z "$UDID" ]; then
        echo "== No \"$DEVICE\" simulator on iOS $IOS_VERSION, so creating one. Simulators there:"
        xcrun simctl list devices "iOS $IOS_VERSION" available
    fi
elif [ "$SIMULATOR" != new ]; then
    echo "SIMULATOR must be new or existing, not $SIMULATOR" >&2
    exit 1
fi

APPEARANCE_BEFORE=
if [ -n "$UDID" ]; then
    echo "== Simulator: $DEVICE, iOS $IOS_VERSION ($UDID, existing, $STATE_BEFORE)"
    cleanup() {
        xcrun simctl status_bar "$UDID" clear >/dev/null 2>&1 || true
        if [ -n "$APPEARANCE_BEFORE" ]; then
            xcrun simctl ui "$UDID" appearance "$APPEARANCE_BEFORE" >/dev/null 2>&1 || true
        fi
        if [ "$STATE_BEFORE" != Booted ]; then
            xcrun simctl shutdown "$UDID" >/dev/null 2>&1 || true
        fi
    }
else
    UDID=$(xcrun simctl create "AWARE render check" "$DEVICE" "$RUNTIME")
    echo "== Simulator: $DEVICE, iOS $IOS_VERSION ($UDID, new)"
    cleanup() {
        xcrun simctl shutdown "$UDID" >/dev/null 2>&1 || true
        xcrun simctl delete "$UDID" >/dev/null 2>&1 || true
    }
fi
trap cleanup EXIT
# Booting in parallel with the build was tried: the build ran about three times
# slower and the job was no faster (xcode-27 runner times vary by minutes).
start=$SECONDS
xcrun simctl bootstatus "$UDID" -b >/dev/null
echo "   booted in $((SECONDS - start))s"
if [ -n "$STATE_BEFORE" ]; then
    APPEARANCE_BEFORE=$(xcrun simctl ui "$UDID" appearance 2>/dev/null || true)
fi
# A fixed status bar keeps screenshots comparable between runs.
start=$SECONDS
xcrun simctl status_bar "$UDID" override --time 9:41 --batteryState charged --batteryLevel 100 --wifiBars 3
echo "   status bar set in $((SECONDS - start))s"

DESTINATION="platform=iOS Simulator,id=$UDID"

echo "== Building (Xcode: $(xcodebuild -version | awk 'NR == 1'))"
start=$SECONDS
# ${a[@]+"${a[@]}"}: macOS's bash 3.2 treats an empty array as unset under set -u.
xcodebuild build-for-testing -project awareapp.xcodeproj -scheme awareapp \
    -destination "$DESTINATION" -derivedDataPath "$DERIVED" ${PACKAGE_FLAGS[@]+"${PACKAGE_FLAGS[@]}"} \
    CODE_SIGNING_ALLOWED=NO -quiet
echo "   built in $((SECONDS - start))s"

echo "== Steps: ${RENDER_STEPS:-full tour}"
status=0
for appearance in $APPEARANCES; do
    echo "== Capturing in $appearance appearance"
    xcrun simctl ui "$UDID" appearance "$appearance"
    recorder=
    if [ "$RECORD_VIDEO" = 1 ] || [ "$RECORD_VIDEO" = true ]; then
        xcrun simctl io "$UDID" recordVideo --codec h264 --force "$OUT/$appearance.mp4" >/dev/null 2>&1 &
        recorder=$!
        sleep 2
    fi
    # Parallel testing would run the test on a clone of this simulator, which
    # has neither the chosen appearance nor the status bar override.
    if ! TEST_RUNNER_RENDER_DIR="$OUT/$appearance" TEST_RUNNER_RENDER_STEPS="$RENDER_STEPS" \
        xcodebuild test-without-building -project awareapp.xcodeproj -scheme awareapp \
        -destination "$DESTINATION" -derivedDataPath "$DERIVED" \
        -only-testing:awareappUITests/RenderCheckUITests -parallel-testing-enabled NO \
        -resultBundlePath "$OUT/$appearance.xcresult" -quiet; then
        echo "!! Render check failed in $appearance appearance; see $OUT/$appearance.xcresult" >&2
        status=1
    fi
    if [ -n "$recorder" ]; then
        kill -INT "$recorder"
        for _ in $(seq 20); do kill -0 "$recorder" 2>/dev/null || break; sleep 0.5; done
    fi
    echo "   $(find "$OUT/$appearance" -name '*.png' 2>/dev/null | wc -l | tr -d ' ') screenshots in $OUT/$appearance"
done
exit $status
