"""Synthesize the AWARE film's score and sound effects (no samples, no licences).

Writes, into video/out/:
  mix.wav       music + effects (the main soundtrack)
  music.wav     the 120 BPM score alone
  sfx_only.wav  the sound effects alone, for scoring the film with other music

Run from the repository root: python3 video/audio/build_audio.py
"""
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48000
DUR = 60.0
N = int(SR * DUR)
OUT = Path(__file__).resolve().parents[1] / "out"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(26)

BEAT = 0.5  # 120 BPM


# ----------------------------------------------------------------- helpers
def buf():
    return np.zeros((N, 2))


def place(bus, sig, t0, gain=1.0, pan=0.0):
    """Add a mono (or stereo) signal at time t0 with equal-power panning."""
    i0 = int(round(t0 * SR))
    if i0 >= N:
        return
    if sig.ndim == 1:
        a = (pan + 1) * np.pi / 4
        sig = np.stack([sig * np.cos(a), sig * np.sin(a)], axis=1)
    j0 = max(0, -i0)
    sig = sig[j0:]
    i0 = max(0, i0)
    n = min(len(sig), N - i0)
    bus[i0:i0 + n] += sig[:n] * gain


def tt(d):
    return np.arange(int(d * SR)) / SR


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, min(f, SR * 0.45), "low", fs=SR, output="sos"), x, axis=0)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "high", fs=SR, output="sos"), x, axis=0)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, min(hi, SR * 0.45)], "band", fs=SR, output="sos"), x, axis=0)


def noise(d):
    return rng.standard_normal(int(d * SR))


def expd(d, k):
    return np.exp(-tt(d) * k)


def fade(x, a=0.005, r=0.02):
    n = len(x)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    e = np.ones(n)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return x * e


def saw(f, d, phase=0.0):
    """PolyBLEP band-limited sawtooth."""
    n = int(d * SR)
    dt = f / SR
    p = (phase + dt * np.arange(n)) % 1.0
    y = 2 * p - 1
    m1 = p < dt
    x = p[m1] / dt
    y[m1] -= x + x - x * x - 1
    m2 = p > 1 - dt
    x = (p[m2] - 1) / dt
    y[m2] -= x * x + x + x + 1
    return y


def swept(d, f0, f1, bw=0.6, curve=1.0, seed=0):
    """Noise through a band-pass whose centre sweeps f0 -> f1 (STFT mask)."""
    x = np.random.default_rng(seed).standard_normal(int(d * SR) + 2048)
    f, tseg, Z = signal.stft(x, SR, nperseg=1024)
    prog = np.clip(tseg / d, 0, 1) ** curve
    fc = f0 * (f1 / f0) ** prog
    lf = np.log2(np.maximum(f, 1)[:, None] / fc[None, :])
    Z *= np.exp(-0.5 * (lf / bw) ** 2)
    _, y = signal.istft(Z, SR, nperseg=1024)
    return y[: int(d * SR)] / (np.abs(y).max() + 1e-9)


def reverb_ir(t60=2.0, seed=1, damp=5000):
    d = t60 * 1.2
    out = []
    for ch in range(2):
        r = np.random.default_rng(seed + ch)
        ir = r.standard_normal(int(d * SR)) * np.exp(-tt(d) * 6.9 / t60)
        ir = lp(ir, damp)
        ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
        out.append(ir / np.sqrt((ir ** 2).sum()))
    return out


def reverb(bus, t60=2.0, mix=0.25, seed=1, damp=5000):
    ir = reverb_ir(t60, seed, damp)
    wet = np.stack([signal.fftconvolve(bus[:, c], ir[c])[:N] for c in range(2)], axis=1)
    return bus + wet * mix


# ----------------------------------------------------------------- instruments
def kick(gain=1.0):
    d = 0.5
    t = tt(d)
    f = 44 + 96 * np.exp(-t * 34)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 7.5)
    click = hp(noise(0.012), 2500) * expd(0.012, 300) * 0.4
    body[: len(click)] += click
    return np.tanh(body * 1.6) * gain


def clap():
    d = 0.35
    x = bp(noise(d), 900, 5200)
    e = np.zeros(int(d * SR))
    for k, o in enumerate([0, 0.011, 0.023]):
        i = int(o * SR)
        seg = np.exp(-np.arange(len(e) - i) / SR * (60 if k < 2 else 14))
        e[i:] += seg
    return x * e * 0.5


