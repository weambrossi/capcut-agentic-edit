"""Render the 30-second Rent-a-Dent promo (1080x1920, 30 fps) to out/rent_a_dent_promo.mp4.

Usage: python3 make_rent_a_dent.py [--preview T1,T2,...]
Sources live in ~/Downloads (the same files the "1018 (1)" CapCut draft uses). Every frame is
composed in Python (zooms, shakes, flashes, meme text), the audio is cut and mixed with ffmpeg.
--preview writes single frames at the given times to out/preview/ instead of rendering.
"""
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
DL = os.path.expanduser("~/Downloads")
VID_A = os.path.join(DL, "1252f43cfa5e4777bbf98fea38977311.MOV")  # dorm serenade, 960x540
VID_B = os.path.join(DL, "fe72ecaabb7e43ddb5663d4b0f3c6a25.MOV")  # vertical solo, 356x634
PHOTO = os.path.join(DL, "IMG_7581.jpg")  # selfie, 4032x3024
SONG = os.path.join(DL, "Jeremih - Birthday Sex.mp3")
OUT_DIR = os.path.join(HERE, "out")
TMP = os.path.join(OUT_DIR, "tmp")
W, H, FPS = 1080, 1920, 30
SR = 44100
BOLD = ("/System/Library/Fonts/Avenir Next.ttc", 0)
HEAVY = ("/System/Library/Fonts/Avenir Next.ttc", 8)
YELLOW = (255, 214, 10)
TOTAL = 29.8

# ---------------------------------------------------------------- timeline
# (t0, t1, kind, params). Video kinds pull from their source at src + (t - t0) * speed.
SHOTS = [
    (0.0, 3.0, "photo_intro", {}),
    (3.0, 5.4, "title", {}),
    (5.4, 7.2, "A", {"src": 8.4, "speed": 2.0}),
    (7.2, 13.4, "B", {"src": 6.0}),
    (13.4, 17.4, "A", {"src": 62.0, "zoom": 1.25}),
    (17.4, 19.0, "A", {"src": 75.0, "zoom": 1.15}),
    (19.0, 21.2, "B", {"src": 24.0}),
    (21.2, 23.8, "A", {"src": 70.2, "zoom": 1.3}),
    (23.8, 26.4, "A", {"src": 80.0, "zoom": 1.2}),
    (26.4, TOTAL, "photo_outro", {}),
]
# quick zoom punches (time, strength) and shakes (time, duration, amplitude px)
PUNCHES = [(5.4, 0.08), (7.2, 0.07), (8.34, 0.08), (13.4, 0.08), (17.4, 0.06), (19.0, 0.07),
           (21.2, 0.07), (23.8, 0.08)]
SHAKES = [(1.9, 0.45, 14), (3.0, 0.25, 12), (26.4, 0.2, 10)]
FLASHES = [2.95, 5.4, 7.2, 13.4, 17.4, 19.0, 21.2, 23.8, 26.4]
# captions: (t0, t1, text, y, size, colour, extra)
LYRIC = {"lyric": True}
TEXTS = [
    (0.08, 1.9, "Is your birthday\ncoming up?", 300, 96, "white", {}),
    (1.95, 3.0, "Let us handle it.", 1560, 92, "white", {}),
    (3.1, 5.4, "INTRODUCING", 690, 44, "white", {"tracking": 14}),
    (3.3, 5.4, "RENT-A-DENT", 830, 150, YELLOW, {"heavy": True}),
    (3.6, 5.4, "a cappella, delivered.", 985, 54, "white", {}),
    (5.45, 7.2, "We show up.", 320, 100, "white", {}),
    (7.25, 9.7, "The whole group.", 300, 92, "white", {}),
    (7.7, 9.15, "It's your birthday", 1600, 62, "white", LYRIC),
    (9.15, 11.6, "so I know you want to ride out", 1600, 62, "white", LYRIC),
    (12.05, 13.4, "even if we only go to my house", 1600, 62, "white", LYRIC),
    (9.75, 13.4, "Any room.\nAny time.", 300, 92, "white", {}),
    (13.45, 17.4, "Live at your door.\nReady when you are.", 330, 84, "white", {}),
    (17.45, 19.0, "Crowd approved.", 330, 92, "white", {}),
    (21.25, 23.8, "No mics.\nNo backing track.", 330, 88, "white", {}),
    (23.85, 26.4, "Just the Dents.", 330, 96, "white", {}),
    (26.5, TOTAL, "RENT-A-DENT", 280, 140, YELLOW, {"heavy": True}),
    (26.75, TOTAL, "Birthdays  ·  Serenades  ·  Surprises", 430, 44, "white", {}),
    (27.2, TOTAL, "DM us to book", 1600, 70, (20, 20, 20), {"pill": YELLOW}),
    (28.0, TOTAL, "(he's coming too)", 1240, 54, "white", {"arrow": True}),
]
# the left guy's face in the photo (source pixels) — the smash-zoom target
FACE = (600, 1230)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- text
_font_cache = {}


