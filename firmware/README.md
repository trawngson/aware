# Bin firmware: MVP

The first firmware for the sorting bin. It uses only three parts: the
ESP32-S3 N16R8 CAM board, its OV2640 camera, and one servo. When an item
lands on the plate and stops moving ([automatic scans](#automatic-scans)), or
when you press the board's **BOOT** button (or type `scan`), it:

1. takes a 640 × 480 photo of the plate,
2. sends it to the detection server over HTTPS,
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

Not in the MVP: fill sensors, the IMU, the display, the drawer switches and
relay, and the yaw-then-tilt pair of servos.

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
  server finds nothing, so the empty plate tips into `other`.
- An item that looks almost like the plate (white tissue on a white plate)
  may change too little to trigger. Press **BOOT** for those. The IMU is
  planned to catch them.
- It only watches while the servo is at home, so `servo <angle>` doesn't set
  it off.
- `auto off` stops it, for example while you aim the camera by hand. It's
  back on after every restart.
- The thresholds in `include/config.h` (`WATCH_*`) are first guesses. Tune
  them on the bin with the `[watch]` log lines.
- The simulator has no live camera, so there it doesn't run. Use the green
  button.

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
`[scan]` green, `[route]` bold green, `[servo]` magenta, `[wifi]` and `[link]`
blue, `[time]` grey. The rules are in `scripts/log_colors.py`;
`NO_COLOR=1` turns the colors off.

The routing rule lives in `include/routing.h` and has unit tests that run on
the Mac, without the board:

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
on a simulated ESP32-S3 with the servo and a green button wired to the BOOT
pin (`diagram.json`). Wokwi has no camera, so the simulator build sends
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
and power problems such as the board resetting when the servo starts.

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

## Commands

| Command | Does |
|---|---|
| `status` | the bin at a glance: settings, connection, memory |
| `ssid <name>`, `pass <password>`, `connect` | join Wi-Fi (2.4 GHz only); saved |
| `server <url>` | detection server address; saved |
| `conf <0.05-0.95>` | lowest confidence routed to a recycling liner; saved |
| `speed <0-1000>` | servo speed in degrees a second, 0 for its top speed; saved (default 300) |
| `quality <4-63>` | camera JPEG quality, lower is sharper and bigger; saved (default 12) |
| `servo <0-180>` | turn the servo now |
| `angle <home\|paper\|plastic_bottles\|other> <0-180>` | save and show an angle |
| `snap` | take a photo and send it to the viewer, without the server |
| `scan` | photo → server → servo, same as BOOT |
| `auto on\|off` | [automatic scans](#automatic-scans); on after every restart |
| `reboot` | restart |

Commands work at any time, even during a scan or while the board is
connecting to the server. The board runs three tasks (`main.cpp`): one
reads what you type and runs the commands that only read or save settings
at once; one owns the camera and servo; one keeps the server connection.
`scan`, `snap`, `servo` and `angle` need the camera or servo, so while
either is busy they wait their turn, up to 8 at a time, and a yellow
`[busy]` line says so. A `scan` or BOOT press while a scan is running or
waiting is skipped, so an item is never tipped twice. `connect` returns at
once; a `[wifi]` line reports how joining went. A scan without Wi-Fi holds
instead of joining first.

## Server contract

`POST` the raw JPEG as the body with `Content-Type: image/jpeg` and the bin
token in `X-Bin-Token`. The reply:

```json
{"count": 1, "objects": [{"label": "plastic_bottle", "conf": 0.91, "box": [207, 108, 428, 480]}], "image_size": [640, 480]}
```

`box` is `[x1, y1, x2, y2]` in pixels of the sent photo. HTTPS trusts the
ISRG Root X1 and X2 certificates in `include/ca_certs.h` (Let's Encrypt). A
server with a certificate from another authority needs its root added there.