def hat(open_=False):
    d = 0.2 if open_ else 0.06
    return hp(noise(d), 7500, 4) * expd(d, 16 if open_ else 70) * 0.35


def shaker():
    d = 0.09
    x = bp(noise(d), 5000, 11000)
    e = np.minimum(tt(d) / 0.012, 1) * np.exp(-tt(d) * 40)
    return x * e * 0.25


def bass(m, d):
    f = mtof(m)
    t = tt(d)
    x = np.sin(2 * np.pi * f * t) + 0.5 * lp(saw(f, d), 420)
    e = np.minimum(t / 0.006, 1) * (0.55 + 0.45 * np.exp(-t * 7)) * np.minimum(1, (d - t) / 0.03)
    return x * e * 0.5


def pad(notes, d, cutoff=1400, attack=0.5, release=1.2):
    t = tt(d + release)
    out = np.zeros((len(t), 2))
    for i, m in enumerate(notes):
        f = mtof(m)
        for j, det in enumerate((-0.12, 0.0, 0.12)):
            v = saw(f * 2 ** (det / 12), d + release, phase=(i * 0.37 + j * 0.21) % 1)
            pan = (j - 1) * 0.6
            a = (pan + 1) * np.pi / 4
            out[:, 0] += v * np.cos(a)
            out[:, 1] += v * np.sin(a)
    out = lp(out, cutoff, 2)
    e = np.minimum(t / attack, 1) * np.where(t < d, 1, np.maximum(0, 1 - (t - d) / release))
    return out * e[:, None] * (0.07 / np.sqrt(len(notes)))


def pluck(m, d=0.9, bright=0.5):
    """Karplus-Strong string via a comb filter."""
    f = mtof(m)
    L = int(SR / f)
    exc = lp(noise(L / SR), 2000 + 6000 * bright)
    x = np.zeros(int(d * SR))
    x[: len(exc)] = exc
    a = np.zeros(L + 2)
    a[0] = 1
    a[L] = -0.497
    a[L + 1] = -0.497
    y = signal.lfilter([1.0], a, x)
    return fade(y / (np.abs(y).max() + 1e-9), 0.001, 0.08) * 0.5


def bell(m, d=1.6, bright=1.0):
    f = mtof(m)
    t = tt(d)
    parts = [(1, 1.0, 2.2), (2.0, 0.5, 3.0), (2.76, 0.35 * bright, 4.5), (5.4, 0.2 * bright, 7), (8.93, 0.1 * bright, 11)]
    y = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * k) for r, a, k in parts)
    return fade(y * 0.3, 0.001, 0.05)


def marimba(m, d=0.6):
    f = mtof(m)
    t = tt(d)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 9) + 0.3 * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t * 30)
    y[: int(0.004 * SR)] += lp(noise(0.004), 3000) * 0.3
    return fade(y * 0.45, 0.001, 0.05)


def glass(f0=2600, d=0.5):
    t = tt(d)
    y = sum(np.sin(2 * np.pi * f0 * r * t) * np.exp(-t * k) * a for r, a, k in [(1, 1, 14), (1.52, 0.6, 18), (2.31, 0.4, 24), (3.1, 0.2, 30)])
    return fade(y * 0.18, 0.0005, 0.03)


def tick(f=3200, d=0.03, g=0.25):
    t = tt(d)
    return fade(np.sin(2 * np.pi * f * t) * np.exp(-t * 180) * g, 0.0003, 0.005)


def click():
    y = bp(noise(0.012), 1800, 7000) * expd(0.012, 400) * 0.5
    return y + np.pad(tick(1900, 0.02, 0.2), (0, 0))[: len(y)]


def pop(f0=1100, f1=260, d=0.09, g=0.4):
    t = tt(d)
    f = f1 + (f0 - f1) * np.exp(-t * 55)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 32)
    return fade(y * g, 0.0005, 0.01)


def thud(f=80, d=0.25, g=0.6):
    t = tt(d)
    fr = f + 60 * np.exp(-t * 40)
    y = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t * 16)
    return y * g


