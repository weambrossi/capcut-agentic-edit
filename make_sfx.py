"""Synthesize the counter ding and the podium chime into assets/sfx/ (no downloads)."""
import os
import wave

import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sfx")


def bell(freq, dur, decay, partials=((1, 1.0), (2.0, 0.35), (3.01, 0.12))):
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-t / decay) * np.minimum(1, t / 0.004)  # 4 ms attack avoids a click
    return sum(a * np.sin(2 * np.pi * freq * m * t) for m, a in partials) * env


def save(name, x, peak_db):
    x = x / np.max(np.abs(x)) * 10 ** (peak_db / 20)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


def main():
    os.makedirs(OUT, exist_ok=True)
    # ding: E6 then a softer B6 just after, like a notification chime
    d = np.zeros(int(SR * 0.9))
    a = bell(1318.5, 0.9, 0.22)
    b = bell(1975.5, 0.8, 0.18) * 0.6
    d[: len(a)] += a
    off = int(SR * 0.07)
    d[off: off + len(b)] += b[: len(d) - off]
    save("ding.wav", d, -9)

    # podium chime: C-E-G-C arpeggio with a shimmer on top
    notes = [1046.5, 1318.5, 1568.0, 2093.0]
    c = np.zeros(int(SR * 1.8))
    for i, f in enumerate(notes):
        n = bell(f, 1.4, 0.35 if i < 3 else 0.6)
        o = int(SR * 0.09 * i)
        c[o: o + len(n)] += n[: len(c) - o]
    rng = np.random.default_rng(7)
    for _ in range(14):
        f = rng.uniform(2600, 4200)
        n = bell(f, 0.4, 0.08, partials=((1, 0.25),))
        o = int(SR * rng.uniform(0.3, 1.0))
        c[o: o + len(n)] += n[: len(c) - o]
    save("podium.wav", c, -8)

    # pop: quick upward "bloop" for words appearing
    t = np.arange(int(SR * 0.16)) / SR
    f = 420 + 1100 * (t / t[-1]) ** 0.6
    p = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.05) * np.minimum(1, t / 0.003)
    save("pop.wav", p, -10)

    # buzzer: soft low two-note "nope"
    def buzz(freq, dur):
        t = np.arange(int(SR * dur)) / SR
        x = sum(np.sin(2 * np.pi * freq * k * t) / k for k in (1, 2, 3, 4, 5))
        return x * np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.04)
    save("buzzer.wav", np.concatenate([buzz(196, 0.16), np.zeros(int(SR * 0.04)), buzz(147, 0.32)]), -12)

    # slide whistle falling, with a little vibrato
    t = np.arange(int(SR * 0.9)) / SR
    f = 1700 * (450 / 1700) ** (t / t[-1]) * (1 + 0.012 * np.sin(2 * np.pi * 7 * t))
    w = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.03) * np.minimum(1, (t[-1] - t) / 0.12)
    save("whistle.wav", w, -12)
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
