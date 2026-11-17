"""Toolkit for the `interview-cut` style: minimal sit-down / on-field interview edits.

Scouting (run from the repo root):

    python3 interview_kit.py words <clip>              # word timings + sentence cut points snapped to silence
    python3 interview_kit.py sheet <dir> [CLIP ...]    # labelled contact sheets, 3 frames per clip
    python3 interview_kit.py sheet <dir> CLIP --every 2   # one frame every 2 s of a single clip

Rendering: a `make_<project>_interview.py` holds only the edit decision list and calls `Edit.main`:

    from interview_kit import Edit
    EDL = [dict(note="Q over B-roll", a="INT_A", ain=6.3, aout=8.8, v="BROLL_1", vin=3.0), ...]
    Edit(src_dir="~/Movies/shoot", name="my_interview").main(EDL)

    python3 make_<project>_interview.py --preview   # one frame per shot + every lower third composited
    python3 make_<project>_interview.py             # render out/<name>/<name>.mp4
    python3 make_<project>_interview.py --verify    # render, then transcribe it and check A/V sync

EDL shot fields
    a, ain, aout    interview clip and in/out seconds. The shot's length comes from the audio.
    v, vin          picture clip and in-point. Defaults to the interview clip at ain. A different
                    v lays B-roll over the interview audio.
    dur             B-roll with its own sound (no `a`): length in seconds. Its nat sound is
                    level-matched 12 dB under speech; `nat_lufs=` on the shot overrides that.
    lower           (name, role) lower third on this shot.
    note            free text, printed while rendering.
Clips are named without extension, for example "MVI_9702"; the first matching file in src_dir is used.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
from fractions import Fraction

import numpy as np

WHISPER_MODEL = "models/ggml-base.en.bin"
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"  # index 2 = Demi Bold, 5 = Medium
WHITE = (255, 255, 255)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", path],
              capture_output=True, text=True).stdout
    return json.loads(out)


# ---------------------------------------------------------------- audio + transcript helpers

def load_audio(path, start=0.0, dur=None, sr=16000):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.4f}"]
    if dur:
        cmd += ["-t", f"{dur:.4f}"]
    cmd += ["-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    return np.frombuffer(run(cmd, capture_output=True).stdout, np.int16).astype(np.float32) / 32768


def energy_db(audio, sr=16000, hop=0.05):
    """dB of each `hop`-second window."""
    n = int(sr * hop)
    frames = audio[: len(audio) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(1)) + 1e-6)


def whisper_words(path):
    """[(start, end, word)] from whisper-cli word-level output."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "a.wav")
        run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", "16000", wav])
        out = run(["whisper-cli", "-m", WHISPER_MODEL, "-f", wav, "-ml", "1", "-sow"],
                  capture_output=True, text=True).stdout
    ts = lambda s: sum(float(x) * m for x, m in zip(s.split(":"), (3600, 60, 1)))
    words = []
    for m in re.finditer(r"^\[([\d:.]+) --> ([\d:.]+)\][ \t]*(\S[^\n]*)$", out, re.M):
        words.append((ts(m[1]), ts(m[2]), m[3].strip()))
    return words


def quiet_gap(db, t, hop=0.05, search=0.4):
    """(start, end) of the longest quiet run within +-search s of time t, or (t, t) if none.
    "Quiet" = within 10 dB of the clip's noise floor."""
    thr = np.percentile(db, 10) + 10
    i0, i1 = max(0, int((t - search) / hop)), min(len(db), int((t + search) / hop) + 1)
    best, run_start = None, None
    for i in range(i0, i1 + 1):
        quiet = i < i1 and db[i] <= thr
        if quiet and run_start is None:
            run_start = i
        elif not quiet and run_start is not None:
            if best is None or i - run_start > best[1] - best[0]:
                best = (run_start, i)
            run_start = None
    return (best[0] * hop, best[1] * hop) if best else (t, t)