def whoosh(d=0.6, f0=300, f1=3000, g=0.35, curve=1.0, seed=0, shape=0.35):
    x = swept(d, f0, f1, 0.7, curve, seed)
    t = tt(d)
    pk = shape * d
    e = np.where(t < pk, (t / pk) ** 2, np.exp(-(t - pk) / (d * 0.25)))
    return x * e * g


def riser(d=1.2, g=0.3, seed=3):
    x = whoosh(d, 400, 7000, 1.0, 1.4, seed, shape=0.98)
    t = tt(d)
    s = np.sin(2 * np.pi * np.cumsum(200 * 2 ** (t / d * 3)) / SR) * (t / d) ** 2 * 0.25
    return (x + s) * g


def impact(g=1.0):
    d = 2.0
    t = tt(d)
    sub = np.sin(2 * np.pi * np.cumsum(38 + 40 * np.exp(-t * 8)) / SR) * np.exp(-t * 2.2)
    nz = lp(noise(d), 900) * np.exp(-t * 5) * 0.5
    y = sub + nz
    k = kick(1.0)
    y[: len(k)] += k
    return np.tanh(y * 1.2) * g


def sparkle(n=7, d=0.6, seed=0, base=84, g=0.14):
    r = np.random.default_rng(seed)
    y = np.zeros(int((d + 0.8) * SR))
    for _ in range(n):
        m = base + r.choice([0, 2, 4, 7, 9, 12, 14, 16])
        b = bell(m, 0.8, 1.2)
        i = int(r.random() * d * SR)
        y[i: i + len(b)] += b[: len(y) - i]
    return y * g / 0.3


def crunch(d=0.32, g=0.5, seed=5):
    r = np.random.default_rng(seed)
    y = np.zeros(int(d * SR))
    for _ in range(46):
        i = int(r.random() ** 1.6 * d * 0.85 * SR)
        L = int((0.002 + r.random() * 0.01) * SR)
        y[i: i + L] += r.standard_normal(L) * r.random() * np.exp(-np.arange(L) / (L * 0.3))
    y = bp(y, 900, 6000) * 1.6
    tb = thud(110, 0.2, 0.4)
    y[: len(tb)] += tb
    return y * g


def pour(d=0.65, g=0.35, seed=9):
    r = np.random.default_rng(seed)
    t = tt(d)
    y = lp(noise(d), 1400) * 0.35 * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * t) ** 2)
    for _ in range(38):
        i = int(r.random() * (d - 0.05) * SR)
        bd = 0.03
        bt = tt(bd)
        fb = (380 + r.random() * 500) * (1 + bt * 14)
        b = np.sin(2 * np.pi * np.cumsum(fb) / SR) * np.exp(-bt * 90) * 0.35
        y[i: i + len(b)] += b
    e = np.minimum(t / 0.06, 1) * np.minimum(1, (d - t) / 0.12)
    return y * e * g


def ratchet(d=0.42, n=9, g=0.35):
    y = np.zeros(int(d * SR) + 2000)
    for k in range(n):
        c = bp(noise(0.006), 2500, 8000) * expd(0.006, 500)
        i = int(k * d / n * SR)
        y[i: i + len(c)] += c
    return y * g


def clack(g=0.4):
    t = tt(0.08)
    y = (np.sin(2 * np.pi * 1450 * t) + 0.6 * np.sin(2 * np.pi * 2380 * t)) * np.exp(-t * 70)
    return fade(y * g, 0.0003, 0.01)


def puff(d=0.3, g=0.25):
    return whoosh(d, 400, 1600, g, 1, 7, shape=0.15)


def reverse_swell(d=1.6, g=0.35):
    x = hp(noise(d), 3000) * (tt(d) / d) ** 3
    return x * g


# ----------------------------------------------------------------- score
music = buf()
kick_times = []

CH = {  # pad voicings, bass root
    "D": ([50, 57, 61, 64, 66, 69], 38), "Bm": ([47, 54, 57, 61, 62, 66], 35),
    "G": ([43, 50, 54, 57, 59, 62], 31), "A": ([45, 52, 57, 59, 61, 64], 33),
}
prog = []
t = 6.0
cyc = ["D", "Bm", "G", "A"]
k = 0
while t < 54 - 1e-6:
    prog.append((t, 2.0, cyc[k % 4]))
    t += 2.0
    k += 1
