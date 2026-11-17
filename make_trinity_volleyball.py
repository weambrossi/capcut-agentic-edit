"""Trinity women's volleyball vs Amherst hype edit: 58 s, 23.976 fps, 9:16 (1080x1920) or 16:9 (--wide).

Usage:
  python3 make_trinity_volleyball.py --init-edl          write edit_decision_list.json from CUT below
                                                         (auto-tracks the 9:16 crop on Trinity's white kits)
  python3 make_trinity_volleyball.py --preview T1,T2     graded stills (before|after) at timeline times
  python3 make_trinity_volleyball.py --audio             music + game audio mix only
  python3 make_trinity_volleyball.py                     full render (video, audio, mux)
  add --wide to any of the above for the 16:9 version (same cut, full frame)

Style follows make_trinity_soccer.py (EDL-driven shots, ffmpeg reframe + optical-flow slow-mo, numpy
grade, Apple Loops music, synthesised SFX) but is cut for volleyball: it opens cold on a kill instead of
a quiet intro, cuts each play from set to finish, and builds to a long rally before the second drop.
Music: Apple Loops "Go Time" set (Modern RnB pack, 120 BPM, D), royalty-free under the GarageBand licence.
Source footage is only read, never modified.
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Desktop/sports video/wvolleyball_vs_amherst_oct_3")
OUT = os.path.join(SRC, "Trinity Volleyball Hype Edit")
EDL = os.path.join(OUT, "edit_decision_list.json")
TMP = os.path.join(HERE, "out", "trinity_volleyball")
LOOPS = "/Library/Audio/Apple Loops/Apple"
WIDE = "--wide" in sys.argv
W, H = (1920, 1080) if WIDE else (1080, 1920)
TAG = "16x9" if WIDE else "9x16"
FPS_N, FPS_D = 24000, 1001
FPS = FPS_N / FPS_D
SR = 48000
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT

# Sections (timeline seconds): cold open 0-6, drop 1 6-22, rally breakdown 22-34, drop 2 34-52, outro 52-58.
# Each shot: (section, clip, in, out, speed, note, extra). in/out are source seconds; duration = (out-in)/speed.
# extra: zoom keyframes [[src_t, z]], flash (white hit on the first frames), cy (vertical centre 0..1).
CUT = [
    # cold open: a kill, the bench erupts, the team
    ("open", "00040", 11.0, 11.9, 1.0, "No. 12 approaches", {"zoom": [[11.0, 1.0], [11.9, 1.12]]}),
    ("open", "00040", 11.9, 12.4, 0.3, "the swing in slow motion", {"zoom": [[11.9, 1.12], [12.4, 1.22]]}),
    ("open", "00040", 12.4, 12.833, 1.0, "kill", {"zoom": [[12.4, 1.22], [12.833, 1.25]]}),
    ("open", "00023", 3.5, 5.0, 1.0, "Trinity bench erupts", {}),
    ("open", "00031", 0.5, 2.0, 1.0, "Team huddle", {"zoom": [[0.5, 1.0], [2.0, 1.08]]}),
    # drop 1: one play per bar or half bar
    ("drop1", "00046", 6.25, 7.5, 1.0, "Serve", {"flash": True, "zoom": [[6.25, 1.15], [7.5, 1.15]]}),
    ("drop1", "00046", 9.75, 10.5, 1.0, "point, high fives", {}),
    ("drop1", "00033", 3.5, 5.0, 0.75, "Double block at the net", {}),
    ("drop1", "00030", 4.95, 5.65, 0.35, "Swing into the Amherst double block, slow motion", {"zoom": [[4.95, 1.0], [5.65, 1.1]]}),
    ("drop1", "00059", 3.0, 4.0, 1.0, "Joust at the net", {"zoom": [[3.0, 1.1], [4.0, 1.1]]}),
    ("drop1", "00063", 1.6, 2.6, 1.0, "Block", {}),
    ("drop1", "00055", 2.25, 4.25, 1.0, "Rally at the net", {}),
    ("drop1", "00028", 29.25, 30.25, 1.0, "Two up on the block", {}),
    ("drop1", "00043", 11.75, 12.75, 1.0, "No. 24 attacks", {}),
    ("drop1", "00062", 2.75, 4.0, 1.0, "Swing from the pin", {}),
    ("drop1", "00062", 6.5, 7.25, 1.0, "libero and the team celebrate", {}),
    ("drop1", "00037", 4.0, 6.0, 1.0, "High fives", {}),
    # rally breakdown: one long rally, played (almost) in full
    ("rally", "00051", 2.5, 7.0, 1.0, "Long rally: serve receive and first attacks", {}),
    ("rally", "00051", 7.5, 10.0, 1.0, "Long rally: block, ball stays alive", {}),
    ("rally", "00051", 11.0, 13.75, 1.0, "Long rally: Amherst attack, dug", {}),
    ("rally", "00051", 18.0, 20.25, 1.0, "Long rally: Trinity finishes it", {}),
    # drop 2
    ("drop2", "00051", 20.25, 22.25, 1.0, "Team swarms after the long rally", {"flash": True}),
    ("drop2", "00052", 10.5, 15.5, 1.0, "Scrambling rally, bodies on the floor", {}),
    ("drop2", "00052", 17.75, 18.75, 1.0, "point Trinity", {}),
    ("drop2", "00034", 7.0, 8.5, 0.75, "Stuff block", {}),
    ("drop2", "00040", 15.5, 17.0, 1.0, "No. 12 again", {}),
    ("drop2", "00043", 17.25, 19.25, 1.0, "Digs on the floor", {}),
    ("drop2", "00058", 8.5, 11.0, 1.0, "Final rally", {}),
    ("drop2", "00058", 11.0, 13.0, 1.0, "point, team celebrates", {"zoom": [[11.0, 1.0], [13.0, 1.1]]}),
    # outro
    ("outro", "00066", 5.0, 6.8, 0.6, "BANTAMS huddle", {}),
    ("outro", "00066", 6.8, 8.3, 0.5, "huddle, fade out", {"zoom": [[6.8, 1.0], [8.3, 1.06]]}),
]


# 9:16 crop centres set by eye from gridded stills: [source_time, centre 0..1]. Shots not listed are auto-tracked.
CROPS = {
    ("00040", 11.0): [[11.0, 0.84], [11.75, 0.80], [11.9, 0.78]],
    ("00040", 11.9): [[11.9, 0.77], [12.15, 0.82], [12.4, 0.84]],
    ("00040", 12.4): [[12.4, 0.84]],
    ("00023", 3.5): [[3.5, 0.50], [5.0, 0.55]],
    ("00031", 0.5): [[0.5, 0.45]],
    ("00046", 6.25): [[6.25, 0.25], [7.0, 0.24], [7.5, 0.45]],
    ("00046", 9.75): [[9.75, 0.45], [10.5, 0.40]],
    ("00033", 3.5): [[3.5, 0.45], [4.0, 0.47], [5.0, 0.45]],
    ("00030", 4.95): [[4.95, 0.55], [5.15, 0.75], [5.65, 0.74]],
    ("00059", 3.0): [[3.0, 0.40], [4.0, 0.45]],
    ("00063", 1.6): [[1.6, 0.35], [2.1, 0.47], [2.6, 0.50]],
    ("00055", 2.25): [[2.25, 0.50], [3.0, 0.52], [3.75, 0.42], [4.25, 0.45]],
    ("00028", 29.25): [[29.25, 0.40], [30.25, 0.45]],
    ("00043", 11.75): [[11.75, 0.16], [12.5, 0.16], [12.75, 0.28]],
    ("00062", 2.75): [[2.75, 0.22], [3.5, 0.28], [4.0, 0.45]],
    ("00062", 6.5): [[6.5, 0.38], [7.25, 0.42]],
    ("00037", 4.0): [[4.0, 0.55], [5.0, 0.50], [6.0, 0.52]],
    ("00051", 2.5): [[2.5, 0.45], [3.0, 0.50], [3.5, 0.55], [4.0, 0.58], [4.5, 0.52], [5.0, 0.40],
                     [5.5, 0.48], [6.0, 0.50], [7.0, 0.45]],
    ("00051", 7.5): [[7.5, 0.40], [8.0, 0.45], [8.5, 0.36], [9.0, 0.32], [9.5, 0.40], [10.0, 0.45]],
    ("00051", 11.0): [[11.0, 0.40], [11.5, 0.40], [12.0, 0.45], [12.5, 0.50], [13.0, 0.45], [13.75, 0.50]],
    ("00051", 18.0): [[18.0, 0.50], [18.5, 0.50], [19.0, 0.42], [19.5, 0.42], [20.25, 0.50]],
    ("00051", 20.25): [[20.25, 0.47], [21.5, 0.52], [22.25, 0.52]],
    ("00052", 10.5): [[10.5, 0.50], [11.25, 0.60], [11.75, 0.55], [12.25, 0.50], [12.75, 0.42], [13.25, 0.55],
                      [14.25, 0.50], [14.75, 0.55], [15.5, 0.60]],
    ("00052", 17.75): [[17.75, 0.32], [18.25, 0.35], [18.75, 0.40]],
    ("00034", 7.0): [[7.0, 0.50], [7.5, 0.55], [7.75, 0.45], [8.5, 0.42]],
    ("00040", 15.5): [[15.5, 0.34], [15.75, 0.30], [16.25, 0.35], [17.0, 0.32]],
    ("00043", 17.25): [[17.25, 0.60], [17.75, 0.70], [18.25, 0.60], [18.75, 0.55], [19.25, 0.60]],
    ("00058", 8.5): [[8.5, 0.55], [9.0, 0.45], [9.5, 0.42], [10.0, 0.35], [11.0, 0.40]],
    ("00058", 11.0): [[11.0, 0.30], [11.75, 0.45], [13.0, 0.45]],
    ("00066", 5.0): [[5.0, 0.45]],
    ("00066", 6.8): [[6.8, 0.45]],
}


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


def pw_expr(keys, var):
    """Piecewise-linear expression over var from [(t, value)] keyframes."""
    if len(keys) == 1:
        return f"{keys[0][1]:.4f}"
    e = f"{keys[-1][1]:.4f}"
    for (ta, xa), (tb, xb) in reversed(list(zip(keys, keys[1:]))):
        lerp = f"({xa:.4f}+({xb - xa:.4f})*({var}-{ta:.3f})/{max(tb - ta, 1e-3):.3f})"
        e = f"if(lt({var},{tb:.3f}),{lerp},{e})"
    return f"if(lt({var},{keys[0][0]:.3f}),{keys[0][1]:.4f},{e})"


def reframe_filters(s):
    """scale (animated when zooming) + crop to W x H. Keyframes are in source time; after slow-mo the
    filter clock t is output time, so source-relative time is t*speed."""
    tv = f"(t*{s['speed']:.4f})"
    rel = lambda keys: [(k - s["in"], v) for k, v in keys]
    zoom = rel(s.get("zoom") or [[s["in"], 1.0]])
    base = H / 1080  # 9:16 crops a 1080-high window, 16:9 uses the full height
    z = pw_expr(zoom, tv)
    animated = len({v for _, v in zoom}) > 1
    if animated:
        sc = (f"scale=w='trunc(1920*{base:.5f}*{z}/2)*2':h='trunc(1080*{base:.5f}*{z}/2)*2'"
              f":eval=frame:flags=lanczos")
    else:
        zz = zoom[0][1]
        sc = f"scale={round(1920 * base * zz / 2) * 2}:{round(1080 * base * zz / 2) * 2}:flags=lanczos"
    cx = pw_expr(rel(s["x"]), tv) if not WIDE else "0.5"
    if WIDE and s.get("xw"):
        cx = pw_expr(rel(s["xw"]), tv)
    cy = f"{s.get('cy', 0.5):.3f}"
    crop = (f"crop={W}:{H}:x='max(0,min(iw-{W},({cx})*iw-{W / 2}))'"
            f":y='max(0,min(ih-{H},{cy}*ih-{H / 2}))'")
    return [sc, crop]


def shot_frames(s, nframes):
    """Yield float32 RGB frames (H, W, 3) in 0..1 for one shot, retimed and reframed."""
    vf = ["hqdn3d=2:1.5:4:4"]
    if s["speed"] < 0.999:
        vf += [f"minterpolate=fps={FPS / s['speed']:.4f}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
               f"setpts=PTS/{s['speed']}", f"fps={FPS_N}/{FPS_D}"]
    vf += reframe_filters(s)
    cmd = ["ffmpeg", "-v", "fatal", "-ss", f"{s['in']:.3f}", "-i", os.path.join(SRC, s["clip"] + ".MTS"),
           "-an", "-vf", ",".join(vf), "-frames:v", str(nframes), "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = W * H * 3 * 2
    last = None
    for _ in range(nframes):
        buf = p.stdout.read(n)
        if len(buf) < n:  # source ran short: hold the last frame
            if last is None:
                raise RuntimeError(f"no frames from {s['clip']} @ {s['in']}")
            yield last
            continue
        last = np.frombuffer(buf, np.uint16).reshape(H, W, 3).astype(np.float32) / 65535
        yield last
    p.stdout.close()
    p.wait()


# ---------------------------------------------------------------- auto reframe (9:16)
def white_kit_centre(frame):
    """Horizontal centre of Trinity's white jerseys: bright, low-chroma pixels in the player band."""
    h = frame.shape[0]
    band = frame[int(h * 0.30):int(h * 0.92)]
    y = band.mean(-1)
    ref = np.percentile(y, 99.5)
    chroma = band.max(-1) - band.min(-1)
    m = (y > 0.62 * ref) & (chroma < 0.10 * ref + 0.02)
    # drop rows that are mostly "white" (the net tape, banners): players are compact blobs
    rowfrac = m.mean(1, keepdims=True)
    m &= rowfrac < 0.25
    cols = m.sum(0).astype(np.float32)
    if cols.sum() < 40:
        return None
    xs = np.arange(len(cols)) / len(cols)
    return float((cols * xs).sum() / cols.sum())


