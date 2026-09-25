#!/bin/bash
# Builds the app for an iOS simulator, runs RenderCheckUITests once per
# appearance, and collects the screenshots.
#
# Usage: .github/scripts/ios-render-check.sh <output-dir>
# Env:   IOS_VERSION   simulator runtime version (default 27.0)
#        DEVICE        simulator device type (default "iPhone 18 Pro")
#        APPEARANCES   "light dark" (default), "light" or "dark"
#        RENDER_STEPS  steps for the UI test, e.g. "tap:Recycling Map | shot:map";
#                      empty runs the full tour (see RenderCheckUITests)
#        RECORD_VIDEO  1 to also record <appearance>.mp4
#        CACHE_DIR     keeps downloaded Swift packages here, so later runs (or CI
#                      with this directory cached) skip fetching them
#
# Output: <output-dir>/<appearance>/NN-name.png and <output-dir>/<appearance>.xcresult
# (plus <appearance>.mp4 when recording). The simulator it creates is deleted on exit.
set -euo pipefail

OUT=${1:?usage: ios-render-check.sh <output-dir>}
IOS_VERSION=${IOS_VERSION:-27.0}
DEVICE=${DEVICE:-iPhone 18 Pro}
APPEARANCES=${APPEARANCES:-light dark}
RENDER_STEPS=${RENDER_STEPS:-}
RECORD_VIDEO=${RECORD_VIDEO:-}

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

UDID=$(xcrun simctl create "AWARE render check" "$DEVICE" "$RUNTIME")
trap 'xcrun simctl shutdown "$UDID" >/dev/null 2>&1 || true; xcrun simctl delete "$UDID" >/dev/null 2>&1 || true' EXIT
echo "== Simulator: $DEVICE, iOS $IOS_VERSION ($UDID)"
# A new simulator's first boot takes minutes on CI, so it boots while the app builds.
( xcrun simctl boot "$UDID" && xcrun simctl bootstatus "$UDID" -b >/dev/null ) &
booting=$!

DESTINATION="platform=iOS Simulator,id=$UDID"

echo "== Building (Xcode: $(xcodebuild -version | awk 'NR == 1'))"
start=$SECONDS
# ${a[@]+"${a[@]}"}: macOS's bash 3.2 treats an empty array as unset under set -u.
xcodebuild build-for-testing -project awareapp.xcodeproj -scheme awareapp \
    -destination "$DESTINATION" -derivedDataPath "$DERIVED" ${PACKAGE_FLAGS[@]+"${PACKAGE_FLAGS[@]}"} \
    CODE_SIGNING_ALLOWED=NO -quiet
echo "   built in $((SECONDS - start))s"

start=$SECONDS
wait "$booting"
echo "   simulator ready $((SECONDS - start))s after the build"
# A fixed status bar keeps screenshots comparable between runs.
xcrun simctl status_bar "$UDID" override --time 9:41 --batteryState charged --batteryLevel 100 --wifiBars 3

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