prog += [(54.0, 1.5, "G"), (55.5, 0.5, "A"), (56.0, 4.0, "D")]

# drone into the cold open, then chords
dr = pad([26 + 12, 33 + 12, 38 + 12], 6.2, cutoff=500, attack=2.5, release=1.5)
place(music, dr * 1.4, 0.0)
place(music, riser(1.0, 0.22), 3.0)
for t0, d, c in prog:
    notes, root = CH[c]
    cut = 900 if t0 < 12 else 1500 if t0 < 54 else 2200
    g = 1.35 if t0 >= 56 else 1.0
    place(music, pad(notes, d, cutoff=cut, attack=0.35 if t0 > 6 else 1.2, release=1.4 if t0 < 56 else 2.5) * g, t0)

# rhythm sections: (start, end, kick pattern, clap, hats)
def drums(a, b, kick_every, claps, hats, shakers=False, kg=0.8):
    t = a
    while t < b - 1e-6:
        beat_in_bar = round((t % 2.0) / BEAT)
        if kick_every and (round(t / BEAT) % int(kick_every / BEAT) == 0):
            place(music, kick(kg), t)
            kick_times.append(t)
        if claps and beat_in_bar in (1, 3):
            place(music, clap(), t, 0.7, 0.05)
        if hats:
            place(music, hat(), t + BEAT / 2, 0.55, 0.3)
        if shakers:
            for s in range(4):
                place(music, shaker(), t + s * BEAT / 4, 0.5 if s % 2 else 0.3, -0.3)
        t += BEAT

for s in np.arange(1.0, 4.0, 0.25):
    place(music, hat(), s, 0.35, 0.25)
place(music, kick(0.6), 0.0); place(music, kick(0.5), 2.0)
drums(12.0, 14.0, 0, False, True)
drums(14.0, 21.9, 0.5, True, True)
drums(24.0, 34.0, 2.0, False, False, shakers=True, kg=0.55)
drums(34.0, 44.0, 0.5, True, True, shakers=True)
drums(44.0, 53.5, 0.5, True, True, kg=0.7)

# bass line (8ths on the root, octave jumps on the off-beats)
def bassline(a, b, g=1.0):
    for t0, d, c in prog:
        root = CH[c][1]
        for s in np.arange(0, d, BEAT / 2):
            t = t0 + s
            if a <= t < b:
                m = root + (12 if int(round(s / (BEAT / 2))) % 4 == 3 else 0)
                place(music, bass(m, 0.22), t, g * 0.8)

bassline(12.0, 21.9)
bassline(24.0, 34.0, 0.55)
bassline(34.0, 53.5)
place(music, bass(26, 3.5), 56.0, 0.9)

# arpeggiated plucks
def arps(a, b, g=0.5, step=BEAT / 2):
    for t0, d, c in prog:
        notes = [n + 12 for n in CH[c][0][1:5]]
        pat = [0, 1, 2, 3, 2, 1, 3, 2]
        for i, s in enumerate(np.arange(0, d, step)):
            t = t0 + s
            if a <= t < b:
                place(music, pluck(notes[pat[i % 8]], 0.6, 0.35), t, g, 0.35 if i % 2 else -0.35)

arps(24.0, 34.0, 0.42)
arps(44.0, 53.5, 0.3)
arps(34.0, 44.0, 0.22)

# sidechain duck on pads/bass after kicks (music bus only)
duck = np.ones(N)
tk = np.arange(N) / SR
for kt in kick_times:
    i = int(kt * SR)
    L = int(0.25 * SR)
    duck[i: i + L] = np.minimum(duck[i: i + L], 1 - 0.35 * np.exp(-np.arange(L) / (0.09 * SR)))
music *= duck[:, None]
# thin the score before the outro, then fade the tail
music[int(53.5 * SR): int(54 * SR)] *= np.linspace(1, 0.55, int(0.5 * SR))[:, None]
music = reverb(music, 2.4, 0.22, 11, 6000)

# ----------------------------------------------------------------- sound effects
sfx = buf()
S = lambda sig, t, g=1.0, p=0.0: place(sfx, sig, t, g, p)