def font(face, size):
    key = (face, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(face[0], size, index=face[1])
    return _font_cache[key]


def render_line(line, size, colour, face, tracking=0):
    f = font(face, size)
    if not tracking:
        box = f.getbbox(line)
        im = Image.new("RGBA", (box[2] - box[0] + 4, int(size * 1.3)))
        ImageDraw.Draw(im).text((-box[0] + 2, int(size * 0.05)), line, font=f, fill=colour)
        return im
    # letter-spaced line, one glyph at a time
    widths = [f.getlength(ch) for ch in line]
    w = int(sum(widths) + tracking * (len(line) - 1)) + 4
    im = Image.new("RGBA", (w, int(size * 1.3)))
    d = ImageDraw.Draw(im)
    x = 2
    for ch, cw in zip(line, widths):
        d.text((x, int(size * 0.05)), ch, font=f, fill=colour)
        x += cw + tracking
    return im


_text_cache = {}


def text_image(text, size, colour, extra):
    key = (text, size, str(colour), str(extra))
    if key in _text_cache:
        return _text_cache[key]
    face = HEAVY if extra.get("heavy") else BOLD
    lines = [render_line(l, size, colour, face, extra.get("tracking", 0)) for l in text.split("\n")]
    gap = -int(size * 0.12)
    w = max(l.width for l in lines)
    h = sum(l.height for l in lines) + gap * (len(lines) - 1)
    img = Image.new("RGBA", (w, h))
    y = 0
    for l in lines:
        img.paste(l, ((w - l.width) // 2, y), l)
        y += l.height + gap
    if extra.get("pill"):
        px, py = 56, 26
        p = Image.new("RGBA", (w + 2 * px, h + 2 * py))
        ImageDraw.Draw(p).rounded_rectangle([0, 0, p.width - 1, p.height - 1], radius=p.height // 2,
                                            fill=extra["pill"] + (255,))
        p.paste(img, (px, py), img)
        img = p
    elif extra.get("lyric"):
        bg = Image.new("RGBA", (w + 64, h + 28))
        ImageDraw.Draw(bg).rounded_rectangle([0, 0, bg.width - 1, bg.height - 1], radius=22,
                                             fill=(0, 0, 0, 140))
        bg.paste(img, (32, 14), img)
        img = bg
    else:
        # soft drop shadow instead of a cartoon outline
        pad = size // 3
        out = Image.new("RGBA", (w + 2 * pad, h + 2 * pad))
        a = img.split()[3].point(lambda v: int(v * 0.8))
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sh.putalpha(a)
        out.paste(sh, (pad, pad + max(2, size // 22)), sh)
        out = out.filter(ImageFilter.GaussianBlur(max(3, size // 14)))
        out.paste(img, (pad, pad), img)
        img = out
    _text_cache[key] = img
    return img


def place_text(frame, t, item):
    t0, t1, text, y, size, colour, extra = item
    if not (t0 <= t < t1):
        return
    img = text_image(text, size, colour, extra)
    age = t - t0
    # quick fade + rise in, slight settle in scale
    k = ease_out(age / 0.22)
    s = 0.94 + 0.06 * k
    if img.width * s > W - 60:
        s *= (W - 60) / (img.width * s)
    im = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)
    if k < 1:
        im.putalpha(im.split()[3].point(lambda v: int(v * k)))
    frame.paste(im, ((W - im.width) // 2, int(y - im.height / 2 + 24 * (1 - k))), im)
    if extra.get("arrow"):
        # thin arrow from the caption to the left guy in the end card
        d = ImageDraw.Draw(frame)
        x0, y0 = W // 2 - 200, y - 30
        x1, y1 = 200, y - 270
        x1, y1 = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
        d.line([x0, y0, x1, y1], fill="white", width=7)
        v = np.array([x1 - x0, y1 - y0], float)
        v /= np.linalg.norm(v) + 1e-9
        n = np.array([-v[1], v[0]])
        tip = np.array([x1, y1])
        d.polygon([tuple(tip + v * 18), tuple(tip - v * 26 + n * 22), tuple(tip - v * 26 - n * 22)],
                  fill="white")

# ---------------------------------------------------------------- video sources
class Reader:
    """Sequential rgb24 frames from a clip, starting at src, optionally sped up."""

    def __init__(self, path, src, dur, speed=1.0):
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height", "-of", "csv=p=0", path],
                               capture_output=True, text=True).stdout.strip().split(",")
        self.w, self.h = int(probe[0]), int(probe[1])
        cmd = ["ffmpeg", "-v", "error", "-ss", str(src), "-t", str(dur * speed + 0.5), "-i", path,
               "-vf", f"setpts=PTS/{speed},fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.last = None

    def next(self):
        n = self.w * self.h * 3
        buf = self.p.stdout.read(n)
        if len(buf) == n:
            self.last = Image.frombytes("RGB", (self.w, self.h), buf)
        return self.last

    def close(self):
        self.p.stdout.close()
        self.p.wait()


def blurred_bg(img):
    small = img.copy()
    small.thumbnail((120, 120))
    sw, sh = small.size
    s = max(54 / sw, 96 / sh)
    small = small.resize((int(sw * s) + 1, int(sh * s) + 1))
    small = small.crop(((small.width - 54) // 2, (small.height - 96) // 2,
                        (small.width - 54) // 2 + 54, (small.height - 96) // 2 + 96))
    bg = small.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
    return ImageEnhance.Brightness(bg).enhance(0.55)


def compose_landscape(src, zoom):
    """Landscape clip big in the middle over a blurred copy of itself."""
    frame = blurred_bg(src)
    fw = int(W * zoom * 1.12)
    fh = int(fw * src.height / src.width)
    fg = src.resize((fw, fh), Image.BILINEAR)
    frame.paste(fg, ((W - fw) // 2, (H - fh) // 2 + 40))
    return frame


def compose_fill(src, zoom):
    s = max(W / src.width, H / src.height) * zoom
    fw, fh = int(src.width * s), int(src.height * s)
    fg = src.resize((fw, fh), Image.BILINEAR)
    x, y = (fw - W) // 2, (fh - H) // 2
    return fg.crop((x, y, x + W, y + H))


# ---------------------------------------------------------------- photo camera
class PhotoCam:
    def __init__(self):
        img = Image.open(PHOTO).convert("RGB")
        self.img = img
        self.pw, self.ph = img.size
        # 9:16 canvas: photo across the middle, blurred copy behind
        cw = self.pw
        ch = int(cw * H / W)
        self.off = (ch - self.ph) // 2
        bg = img.resize((self.pw // 20, self.ph // 20)).filter(ImageFilter.GaussianBlur(4))
        bg = bg.resize((int(ch * self.pw / self.ph), ch), Image.BILINEAR)
        bg = bg.crop(((bg.width - cw) // 2, 0, (bg.width - cw) // 2 + cw, ch))
        bg = ImageEnhance.Brightness(bg).enhance(0.5)
        bg.paste(img, (0, self.off))
        self.canvas = bg
        self.cw, self.ch = cw, ch

    def view(self, cx, cy, height):
        """Camera centred on photo pixel (cx, cy), showing `height` source pixels vertically."""
        h = height
        w = h * W / H
        cy = cy + self.off
        x0 = min(max(cx - w / 2, 0), self.cw - w)
        y0 = min(max(cy - h / 2, 0), self.ch - h)
        crop = self.canvas.crop((int(x0), int(y0), int(x0 + w), int(y0 + h)))
        return crop.resize((W, H), Image.BILINEAR)


def deep_fry(frame, k):
    """Light contrast lift for the face zoom."""
    f = ImageEnhance.Contrast(frame).enhance(1 + 0.25 * k)
    return ImageEnhance.Color(f).enhance(1 + 0.15 * k)


_vig = None


def vignette(frame, k):
    global _vig
    if _vig is None:
        y, x = np.mgrid[0:H, 0:W]
        r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
        _vig = np.clip((r - 0.55) / 0.8, 0, 1)[..., None]
    a = np.asarray(frame).astype(np.float32)
    a *= 1 - _vig * 0.85 * k
    return Image.fromarray(a.astype(np.uint8))


# ---------------------------------------------------------------- per-frame
def punch_amount(t):
    z = 0.0
    for pt, s in PUNCHES:
        if pt <= t < pt + 0.35:
            z = max(z, s * (1 - ease_out((t - pt) / 0.35)))
    return z


def shake_offset(t, rng):
    for st, dur, amp in SHAKES:
        if st <= t < st + dur:
            a = amp * (1 - (t - st) / dur)
            return int(rng.uniform(-a, a)), int(rng.uniform(-a, a))
    return 0, 0


def flash_amount(t):
    a = 0.0
    for ft in FLASHES:
        if ft <= t < ft + 0.15:
            a = max(a, 0.4 * (1 - (t - ft) / 0.15))
    return a


_title_bg = None


def title_frame(t, cam):
    """Blurred, darkened group photo slowly pushing in behind the title."""
    global _title_bg
    if _title_bg is None:
        v = cam.view(cam.pw / 2 + 150, cam.ph / 2, cam.ch * 0.5)
        v = v.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
        _title_bg = ImageEnhance.Brightness(v).enhance(0.35)
    z = 1 + 0.05 * (t - 3.0) / 2.4
    big = _title_bg.resize((int(W * z), int(H * z)), Image.BILINEAR)
    x, y = (big.width - W) // 2, (big.height - H) // 2
    return big.crop((x, y, x + W, y + H))


def make_frame(t, cam, readers, rng):
    shot = next(s for s in SHOTS if s[0] <= t < s[1])
    t0, t1, kind, p = shot
    zoom = p.get("zoom", 1.0) * (1 + punch_amount(t))
    if kind == "photo_intro":
        # slow push on the group, then a smash zoom onto the left guy's face at 1.9s
        if t < 1.9:
            k = t / 1.9
            frame = cam.view(cam.pw / 2 - 600 * k, cam.ph / 2, cam.ch * (0.78 - 0.12 * k))
        else:
            k = ease_out((t - 1.9) / 0.22)
            sx, sy, sh = cam.pw / 2 - 600, cam.ph / 2, cam.ch * 0.66
            fx, fy, fh = FACE[0], FACE[1] + 80, 1250 - 120 * (t - 1.9)
            frame = cam.view(sx + (fx - sx) * k, sy + (fy - sy) * k, sh + (fh - sh) * k)
            frame = vignette(deep_fry(frame, k), k)
    elif kind == "photo_outro":
        # start tight on his face, pull out to the whole group
        k = ease_in_out((t - t0) / 1.6)
        fx, fy, fh = FACE[0], FACE[1] + 80, 1250
        ex, ey, eh = cam.pw / 2 - 200, cam.ph / 2 + 150, cam.ch * 0.62
        frame = cam.view(fx + (ex - fx) * k, fy + (ey - fy) * k, fh + (eh - fh) * k)
        frame = ImageEnhance.Brightness(frame).enhance(1 - 0.35 * k)
    elif kind == "title":
        frame = title_frame(t, cam)
    else:
        src = readers[shot[0]].next()
        frame = compose_landscape(src, zoom) if kind == "A" else compose_fill(src, zoom)
        zoom = 1.0
    if kind.startswith("photo") and punch_amount(t):
        z = 1 + punch_amount(t)
        big = frame.resize((int(W * z), int(H * z)), Image.BILINEAR)
        x, y = (big.width - W) // 2, (big.height - H) // 2
        frame = big.crop((x, y, x + W, y + H))
    dx, dy = shake_offset(t, rng)
    if dx or dy:
        big = frame.resize((W + 80, H + 140), Image.BILINEAR)
        frame = big.crop((40 + dx, 70 + dy, 40 + dx + W, 70 + dy + H))
    frame = frame.convert("RGB")
    for item in TEXTS:
        place_text(frame, t, item)
    fl = flash_amount(t)
    if fl:
        frame = Image.blend(frame, Image.new("RGB", (W, H), "white"), fl)
    return frame


# ---------------------------------------------------------------- audio
def read_wav(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels()).mean(axis=1)


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())


def decode(path, start, dur):
    out = os.path.join(TMP, "cut.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(dur), "-i", path,
                    "-ac", "1", "-ar", str(SR), out], check=True)
    return read_wav(out)


def rms_norm(x, target=0.12):
    r = np.sqrt(np.mean(x ** 2)) + 1e-9
    return x * (target / r)


def fade(x, fin=0.01, fout=0.03):
    n = len(x)
    a, b = int(fin * SR), int(fout * SR)
    env = np.ones(n)
    if a:
        env[:a] = np.linspace(0, 1, a)
    if b:
        env[-b:] = np.linspace(1, 0, b)
    return x * env


def synth_boom():
    t = np.arange(int(SR * 1.4)) / SR
    f = 62 * np.exp(-t * 0.6) + 30
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    x += 0.5 * np.sin(2 * np.pi * np.cumsum(2 * f) / SR) * np.exp(-t * 4)
    x[: int(SR * 0.01)] += np.random.default_rng(1).normal(0, 0.6, int(SR * 0.01))
    return np.tanh(x * 2.5) * 0.9


def synth_whoosh(dur=0.4):
    n = int(SR * dur)
    noise = np.random.default_rng(2).normal(0, 1, n)
    t = np.arange(n) / n
    cut = 300 + 5000 * np.sin(np.pi * t) ** 2
    out = np.zeros(n)
    y = 0.0
    for i in range(n):
        a = 1 - np.exp(-2 * np.pi * cut[i] / SR)
        y += a * (noise[i] - y)
        out[i] = y
    return out * np.sin(np.pi * t) ** 1.5 * 0.9


def synth_scratch(song):
    """Wiggle a slice of the song back and forth like a DJ scratch."""
    base = song[int(SR * 1.0): int(SR * 2.5)]
    n = int(SR * 0.42)
    t = np.arange(n) / SR
    pos = SR * 0.6 + SR * 0.22 * np.sin(2 * np.pi * 4.6 * t) * np.minimum(1, t / 0.05)
    x = np.interp(pos, np.arange(len(base)), base)
    x += np.random.default_rng(3).normal(0, 0.05, n)
    return np.tanh(rms_norm(x, 0.25) * 2) * 0.8


def build_audio(path):
    mix = np.zeros(int(SR * (TOTAL + 1)))

    def put(x, at, gain=1.0):
        i = int(at * SR)
        x = x[: len(mix) - i]
        mix[i: i + len(x)] += x * gain

    song = decode(SONG, 0, 4)
    put(fade(rms_norm(song[: int(SR * 2.98)], 0.11), 0.01, 0.08), 0.0)
    put(synth_scratch(song), 2.92, 0.7)
    put(fade(rms_norm(decode(VID_A, 0.0, 1.3), 0.1), 0.01, 0.15), 3.15)  # knock knock
    put(fade(rms_norm(decode(VID_B, 0.9, 3.1), 0.12), 0.4, 0.03), 4.1)  # the "oh oh" intro
    put(fade(rms_norm(decode(VID_B, 6.0, 6.2), 0.12)), 7.2)  # skips the whispered count-in
    put(fade(rms_norm(decode(VID_A, 62.0, 10.4), 0.12)), 13.4)
    put(fade(rms_norm(decode(VID_A, 80.0, 2.6), 0.12)), 23.8)
    put(fade(rms_norm(decode(VID_A, 85.4, 3.4), 0.12), 0.01, 1.2), 26.4)
    boom = synth_boom()
    whoosh = synth_whoosh()
    put(whoosh, 1.7, 0.3)
    put(boom, 1.9, 0.5)
    put(boom, 26.4, 0.4)
    for tt in (5.25, 7.05, 13.25, 17.25, 18.85, 21.05, 23.65):
        put(whoosh, tt, 0.15)
    put(read_wav(os.path.join(HERE, "assets", "sfx", "ding.wav")), 27.2, 0.5)
    mix = mix[: int(SR * TOTAL)]
    mix = np.tanh(mix / (np.max(np.abs(mix)) + 1e-9) * 1.4) * 0.89
    write_wav(path, mix)


# ---------------------------------------------------------------- main
def main():
    os.makedirs(TMP, exist_ok=True)
    cam = PhotoCam()
    rng = np.random.default_rng(42)
    if "--preview" in sys.argv:
        times = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1].split(",")]
        os.makedirs(os.path.join(OUT_DIR, "preview"), exist_ok=True)
        for t in times:
            shot = next(s for s in SHOTS if s[0] <= t < s[1])
            readers = {}
            if shot[2] in ("A", "B"):
                p = shot[3]
                src = p["src"] + (t - shot[0]) * p.get("speed", 1.0)
                readers[shot[0]] = Reader(VID_A if shot[2] == "A" else VID_B, src, 0.2)
            make_frame(t, cam, readers, rng).save(os.path.join(OUT_DIR, "preview", f"{t:05.2f}.jpg"))
            for r in readers.values():
                r.close()
        return

    audio = os.path.join(TMP, "mix.wav")
    build_audio(audio)
    out = os.path.join(OUT_DIR, "rent_a_dent_promo.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out],
                           stdin=subprocess.PIPE)
    readers = {}
    nframes = int(TOTAL * FPS)
    for i in range(nframes):
        t = i / FPS
        shot = next(s for s in SHOTS if s[0] <= t < s[1])
        if shot[2] in ("A", "B") and shot[0] not in readers:
            for r in readers.values():
                r.close()
            readers = {shot[0]: Reader(VID_A if shot[2] == "A" else VID_B, shot[3]["src"],
                                    shot[1] - shot[0], shot[3].get("speed", 1.0))}
        enc.stdin.write(make_frame(t, cam, readers, rng).tobytes())
        if i % 90 == 0:
            print(f"{t:5.1f}s / {TOTAL}s", flush=True)
    for r in readers.values():
        r.close()
    enc.stdin.close()
    enc.wait()
    print("wrote", out)


if __name__ == "__main__":
    main()