def snap_cuts(db, start, end, lead=0.08, tail=0.12):
    """Whisper's word edges drift by a few hundred ms and its words touch end to end, so cut inside
    the real silence instead: the in-point just before speech resumes after the quiet gap nearest
    `start`, the out-point just after speech stops in the gap nearest `end`."""
    g0, g1 = quiet_gap(db, start)
    h0, h1 = quiet_gap(db, end)
    cin = max(g0, g1 - lead) if g1 > g0 else start
    cout = max(h0, min(h0 + tail, h1 - 0.04)) if h1 > h0 else end
    return max(0.0, cin), cout


def cmd_words(args):
    path = args.clip
    words = whisper_words(path)
    db = energy_db(load_audio(path))
    print(f"# {path}\n# words (start-end):")
    print(" ".join(f"{w}[{a:.2f}-{b:.2f}]" for a, b, w in words))
    print("\n# sentences, cut points snapped to silence (in -> out):")
    sent = []
    for i, (a, b, w) in enumerate(words):
        sent.append((a, b, w))
        if re.search(r"[.?!]$", w) or i == len(words) - 1:
            cin, cout = snap_cuts(db, sent[0][0], sent[-1][1])
            print(f"  {cin:7.2f} -> {cout:7.2f}  {' '.join(x[2] for x in sent)}")
            sent = []


# ---------------------------------------------------------------- contact sheets