# Act 1
S(tick(1500, 0.08, 0.3), 0.05)
S(whoosh(0.4, 2000, 6000, 0.12, seed=1), 0.3)
for i, s in enumerate(np.arange(1.0, 3.8, 0.25)):
    S(tick(2400 + (i % 4) * 200, 0.04, 0.22), s, 1, (i % 2) * 0.4 - 0.2)
for i, s in enumerate([2.75, 3.0, 3.25, 3.5]):
    S(pop(900 + i * 150, 300 + i * 40, 0.1, 0.35), s, 1, [-0.6, 0.6, -0.5, 0.5][i])
S(impact(1.0), 4.0)
S(whoosh(1.4, 200, 1400, 0.25, seed=2, shape=0.1), 4.0)
S(whoosh(0.45, 3000, 400, 0.2, seed=3, shape=0.8), 5.5)
S(tick(1800, 0.1, 0.35), 5.95)
# Act 2
S(tick(2600, 0.05, 0.3), 6.3)
S(whoosh(0.9, 800, 5000, 0.12, seed=4, shape=0.6), 6.45)
S(pour(0.9, 0.18, 12), 7.15)
S(bell(81, 2.2) * 1.6, 8.02)
S(whoosh(0.35, 2000, 8000, 0.22, seed=5, shape=0.2), 8.0)
S(sparkle(8, 0.5, 2, 86, 0.12), 8.05)
for i in range(5):
    S(thud(95, 0.18, 0.35), 8.45 + i * 0.09, 1, (i - 2) * 0.2)
for i, m in enumerate([71, 74, 78, 81, 85]):
    S(pluck(m, 1.2, 0.6), 8.85 + i * 0.25, 0.9, (i - 2) * 0.25)
S(whoosh(0.3, 3000, 600, 0.14, seed=6, shape=0.7), 10.02)
S(whoosh(0.6, 500, 2600, 0.2, seed=7), 10.25)
S(sparkle(5, 0.35, 3, 91, 0.08), 10.72)
S(riser(1.1, 0.3, 8), 11.0)
S(whoosh(1.2, 4000, 200, 0.3, seed=9, shape=0.15), 12.15)
# Act 3
S(thud(70, 0.3, 0.45), 12.95)
S(click(), 12.95, 0.6)
S(thud(70, 0.3, 0.45), 14.45)
S(whoosh(0.8, 800, 6000, 0.16, seed=10, shape=0.5), 14.15)
S(tick(2000, 0.06, 0.3), 14.75)
for i in range(12):
    S(tick(1200 + i * 110, 0.03, 0.14), 14.8 + i * 0.11)
S(bell(88, 1.2, 0.8) * 1.2, 15.45, 1, 0.2)
for i in range(4):
    S(tick(3400, 0.04, 0.22), 15.2 + i * 0.5, 1, 0.5)
    S(whoosh(0.35, 1500, 5000, 0.07, seed=20 + i, shape=0.3), 15.2 + i * 0.5, 1, 0.6)
S(bell(93, 1.6, 1.0) * 1.3, 16.45, 1, 0)
S(bell(88, 1.6, 1.0) * 0.8, 16.45)
S(whoosh(0.5, 600, 3000, 0.16, seed=30), 17.35)
S(whoosh(0.6, 400, 4000, 0.22, seed=31, shape=0.6), 18.0)
pos = lambda t: 21 * (1 - (1 - np.clip((t - 18.6) / 2.95, 0, 1)) ** 4)
prev = 0
for ti in np.arange(18.6, 21.6, 1 / 500):
    p = int(np.floor(pos(ti) + 0.5))
    if p != prev:
        S(tick(2800 + (p % 7) * 120, 0.03, 0.28), ti, 1, 0.3)
        prev = p
S(bell(86, 1.4, 1.0), 21.55)
S(thud(120, 0.2, 0.4), 21.55)
S(impact(0.9), 22.0)
S(bell(81, 2.4, 1.2) * 1.2, 22.02, 1, -0.2)
S(bell(88, 2.4, 1.2) * 1.0, 22.02, 1, 0.2)
S(sparkle(9, 0.5, 5, 88, 0.12), 22.12)
S(whoosh(0.9, 300, 6000, 0.3, seed=32, shape=0.5), 23.3)
# Act 4
for i in range(4):
    S(glass(2200 + i * 380), 24.0 + i * 0.1, 1, -0.3 + i * 0.2)