def auto_track(clip, t_in, t_out):
    """Crop-centre keyframes every 0.25 s of source time, smoothed so the frame glides."""
    fps, w, h = 8, 480, 270
    raw = subprocess.run(["ffmpeg", "-v", "fatal", "-ss", f"{t_in:.3f}", "-i", os.path.join(SRC, clip + ".MTS"),
                          "-t", f"{t_out - t_in:.3f}", "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32) / 255
    c = [white_kit_centre(f) for f in fr]
    good = [v for v in c if v is not None]
    fill = float(np.median(good)) if good else 0.5
    c = np.array([fill if v is None else v for v in c])
    k = 5  # ~0.6 s moving average, edge-padded
    c = np.convolve(np.pad(c, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
    half = 0.5 * (1080 * 9 / 16) / 1920  # half crop width as a fraction of the frame
    c = np.clip(c, half, 1 - half)
    keys = [[round(t_in + i / fps, 3), round(float(v), 3)] for i, v in enumerate(c) if i % 2 == 0]
    keys.append([round(t_out, 3), round(float(c[-1]), 3)])
    return keys


def init_edl():
    os.makedirs(OUT, exist_ok=True)
    keep = {}
    if os.path.exists(EDL) and "--retrack" not in sys.argv:  # keep hand-tuned crops for unchanged shots
        for s in json.load(open(EDL))["shots"]:
            keep[(s["clip"], s["in"], s["out"])] = s["x"]
    shots = []
    for sec, clip, a, b, sp, note, extra in CUT:
        x = CROPS.get((clip, a)) or keep.get((clip, a, b)) or auto_track(clip, a, b)
        shots.append({"section": sec, "clip": clip, "in": a, "out": b, "speed": sp, "note": note, "x": x, **extra})
        print(f"  {clip} {a:6.2f}-{b:6.2f}  x {x[0][1]:.2f}..{x[-1][1]:.2f}  {note}")
    json.dump({"_about": "Trinity vs Amherst women's volleyball hype edit. Each shot: source clip, in/out "
                         "(source seconds), playback speed, x = 9:16 crop-centre keyframes [source_time, 0..1], "
                         "optional zoom keyframes [source_time, scale], flash. 120 BPM: 1 beat = 0.5 s, 1 bar = 2 s. "
                         "Edit and re-run make_trinity_volleyball.py.",
               "source_dir": SRC, "fps": 23.976, "bpm": BPM, "shots": shots}, open(EDL, "w"), indent=1)
    t = sum((s["out"] - s["in"]) / s["speed"] for s in shots)
    print(f"{len(shots)} shots, {t:.2f} s -> {EDL}")


# ---------------------------------------------------------------- grade
def luma(x):
    return x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722


def shot_stats(frame):
    """Levels and white balance for a shot, from its first frame. The camera's flat profile puts black
    near 4% and the white kits near 55%, so each shot is stretched from its own black to its own white."""
    y = luma(frame)
    ch = frame.max(-1) - frame.min(-1)
    sel = (y > np.percentile(y, 97)) & (ch < 0.12) & (frame.max(-1) < 0.97)
    if sel.sum() > 300:
        c = frame[sel].mean(0)
        wb = np.clip(c.mean() / c, 0.85, 1.2)
        wb = 1 + 0.85 * (wb - 1)  # white kits go (almost) neutral
    else:
        wb = np.ones(3)
    lo = float(np.percentile(y, 0.5)) * 0.85
    hi = float(np.percentile(y, 99.6))
    gain = float(np.clip(0.90 / max(hi - lo, 1e-3), 1.0, 2.6))
    gain = min(gain, 0.42 / max(float(np.median(y)) - lo, 1e-3))  # don't lift dark shots to grey
    gain = max(gain, 1.0)
    return (lo, gain), wb.astype(np.float32)


_vig = None


def grade(x, gain, wb):
    global _vig
    if _vig is None:
        yy, xx = np.mgrid[0:x.shape[0], 0:x.shape[1]].astype(np.float32)
        r = np.sqrt(((xx / x.shape[1] - 0.5) * (x.shape[1] / max(x.shape)) * 1.6) ** 2
                    + ((yy / x.shape[0] - 0.5) * (x.shape[0] / max(x.shape)) * 1.6) ** 2)
        _vig = (1 - 0.26 * np.clip((r - 0.32) / 0.5, 0, 1) ** 1.5)[..., None].astype(np.float32)
    lo, gain = gain
    x = np.maximum(x * wb - lo, 0) * gain
    x = np.power(x, 1.04)
    k = 0.74
    x = np.where(x > k, k + (1 - k) * np.tanh((x - k) / (1 - k)), x)  # keep white jerseys from clipping
    x = x + 0.75 * x * (1 - x) * (x - 0.40)  # S-curve: punchy mids
    y = luma(x)[..., None]
    sat = 1.28 * np.clip(y / 0.15, 0.55, 1.0)  # richer navy and gold, quiet shadows
    x = y + (x - y) * sat
    # split tone: cool shadows, warm highlights (gym lights, maple floor)
    sh = np.clip(1 - y / 0.30, 0, 1)
    hi = np.clip((y - 0.55) / 0.45, 0, 1)
    x = x + sh * np.array([-0.006, 0.0, 0.010], np.float32) + hi * np.array([0.010, 0.004, -0.010], np.float32)
    x = x * _vig
    return np.clip(x, 0, 1)


# ---------------------------------------------------------------- titles
def end_title():
    """RGBA overlay: TRINITY / VOLLEYBALL, low in frame."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    big = ImageFont.truetype("/System/Library/Fonts/Avenir Next Condensed.ttc", int(W * (0.075 if WIDE else 0.14)), index=8)
    small = ImageFont.truetype("/System/Library/Fonts/Avenir Next Condensed.ttc", int(W * (0.026 if WIDE else 0.052)), index=2)
    t1, t2 = "TRINITY", "W O M E N ' S   V O L L E Y B A L L"
    y0 = int(H * (0.38 if WIDE else 0.40))
    b1 = d.textbbox((0, 0), t1, font=big)
    d.text(((W - (b1[2] - b1[0])) / 2 - b1[0], y0), t1, font=big, fill=(255, 255, 255, 255))
    b2 = d.textbbox((0, 0), t2, font=small)
    yb = y0 + (b1[3] - b1[1]) + b1[1] + int(H * 0.03)
    d.text(((W - (b2[2] - b2[0])) / 2 - b2[0], yb), t2, font=small, fill=(240, 196, 64, 255))
    yr = yb + (b2[3] - b2[1]) + b2[1] + int(H * 0.018)
    d.rectangle([W * 0.42, yr, W * 0.58, yr + max(3, H // 400)], fill=(240, 196, 64, 255))
    a = np.asarray(im).astype(np.float32) / 255
    return a[..., :3], a[..., 3:4]


# ---------------------------------------------------------------- preview
def preview(times):
    os.makedirs(os.path.join(TMP, "preview"), exist_ok=True)
    shots = load_shots()
    for T in times:
        s = next(s for s in shots if s["t0"] <= T < s["t1"])
        k = int(round((T - s["t0"]) * FPS))
        frames = list(shot_frames(s, k + 1))
        gain, wb = shot_stats(frames[0])
        before, after = frames[k], grade(frames[k], gain, wb)
        im = np.concatenate([before, after], 1)
        Image.fromarray((im * 255).astype(np.uint8)).resize((W // 2 * 2 // 2 * 2 // 2, H // 2)).save(
            os.path.join(TMP, "preview", f"{TAG}_{T:05.2f}.jpg"), quality=88)
        print(f"{T:6.2f}s  {s['clip']} @{s['in'] + (T - s['t0']) * s['speed']:.2f}  lo={gain[0]:.3f} gain={gain[1]:.2f} wb={np.round(wb, 3)}")


# ---------------------------------------------------------------- full render
def render_video(path):
    shots = load_shots()
    total = shots[-1]["f1"]
    end = shots[-1]["t1"]
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-s", f"{W}x{H}",
         "-r", f"{FPS_N}/{FPS_D}", "-i", "-",
         "-vf", "unsharp=5:5:0.5:5:5:0,noise=alls=3:allf=t,format=yuv420p10le",
         "-c:v", "libx265", "-preset", "slow", "-crf", "12", "-tag:v", "hvc1", path],
        stdin=subprocess.PIPE)
    title_rgb, title_a = end_title()
    title_in = shots[-2]["t0"] + 0.8
    done = 0
    for i, s in enumerate(shots):
        n = s["f1"] - s["f0"]
        gain = wb = None
        for j, fr in enumerate(shot_frames(s, n)):
            if gain is None:
                gain, wb = shot_stats(fr)
            g = grade(fr, gain, wb)
            t = (s["f0"] + j) / FPS
            if s.get("flash") and j < 5:  # white hit on the downbeat
                g = g + (1 - g) * (0.75 * (1 - j / 5) ** 2)
            if t >= title_in:
                a = title_a * min(1.0, (t - title_in) / 0.8)
                g = g * (1 - 0.35 * min(1.0, (t - title_in) / 0.8))  # dim the picture under the title
                g = g * (1 - a) + title_rgb * a
            if t > end - 1.2:
                g = g * max(0.0, (end - t) / 1.2)
            enc.stdin.write((np.clip(g, 0, 1) * 65535).astype(np.uint16).tobytes())
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
    if i < 0:
        x, env, i = x[-i:], env[-i:], 0
    j = min(len(buf), i + len(x))
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
    rng = np.random.default_rng(11)
    out = {}
    for name, d in (("riser", 4.0), ("riser_short", 2.0)):
        t = np.arange(int(d * SR)) / SR
        noise = rng.standard_normal((len(t), 2)).astype(np.float32)
        r = onepole(noise, 300 * (40 ** (t / d))) - onepole(noise, 150)
        tone = np.sin(2 * np.pi * np.cumsum(220 * 5 ** (t / d)) / SR)[:, None]
        out[name] = ((0.6 * r + 0.12 * tone) * ((t / d) ** 2.4)[:, None]).astype(np.float32)
    d = 1.0
    t = np.arange(int(d * SR)) / SR
    noise = rng.standard_normal((len(t), 2)).astype(np.float32)
    out["revcym"] = ((noise - onepole(noise, 3500)) * ((t / d) ** 3)[:, None] * 0.7).astype(np.float32)
    d = 2.0
    t = np.arange(int(d * SR)) / SR
    f = 34 + 46 * np.exp(-t / 0.15)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.55)
    thump = onepole(rng.standard_normal((len(t), 2)).astype(np.float32), 1100) * np.exp(-t / 0.04)[:, None] * 3
    out["impact"] = (boom[:, None] * 0.9 + thump).astype(np.float32)
    d = 0.5
    t = np.arange(int(d * SR)) / SR
    noise = rng.standard_normal((len(t), 2)).astype(np.float32)
    w = onepole(noise, 5000 * (0.1 ** (t / d))) - onepole(noise, 250)
    out["whoosh"] = (w * np.sin(np.pi * t / d)[:, None] ** 2 * 0.8).astype(np.float32)
    return out


def loop(name, pack="04 Modern RnB", af=None):
    a = read_audio(os.path.join(LOOPS, pack, name + ".caf"), af=af)
    return a / max(np.abs(a).max(), 1e-6) * 0.7


def tile(x, dur):
    """Repeat a loop to fill dur seconds."""
    n = int(dur * SR)
    return np.tile(x, (n // len(x) + 1, 1))[:n]


def build_music(shots, total):
    beat1, beat2, bass, lead = loop("Go Time Beat 01"), loop("Go Time Beat 02"), loop("Go Time Layered Bass"), loop("World Champion Synth")
    lead_lp = loop("World Champion Synth", af="lowpass=f=900,lowpass=f=900")
    bass_lp = loop("Go Time Layered Bass", af="lowpass=f=180,lowpass=f=180")
    hats = loop("Go Time Beat 02", af="highpass=f=6000,highpass=f=6000")
    brick = loop("Busting Brick Beat 02")
    roll = loop("Big Snare Roll Topper", "02 Electro House", af=f"atempo={BPM / 128:.5f}")
    m = np.zeros((int((total + 3) * SR), 2), np.float32)
    fx = sfx()
    sec = {s["section"]: [] for s in shots}
    for s in shots:
        sec[s["section"]].append(s)
    t_drop1 = sec["drop1"][0]["t0"]
    t_rally = sec["rally"][0]["t0"]
    t_drop2 = sec["drop2"][0]["t0"]
    t_outro = sec["outro"][0]["t0"]
    # contact frame of the cold-open kill: end of the slow swing shot minus its tail
    swing = sec["open"][1]
    t_kill = swing["t0"] + (12.0 - swing["in"]) / swing["speed"]

    # cold open: crowd only, a boom on the kill, then the hook creeps in filtered and a riser into the drop
    place(m, fx["impact"], t_kill, -2, fout=0.5)
    place(m, tile(lead_lp, t_drop1 - sec["open"][3]["t0"]), sec["open"][3]["t0"], -3, fin=1.0)
    place(m, fx["riser"], t_drop1 - len(fx["riser"]) / SR, -8, fout=0.02)
    # drop 1
    d1 = t_rally - t_drop1
    place(m, fx["impact"], t_drop1, -3, fout=0.4)
    place(m, tile(beat1, d1), t_drop1, 0, fout=0.02)
    place(m, tile(bass, d1), t_drop1, -3, fout=0.02)
    place(m, tile(lead, d1), t_drop1, -6, fout=0.02)
    place(m, fx["whoosh"], t_rally - 0.4, -8)
    # rally: the band drops out to hats and a filtered pulse so the rally's own sound carries it,
    # snare roll + riser over the last two bars, one beat of silence before the drop
    dr = t_drop2 - t_rally
    place(m, tile(lead_lp, dr - BEAT), t_rally, -4, fout=0.05)
    place(m, tile(bass_lp, dr - BEAT), t_rally, -4, fout=0.05)
    place(m, tile(hats, dr - BEAT - 2 * BAR), t_rally + 2 * BAR, -10, fin=2.0, fout=0.05)
    place(m, tile(roll, 2 * BAR - BEAT), t_drop2 - 2 * BAR, -9, fin=1.5, fout=0.02)
    place(m, fx["riser"], t_drop2 - BEAT - len(fx["riser"]) / SR, -9, fout=0.02)
    place(m, fx["revcym"], t_drop2 - len(fx["revcym"]) / SR, -10, fout=0.01)
    # drop 2: busier beat with an extra percussion layer
    d2 = t_outro - t_drop2
    place(m, fx["impact"], t_drop2, -2, fout=0.4)
    place(m, tile(beat2, d2), t_drop2, 0, fout=0.02)
    place(m, tile(brick, d2), t_drop2, -12, fout=0.02)
    place(m, tile(bass, d2), t_drop2, -3, fout=0.02)
    place(m, tile(lead, d2), t_drop2, -5, fout=0.02)
    place(m, fx["riser_short"], t_outro - len(fx["riser_short"]) / SR, -12, fout=0.02)
    # outro: last hit, the hook rings out filtered
    place(m, fx["impact"], t_outro, -3, fout=0.8)
    place(m, tile(lead_lp, total - t_outro + 1), t_outro, 0, fout=3.0)
    place(m, tile(bass_lp, BAR), t_outro, -4, fout=1.5)
    return m[:int(total * SR)]


def build_game_audio(shots, total):
    """Ball contacts and crowd: up front in the cold open and the rally, a bed under the drops."""
    g = np.zeros((int(total * SR), 2), np.float32)
    level = {"open": -4, "drop1": -14, "rally": -6, "drop2": -14, "outro": -10}
    for s in shots:
        src = os.path.join(SRC, s["clip"] + ".MTS")
        if s["speed"] < 0.999:  # slowed shots get slowed, lower-pitched sound
            a = read_audio(src, s["in"], s["out"] - s["in"], af=f"asetrate={SR * s['speed']:.0f},aresample={SR}")
        else:
            a = read_audio(src, s["in"], s["dur"])
        place(g, a, s["t0"], level[s["section"]], fin=0.02, fout=0.04)
    return g


def render_audio(path):
    shots = load_shots()
    total = shots[-1]["t1"]
    music = build_music(shots, total)
    game = build_game_audio(shots, total)
    mix = music + game
    mix[-int(1.2 * SR):] *= np.linspace(1, 0, int(1.2 * SR))[:, None]
    tmp = os.path.join(TMP, "mix_raw.wav")
    pcm = (np.clip(mix / max(1.0, np.abs(mix).max()), -1, 1) * 32767).astype(np.int16)
    with wave.open(tmp, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    lufs = float(r.split("Integrated loudness:")[1].split("I:")[1].split("LUFS")[0])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af",
                    f"volume={-14 - lufs:.2f}dB,alimiter=limit=0.89:attack=3:release=60:level=false",
                    "-ar", str(SR), "-c:a", "pcm_s24le", path], check=True)
    print(f"mix: measured {lufs:.1f} LUFS, gain {-14 - lufs:+.1f} dB")


def mux():
    v, a = os.path.join(TMP, f"video_{TAG}.mov"), os.path.join(TMP, "mix.wav")
    base = os.path.join(OUT, f"Trinity_WVolleyball_vs_Amherst_Hype_{TAG}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", v, "-i", a, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "pcm_s24le", "-shortest", base + "_MASTER.mov"], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", v, "-i", a, "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high",
                    "-pix_fmt", "yuv420p", "-maxrate", "40M", "-bufsize", "60M",
                    "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", "-shortest",
                    base + f"_{'YouTube' if WIDE else 'Instagram'}.mp4"], check=True)


if __name__ == "__main__":
    os.makedirs(TMP, exist_ok=True)
    if "--init-edl" in sys.argv:
        init_edl()
    elif "--preview" in sys.argv:
        preview([float(v) for v in sys.argv[sys.argv.index("--preview") + 1].split(",")])
    elif "--video" in sys.argv:
        render_video(os.path.join(TMP, f"video_{TAG}.mov"))
    elif "--audio" in sys.argv:
        render_audio(os.path.join(TMP, "mix.wav"))
    elif "--mux" in sys.argv:
        mux()
    else:
        render_video(os.path.join(TMP, f"video_{TAG}.mov"))
        render_audio(os.path.join(TMP, "mix.wav"))
        mux()
