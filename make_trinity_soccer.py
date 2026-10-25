"""Trinity vs Wesleyan men's soccer hype edit: 60 s, 1080x1920, 23.976 fps.

Usage:
  python3 make_trinity_soccer.py --preview T1,T2,...   graded stills (before|after) at timeline times
  python3 make_trinity_soccer.py --music               build the music bed only
  python3 make_trinity_soccer.py                       full render

The cut lives in edit_decision_list.json next to the output (one entry per shot: clip, in/out,
speed, crop keyframes). Per shot, ffmpeg denoises, reframes to 9:16 with a keyframed crop,
does optical-flow slow motion and upscales; numpy grades every frame; a second ffmpeg encodes.
Music is composed from the Apple Loops "Stone Cold" kit (royalty-free under the GarageBand
licence) at 96 BPM; SFX are synthesised here. Source footage is only read, never modified.
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Desktop/Sports Video/mens soccer v weslyan")
OUT = os.path.join(SRC, "Trinity Hype Edit")
EDL = os.path.join(OUT, "edit_decision_list.json")
TMP = os.path.join(HERE, "out", "trinity_soccer")
LOOPS = "/Library/Audio/Apple Loops/Apple/01 Hip Hop"
W, H = 1080, 1920
FPS_N, FPS_D = 24000, 1001
FPS = FPS_N / FPS_D
SR = 48000
BEAT = 60 / 96
BAR = 4 * BEAT
CROP_W = 608  # 9:16 window out of the 1920x1080 source


# ---------------------------------------------------------------- timeline
def load_shots():
    shots = json.load(open(EDL))["shots"]
    t = 0.0
    for s in shots:
        s["dur"] = (s["out"] - s["in"]) / s["speed"]
        s["t0"], s["t1"] = t, t + s["dur"]
        s["f0"], s["f1"] = round(s["t0"] * FPS), round(s["t1"] * FPS)
        t = s["t1"]
    return shots


def crop_expr(s):
    """Piecewise-linear crop x (pixels) over source time t (0 = shot in-point)."""
    keys = [(k - s["in"], min(max(c * 1920 - CROP_W / 2, 0), 1920 - CROP_W)) for k, c in s["x"]]
    if len(keys) == 1:
        return f"{keys[0][1]:.1f}"
    e = f"{keys[-1][1]:.1f}"
    for (ta, xa), (tb, xb) in reversed(list(zip(keys, keys[1:]))):
        lerp = f"({xa:.1f}+({xb - xa:.1f})*(t-{ta:.3f})/{max(tb - ta, 1e-3):.3f})"
        e = f"if(lt(t,{tb:.3f}),{lerp},{e})"
    return f"if(lt(t,{keys[0][0]:.3f}),{keys[0][1]:.1f},{e})"


def shot_frames(s, nframes, scale=True):
    """Yield float32 RGB frames (H, W, 3) in 0..1 for one shot, reframed and retimed."""
    vf = [f"hqdn3d=2.5:2:5:5", f"crop={CROP_W}:1080:x='{crop_expr(s)}':y=0"]
    if s["speed"] < 0.999:
        vf += [f"minterpolate=fps={FPS / s['speed']:.4f}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
               f"setpts=PTS/{s['speed']}", f"fps={FPS_N}/{FPS_D}"]
    w, h = (W, H) if scale else (CROP_W, 1080)
    if scale:
        vf.append(f"scale={W}:{H}:flags=lanczos")
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{s['in']:.3f}", "-i", os.path.join(SRC, s["clip"] + ".MTS"),
           "-an", "-vf", ",".join(vf), "-frames:v", str(nframes), "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 3 * 2
    last = None
    for _ in range(nframes):
        buf = p.stdout.read(n)
        if len(buf) < n:  # source ran short: hold the last frame
            if last is None:
                raise RuntimeError(f"no frames from {s['clip']} @ {s['in']}")
            yield last
            continue
        last = np.frombuffer(buf, np.uint16).reshape(h, w, 3).astype(np.float32) / 65535
        yield last
    p.stdout.close()
    p.wait()


# ---------------------------------------------------------------- grade
def luma(x):
    return x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722


def shot_stats(frame):
    """Exposure gain and white balance for a shot, from its first frame."""
    y = luma(frame)
    lower = y[int(y.shape[0] * 0.45):]  # pitch + players; ignore the black sky
    med = float(np.median(lower))
    gain = float(np.clip(0.30 / max(med, 1e-3), 0.85, 2.2))
    # white balance from the brightest low-chroma pixels (white jerseys, lines)
    sel = (y > np.percentile(y, 99.3)) & (frame.max(-1) < 0.98)
    if sel.sum() > 200:
        c = frame[sel].mean(0)
        wb = np.clip(c.mean() / c, 0.85, 1.2)
        wb = 1 + 0.7 * (wb - 1)  # neutralise most, not all, of the cast
    else:
        wb = np.ones(3)
    return gain, wb.astype(np.float32)


_vig = None


def grade(x, gain, wb):
    global _vig
    if _vig is None:
        yy, xx = np.mgrid[0:x.shape[0], 0:x.shape[1]].astype(np.float32)
        r = np.sqrt(((xx / x.shape[1] - 0.5) * 1.0) ** 2 + ((yy / x.shape[0] - 0.5) * 0.75) ** 2)
        _vig = (1 - 0.32 * np.clip((r - 0.25) / 0.45, 0, 1) ** 1.6)[..., None].astype(np.float32)
    x = x * wb * gain
    # filmic tone: lift the toe a touch, roll the highlights off so white kits keep detail
    x = np.maximum(x - 0.022, 0) / 0.978
    x = np.power(x, 0.94)
    k = 0.72
    x = np.where(x > k, k + (1 - k) * np.tanh((x - k) / (1 - k)), x)
    # contrast S-curve around mid grey
    x = x + 0.55 * x * (1 - x) * (x - 0.42)
    y = luma(x)[..., None]
    # saturation: rich pitch, clean shadows (night-sky noise and purple cast go neutral)
    green = np.clip((x[..., 1:2] - np.maximum(x[..., 0:1], x[..., 2:3])) / 0.15, 0, 1)
    sat = (1.12 - 0.2 * green) * np.clip(y / 0.18, 0.5, 1.0)  # keep turf natural, not neon
    x = y + (x - y) * sat
    # split tone: barely-cool shadows, warm highlights
    sh = np.clip(1 - y / 0.35, 0, 1)
    hi = np.clip((y - 0.55) / 0.45, 0, 1)
    x = x + sh * np.array([-0.004, 0.0, 0.005], np.float32) + hi * np.array([0.012, 0.004, -0.012], np.float32)
    x = x * _vig
    return np.clip(x, 0, 1)


# ---------------------------------------------------------------- preview
def preview(times):
    os.makedirs(os.path.join(TMP, "preview"), exist_ok=True)
    shots = load_shots()
    for T in times:
        s = next(s for s in shots if s["t0"] <= T < s["t1"])
        k = int(round((T - s["t0"]) * FPS))
        frames = list(shot_frames(s, k + 1))
        gain, wb = shot_stats(frames[0])
        before = frames[k]
        after = grade(before, gain, wb)
        im = np.concatenate([before, after], 1)
        Image.fromarray((im * 255).astype(np.uint8)).resize((W, H // 2)).save(
            os.path.join(TMP, "preview", f"p_{T:05.2f}.jpg"), quality=88)
        print(f"{T:6.2f}s  {s['clip']} @{s['in'] + (T - s['t0']) * s['speed']:.2f}  gain={gain:.2f} wb={np.round(wb, 3)}")


# ---------------------------------------------------------------- full render
def render_video(path):
    shots = load_shots()
    total = shots[-1]["f1"]
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-s", f"{W}x{H}",
         "-r", f"{FPS_N}/{FPS_D}", "-i", "-",
         "-vf", "unsharp=5:5:0.45:5:5:0,noise=alls=3:allf=t,format=yuv420p10le",
         "-c:v", "libx265", "-preset", "slow", "-crf", "12", "-tag:v", "hvc1", path],
        stdin=subprocess.PIPE)
    fade_out = 1.5  # seconds to black at the very end
    done = 0
    for i, s in enumerate(shots):
        n = s["f1"] - s["f0"]
        gain = wb = None
        for j, fr in enumerate(shot_frames(s, n)):
            if gain is None:
                gain, wb = shot_stats(fr)
            g = grade(fr, gain, wb)
            t = (s["f0"] + j) / FPS
            if t > shots[-1]["t1"] - fade_out:
                g = g * max(0.0, (shots[-1]["t1"] - t) / fade_out)
            if t < 0.6:  # fade up from black
                g = g * (t / 0.6)
            enc.stdin.write((g * 65535).astype(np.uint16).tobytes())
            done += 1
        print(f"  shot {i + 1:2d}/{len(shots)} {s['clip']} {s['t0']:6.2f}-{s['t1']:6.2f}s  ({done}/{total} frames)", flush=True)
    enc.stdin.close()
    enc.wait()


# ---------------------------------------------------------------- audio
def read_audio(path, start=0.0, dur=None, af=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", path]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    if af:
        cmd += ["-af", af]
    cmd += ["-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32).reshape(-1, 2).copy()


def place(buf, x, t, gain_db=0.0, fin=0.005, fout=0.005):
    x = x * 10 ** (gain_db / 20)
    n = len(x)
    if n == 0:
        return
    env = np.ones(n, np.float32)
    a, b = int(fin * SR), int(fout * SR)
    if a:
        env[:min(a, n)] = np.linspace(0, 1, min(a, n))
    if b:
        env[-min(b, n):] = np.minimum(env[-min(b, n):], np.linspace(1, 0, min(b, n)))
    i = int(round(t * SR))
    j = min(len(buf), i + n)
    buf[i:j] += x[:j - i] * env[:j - i, None]


def onepole(x, cut):
    """One-pole low-pass with per-sample cutoff (Hz array or scalar)."""
    cut = np.broadcast_to(np.asarray(cut, np.float32), (len(x),))
    a = 1 - np.exp(-2 * np.pi * cut / SR)
    y = np.empty_like(x)
    s = np.zeros(x.shape[1], np.float32)
    for i in range(len(x)):
        s += a[i] * (x[i] - s)
        y[i] = s
    return y


def sfx():
    rng = np.random.default_rng(7)
    out = {}
    # riser: noise whose low-pass opens up, plus a rising sine, swelling in
    d = 4.5
    t = np.arange(int(d * SR)) / SR
    noise = rng.standard_normal((len(t), 2)).astype(np.float32)
    r = onepole(noise, 300 * (40 ** (t / d))) - onepole(noise, 120)
    tone = np.sin(2 * np.pi * np.cumsum(180 * 6 ** (t / d)) / SR)[:, None]
    out["riser"] = ((0.6 * r + 0.15 * tone) * ((t / d) ** 2.2)[:, None]).astype(np.float32)
    # reverse cymbal: bright noise swelling to a hard stop
    d = 1.6
    t = np.arange(int(d * SR)) / SR
    noise = rng.standard_normal((len(t), 2)).astype(np.float32)
    hp = noise - onepole(noise, 3500)
    out["revcym"] = (hp * ((t / d) ** 3)[:, None] * 0.7).astype(np.float32)
    # impact: falling sub boom + short noise thump
    d = 2.2
    t = np.arange(int(d * SR)) / SR
    f = 32 + 38 * np.exp(-t / 0.18)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.7)
    thump = onepole(rng.standard_normal((len(t), 2)).astype(np.float32), 900) * np.exp(-t / 0.05)[:, None] * 3
    out["impact"] = (boom[:, None] * 0.9 + thump).astype(np.float32)
    # whoosh: band of noise sweeping down
    d = 0.7
    t = np.arange(int(d * SR)) / SR
    noise = rng.standard_normal((len(t), 2)).astype(np.float32)
    w = onepole(noise, 4000 * (0.08 ** (t / d))) - onepole(noise, 200)
    out["whoosh"] = (w * np.sin(np.pi * t / d)[:, None] ** 2 * 0.8).astype(np.float32)
    return out


def build_music(total):
    L = lambda n, af=None: read_audio(os.path.join(LOOPS, f"Stone Cold {n}.caf"), af=af)
    beat, sub, syn, orch, piano = L("Beat"), L("Sub Bass"), L("Synth Bass"), L("Orchestra Hits"), L("Warped Piano")
    orch_lp = L("Orchestra Hits", "lowpass=f=700,lowpass=f=700")
    piano_lp = L("Warped Piano", "lowpass=f=2500")
    seg = lambda x, a, b: x[int(a * SR):int(b * SR)]
    m = np.zeros((int((total + 3) * SR), 2), np.float32)
    fx = sfx()

    # intro 0-12.5: warped piano + muffled orchestra hits, hats creep in, riser, a beat of silence
    place(m, seg(piano_lp, 0, 12.0), 0.0, 0, fin=1.5, fout=0.3)
    place(m, seg(orch_lp, 0, 10), 0.0, 1, fin=0.8)
    place(m, seg(orch_lp, 0, 2.0), 10.0, 1, fout=0.2)
    place(m, seg(beat, 0, 2.0), 10.0, -5, fout=0.05)
    place(m, fx["riser"], 12.0 - len(fx["riser"]) / SR, -9, fout=0.02)
    # drop 1 12.5-32.5
    place(m, fx["impact"], 12.5, -3, fout=0.4)
    place(m, seg(beat, 15, 35), 12.5, 0)
    place(m, sub, 12.5, -2)
    place(m, seg(syn, 0, 20), 12.5, -7)
    place(m, orch, 12.5, -5)
    place(m, orch, 22.5, -5)
    place(m, fx["whoosh"], 32.1, -8)
    # breakdown 32.5-37.5: piano + muffled hits, hats return, reverse cymbal into the drop
    place(m, seg(piano, 10, 15), 32.5, 3, fin=0.05, fout=0.1)
    place(m, seg(orch_lp, 0, 5), 32.5, 1)
    place(m, seg(sub, 0, 2.5), 32.5, -6, fout=0.6)
    place(m, seg(beat, 5, 7.5), 35.0, -6)
    place(m, fx["revcym"], 37.5 - len(fx["revcym"]) / SR, -8, fout=0.01)
    # drop 2 37.5-50
    place(m, fx["impact"], 37.5, -3, fout=0.4)
    place(m, seg(beat, 27.5, 40), 37.5, 0, fout=0.02)
    place(m, seg(sub, 0, 12.5), 37.5, -2, fout=0.02)
    place(m, seg(syn, 20, 32.5), 37.5, -7, fout=0.02)
    place(m, orch, 37.5, -4)
    place(m, seg(orch, 0, 2.5), 47.5, -4, fout=0.02)
    # outro 50-60: one last hit, piano rings out
    place(m, fx["impact"], 50.0, -4, fout=0.6)
    place(m, seg(orch, 0, 5), 50.0, 2, fout=3.0)
    place(m, seg(piano_lp, 0, 10), 50.0, 3, fin=0.3, fout=4.0)
    return m[:int(total * SR)]


def build_game_audio(shots, total):
    """Natural sound under the music: a quiet bed in the drops, up front in the quiet sections."""
    g = np.zeros((int(total * SR), 2), np.float32)
    level = {"intro": -3, "drop1": -15, "breakdown": -9, "drop2": -15, "outro": -10}
    for s in shots:
        src = os.path.join(SRC, s["clip"] + ".MTS")
        if s["speed"] < 0.999:  # slowed shots get slowed, lower-pitched sound
            a = read_audio(src, s["in"], s["out"] - s["in"], af=f"asetrate={SR * s['speed']:.0f},aresample={SR}")
        else:
            a = read_audio(src, s["in"], s["dur"])
        if np.abs(a).max() < 1e-4:
            continue  # silent clip (huddle shots have no audio track content)
        place(g, a, s["t0"], level[s["section"]], fin=0.02, fout=0.04)
    # crowd bed for the silent huddle outro, from the bench-side clip with the crowd behind it
    crowd = read_audio(os.path.join(SRC, "00103.MTS"), 0.5, 9.5)
    place(g, crowd, 50.0, -4, fin=0.6, fout=3.0)
    return g


def render_audio(path):
    shots = load_shots()
    total = shots[-1]["t1"]
    music = build_music(total)
    game = build_game_audio(shots, total)
    # the slow-mo corner kick: real-time ball strike lands right before the drop
    strike = read_audio(os.path.join(SRC, "00117.MTS"), 0.30, 0.5)
    place(game, strike, 12.5 - 0.30, -2, fout=0.1)
    mix = music + game
    tmp = os.path.join(TMP, "mix_raw.wav")
    pcm = (np.clip(mix / max(1.0, np.abs(mix).max()), -1, 1) * 32767).astype(np.int16)
    with wave.open(tmp, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    # measure integrated loudness, gain to -14 LUFS, then a true-peak limiter at -1 dBTP
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    lufs = float(r.split("Integrated loudness:")[1].split("I:")[1].split("LUFS")[0])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af",
                    f"volume={-14 - lufs:.2f}dB,alimiter=limit=0.89:attack=3:release=60:level=false",
                    "-ar", str(SR), "-c:a", "pcm_s24le", path], check=True)
    print(f"mix: measured {lufs:.1f} LUFS, gain {-14 - lufs:+.1f} dB")
    # separate stems at the same gain, for the editable CapCut project
    g = 10 ** ((-14 - lufs) / 20) / max(1.0, np.abs(mix).max())
    for name, x in (("music_stem.wav", music), ("game_audio_stem.wav", game)):
        with wave.open(os.path.join(TMP, name), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((np.clip(x * g, -1, 1) * 32767).astype(np.int16).tobytes())


def capcut_assets():
    """Per-shot graded clips + audio stems into ~/Movies (CapCut is sandboxed there)."""
    dst = os.path.expanduser("~/Movies/Trinity Hype Edit")
    os.makedirs(os.path.join(dst, "shots"), exist_ok=True)
    v = os.path.join(TMP, "video_only.mov")
    manifest = []
    for i, s in enumerate(load_shots()):
        name = f"{i + 1:02d}_{s['section']}_{s['clip']}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", v, "-vf",
                        f"trim=start_frame={s['f0']}:end_frame={s['f1']},setpts=PTS-STARTPTS",
                        "-an", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p",
                        os.path.join(dst, "shots", name)], check=True)
        manifest.append({"file": f"shots/{name}", "start": s["f0"] / FPS, "end": s["f1"] / FPS, "note": s["note"]})
    for n in ("music_stem.wav", "game_audio_stem.wav", "mix.wav"):
        subprocess.run(["cp", os.path.join(TMP, n), dst], check=True)
    json.dump(manifest, open(os.path.join(dst, "timeline.json"), "w"), indent=1)
    print(dst)


def mux():
    v, a = os.path.join(TMP, "video_only.mov"), os.path.join(TMP, "mix.wav")
    # master: 10-bit HEVC + PCM audio
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", v, "-i", a, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "pcm_s24le", "-shortest",
                    os.path.join(OUT, "Trinity_MSoccer_vs_Wesleyan_Hype_9x16_MASTER.mov")], check=True)
    # upload: H.264 High, 8-bit, AAC - what Instagram ingests most reliably
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", v, "-i", a, "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high",
                    "-pix_fmt", "yuv420p", "-maxrate", "40M", "-bufsize", "60M",
                    "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", "-shortest",
                    os.path.join(OUT, "Trinity_MSoccer_vs_Wesleyan_Hype_9x16_Instagram.mp4")], check=True)


if __name__ == "__main__":
    os.makedirs(TMP, exist_ok=True)
    if "--preview" in sys.argv:
        preview([float(v) for v in sys.argv[sys.argv.index("--preview") + 1].split(",")])
    elif "--video" in sys.argv:
        render_video(os.path.join(TMP, "video_only.mov"))
    elif "--audio" in sys.argv:
        render_audio(os.path.join(TMP, "mix.wav"))
    elif "--mux" in sys.argv:
        mux()
    elif "--capcut-assets" in sys.argv:
        capcut_assets()
    else:
        render_video(os.path.join(TMP, "video_only.mov"))
        render_audio(os.path.join(TMP, "mix.wav"))
        mux()
