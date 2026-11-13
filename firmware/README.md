# Bin firmware: MVP

The first firmware for the sorting bin. It uses only three parts: the
ESP32-S3 N16R8 CAM board, its OV2640 camera, and one servo. When an item
lands on the plate and stops moving ([automatic scans](#automatic-scans)), or
when you press the board's **BOOT** button (or type `scan`), it:

1. takes a 640 × 480 photo of the plate,
2. sends it to the detection server over HTTPS (or, in [LLM mode](#llm-mode),
   straight to an OpenAI model),
3. routes the detections with routing-v1 (below),
4. turns the servo to that stream's angle, holds it for 1 s, and returns home.

If anything fails (no Wi-Fi, no server, a bad reply), it **holds**: the servo
stays home and the serial log says why.

The board's RGB LED shows where a scan is:

| LED | Means |
|---|---|
| blue | an item was spotted (or BOOT, or `scan`): scanning |
| green | sorted: the servo turned to a bin |
| red | held: something failed and the servo stayed home |

Green and red stay on for 3 s, then the LED goes dark. The LED is the
WS2812 on GPIO 48, built into ESP32-S3 DevKitC-1 style boards; `LED_PIN`,
`LED_BRIGHTNESS` and `LED_RESULT_MS` in `include/config.h` change it.

Not in the MVP: fill sensors, the display, the drawer switches and relay, and
the yaw-then-tilt pair of servos. An [IMU](#imu-mpu-6050-optional) under the
plate is optional: without one the bin runs as described here.

## Automatic scans

Ten times a second the board shrinks the camera's latest frame to 80 × 60
grey pixels and compares it with two others: the frame from the last check,
and the empty plate. It scans when more than 1% of the plate differs from the
empty plate and nothing has moved for two checks in a row, about 0.2 s after
the item stops. So the photo shows the item at rest, not falling, and a hand
or a shadow that passes and leaves nothing behind doesn't trigger a scan.
After each scan, whatever is on the plate becomes the new empty plate. While
the plate is empty, the empty plate keeps updating, so slow changes in the
light don't trigger a scan either.

Things to know:
- A sudden lasting change, such as lights switched on, triggers one scan. The
  server finds nothing, so the empty plate tips into `other`. With the
  [IMU](#imu-mpu-6050-optional), a change over 80% of the view that the
  plate didn't feel is taken as the light instead.
- An item that looks almost like the plate (white tissue on a white plate)
  may change too little to trigger. Press **BOOT** for those. The IMU
  catches the ones heavy enough to jolt the plate, but not a tissue.
- It only watches while the servo is at home, so `servo <angle>` doesn't set
  it off.
- `auto off` stops it, for example while you aim the camera by hand. It's
  back on after every restart.
- The thresholds in `include/config.h` (`WATCH_*`) are first guesses. Tune
  them on the bin with the `[watch]` log lines.
- The simulator has no live camera, so there only an impact on its
  MPU-6050 starts a scan ([Simulator](#simulator-no-board-needed)). Or use
  the green button.

## Routing (routing-v1, approved 2026-10-17)

| Stream | Liner | Classes |
|---|---|---|
| `paper` | 1 | `paper` |
| `plastic_bottles` | 2 | `plastic_bottle` |
| `other` | 3 and 4 | everything else |

If every detected item belongs to one stream, the whole plate goes there.
Items for more than one stream go to `other`. So does the plate when nothing
is detected, when any detection is below the confidence limit (`conf`,
default 0.5, a placeholder until it is set on bin photos), or when a label is
not an ontology v4 class. One servo can point at only one place per stream,
so `other` has one angle.

## Wiring

| Servo wire | Goes to |
|---|---|
| Signal (orange or yellow) | GPIO 14 |
| + (red) | + of a separate 5–6 V supply that can give 2 A or more |
| − (brown or black) | − of that supply **and** a GND pin on the board |

Do not power the servo from the board's 5 V pin. An MG996R can draw over 2 A
when it starts, which resets the ESP32. Both grounds must be joined, or the
signal has no reference. A large capacitor (470–2200 µF, 10 V or more) across
the servo supply helps. Test with the horn free before fixing anything to it.

## IMU (MPU-6050, optional)

An MPU-6050 (accelerometer and gyro) fixed under the plate tells the bin how
the plate really sits, since the servo has no feedback of its own. It can't
weigh anything: it feels tilt and jolts.

| MPU-6050 pin | Goes to |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 1 |
| SCL | GPIO 2 |
| AD0 | leave open (address 0x68), or 3V3 for 0x69 |
| INT, XDA, XCL | not used |

It uses I²C port 0 at 100 kHz; the camera has port 1. Wire it with the board
off. Fix it flat and close to the tilt axis, where the plate's own motion
disturbs the reading least, and give the wires a slack loop with strain
relief, because they bend on every tip. Twist SDA and SCL with GND if they
run near the servo's wires. The pins and every threshold below are in
`include/config.h` (`IMU_*`).

What it does once found (the bin logs `[imu] MPU-6050 at 0x68` at start):

- **Before each scan** the plate must be level within 3° at home, or the
  scan holds: `[hold] the plate is 6.2° off level at home`.
- **After each tip** the log says how far the plate went and whether it came
  back: `[imu] tipped to 44.8°, back at 0.4°`. The LED turns red if the
  plate tipped less than 10° (stuck, or the servo stalled) or isn't level
  back home.
- **`servo` and `angle`** print the plate's real tilt (`[imu] plate at
  22.5° from level`), so you can set the angles by the plate rather than the
  servo.
- **Automatic scans** weigh what the plate felt with what the camera saw
  (`include/presence.h`):

| Camera, once nothing moves | Plate felt | The bin |
|---|---|---|
| 0.2% or more changed | an impact | scans |
| 1% or more changed | nothing | scans (an item too light to feel) |
| 80% or more changed | nothing | takes it as the light and watches the new view |
| under 0.2% changed, 1 s on | an impact | logs a bump and doesn't scan |

The servo's own starts and stops jolt the plate too, so impacts only count
with the servo home and still for 0.5 s.

Without the chip the bin runs as before, and looks for one every second, so
a loose wire that comes back is picked up again. `imu off` makes the bin
ignore it (saved).

First run with the IMU:

1. `imu`: the chip, the tilt, and the gravity it reads. At rest gravity
   should be close to 1.00 g; if not, the chip's range differs from the
   MPU-6050's. The plate should read `still` with the servo holding home;
   if it always reads `moving`, the servo's hum shakes it more than
   `IMU_STILL_G` (0.03 g) allows, so raise that.
2. With the plate home, check it is level with a spirit level (adjust
   `angle home` until it is), then type `imu level`. Tilt reads from there
   on, however the chip is fixed. Until then it assumes the chip lies flat.
3. Drop a few items and read the impacts in `imu`
   (`Impacts: 3, the last 0.42 g`) and the `[watch]` lines. Raise
   `IMU_IMPACT_G` (0.08 g) if the servo's hum or the room counts as an
   impact; lower it if light items go unfelt.

## Build and flash

The firmware uses Arduino core 3.3.12 (PlatformIO platform `espressif32`
8.0.0), built as a component of ESP-IDF 5.5.5 so that `sdkconfig.defaults`
can change ESP-IDF settings, such as the network buffers (see Speed). The
first build of each environment takes 2–4 minutes and downloads about
600 MB of ESP-IDF components into `managed_components/` (git ignores it);
later builds take seconds. After editing `sdkconfig.defaults`, delete
`sdkconfig.esp32s3cam` and `sdkconfig.sim` so they are made again.

PlatformIO is installed in `~/.platformio/penv`. Plug the board in with the
USB-C port marked **COM** or **UART** (the serial log comes out there), then
run from the repository root:

```sh
~/.platformio/penv/bin/pio run -d firmware -e esp32s3cam -t upload
```

If the upload cannot connect, hold **BOOT**, tap **RST**, release **BOOT**,
and run it again. Then press **RST** to start the new firmware.

To see the log and type commands:

```sh
~/.platformio/penv/bin/pio device monitor -d firmware --no-reconnect
```

Exit with Ctrl+C. `--no-reconnect` makes the monitor quit when the board is
unplugged; without it, the monitor waits for the board to come back.

Type `feed` to open the [viewer](#viewer)'s window from the monitor, with the
live camera, the last scan and the scan's stage; the monitor keeps working
beside it. `feed off` or closing the window stops it. Photos never print as
text in the monitor (`monitor/filter_aware_feed.py` keeps them out); the
window shows them.

The board draws a prompt like zsh's robbyrussell theme and keeps it on the
last line, with the log scrolling above it:

```
➜  aware-bin status
```

The arrow turns red after a command that failed. Up and Down go through the
last 20 commands, Tab completes commands and the names after `angle` and
`auto`, and Left/Right, Ctrl+A/E, Ctrl+W (delete a word), Ctrl+U (clear the
line) and Ctrl+L (clear the screen) work as in a shell. `status` shows the
bin at a glance, neofetch style.

The serial speed is 2 Mbit/s (`SERIAL_BAUD` in `include/config.h`, and
`monitor_speed` in `platformio.ini`), fast enough for the viewer's live view.
The chip's own boot messages stay at 115200, so a few garbled characters at
reset are normal.

The log is color coded, here and in the [viewer](#viewer). Red means the
board held (the servo stays home), a connection failed or the chip crashed;
yellow is a warning. The steps of a scan: `[watch]` and `[camera]` cyan,
`[scan]` green, `[route]` bold green, `[servo]` and `[imu]` magenta, `[wifi]` and `[link]`
blue, `[time]` grey. The rules are in `scripts/log_colors.py`;
`NO_COLOR=1` turns the colors off.

The routing rule (`include/routing.h`), the IMU's arithmetic
(`include/imu_math.h`) and the camera-and-IMU rules (`include/presence.h`)
have unit tests that run on the Mac, without the board:

```sh
~/.platformio/penv/bin/pio test -d firmware -e native
```

The `native` env is only for these tests. Building it (rather than testing
it) stops with a reminder, because the firmware needs the ESP32 compiler.

The server address is built in from `include/local_settings.h`, which git
ignores. Copy `include/local_settings.example.h` to make one, or type
`server <url>` once; the board remembers it.

The server only accepts scans that carry the bin token. It lives in
`include/secrets.h`, which git also ignores: copy
`include/secrets.example.h` and paste the token. The build stops with a
reminder if the file is missing. A refused token shows as
`server refused the bin token` in the log.

## Viewer

`scripts/viewer.py` (or `feed` in the monitor) opens a window with the
camera's live view on the left
and the last scan on the right: its photo with the server's boxes and the
decision (or the photo from the last `snap`). A bar along the bottom follows
each scan like the LED: blue while scanning, green with the route when
sorted, red with the reason when held. Use it in place of the monitor. It
prints the same log, and lines typed in its terminal go to the board.

The live view runs while the window is open: the viewer sends the board a
heartbeat byte every second, and the board streams each camera frame over
the USB cable, about 7–8 frames a second for 12 KB frames, until a few
seconds after the window closes. It checks the plate for automatic scans on
the same frames. During a scan the stream pauses, and the bar says so.

One-time setup (Python packages in `firmware/.venv`, which git ignores):

```sh
python3 -m venv firmware/.venv
firmware/.venv/bin/pip install pyserial pillow
```

`feed` in the monitor opens the window without closing the monitor. To run
the viewer on its own instead, close the monitor first (only one program can
use the port), then:

```sh
firmware/.venv/bin/python firmware/scripts/viewer.py
```

If more than one USB serial port is plugged in, name the board's:
`viewer.py /dev/cu.usbserial-110`. Close the window, press Ctrl+C in the
terminal, or unplug the board to quit.

The board sends each photo as text at 2 Mbit/s, about 0.15 s for 30 KB. It
sends a scan's photo while the servo holds at the bin, so sorting is no
slower. With the simulator running, `viewer.py rfc2217://localhost:4000`
connects to it. The simulator has no live camera, so only scan photos show.

## Simulator (no board needed)

The [Wokwi](https://wokwi.com) extension for VS Code runs the real firmware
on a simulated ESP32-S3 with the servo, an MPU-6050 and a green button wired
to the BOOT pin (`diagram.json`). Wokwi has no camera, so the simulator build sends
photos from `sim/photos` instead, one per scan, in turn. Its Wi-Fi reaches
the internet, so scans go to the real detection server.

One-time setup: in VS Code press F1, run **Wokwi: Request a new License**,
and sign in with a free Wokwi account.

1. Build the simulator firmware: in the PlatformIO sidebar choose
   **sim → General → Build**, or run
   `~/.platformio/penv/bin/pio run -d firmware -e sim`.
2. Press F1 and run **Wokwi: Start Simulator**. The diagram opens with a
   terminal; it joins `Wokwi-GUEST` by itself.
3. Click the green button, or type `scan` in the terminal. Each scan sends
   the next photo and logs the server's reply and the route. Once the server
   runs the bin model, a paper photo should give:

```
[scan] photo 640x480, 34 KB (01_paper_envelope.jpg)
[scan] detected paper 0.88 box 0,0,612,480
[route] paper, liner 1: every item goes to paper
[servo] 90 -> 45
```

and the servo in the diagram turns. `photos` lists the photos and
`photo 3` picks the next one to send.

The MPU-6050 stands for the plate. Click it while the simulation runs to
change what it reads (or set `accelX`, `accelY` and `accelZ` in its `attrs`
in `diagram.json`). Any change counts as an impact and starts a scan, since
there is no camera to look. Lean it (`accelX` 0.2, about 11°) to see a scan
hold because the plate is off level. It doesn't tip when the servo turns, so
after each scan the log says the plate tipped 0° and the LED turns red.

### Simulator photos

`sim/photos` holds 11 photos on plain backgrounds from the **test split** of
the v4 bin release on VAST (`aware-bin-v4-seed26-r2`), so the model never
trained on them. `sim/photos/sources.json` records each one's source, image
ID, labelled classes, attribution and the stream it should go to:

| Photo | Source | Should go to |
|---|---|---|
| 01–02 paper | TrashNet | paper |
| 03–04 plastic bottle | Drinking Waste | plastic_bottles |
| 05 fork | Kaggle utensils | other |
| 06 tissue | kitchen-tissue | other |
| 07 food wrappers, 08 food containers | TOD | other |
| 09 paper + bottle, 10 cup + bottle | TOD | other (mixed) |
| 11 empty floor | crop of photo 10 | other (nothing detected) |

To add photos, put JPEG, PNG or HEIC files in `sim/photos` (they are shrunk
to 640 px) and build `sim` again. Git ignores them, like the `demo/` videos.

What the simulator can't show: the camera itself, the servo's real torque,
the plate tipping, and power problems such as the board resetting when the
servo starts.

## First run

Type these in the monitor:

```
ssid <your 2.4 GHz network>
pass <its password>
connect
status
```

`status` should show `Camera: 640x480, JPEG quality 12`, `Auto scan: on`,
the network with its signal (`joining` for the first few seconds), and the
server as `connected`. Then:

0. `auto off`, so moving things around doesn't start scans while you set up.
1. `servo 45`, `servo 135`, `servo 90`: the servo should follow.
2. `angle paper 45`, `angle plastic_bottles 135`, `angle other 180`,
   `angle home 90`: saves each angle and shows it.
3. See what the camera sees: close the monitor (Ctrl+C) and start the
   [viewer](#viewer). Check that the whole plate is in view, in focus and
   the right way up.
4. `auto on`, wait for `[watch] plate empty, watching`, then drop an item on
   the plate. The viewer shows the photo with its boxes and the decision.
   Expected log:

```
[watch] 5.2% of the plate changed and nothing moves: scanning
[scan] start
[scan] photo 640x480, 21 KB
[scan] detected plastic_bottle 0.91 box 207,108,428,480
[route] plastic_bottles, liner 2: every item goes to plastic_bottles
[servo] 90 -> 135
[time] photo 40 | connect 0 (kept open) | send 450 | wait 700 | read 2 | decide 3 | servo 150 | total 1345 ms
[servo] 135 -> 90
[scan] done
```

## Speed

The `[time]` line splits each scan from the press to the servo reaching the
bin, in milliseconds:

| Field | What it covers |
|---|---|
| photo | taking the photo |
| connect | DNS, TCP and TLS; 0 when the connection was already open |
| send | handing the photo to the network stack |
| wait | the rest of the upload, the server's work, and the reply's trip back |
| read | reading the reply |
| decide | parsing the reply and routing |
| servo | the servo turning to the bin's angle |

The board keeps one HTTPS connection to the server open between scans
(`server_link.cpp`), opens it once Wi-Fi joins, and reopens it when the
server closes it, so a scan normally skips the TLS handshake. A task of its
own does this, so a slow or failed connection (40 s on weak Wi-Fi) doesn't
hold up typed commands. The log shows `[link]` lines when that happens.

The server closes a connection after 5 minutes without a request; the board
then opens a new one in the background.

The upload was the slowest step. The prebuilt Arduino core lets only 5,760
bytes be in flight on a TCP connection, which is about 25 KB/s at the 230 ms
round trip from Vietnam to the US server: 0.75 s for a 23 KB photo, 1.8 s
for 50 KB. `sdkconfig.defaults` raises that to 64 KB, so a whole photo can
be in flight at once. A connection starts with about 5.7 KB in flight and
doubles that each round trip, so the first scan on a new connection still
takes a few round trips; later scans on the same connection don't.

Measured from a Mac in Vietnam with the board's TLS version and send
buffer, upload + server + reply on a kept-open connection:

| Photo | 5.7 KB buffer (before) | 64 KB buffer (now) |
|---|---:|---:|
| 23 KB | 1.06 s | 0.36 s |
| 31 KB | 1.27 s | 0.42 s |
| 50 KB | 2.10 s | 0.37 s |

To measure from the Mac the way the board sends scans (same headers, TLS
version and send buffer), with the address from `include/local_settings.h`:

```sh
cd firmware
BIN_TOKEN=<token> python3 scripts/measure_latency.py sim/photos/*.jpg
```

`SEND_BUFFER=5760` in front mimics the old 5.7 KB buffer.

`speed` sets the servo's speed in degrees a second (default 300; 0 lets the
servo go at its own top speed).

## LLM mode

`mode llm` sends each photo from the board straight to an OpenAI model
(GPT-6-Luna by default) instead of to the detection server. The model lists
the items it sees, and routing-v1 routes them as it routes the server's
boxes. `mode yolo` switches back. The mode is saved.

The board talks to the ChatGPT Codex backend
(`chatgpt.com/backend-api/codex/responses`), the server OpenAI's Codex CLI
uses, with a ChatGPT sign-in of its own, so it needs no OpenAI API key. This
is not a published API: OpenAI can change or block it at any time, and a
ChatGPT plan's terms may not cover this use. Use it for tests.

### Sign in

Once, with the board on Wi-Fi:

```
llm login
```

The board prints a code. Open https://auth.openai.com/codex/device on a phone
or the Mac, sign in to ChatGPT and enter the code within 15 minutes. `status`
then shows `ChatGPT: signed in as <email>, token good for 9 days`. If the
sign-in fails at once, device-code sign-in may need turning on in ChatGPT's
security settings (as `codex login --device-auth` may need).

The board saves the tokens and renews them a day before they run out (they
last 10 days), in the background, so a scan never waits for the sign-in. It
needs the time for that, which it gets from the internet once Wi-Fi joins.
`llm logout` forgets the sign-in.

The board signs in on its own rather than taking a copy of the Mac's Codex
sign-in: each renewal replaces the renewal token, so two programs sharing
one sign-in would log each other out. Anyone with the board can read the
tokens from its flash, so sign out (`llm logout`) before you lend it.

### What changes in LLM mode

Expected log:

```
[scan] start
[scan] photo 640x480, 23 KB
[scan] asking gpt-6-luna
[scan] gpt-6-luna saw plastic_bottle
[route] plastic_bottles, liner 2: every item goes to plastic_bottles
```

- There are no boxes, so the viewer shows the photo and the decision only.
- `conf` doesn't apply: the model gives no confidence.
- The model may name an item with no v4 class (`drink_carton`, `can`,
  `hazard`, `other`, ...). The plate then goes to other.
- The board holds when no answer comes within 15 s (`LLM_TIMEOUT_MS`), when
  ChatGPT refuses the sign-in (401: it renews the token; scan again), and at
  the plan's usage limit (429).
- `llm model <name>` picks another model, for example `gpt-6-sol`.

The question the model gets is in `include/llm_prompt.h`: the 7 v4 classes
plus 11 labels for common items with no class (drink cartons, food waste,
foam boxes, cans, straws, chopsticks, pens, masks, glass, hazards such as
batteries, and other). Those 11 all send the plate to other, as an item with
no class always has. The model, its reasoning effort (`low`) and the image
detail (`high`) are in `include/config.h`. The board sends the photo as base64 inside the JSON
request, and the reply streams 15–25 KB of events, from which the board
takes the answer.

### Speed

From a Mac in Vietnam on 2026-11-07, the answer took 1.3–4.8 s (median about
1.8 s) over the 11 simulator photos sent twice, against about 0.4 s for the
detection server. Most of it is the model's server: usually 0.6–1.6 s before
the first byte comes back, then 0.5–1 s for the answer. 20 of the 22 went to
the right stream; both misses were photo 10, where the model took the small
paper cup among four bottles for a bottle, so a mixed plate went to
`plastic_bottles` (in an earlier run it got the same photo right 3 times out
of 3). The simulator photos are from the test split, so don't tune the prompt
on them; use bin photos. These did not make it faster:
OpenAI's priority tier, a WebSocket instead of HTTPS, HTTP/2, a 320 × 240
photo, and dropping the JSON schema. With the 18-label prompt, reasoning
`low` and `none` both routed all 22 right, at a median of 1.6 s and 1.8 s
(`llm_latency.py --effort none` compares them).

To time it from the Mac with the board's exact request (it uses the Mac's
own Codex sign-in in `~/.codex/auth.json`, read only):

```sh
cd firmware
python3 scripts/llm_latency.py --rounds 2 sim/photos/*.jpg
```

It prints each photo's time, the model's items and the stream they route
to, checked against `sim/photos/sources.json`.

Not yet: saving the photo with the model's labels and boxes as training
data, and a mode that asks the model only when the detection server is
unsure.

## Commands

| Command | Does |
|---|---|
| `status` | the bin at a glance: settings, connection, memory |
| `ssid <name>`, `pass <password>`, `connect` | join Wi-Fi (2.4 GHz only); saved |
| `server <url>` | detection server address; saved |
| `mode [yolo\|llm]` | who names the items: the detection server (yolo) or an LLM ([LLM mode](#llm-mode)); saved |
| `llm login`, `llm logout` | sign the board in to ChatGPT for LLM mode, or forget the sign-in |
| `llm model <name>` | the model LLM mode asks (default `gpt-6-luna`); saved |
| `llm` | the ChatGPT sign-in and the model |
| `conf <0.05-0.95>` | lowest confidence routed to a recycling liner (yolo mode); saved |
| `speed <0-1000>` | servo speed in degrees a second, 0 for its top speed; saved (default 300) |
| `quality <4-63>` | camera JPEG quality, lower is sharper and bigger; saved (default 12) |
| `servo <0-180>` | turn the servo now |
| `angle <home\|paper\|plastic_bottles\|other> <0-180>` | save and show an angle |
| `snap` | take a photo and send it to the viewer, without the server |
| `scan` | photo → server → servo, same as BOOT |
| `auto on\|off` | [automatic scans](#automatic-scans); on after every restart |
| `imu` | what the [IMU](#imu-mpu-6050-optional) reads: tilt, shake, impacts |
| `imu level` | save the plate's tilt now as level (plate home and level) |
| `imu on\|off` | use the IMU's checks, or ignore it; saved |
| `reboot` | restart |

Commands work at any time, even during a scan or while the board is
connecting to the server. The board runs five tasks (`main.cpp`): one
reads what you type and runs the commands that only read or save settings
at once; one owns the camera and servo; one keeps the server connection;
one signs in to ChatGPT and renews the sign-in (`llm.cpp`); one reads the
IMU (`imu.cpp`).
`scan`, `snap`, `servo` and `angle` need the camera or servo, so while
either is busy they wait their turn, up to 8 at a time, and a yellow
`[busy]` line says so. A `scan` or BOOT press while a scan is running or
waiting is skipped, so an item is never tipped twice. `connect` returns at
once; a `[wifi]` line reports how joining went. A scan without Wi-Fi holds
instead of joining first.

## Server contract

The detection server is `server/app.py`, a [Modal](https://modal.com) app
(`smart-bin-api`). Deploy it from the repository root with
`modal deploy server/app.py`. Its `/config` repeats routing-v1 for the demo
page, so a change to `include/routing.h` goes there too.

In yolo mode, `POST` the raw JPEG as the body with `Content-Type: image/jpeg`
and the bin token in `X-Bin-Token`. ([LLM mode](#llm-mode) doesn't use this
server.) The reply:

```json
{"count": 1, "objects": [{"label": "plastic_bottle", "conf": 0.91, "box": [207, 108, 428, 480]}], "image_size": [640, 480]}
```

`box` is `[x1, y1, x2, y2]` in pixels of the sent photo. HTTPS trusts the
ISRG Root X1 and X2 certificates in `include/ca_certs.h` (Let's Encrypt). A
server with a certificate from another authority needs its root added there.
