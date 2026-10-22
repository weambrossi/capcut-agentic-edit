"""Render the podium celebration clip into assets/celebration/celebration.mp4.

Usage: python3 make_celebration.py "<original draft folder>"   (e.g. .../com.lveditor.draft/1008)
The background is the footage the draft shows during the celebration window, blurred.
"""
import json
import math
import os
import random
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import votes_config as C

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "assets", "celebration")
W, H, FPS = 1920, 1080, 30
GOLD = (255, 200, 40)
NAVY = (24, 38, 84)
NAVY_DARK = (14, 22, 52)
CONFETTI = [(255, 200, 40), (255, 255, 255), (36, 70, 160), (230, 60, 80), (80, 200, 255), (255, 120, 200)]

FONT_BIG = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def ease_out_cubic(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.7):
    x = max(0.0, min(1.0, x))
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def lerp(a, b, k):
    return a + (b - a) * k


def background_frames(draft, start, end, tmp):
    """Pull the frames the original edit shows in [start, end) from the topmost video track."""
    d = json.load(open(os.path.join(draft, "draft_info.json")))
    vids = {m["id"]: m for m in d["materials"]["videos"]}
    tracks = [t for t in d["tracks"] if t["type"] == "video"]
    n = int(round((end - start) * FPS))
    paths = []
    for i in range(n):
        t = start + i / FPS
        for tr in reversed(tracks):
            seg = next((s for s in tr["segments"]
                        if s["target_timerange"]["start"] <= t * 1e6 < s["target_timerange"]["start"] + s["target_timerange"]["duration"]), None)
            if seg:
                break
        src = (seg["source_timerange"]["start"] + (t * 1e6 - seg["target_timerange"]["start"]) * seg.get("speed", 1.0)) / 1e6
        paths.append((vids[seg["material_id"]]["path"], src))
    # grab each run of consecutive frames from the same file in one ffmpeg call
    frames, i = [], 0
    while i < n:
        path, s0 = paths[i]
        j = i
        while j + 1 < n and paths[j + 1][0] == path and abs(paths[j + 1][1] - paths[j][1] - 1 / FPS) < 1e-3:
            j += 1
        pat = os.path.join(tmp, f"bg{i:04d}_%04d.png")
        subprocess.run(["ffmpeg", "-loglevel", "fatal", "-y", "-ss", f"{s0:.3f}", "-i", path,
                        "-frames:v", str(j - i + 1), "-vf", f"fps={FPS},scale={W}:{H}", pat], check=True)
        for k in range(j - i + 1):
            f = pat % (k + 1)
            frames.append(f if os.path.exists(f) else frames[-1])
        i = j + 1
    return frames


