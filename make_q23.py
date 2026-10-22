"""Render question 2 + 3 graphics: sticker PNGs and the two reveal clips.

Usage: python3 make_q23.py "<original draft folder>"   (e.g. .../com.lveditor.draft/1008)
Writes assets/q2/ and assets/q3/. Stickers are drawn at the exact pixel size they appear on
the 1920x1080 canvas; the builder places them at that size.
"""
import math
import os
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import votes_config as C
from make_celebration import (FONT_BIG, GOLD, H, NAVY, NAVY_DARK, W, FPS, background_frames, blurred,
                              draw_confetti, ease_out_back, ease_out_cubic, encoder, lerp, make_confetti,
                              paste_center, text_img)

HERE = os.path.dirname(os.path.abspath(__file__))
Q2 = os.path.join(HERE, "assets", "q2")
Q3 = os.path.join(HERE, "assets", "q3")
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"
SKY = (120, 200, 255)
RED = (230, 50, 60)
FILLS = {"gold": GOLD, "white": (255, 255, 255), "sky": SKY}


def stickerize(im, outline=9, shadow=True):
    """White die-cut outline + soft drop shadow around an RGBA image."""
    pad = outline + 14
    base = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    base.alpha_composite(im, (pad, pad))
    a = base.getchannel("A").point(lambda v: 255 if v > 90 else 0)
    o = a
    for _ in range(max(1, outline // 3)):
        o = o.filter(ImageFilter.MaxFilter(7))
    o = o.filter(ImageFilter.GaussianBlur(1.5)).point(lambda v: 255 if v > 120 else int(v * 2))
    white = Image.new("RGBA", base.size, (255, 255, 255, 0))
    white.putalpha(o)
    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
        sh.putalpha(o.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.4)))
        out.alpha_composite(sh, (0, 4))
    out.alpha_composite(white)
    out.alpha_composite(base)
    return out.crop(out.getbbox())


