"""Render the navy b-roll backgrounds for the question cards into assets/broll/.

Usage: python3 make_broll.py "<original draft folder>"   (e.g. .../com.lveditor.draft/1008)
Each clip has the b-roll picture (muted) and the audio the card already plays in the draft,
so swapping the picture in CapCut leaves the sound exactly as it was.
"""
import json
import os
import subprocess
import sys

import votes_config as C

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets", "broll")


def card_segments(draft):
    """Bottom-track clip under each configured card start: (start, duration, source path, source start)."""
    d = json.load(open(os.path.join(draft, "draft_info.json")))
    vids = {m["id"]: m for m in d["materials"]["videos"]}
    base = next(t for t in d["tracks"] if t["type"] == "video")
    out = []
    for start, _, _ in C.BROLL:
        s = next(s for s in base["segments"] if abs(s["target_timerange"]["start"] / 1e6 - start) < 0.02)
        out.append((s["target_timerange"]["start"] / 1e6, s["target_timerange"]["duration"] / 1e6,
                    vids[s["material_id"]]["path"], s["source_timerange"]["start"] / 1e6))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, ((start, dur, apath, astart), (_, clip, bstart)) in enumerate(zip(card_segments(sys.argv[1]), C.BROLL)):
        out = os.path.join(OUT, f"card_{i + 1}.mp4")
        subprocess.run([
            "ffmpeg", "-loglevel", "error", "-y",
            "-ss", f"{bstart:.3f}", "-t", f"{dur + 0.1:.3f}", "-i", os.path.join(C.BROLL_DIR, clip),
            "-ss", f"{astart:.3f}", "-t", f"{dur + 0.1:.3f}", "-i", apath,
            "-filter_complex", f"[0:v]scale=1920:1080,fps=30,{C.BROLL_LOOK},format=yuv420p[v]",
            "-map", "[v]", "-map", "1:a:0", "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", out], check=True)
        print(f"card {i + 1}: {start:.2f}s +{dur:.2f}s  {clip}@{bstart}s  audio {os.path.basename(apath)}@{astart:.2f}s -> {out}")


if __name__ == "__main__":
    main()