for i in range(4):
    S(tick(3000, 0.04, 0.18), 24.35 + i * 0.13, 1, 0.5)
S(whoosh(0.8, 3000, 500, 0.15, seed=33, shape=0.6), 25.55)
S(whoosh(0.6, 400, 3000, 0.2, seed=34, shape=0.8), 25.85)
S(whoosh(0.4, 900, 3000, 0.12, seed=35, shape=0.3), 26.45, 1, 0.5)
S(pop(1300, 400, 0.1, 0.4), 26.6)
S(sparkle(10, 0.5, 6, 88, 0.14), 26.62)
for i in range(3):
    S(pop(1000 + i * 180, 400, 0.08, 0.25), 26.85 + i * 0.125, 1, -0.3)
for i in range(12):
    S(tick(1600 + i * 60, 0.03, 0.12), 27.0 + i * 0.066, 1, 0.4)
for i in range(3):
    S(pluck(79 + i * 3, 0.5, 0.4), 27.25 + i * 0.13, 0.5, 0.4)
S(click(), 28.85, 0.8)
S(bell(90, 1.0, 0.8) * 0.8, 29.12)
S(whoosh(0.5, 2000, 400, 0.14, seed=36, shape=0.6), 29.95)
S(tick(2600, 0.05, 0.25), 30.35)
S(whoosh(0.5, 500, 1200, 0.12, seed=37), 30.4)
S(pour(0.65, 0.45, 13), 30.85)
S(thud(90, 0.2, 0.35), 31.72)
S(tick(2600, 0.05, 0.25), 31.75)
S(ratchet(0.42, 9, 0.4), 31.82)
S(pop(700, 180, 0.12, 0.6), 32.24)
S(clack(0.45), 32.64)
S(clack(0.2), 32.76)
S(tick(2600, 0.05, 0.25), 32.75)
S(crunch(0.34, 0.7, 5), 32.95)
S(puff(0.3, 0.25), 32.98)
S(tick(2600, 0.05, 0.25), 33.5)
S(bell(84, 1.0, 0.7) * 0.6, 33.5)
S(pop(1400, 300, 0.1, 0.5), 34.14)
S(impact(0.35), 34.14)
S(sparkle(12, 0.6, 7, 86, 0.16), 34.15)
# Act 5
def xorshift(seed):
    """Same generator as A.rng in src/engine.js, so cues match the animation."""
    s = seed & 0xFFFFFFFF or 1
    while True:
        s ^= (s << 13) & 0xFFFFFFFF
        signed = s - (1 << 32) if s & 0x80000000 else s  # JS ">>" is a signed shift
        s ^= (signed >> 17) & 0xFFFFFFFF
        s ^= (s << 5) & 0xFFFFFFFF
        yield s / 4294967296


# leaf arrival times from act5.js (six draws per leaf: a, R, d, spin, size, ox)
g = xorshift(99)
arr = []
for i in range(20):
    draws = [next(g) for _ in range(6)]
    arr.append(34.16 + i * 0.022 + 0.8 + draws[2] * 0.3)