def word_sticker(text, fill, height):
    t = text_img(text, FONT_BIG, int(height * 0.72), fill, stroke=max(4, height // 14), stroke_fill=NAVY_DARK)
    return stickerize(t, outline=max(6, height // 11))


def emoji(ch, size):
    f = ImageFont.truetype(EMOJI, 160)
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((20, 20), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((int(im.width * size / im.height), size), Image.LANCZOS)


def pill(text, fill, text_fill, icon=None, icon_left=True, h=86):
    t = text_img(text, FONT_BIG, int(h * 0.42), text_fill)
    ic = emoji(icon, int(h * 0.62)) if icon else None
    w = t.width + 64 + (ic.width + 14 if ic else 0)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=fill + (255,),
                                         outline=NAVY_DARK + (255,), width=5)
    x = 32
    if ic and icon_left:
        im.alpha_composite(ic, (x, (h - ic.height) // 2))
        x += ic.width + 14
    im.alpha_composite(t, (x, (h - t.height) // 2))
    if ic and not icon_left:
        im.alpha_composite(ic, (x + t.width + 14, (h - ic.height) // 2))
    return im


def meter_base():
    """Labels on each end and the tug-of-war bar between them; bar centre = image centre."""
    left = pill(C.Q3_SIDES[0], GOLD, NAVY_DARK, "\U0001FA74", True)
    right = pill(C.Q3_SIDES[1], SKY, NAVY_DARK, "✋", False)
    bar_w, bar_h, gap = 560, 30, 30
    w = max(left.width, right.width) * 2 + bar_w + 2 * gap
    h = max(left.height, 100)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    im.alpha_composite(left, (0, (h - left.height) // 2))
    im.alpha_composite(right, (w - right.width, (h - right.height) // 2))
    bx0, by0 = (w - bar_w) // 2, (h - bar_h) // 2
    grad = Image.new("RGBA", (bar_w, bar_h))
    for x in range(bar_w):
        k = x / (bar_w - 1)
        ImageDraw.Draw(grad).line((x, 0, x, bar_h), fill=tuple(int(lerp(a, b, k)) for a, b in zip(GOLD, SKY)) + (255,))
    mask = Image.new("L", (bar_w, bar_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bar_w - 1, bar_h - 1), radius=bar_h // 2, fill=255)
    im.paste(grad, (bx0, by0), mask)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((bx0, by0, bx0 + bar_w - 1, by0 + bar_h - 1), radius=bar_h // 2, outline=NAVY_DARK + (255,), width=4)
    d.rectangle((w // 2 - 3, by0 - 12, w // 2 + 3, by0 + bar_h + 12), fill=(255, 255, 255, 255))
    return stickerize(im, outline=7)


def volleyball(size=78):
    return stickerize(emoji("\U0001F3D0", size), outline=6)


def red_x(size):
    s = size * 3
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for (x0, y0, x1, y1) in ((0.12, 0.12, 0.88, 0.88), (0.88, 0.12, 0.12, 0.88)):
        d.line((x0 * s, y0 * s, x1 * s, y1 * s), fill=(255, 255, 255, 255), width=int(s * 0.2))
        d.line((x0 * s, y0 * s, x1 * s, y1 * s), fill=RED + (255,), width=int(s * 0.13))
    return im.resize((size, size), Image.LANCZOS)


def save(im, folder, name):
    os.makedirs(folder, exist_ok=True)
    im.save(os.path.join(folder, name))
    return im


def stickers():
    words = {}
    for w, (_, _, _, fill) in C.Q2_WORDS.items():
        words[w] = save(word_sticker(w, FILLS[fill], C.Q2_WORD_PX), Q2, f"word_{w}.png")
    save(word_sticker(C.Q2_GAG["word"], (255, 255, 255), C.Q2_WORD_PX), Q2, "word_gag.png")
    save(red_x(int(C.Q2_WORD_PX * 1.25)), Q2, "x.png")

    save(meter_base(), Q3, "meter.png")
    save(volleyball(), Q3, "ball.png")
    for n in range(max(C.q3_counts()) + 1):
        save(word_sticker(str(n), GOLD, 74), Q3, f"n{n}.png")
    fall = emoji("\U0001F4C9", 150)
    save(stickerize(fall, outline=8), Q3, "fall.png")
    save(stickerize(pill("FLIP FLOP PRO", GOLD, NAVY_DARK, "\U0001F3C5", True, h=96), outline=8), Q3, "pro.png")
    return words


def q2_reveal(draft, words):
    counts = C.q2_counts()
    top = sorted(C.Q2_WORDS, key=lambda w: (-counts[w], list(C.Q2_WORDS).index(w)))[:3]
    title = text_img("THE TEAM IN 3 WORDS", FONT_BIG, 76, (255, 255, 255), stroke=7, stroke_fill=NAVY_DARK)
    confetti = make_confetti(0.95, cannons=((120, 1080), (1800, 1080)), rain=140, seed=7)
    targets = {w: (W / 2, 470 + 175 * i) for i, w in enumerate(top)}
    with tempfile.TemporaryDirectory() as tmp:
        bgs = background_frames(draft, C.Q2_REVEAL_START, C.Q2_END, tmp)
        enc = encoder(os.path.join(Q2, "reveal.mp4"))
        for fi, bg in enumerate(bgs):
            t = fi / FPS
            frame = blurred(bg, t)
            for w, (x, y, rot, _) in C.Q2_WORDS.items():
                if counts[w] == 0:
                    continue
                size = C.Q2_GROW ** (counts[w] - 1)
                # PIL rotates counter-clockwise; CapCut's rotation is clockwise
                im = words[w].rotate(-rot, expand=True, resample=Image.BICUBIC) if rot else words[w]
                if w in targets:
                    i = top.index(w)
                    k = ease_out_back((t - 0.2 - 0.18 * i) / 0.5, 1.4)
                    tx, ty = targets[w]
                    pulse = 1 + (0.05 * math.sin((t - 1.2) * 2 * math.pi * 1.5) if t > 1.2 else 0)
                    paste_center(frame, words[w] if k > 0.5 else im, lerp(x, tx, k), lerp(y, ty, k),
                                 scale=lerp(size, 1.55, max(0.0, k)) * pulse)
                else:
                    paste_center(frame, im, x, y, scale=size, alpha=1 - ease_out_cubic(t / 0.3))
            kt = ease_out_back((t - 0.1) / 0.35, 2.0)
            if kt > 0:
                paste_center(frame, title, W / 2, 300, scale=kt)
            draw_confetti(frame, confetti, t)
            enc.stdin.write(frame.convert("RGB").tobytes())
            if fi == len(bgs) - 1:
                frame.convert("RGB").save(os.path.join(Q2, "preview_reveal.jpg"), quality=85)
        enc.stdin.close()
        enc.wait()
    return top


def q3_reveal(draft):
    votes = C.q3_counts()
    win = 0 if votes[0] > votes[1] else 1
    meter = Image.open(os.path.join(Q3, "meter.png"))
    ball = Image.open(os.path.join(Q3, "ball.png"))
    nums = [Image.open(os.path.join(Q3, f"n{n}.png")) for n in votes]
    lead = votes[1] - votes[0]
    title = text_img(f"{C.Q3_SIDES[win]} WIN!" if win == 0 else f"{C.Q3_SIDES[win]} WINS!", FONT_BIG, 128, GOLD,
                     stroke=9, stroke_fill=NAVY_DARK)
    score = text_img(f"{max(votes)} – {min(votes)}", FONT_BIG, 90, (255, 255, 255), stroke=7, stroke_fill=NAVY_DARK)
    icon = stickerize(emoji("\U0001FA74" if win == 0 else "✋", 150), outline=9)
    confetti = make_confetti(0.5, cannons=((120, 1080), (1800, 1080)), rain=150, seed=11)
    my = C.Q3_METER_Y_PX
    with tempfile.TemporaryDirectory() as tmp:
        bgs = background_frames(draft, C.Q3_REVEAL_START, C.Q3_END, tmp)
        enc = encoder(os.path.join(Q3, "reveal.mp4"))
        for fi, bg in enumerate(bgs):
            t = fi / FPS
            frame = blurred(bg, t)
            fade = 1 - ease_out_cubic(t / 0.35)
            paste_center(frame, meter, W / 2, my, alpha=fade)
            paste_center(frame, ball, W / 2 + lead * C.Q3_STEP_PX, my, alpha=fade)
            for side, n in enumerate(nums):
                paste_center(frame, n, W / 2 + (-1 if side == 0 else 1) * (meter.width / 2 - 200), my + 95, alpha=fade)
            ki = ease_out_back((t - 0.2) / 0.45, 1.8)
            if ki > 0:
                bob = 8 * math.sin((t - 0.6) * 2 * math.pi * 1.6) if t > 0.6 else 0
                for dx, rot in ((-110, 14), (110, -14)):
                    paste_center(frame, icon.rotate(rot + bob / 2, expand=True, resample=Image.BICUBIC),
                                 W / 2 + dx, 470 + bob, scale=ki * 1.15)
            kt = ease_out_back((t - 0.45) / 0.35, 2.0)
            if kt > 0:
                paste_center(frame, title, W / 2, 210, scale=kt)
            ks = ease_out_back((t - 0.75) / 0.3, 1.6)
            if ks > 0:
                paste_center(frame, score, W / 2, 720, scale=ks)
            draw_confetti(frame, confetti, t)
            enc.stdin.write(frame.convert("RGB").tobytes())
            if fi == len(bgs) - 1:
                frame.convert("RGB").save(os.path.join(Q3, "preview_reveal.jpg"), quality=85)
        enc.stdin.close()
        enc.wait()
    return C.Q3_SIDES[win]


def main():
    draft = sys.argv[1]
    words = stickers()
    print("q2 top words:", q2_reveal(draft, words))
    print("q3 winner:", q3_reveal(draft))


if __name__ == "__main__":
    main()