def text_img(text, font_path, size, fill, stroke=0, stroke_fill=(0, 0, 0)):
    font = ImageFont.truetype(font_path, size)
    box = font.getbbox(text, stroke_width=stroke)
    im = Image.new("RGBA", (box[2] - box[0] + 4, box[3] - box[1] + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - box[0], 2 - box[1]), text, font=font, fill=fill,
                            stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def paste_center(canvas, im, cx, cy, scale=1.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    if alpha < 1.0:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def make_confetti(t0, cannons=(), rain=170, per_cannon=90, seed=42):
    """Confetti pieces: a rain from above starting at t0, plus a burst from each cannon (x, y)."""
    rng = random.Random(seed)
    confetti = []
    for _ in range(rain):
        confetti.append(dict(x=rng.uniform(-50, W + 50), y=rng.uniform(-700, -20), vx=rng.uniform(-60, 60),
                             vy=rng.uniform(250, 520), g=120, t0=t0, c=rng.choice(CONFETTI),
                             w=rng.uniform(10, 18), h=rng.uniform(16, 28), rot=rng.uniform(0, 360),
                             spin=rng.uniform(-500, 500), sway=rng.uniform(0, 6.28)))
    for cx, cy in cannons:
        side = -1 if cx < W / 2 else 1   # shoot inward and up
        for _ in range(per_cannon):
            a = math.radians(rng.uniform(55, 85))
            sp = rng.uniform(900, 1500)
            confetti.append(dict(x=cx, y=cy, vx=-side * math.cos(a) * sp * rng.uniform(0.3, 0.8),
                                 vy=-math.sin(a) * sp, g=1300, t0=t0 + 0.05 + rng.uniform(0, 0.08),
                                 c=rng.choice(CONFETTI), w=rng.uniform(10, 16), h=rng.uniform(14, 24),
                                 rot=rng.uniform(0, 360), spin=rng.uniform(-700, 700), sway=rng.uniform(0, 6.28)))
    return confetti


def draw_confetti(frame, confetti, t):
    dr = ImageDraw.Draw(frame)
    for p in confetti:
        tt = t - p["t0"]
        if tt < 0:
            continue
        x = p["x"] + p["vx"] * tt + 25 * math.sin(p["sway"] + tt * 5)
        y = p["y"] + p["vy"] * tt + 0.5 * p["g"] * tt * tt
        if y > H + 40 or x < -60 or x > W + 60:
            continue
        ang = math.radians(p["rot"] + p["spin"] * tt)
        flip = abs(math.cos(p["sway"] + tt * 8))      # tumbling look
        hw, hh = p["w"] / 2, p["h"] / 2 * max(0.15, flip)
        pts = [(x + dx * math.cos(ang) - dy * math.sin(ang), y + dx * math.sin(ang) + dy * math.cos(ang))
               for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
        dr.polygon(pts, fill=p["c"] + (255,))


def encoder(out):
    return subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16",
                             "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                            stdin=subprocess.PIPE)


def blurred(bg_path, t, ramp=0.35, radius=22, dim=110):
    bg = Image.open(bg_path).convert("RGB")
    k = ease_out_cubic(t / ramp)
    if k > 0:
        bg = bg.filter(ImageFilter.GaussianBlur(radius * k))
    frame = bg.convert("RGBA")
    frame.alpha_composite(Image.new("RGBA", (W, H), (8, 12, 30, int(dim * k))))
    return frame


def layout(counts):
    """Podium blocks and where each person lands. Tied people share a step."""
    tiers = sorted({c for c in counts.values() if c > 0}, reverse=True)
    groups = [[n for n in C.PEOPLE if counts[n] == c] for c in tiers]
    blocks = [dict(rank=1, x0=600, x1=1320, top=700, people=groups[0])]
    rest = groups[1:]
    if rest and len(rest[0]) == 2:            # two tied for 2nd: one each side
        blocks += [dict(rank=2, x0=150, x1=580, top=820, people=[rest[0][0]]),
                   dict(rank=2, x0=1340, x1=1770, top=820, people=[rest[0][1]])]
    else:
        if len(rest) > 0:
            blocks.append(dict(rank=2, x0=150, x1=580, top=820, people=rest[0]))
        if len(rest) > 1:
            blocks.append(dict(rank=3, x0=1340, x1=1770, top=880, people=rest[1]))
    land = {}
    for b in blocks:
        k = len(b["people"])
        head_h = (400 if k <= 2 else 300) if b["rank"] == 1 else (270 if k == 1 else 200)
        for i, n in enumerate(b["people"]):
            cx = lerp(b["x0"], b["x1"], (i + 0.5) / k)
            land[n] = dict(cx=cx, cy=b["top"] - head_h / 2 + 12, h=head_h, block=b)
    return blocks, land


def main():
    draft = sys.argv[1]
    os.makedirs(OUT_DIR, exist_ok=True)
    counts = C.counts()
    top = max(counts.values())
    winners = [n for n, c in counts.items() if c == top]
    blocks, land = layout(counts)
    dur = C.QUESTION_END - C.CELEB_START
    heads = {n: Image.open(os.path.join(HERE, "stickers", p)).convert("RGBA") for n, p in C.PEOPLE.items()}

    title = text_img("IT'S A TIE!" if len(winners) > 1 else winners[0].upper() + " WINS!",
                     FONT_BIG, 120, GOLD, stroke=8, stroke_fill=NAVY_DARK)
    subtitle = text_img("FUNNIEST ON THE TEAM", FONT_BIG, 50, (255, 255, 255), stroke=6, stroke_fill=NAVY_DARK)
    row_counter = {n: text_img(f"x{c}", FONT_BIG, 40, (255, 255, 255), stroke=4) for n, c in counts.items()}
    podium_counter = {n: text_img(f"x{c}", FONT_BIG, 64 if land[n]["block"]["rank"] == 1 else 48, GOLD, stroke=5,
                                  stroke_fill=NAVY_DARK) for n, c in counts.items() if n in land}

    glow = Image.new("RGBA", (900, 600), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((150, 100, 750, 500), fill=GOLD + (170,))
    glow = glow.filter(ImageFilter.GaussianBlur(70))

    confetti = make_confetti(0.75, cannons=((960 - 380, 720), (960 + 380, 720)))

    with tempfile.TemporaryDirectory() as tmp:
        bgs = background_frames(draft, C.CELEB_START, C.QUESTION_END, tmp)
        out = os.path.join(OUT_DIR, "celebration.mp4")
        enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16",
                                "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                               stdin=subprocess.PIPE)
        for fi, bg_path in enumerate(bgs):
            t = fi / FPS
            bg = Image.open(bg_path).convert("RGB")
            k_blur = ease_out_cubic(t / 0.35)
            if k_blur > 0:
                bg = bg.filter(ImageFilter.GaussianBlur(22 * k_blur))
            frame = bg.convert("RGBA")
            frame.alpha_composite(Image.new("RGBA", (W, H), (8, 12, 30, int(110 * k_blur))))

            # podium blocks rise from below
            rise = ease_out_cubic((t - 0.15) / 0.5)
            dr = ImageDraw.Draw(frame)
            for b in blocks:
                off = (1 - rise) * 420
                y0 = b["top"] + off
                if y0 + 14 >= H:
                    continue
                dr.rectangle((b["x0"], y0, b["x1"], H + 10), fill=NAVY + (240,))
                dr.rectangle((b["x0"], y0, b["x1"], y0 + 14), fill=GOLD + (255,))
                dr.rectangle((b["x0"], y0 + 14, b["x0"] + 10, H + 10), fill=NAVY_DARK + (255,))
                num = text_img(str(b["rank"]), FONT_BIG, 150 if b["rank"] == 1 else 110, (255, 255, 255, 60))
                paste_center(frame, num, (b["x0"] + b["x1"]) / 2, y0 + (H - y0) * 0.62)

            # winner glow
            k_land = (t - 0.25) / 0.6
            if k_land > 0.8:
                pulse = 0.85 + 0.15 * math.sin((t - 0.85) * 2 * math.pi * 1.4)
                wx = sum(land[n]["cx"] for n in winners) / len(winners)
                wy = sum(land[n]["cy"] for n in winners) / len(winners)
                paste_center(frame, glow, wx, wy, scale=1.0 + 0.05 * pulse,
                             alpha=min(1, (k_land - 0.8) / 0.4) * pulse)

            # heads fly from the top row onto the podium
            for slot, n in enumerate(C.PEOPLE):
                if n not in land:
                    continue
                L = land[n]
                sx0 = C.slot_x(slot, W) + C.HEAD_DX_PX
                k = ease_out_back(k_land, 1.2)
                cx, cy = lerp(sx0, L["cx"], k), lerp(C.ROW_Y_PX, L["cy"], k)
                h = lerp(C.HEAD_PX, L["h"], k)
                if n in winners and k_land > 1:
                    h *= 1 + 0.04 * math.sin((t - 0.85) * 2 * math.pi * 1.4)
                paste_center(frame, heads[n], cx, cy, scale=h / heads[n].height)
                # top-row counter fades as the heads leave; podium counter pops in after landing
                paste_center(frame, row_counter[n], C.slot_x(slot, W) + C.COUNTER_DX_PX, C.ROW_Y_PX + C.COUNTER_DY_PX,
                             alpha=1 - ease_out_cubic(t / 0.3))
                pc = ease_out_back((t - 0.9) / 0.3)
                if pc > 0:
                    b = L["block"]
                    paste_center(frame, podium_counter[n], L["cx"], b["top"] + 70, scale=pc)

            # title
            kt = ease_out_back((t - 0.85) / 0.35, 2.2)
            if kt > 0:
                paste_center(frame, title, W / 2, 175, scale=kt)
                paste_center(frame, subtitle, W / 2, 275, scale=kt)

            draw_confetti(frame, confetti, t)
            enc.stdin.write(frame.convert("RGB").tobytes())
            if fi in (0, 12, 27, len(bgs) - 1):
                frame.convert("RGB").save(os.path.join(OUT_DIR, f"preview_{fi:02d}.jpg"), quality=85)
        enc.stdin.close()
        enc.wait()
    print("wrote", out, f"{len(bgs)} frames, winners={winners}")


if __name__ == "__main__":
    main()