penta = [74, 76, 78, 81, 83, 86, 88, 90, 93, 95]
for i, a in enumerate(sorted(arr)):
    S(pluck(penta[min(i // 2, 9)], 0.5, 0.7), a, 0.35, 0.3)
S(whoosh(0.5, 3000, 600, 0.15, seed=40, shape=0.6), 34.25)
S(thud(70, 0.25, 0.35), 34.6)
S(thud(70, 0.25, 0.3), 34.78)
for i in range(8):
    S(whoosh(0.45, 600, 2800, 0.07, seed=41 + i, shape=0.7), 35.75 + i * 0.1, 1, (i % 3 - 1) * 0.5)
for j, d in enumerate([0, 1, 2, 4, 5, 6]):
    S(marimba([74, 76, 78, 81, 83, 86][j]), 37.0 + j * 0.25, 1, 0.4)
S(whoosh(0.8, 2500, 300, 0.2, seed=50, shape=0.5), 39.75)
S(whoosh(0.6, 400, 2500, 0.2, seed=51, shape=0.6), 39.9)
for i in range(6):
    S(whoosh(0.3, 1200, 4000, 0.06, seed=52 + i, shape=0.4), 40.3 + i * 0.08, 1, 0.5)
S(sparkle(5, 0.4, 8, 91, 0.1), 41.3)
S(impact(0.55), 41.6)
S(bell(86, 1.8, 1.2) * 1.1, 41.6, 1, 0.5)
S(sparkle(10, 0.5, 9, 88, 0.12), 41.66, 1, 0.5)
S(whoosh(0.9, 200, 4000, 0.3, seed=60, shape=0.7), 43.3)
# Act 6
for i, s in enumerate([44.62, 44.76, 44.9]):
    S(marimba([81, 86, 88][i]), s, 0.9, (i - 1) * 0.5)
for i in range(7):
    S(pop(900 + i * 70, 400, 0.08, 0.2), 44.75 + i * 0.08, 1, (i % 3 - 1) * 0.6)
S(whoosh(0.4, 700, 2500, 0.12, seed=61, shape=0.4), 45.2, 1, -0.5)
S(click(), 46.45, 0.8)
S(whoosh(0.3, 1500, 4000, 0.08, seed=62), 46.45)
for i in range(2):
    S(pop(500, 900, 0.1, 0.18), 46.5 + i * 0.05)
S(whoosh(0.4, 700, 2500, 0.12, seed=63, shape=0.4), 46.9, 1, 0.5)
S(riser(0.7, 0.2, 64), 47.4)
S(whoosh(0.8, 4000, 300, 0.28, seed=65, shape=0.25), 47.95)
S(pop(800, 300, 0.1, 0.35), 48.75)
S(whoosh(0.4, 600, 2400, 0.12, seed=66, shape=0.3), 48.7, 1, 0.5)
S(whoosh(0.8, 1800, 500, 0.1, seed=67, shape=0.5), 49.75, 1, 0.5)
S(pop(1200, 500, 0.08, 0.45), 50.95, 1, 0.4)
S(sparkle(8, 0.8, 10, 88, 0.12), 51.0, 1, 0.4)
S(whoosh(2.0, 1500, 600, 0.07, seed=68, shape=0.5), 51.6, 1, 0.4)
S(whoosh(0.8, 2000, 300, 0.16, seed=69, shape=0.6), 53.5)
# Act 7
S(reverse_swell(1.65, 0.4), 53.9)
S(riser(1.6, 0.25, 70), 53.9)
for i in range(24):
    S(tick(3000 + (i % 5) * 300, 0.02, 0.06), 54.1 + i * 0.05, 1, np.sin(i) * 0.7)
S(impact(0.7), 55.55)
S(bell(86, 2.8, 1.2) * 1.3, 55.55, 1, -0.15)
S(bell(93, 2.8, 1.0) * 0.9, 55.55, 1, 0.15)
S(sparkle(10, 0.6, 11, 91, 0.12), 55.6)
S(thud(55, 0.8, 0.5), 56.0)
S(pop(700, 300, 0.12, 0.3), 56.2)
for i in range(5):
    S(pluck([74, 78, 81, 85, 86][i], 1.0, 0.5), 56.55 + i * 0.06, 0.5, (i - 2) * 0.3)
S(sparkle(6, 0.6, 12, 93, 0.1), 57.2)
for i in range(3):
    S(tick(2400, 0.04, 0.15), 57.4 + i * 0.18)

sfx = reverb(sfx, 1.3, 0.18, 21, 7000)

# ----------------------------------------------------------------- mix and master
def master(x, target_peak=0.89):
    x = hp(x, 28)
    x = np.tanh(x * 1.15) / np.tanh(1.15)
    t = np.arange(N) / SR
    env = np.clip((60.0 - t) / 0.9, 0, 1) ** 1.5  # fade out over the last 0.9 s
    x *= env[:, None]
    return x / (np.abs(x).max() + 1e-9) * target_peak


def write(path, x):
    from scipy.io import wavfile
    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))


mix = master(music * 0.8 + sfx * 1.0)
write(OUT / "mix.wav", mix)
write(OUT / "music.wav", master(music))
write(OUT / "sfx_only.wav", master(sfx))
print("wrote", [p.name for p in OUT.glob("*.wav")])