def cmd_sheet(args):
    from PIL import Image, ImageDraw, ImageFont
    src_dir = os.path.expanduser(args.dir)
    files = sorted(f for f in glob.glob(os.path.join(src_dir, "*"))
                   if os.path.splitext(f)[1].lower() in (".mov", ".mp4", ".mts", ".m4v", ".mxf"))
    if args.clips:
        files = [f for f in files if os.path.splitext(os.path.basename(f))[0] in args.clips]
    out_dir = args.out or os.path.join("out", "sheets")
    os.makedirs(out_dir, exist_ok=True)
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    tiles = []  # (label, image)
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        dur = float(probe(f)["format"]["duration"])
        times = (list(np.arange(0, dur - 0.1, args.every)) if args.every
                 else [dur * k / 6 for k in (1, 3, 5)])
        for t in times:
            raw = run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", f, "-frames:v", "1",
                       "-vf", "scale=320:180", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                      capture_output=True).stdout
            if len(raw) == 320 * 180 * 3:
                tiles.append((f"{name}@{t:.1f}", Image.frombytes("RGB", (320, 180), raw)))
    cols, rows = (6, 5) if args.every else (3, 12)
    for page in range(0, len(tiles), cols * rows):
        chunk = tiles[page:page + cols * rows]
        sheet = Image.new("RGB", (cols * 320, -(-len(chunk) // cols) * 180))
        d = ImageDraw.Draw(sheet)
        for i, (label, im) in enumerate(chunk):
            x, y = i % cols * 320, i // cols * 180
            sheet.paste(im, (x, y))
            d.rectangle((x, y, x + d.textlength(label, font=font) + 8, y + 27), fill="black")
            d.text((x + 4, y + 2), label, font=font, fill="yellow")
        path = os.path.join(out_dir, f"sheet_{page // (cols * rows):02d}.jpg")
        sheet.save(path, quality=80)
        print(path)


# ---------------------------------------------------------------- render

class Edit:
    def __init__(self, src_dir, name, out_dir=None, size=(1920, 1080), fps=None,
                 accent=WHITE, fade=0.6, lower_timing=(0.4, 3.6, 0.4), loudness=-16,
                 speech_lufs=-20, nat_lufs=-32):
        """size/fps: output format. fps defaults to the first interview clip's frame rate.
        accent: lower-third bar colour (team colour). lower_timing: (fade-in start, hold, fade).
        speech_lufs / nat_lufs: every interview shot is matched to speech_lufs and every B-roll
        nat-sound shot to nat_lufs (12 dB under speech); the mix is then lifted to `loudness`."""
        self.src_dir = os.path.expanduser(src_dir)
        self.name = name
        self.out_dir = out_dir or os.path.join("out", name)
        self.W, self.H = size
        self.fps = fps
        self.accent = tuple(accent)
        self.fade = fade
        self.lt_in, self.lt_hold, self.lt_fade = lower_timing
        self.loudness = loudness
        self.speech_lufs = speech_lufs
        self.nat_lufs = nat_lufs

    # -- sources
    def src(self, clip):
        hits = sorted(glob.glob(os.path.join(glob.escape(self.src_dir), clip + ".*")))
        if not hits:
            sys.exit(f"no file for clip {clip!r} in {self.src_dir}")
        return hits[0]

    def plan(self, edl):
        if not self.fps:
            first = next(s.get("a") for s in edl if s.get("a"))
            v = next(st for st in probe(self.src(first))["streams"] if st["codec_type"] == "video")
            self.fps = v["r_frame_rate"]
        frame = 1 / float(Fraction(self.fps))
        t, out = 0.0, []
        for s in edl:
            s = dict(s)
            if "a" in s:
                s.setdefault("v", s["a"])
                s.setdefault("vin", s["ain"])
                s["dur"] = s["aout"] - s["ain"]
            # Whole frames per shot, audio trimmed to match: otherwise every shot's video rounds up
            # a frame while its audio doesn't, and the concat drifts picture behind sound.
            s["frames"] = round(s["dur"] / frame)
            s["dur"] = s["frames"] * frame
            s["start"] = round(t, 3)
            s["v_path"] = self.src(s["v"])
            if "a" in s:
                s["a_path"] = self.src(s["a"])
            t += s["dur"]
            out.append(s)
        return out

    # -- graphics
    def lower_third_png(self, name, role, path):
        """Name (Avenir Next Demi Bold) over role (Medium), accent bar on the left, soft shadow."""
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
        k = self.H / 1080
        big = ImageFont.truetype(AVENIR, round(62 * k), index=2)
        small = ImageFont.truetype(AVENIR, round(34 * k), index=5)
        x, y = round(150 * k), round(836 * k)
        text = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(text)
        d.rectangle((x - round(30 * k), y + round(12 * k), x - round(22 * k), y + round(128 * k)),
                    fill=self.accent + (255,))
        d.text((x, y), name, font=big, fill=(255, 255, 255, 255))
        d.text((x + 2, y + round(86 * k)), role, font=small, fill=(235, 235, 235, 255))
        shadow = Image.new("RGBA", text.size, (0, 0, 0, 0))
        shadow.putalpha(text.getchannel("A").point(lambda a: a * 0.75))
        shadow = shadow.filter(ImageFilter.GaussianBlur(6 * k))
        out = Image.new("RGBA", text.size, (0, 0, 0, 0))
        out.alpha_composite(shadow, (3, 4))
        out.alpha_composite(text)
        out.save(path)

    # -- audio levels
    @staticmethod
    def lufs(path, t, d):
        """Integrated (gated) loudness of path[t : t+d], or None if it is silence."""
        err = subprocess.run(["ffmpeg", "-nostats", "-ss", f"{t:.4f}", "-t", f"{d:.4f}", "-i", path,
                              "-vn", "-af", "ebur128", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        vals = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", err)
        return float(vals[-1]) if vals and vals[-1] != "-inf" and float(vals[-1]) > -70 else None

    def shot_gain(self, path, t, d, target):
        """dB that brings this shot's speech (or nat sound) to `target` LUFS. Off-camera questions
        are usually much louder than the on-camera answers, and people differ, so every shot is
        matched before the final mix. Clamped to +-20 dB so a near-silent shot isn't blown up."""
        level = self.lufs(path, t, max(d, 0.5))
        return 0.0 if level is None else float(np.clip(target - level, -20, 20))

    def _fit(self):
        return (f"scale={self.W}:{self.H}:force_original_aspect_ratio=decrease,"
                f"pad={self.W}:{self.H}:(ow-iw)/2:(oh-ih)/2,setsar=1")

    def render_shot(self, s, path):
        d = s["dur"]
        pad = str(d + 0.5)  # read a little extra; -frames:v and atrim set the exact length
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(s["vin"]), "-t", pad, "-i", s["v_path"]]
        if "a" in s:
            cmd += ["-ss", str(s["ain"]), "-t", pad, "-i", s["a_path"]]
            amap, gain = "1:a", self.shot_gain(s["a_path"], s["ain"], d, self.speech_lufs)
        else:
            amap, gain = "0:a", self.shot_gain(s["v_path"], s["vin"], d, s.get("nat_lufs", self.nat_lufs))
        s["gain_db"] = round(gain, 1)
        vf = f"[0:v]{self._fit()},fps={self.fps},format=yuv420p[v]"
        if "lower" in s:
            png = path + ".lower.png"
            self.lower_third_png(*s["lower"], png)
            li = 2 if "a" in s else 1
            cmd += ["-loop", "1", "-t", str(d), "-i", png]
            vf = (f"[{li}:v]format=rgba,fade=t=in:st={self.lt_in}:d={self.lt_fade}:alpha=1,"
                  f"fade=t=out:st={self.lt_in + self.lt_hold}:d={self.lt_fade}:alpha=1[lt];"
                  f"[0:v]{self._fit()}[bg];[bg][lt]overlay=0:0:shortest=1,"
                  f"fps={self.fps},format=yuv420p[v]")
        # 15 ms audio fades on every cut so joins never click
        af = (f"volume={gain:.2f}dB,apad,atrim=end={d:.6f},asetpts=PTS-STARTPTS,"
              f"afade=t=in:d=0.015,afade=t=out:st={d - 0.015:.6f}:d=0.015")
        cmd += ["-filter_complex", vf, "-map", "[v]", "-map", amap, "-af", af,
                "-frames:v", str(s["frames"]), "-ac", "2", "-ar", "48000",
                "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-c:a", "pcm_s16le", path]
        run(cmd)

    def preview(self, plan):
        for i, s in enumerate(plan):
            run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["vin"] + s["dur"] / 2), "-i", s["v_path"],
                 "-frames:v", "1", "-vf", "scale=640:-1",
                 os.path.join(self.out_dir, f"preview_{i:02d}.jpg")])
        for i, s in enumerate(p for p in plan if "lower" in p):
            png = os.path.join(self.out_dir, f"lower_{i}.png")
            self.lower_third_png(*s["lower"], png)
            run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["vin"] + self.lt_in + 1.5), "-i", s["v_path"],
                 "-i", png, "-filter_complex", f"[0:v]{self._fit()}[bg];[bg][1:v]overlay", "-frames:v", "1",
                 os.path.join(self.out_dir, f"preview_lower_{i}.jpg")])
            os.remove(png)

    def render(self, plan, out):
        total = plan[-1]["start"] + plan[-1]["dur"]
        with tempfile.TemporaryDirectory() as tmp:
            parts = []
            for i, s in enumerate(plan):
                p = os.path.join(tmp, f"{i:03d}.mov")
                self.render_shot(s, p)
                parts.append(p)
                print(f"{i + 1}/{len(plan)} {s.get('note', '')}")
            lst = os.path.join(tmp, "list.txt")
            with open(lst, "w") as f:
                f.writelines(f"file '{p}'\n" for p in parts)
            fd = self.fade
            run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                 "-vf", f"fade=t=in:d={fd},fade=t=out:st={total - fd:.3f}:d={fd}",
                 # shots are already level-matched, so a static gain + peak limiter (-1.5 dBFS)
                 # instead of loudnorm, whose dynamic mode rides the gain shot to shot
                 "-af", f"volume={self.loudness - self.speech_lufs}dB,"
                        f"alimiter=limit=0.84:level=false,afade=t=in:d={fd / 2},"
                        f"afade=t=out:st={total - fd:.3f}:d={fd}",
                 "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out])
        print(f"wrote {out} ({total:.1f}s)")

    # -- checks
    def verify(self, plan, out):
        """Transcript of the render (clipped words, stray interviewer lines) and a per-shot sync check:
        the offset of the output picture and of the output sound against their sources should match."""
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, "o.wav")
            run(["ffmpeg", "-v", "error", "-y", "-i", out, "-ac", "1", "-ar", "16000", wav])
            print(run(["whisper-cli", "-m", WHISPER_MODEL, "-f", wav], capture_output=True,
                      text=True).stdout.strip())

        def gray(path, t):
            raw = run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", path, "-frames:v", "1",
                       "-vf", f"{self._fit()},scale=192:108,format=gray", "-f", "rawvideo", "-"],
                      capture_output=True).stdout
            return np.frombuffer(raw, np.uint8).astype(float)

        frame = 1 / float(Fraction(self.fps))
        print("\nshot                                   picture  sound   (offset vs source, ms)")
        worst = 0.0
        for s in plan:
            if "a" not in s or s["dur"] < 1.5 or "lower" in s:
                continue
            t = min(1.0, s["dur"] / 2)
            o = gray(out, s["start"] + t)
            errs = {k: np.mean(abs(o - gray(s["v_path"], s["vin"] + t + k * frame))) for k in range(-6, 7)}
            v_off = min(errs, key=errs.get) * frame
            a = load_audio(out, s["start"] + 0.3, 1.0, sr=8000)
            b = load_audio(s["a_path"], s["ain"] + 0.05, 1.5, sr=8000)
            a_off = (np.argmax(np.correlate(b, a, "valid")) - 2000) / 8000
            worst = max(worst, abs(v_off - a_off))
            print(f"{s.get('note', s['v'])[:38]:38s} {v_off * 1000:+6.0f}  {a_off * 1000:+6.0f}")
        ok = worst <= frame * 1.5
        print(f"\nA/V sync {'OK' if ok else 'OFF'}: worst picture-vs-sound gap {worst * 1000:.0f} ms "
              f"(one frame = {frame * 1000:.0f} ms)")

    def main(self, edl, argv=None):
        ap = argparse.ArgumentParser()
        ap.add_argument("--preview", action="store_true", help="one frame per shot, no render")
        ap.add_argument("--verify", action="store_true", help="render, then transcribe + sync-check")
        args = ap.parse_args(argv)
        os.makedirs(self.out_dir, exist_ok=True)
        plan = self.plan(edl)
        total = plan[-1]["start"] + plan[-1]["dur"]
        with open(os.path.join(self.out_dir, "edit_decision_list.json"), "w") as f:
            json.dump(dict(total=round(total, 3), fps=self.fps, shots=plan), f, indent=2)
        if args.preview:
            self.preview(plan)
            print(f"{len(plan)} shots, {total:.1f}s -> {self.out_dir}/preview_*.jpg")
            return
        out = os.path.join(self.out_dir, self.name + ".mp4")
        self.render(plan, out)
        if args.verify:
            self.verify(plan, out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("words", help="word timings + snapped sentence cut points for one clip")
    w.add_argument("clip")
    w.set_defaults(fn=cmd_words)
    sh = sub.add_parser("sheet", help="labelled contact sheets of a footage folder")
    sh.add_argument("dir")
    sh.add_argument("clips", nargs="*", help="clip names without extension (default: all)")
    sh.add_argument("--every", type=float, help="one frame every N seconds instead of 3 per clip")
    sh.add_argument("--out", help="output folder (default out/sheets)")
    sh.set_defaults(fn=cmd_sheet)
    a = ap.parse_args()
    a.fn(a)
