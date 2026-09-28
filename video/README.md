# AWARE motion piece

A 60-second, 1920×1080, 60 fps motion-graphics film about the AWARE app. It
follows one plastic bottle through the app: scanned on-device, sorted by
Hanoi's rules, turned into leaves on the dashboard, and shown next to a
community project made from bottles.

Everything is code. The screens are rebuilt from the SwiftUI source (colours
from `awareapp/DesignSystem/Theme.swift`, glass from `Glass.swift`, copy and
demo data from the views), the bottle and the seven waste classes are vector
illustrations, and the score and sound effects are synthesized. Nothing needs a
licence.

## Structure

| Time | Act | File |
|---|---|---|
| 0:00 | Cold open: "Is this recyclable?", "Stop guessing." | `src/act1.js` |
| 0:06 | The leaf draws itself; AWARE unpacks into its acronym | `src/act2.js` |
| 0:11 | Point. Scan. Know.: leaf portal, detection, seven classes | `src/act3.js` |
| 0:23 | Results in layers, +20 leaves and CO₂e, the recycling steps | `src/act4.js` |
| 0:34 | Leaves fly home, dashboard in 3D, leaderboard | `src/act5.js` |
| 0:44 | Recycling Map of Hoàn Kiếm, then the Gallery | `src/act6.js` |
| 0:54 | Leaves converge into the logo; end card | `src/act7.js` |

- `src/engine.js`: the animation engine. Every frame is a pure function of time
  (`seek(t)`): easing curves, springs, keyframes and scene activation. There are
  no CSS transitions and no wall-clock timing, so renders are frame-exact.
- `src/art.js`: the hero bottle (with a cap that unscrews, liquid that stays
  level when tilted and a body that squashes), the seven class illustrations
  and the icons.
- `src/common.js`: shared pieces (brand bracket, phone, scan screen, odometer,
  leaf bursts).
- `audio/build_audio.py`: the 120 BPM score (D, Bm, G, A, resolving to D on the
  end card) and about 120 sound effects cued to the timeline.

## Build

Requirements: Node 18+ with Playwright's Chromium, Python 3 with `numpy`,
`scipy`, `pillow` and `imageio-ffmpeg` (or an `ffmpeg` on the path).

```sh
# from the repository root
python3 video/tools/prepare_assets.py      # derive images from the asset catalog
python3 video/audio/build_audio.py         # writes video/out/mix.wav, music.wav, sfx_only.wav

cd video
node render/render.mjs --out out/aware-motion.mp4 --audio out/mix.wav --workers 4
```

Useful options: `--from`/`--to` render a time range, `--scale 0.5` renders a
quick half-size preview, `--audio out/sfx_only.wav` gives a version without
music.

To scrub the film in a browser, open `video/index.html` (Chromium-based
browsers; allow file access). Space plays, arrow keys step, `?t=34` opens at a
time. `node render/preview.mjs <dir> 12.5 30` saves stills for review.

Rendered files go to `video/out/`, which git ignores.

Fonts: Bricolage Grotesque and Inter, both under the SIL Open Font License,
served locally from `assets/fonts/` so renders don't depend on the network.
