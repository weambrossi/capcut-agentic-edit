"""Add pop-up head stickers, vote counters, dings and the podium celebration to a CapCut draft.

Usage: python3 add_vote_heads.py "<draft folder>" "<template draft with a photo clip>" "<original draft>"
Run make_sfx.py, make_celebration.py and make_broll.py first. Settings live in votes_config.py.
Edits draft_info.json (root + Timelines copy) in place and is safe to re-run: anything it added
before is removed first, the question-card clips it swapped are restored from the original draft,
and the rest of the draft is left alone. Run only while CapCut is closed.
"""
import copy
import json
import os
import shutil
import sys
import uuid

from PIL import Image

import votes_config as C

DRAFT = sys.argv[1]
PHOTO_TEMPLATE = sys.argv[2]
ORIGINAL = sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))
US = 1_000_000
# folders copied into the draft; CapCut is sandboxed to ~/Movies so media must live there
OWN_DIRS = ("stickers", "sfx", "celebration", "broll", "q2", "q3")
# effects dropped from the card clips because the b-roll has its blur and colour baked in
CARD_DROP_REFS = {"video_effects", "smart_relights"}


def uid():
    return str(uuid.uuid4()).upper()


def us(sec):
    return int(round(sec * US))


def load(path):
    with open(path) as f:
        return json.load(f)


def find(materials, mid):
    for k, v in materials.items():
        if isinstance(v, list):
            for m in v:
                if isinstance(m, dict) and m.get("id") == mid:
                    return k, m
    raise KeyError(mid)


def into_draft(sub, name):
    """Copy an asset into the draft folder and return its path there."""
    src = os.path.join(HERE, "stickers" if sub == "stickers" else os.path.join("assets", sub), name)
    dst_dir = os.path.join(DRAFT, sub)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, name)
    shutil.copyfile(src, dst)
    return dst


def is_own_path(p):
    # CapCut rewrites the draft folder as "##_draftpath_placeholder_<id>_##" when it saves
    if not (p.startswith(DRAFT + os.sep) or p.startswith("##_draftpath_placeholder_")):
        return False
    return any(f"/{sub}/" in p for sub in OWN_DIRS)


def is_counter_text(m):
    try:
        text = json.loads(m["content"])["text"]
    except (KeyError, ValueError):
        return False
    return text[:1] == "x" and text[1:].isdigit()


def kf_list(prop, points):
    return {
        "id": uid(),
        "keyframe_list": [{
            "curveType": "Line", "graphID": "",
            "left_control": {"x": 0.0, "y": 0.0}, "right_control": {"x": 0.0, "y": 0.0},
            "id": uid(), "time_offset": t, "values": [v],
        } for t, v in points],
        "material_id": "",
        "property_type": prop,
    }


def pop_keyframes(scale, bumps):
    """Scale-in at offset 0, then a bounce at every offset in bumps."""
    return grow_keyframes([(0, scale)] + [(b, scale) for b in bumps])


def grow_keyframes(steps, overshoot=1.2):
    """Pop in at steps[0], then bounce to each new (offset, scale) — same scale gives a plain bounce."""
    o0, s0 = steps[0]
    pts = [(o0, 0.0), (o0 + us(0.15), s0 * overshoot), (o0 + us(0.3), s0)]
    prev = s0
    for off, s in steps[1:]:
        pts += [(off, prev), (off + us(0.12), s * (overshoot + 0.05)), (off + us(0.3), s)]
        prev = s
    return [kf_list("KFTypeScaleX", pts), kf_list("KFTypeScaleY", pts)]


class Timeline:
    """Map a time on the ORIGINAL 1008 timeline (where every time in votes_config was measured) to the
    same moment of footage in the draft being edited, so trims and moves made in CapCut are followed.
    Must be built after strip_previous() has put the original footage back on the card clips."""

    def __init__(self, orig, cur):
        vids = lambda d: [t for t in d["tracks"] if t["type"] == "video"][:2]
        self.orig_tracks = vids(orig)
        self.cur_segs = [s for t in vids(cur) for s in t["segments"]]
        self.cur_by_id = {s["id"]: s for s in self.cur_segs}
        mats = lambda d: {m["id"]: m.get("path") for m in d["materials"]["videos"]}
        self.orig_path, self.cur_path = mats(orig), mats(cur)
        self.duration = cur["duration"]
        self.misses = []

    @staticmethod
    def covers(s, t):
        r = s["target_timerange"]
        return r["start"] <= t < r["start"] + r["duration"]

    def to_current(self, sec, clamp=False):
        t = us(sec)
        for track in reversed(self.orig_tracks):          # top layer first
            o = next((s for s in track["segments"] if self.covers(s, t)), None)
            if not o:
                continue
            speed = o.get("speed", 1.0) or 1.0
            src = o["source_timerange"]["start"] + (t - o["target_timerange"]["start"]) * speed
            path = self.orig_path.get(o["material_id"])
            cands = [self.cur_by_id[o["id"]]] if o["id"] in self.cur_by_id else []
            cands += [s for s in self.cur_segs if self.cur_path.get(s["material_id"]) == path]
            for c in cands:
                cs = c["source_timerange"]
                if self.cur_path.get(c["material_id"]) == path and cs["start"] <= src <= cs["start"] + cs["duration"]:
                    return int(c["target_timerange"]["start"] + (src - cs["start"]) / (c.get("speed", 1.0) or 1.0))
        if clamp:
            return min(t, self.duration)
        self.misses.append(sec)
        return t


TIMELINE = None


def at(sec, clamp=False):
    """Timeline position (µs) in the draft being edited for a time measured on the original 1008."""
    return TIMELINE.to_current(sec, clamp)


def strip_previous(d):
    """Remove tracks added by an earlier run so re-running is safe."""
    M = d["materials"]
    by_id = {m["id"]: m for v in M.values() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}

    def ours(track):
        mats = [by_id.get(s["material_id"], {}) for s in track["segments"]]
        if not mats:
            return False
        if track["type"] == "text":
            return all(is_counter_text(m) for m in mats)
        return all(is_own_path(m.get("path", "")) for m in mats)

    drop = [t for t in d["tracks"] if ours(t)]
    dead = {i for t in drop for s in t["segments"] for i in [s["material_id"], *s["extra_material_refs"]]}
    d["tracks"] = [t for t in d["tracks"] if t not in drop]

    # put back the original footage + effects on question-card clips whose picture was swapped for
    # b-roll, keeping the clip's current position/length (it may have been moved or trimmed in CapCut).
    # CapCut deletes materials nothing uses when it saves, so copy back whatever the clip needs.
    orig = load(os.path.join(ORIGINAL, "draft_info.json"))
    original = {s["id"]: s for t in orig["tracks"] for s in t["segments"]}
    orig_base = [s for s in next(t for t in orig["tracks"] if t["type"] == "video")["segments"]]
    orig_mats = {m["id"]: (k, m) for k, v in orig["materials"].items() if isinstance(v, list)
                 for m in v if isinstance(m, dict) and "id" in m}
    for t in d["tracks"]:
        for i, s in enumerate(t["segments"]):
            if is_own_path(by_id.get(s["material_id"], {}).get("path", "")) and s["id"] in original:
                dead.add(s["material_id"])
                o = original[s["id"]]
                o0 = o["target_timerange"]["start"]
                window = next(b for b in orig_base if b["target_timerange"]["start"] <= o0 <
                              b["target_timerange"]["start"] + b["target_timerange"]["duration"])
                # exact inverse of broll_cards(): b-roll time 0 = the card's original start in the footage
                seg = copy.deepcopy(s)
                seg.update(material_id=o["material_id"], extra_material_refs=list(o["extra_material_refs"]),
                           source_timerange={"start": s["source_timerange"]["start"] + window["source_timerange"]["start"],
                                             "duration": s["source_timerange"]["duration"]})
                t["segments"][i] = seg
                for mid in [seg["material_id"], *seg["extra_material_refs"]]:
                    if mid not in by_id and mid in orig_mats:
                        k, m = orig_mats[mid]
                        M.setdefault(k, []).append(copy.deepcopy(m))
                        by_id[mid] = m

    for k, v in M.items():
        if isinstance(v, list):
            M[k] = [m for m in v if not (isinstance(m, dict) and m.get("id") in dead)]
    return len(drop)


class Builder:
    def __init__(self, d, template):
        self.d = d
        self.M = d["materials"]
        self.W, self.H = d["canvas_config"]["width"], d["canvas_config"]["height"]

        # photo/visual clip templates from a draft that already has a PNG on the timeline
        self.photo_mat = next(m for m in template["materials"]["videos"] if m["type"] == "photo")
        self.visual_seg = next(s for tr in template["tracks"] for s in tr["segments"]
                               if s["material_id"] == self.photo_mat["id"])
        keep = {"speeds", "placeholder_infos", "canvases", "sound_channel_mappings", "material_colors"}
        self.visual_refs = [(k, m) for k, m in (find(template["materials"], r) for r in self.visual_seg["extra_material_refs"])
                            if k in keep]
        # this draft's own video, text and audio clips as templates
        self.video_mat = next(m for m in self.M["videos"] if m["type"] == "video")
        self.text_seg = next(s for tr in d["tracks"] if tr["type"] == "text" for s in tr["segments"])
        self.text_mat = find(self.M, self.text_seg["material_id"])[1]
        self.font = json.loads(self.text_mat["content"])["styles"][0]["font"]
        self.audio_seg = next(s for tr in d["tracks"] if tr["type"] == "audio" for s in tr["segments"])
        self.audio_mat = find(self.M, self.audio_seg["material_id"])[1]
        akeep = {"speeds", "placeholder_infos", "sound_channel_mappings"}
        self.audio_refs = [(k, m) for k, m in (find(self.M, r) for r in self.audio_seg["extra_material_refs"]) if k in akeep]

        segs = [s for tr in d["tracks"] for s in tr["segments"]]
        self.video_ri = max((s["render_index"] for tr in d["tracks"] if tr["type"] == "video" for s in tr["segments"]), default=0)
        self.text_ri = max((s["render_index"] for s in segs if s["render_index"] >= 10000), default=14000)
        self.tracks = []
        self.lanes = []

    def refs(self, templates):
        ids = []
        for k, m in templates:
            m = copy.deepcopy(m)
            m["id"] = uid()
            self.M.setdefault(k, []).append(m)
            ids.append(m["id"])
        return ids

    def visual(self, mat, start, dur, clip, keyframes=(), volume=1.0):
        seg = copy.deepcopy(self.visual_seg)
        self.video_ri += 1
        seg.update(id=uid(), material_id=mat["id"], extra_material_refs=self.refs(self.visual_refs),
                   source_timerange={"start": 0, "duration": dur},
                   target_timerange={"start": start, "duration": dur},
                   render_index=self.video_ri, keyframe_refs=[], common_keyframes=list(keyframes),
                   volume=volume, last_nonzero_volume=1.0, clip=clip,
                   uniform_scale={"on": True, "value": 1.0})
        return seg

    def clip(self, x_px, y_px, scale=1.0):
        return {"scale": {"x": scale, "y": scale}, "rotation": 0.0,
                "transform": {"x": (x_px - self.W / 2) / (self.W / 2), "y": (self.H / 2 - y_px) / (self.H / 2)},
                "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0}

    def head(self, slot, png, times, end):
        path = into_draft("stickers", png)
        iw, ih = Image.open(path).size
        fit = min(self.W / iw, self.H / ih)  # CapCut fits photos to the canvas at scale 1
        scale = C.HEAD_PX / (ih * fit)
        mat = copy.deepcopy(self.photo_mat)
        mat.update(id=uid(), path=path, material_name=png, width=iw, height=ih,
                   local_material_id="", category_name="local")
        self.M["videos"].append(mat)
        start = times[0]
        seg = self.visual(mat, start, end - start,
                          self.clip(C.slot_x(slot, self.W) + C.HEAD_DX_PX, C.ROW_Y_PX, scale),
                          pop_keyframes(scale, [x - start for x in times[1:]]))
        self.tracks.append(("video", [seg]))

    def counter(self, slot, times, end):
        segs = []
        for i, t0 in enumerate(times):
            t1 = times[i + 1] if i + 1 < len(times) else end
            label = f"x{i + 1}"
            tm = copy.deepcopy(self.text_mat)
            style = {"fill": {"content": {"solid": {"color": [1, 1, 1]}, "render_type": "solid"}},
                     "range": [0, len(label)], "size": C.COUNTER_SIZE, "bold": True, "font": self.font,
                     "strokes": [{"content": {"solid": {"color": [0, 0, 0]}, "render_type": "solid"}, "width": 0.12}]}
            tm.update(id=uid(), content=json.dumps({"styles": [style], "text": label}),
                      font_size=C.COUNTER_SIZE, border_color="#000000", border_width=0.12, border_alpha=1.0)
            self.M["texts"].append(tm)
            anim = {"id": uid(), "type": "sticker_animation", "animations": [], "multi_language_current": "none"}
            self.M["material_animations"].append(anim)
            ts = copy.deepcopy(self.text_seg)
            self.text_ri += 1
            ts.update(id=uid(), material_id=tm["id"], extra_material_refs=[anim["id"]],
                      target_timerange={"start": t0, "duration": t1 - t0},
                      render_index=self.text_ri, keyframe_refs=[], common_keyframes=pop_keyframes(1.0, []))
            ts["clip"] = self.clip(C.slot_x(slot, self.W) + C.COUNTER_DX_PX, C.ROW_Y_PX + C.COUNTER_DY_PX)
            segs.append(ts)
        self.tracks.append(("text", segs))

    def sound(self, name, times, volume):
        path = into_draft("sfx", name)
        with open(path, "rb") as f:
            f.seek(40)
            data_bytes = int.from_bytes(f.read(4), "little")
        dur = int(data_bytes / (44100 * 4) * US)
        mat = copy.deepcopy(self.audio_mat)
        mat.update(id=uid(), type="music", name=name, path=path, duration=dur, music_id=str(uuid.uuid4()),
                   local_material_id="", wave_points=[])
        self.M["audios"].append(mat)
        lanes = []  # clips can't overlap on a track, so close-together sounds spill onto another lane
        for t in sorted(times):
            s = copy.deepcopy(self.audio_seg)
            s.update(id=uid(), material_id=mat["id"], extra_material_refs=self.refs(self.audio_refs),
                     source_timerange={"start": 0, "duration": dur},
                     target_timerange={"start": t, "duration": dur},
                     volume=volume, last_nonzero_volume=volume, keyframe_refs=[], common_keyframes=[])
            lane = next((l for l in lanes if l[-1]["target_timerange"]["start"] + dur <= t), None)
            if lane is None:
                lanes.append([s])
            else:
                lane.append(s)
        for lane in lanes:
            self.tracks.append(("audio", lane))

    def reveal(self, sub, name, start, end):
        """Full-frame rendered clip (celebrations/reveals) on its own top track."""
        path = into_draft(sub, name)
        mat = copy.deepcopy(self.video_mat)
        mat.update(id=uid(), path=path, material_name=name, width=self.W, height=self.H,
                   duration=end - start, has_audio=False, local_material_id="", category_name="local")
        self.M["videos"].append(mat)
        seg = self.visual(mat, start, end - start, self.clip(self.W / 2, self.H / 2), volume=0.0)
        self.tracks.append(("video", [seg]))

    def celebration(self, start, end):
        self.reveal("celebration", "celebration.mp4", start, end)

    def sticker(self, sub, name, start, end, x, y, rot=0.0, steps=None, extra_keyframes=(), animate=True):
        """PNG shown at its native pixel size, centred at (x, y); steps = [(offset, size multiplier)].
        animate=False gives a plain static clip with no keyframes."""
        path = into_draft(sub, name)
        iw, ih = Image.open(path).size
        base = 1 / min(self.W / iw, self.H / ih)   # undo CapCut's fit-to-canvas
        mat = copy.deepcopy(self.photo_mat)
        mat.update(id=uid(), path=path, material_name=name, width=iw, height=ih,
                   local_material_id="", category_name="local")
        self.M["videos"].append(mat)
        steps = steps or [(0, 1.0)]
        clip = self.clip(x, y, base * steps[0][1])
        clip["rotation"] = rot
        keys = grow_keyframes([(o, base * k) for o, k in steps]) + list(extra_keyframes) if animate else []
        seg = self.visual(mat, start, end - start, clip, keys)
        self.lanes.append(seg)
        return seg

    def flush_lanes(self):
        """Put stickers on as few video tracks as possible (clips on one track can't overlap)."""
        lanes = []
        for s in sorted(self.lanes, key=lambda s: s["target_timerange"]["start"]):
            st = s["target_timerange"]["start"]
            lane = next((l for l in lanes if all(o["target_timerange"]["start"] + o["target_timerange"]["duration"] <= st
                                                 for o in l)), None)
            if lane is None:
                lanes.append([s])
            else:
                lane.append(s)
        for lane in lanes:
            self.tracks.append(("video", lane))
        self.lanes = []

    def q2_word_cloud(self):
        end = at(C.Q2_REVEAL_START)
        for word, (x, y, rot, _) in C.Q2_WORDS.items():
            times = [at(t) for t, w in C.Q2_EVENTS if w == word]
            if not times:
                continue
            steps = [(t - times[0], C.Q2_GROW ** i) for i, t in enumerate(times)]
            self.sticker("q2", f"word_{word}.png", times[0], end, x, y, rot, steps)
        g = C.Q2_GAG
        gx, gy, grot = g["pos"]
        self.sticker("q2", "word_gag.png", at(g["at"]), at(g["end"]), gx, gy, grot)
        self.sticker("q2", "x.png", at(g["x_at"]), at(g["end"]), gx, gy, 0, [(0, 1.0)])
        self.flush_lanes()
        self.sound("pop.wav", [at(t) for t, _ in C.Q2_EVENTS] + [at(g["at"])], C.POP_VOLUME)
        self.sound("buzzer.wav", [at(g["x_at"])], C.BUZZER_VOLUME)
        self.reveal("q2", "reveal.mp4", end, at(C.Q2_END))
        self.sound("podium.wav", [end + us(0.95)], C.PODIUM_VOLUME)

    def q3_meter(self):
        start, end = at(C.Q3_METER_START), at(C.Q3_REVEAL_START)
        y = C.Q3_METER_Y_PX
        meter_w = Image.open(os.path.join(HERE, "assets", "q3", "meter.png")).width
        self.sticker("q3", "meter.png", start, end, self.W / 2, y)

        # the ball sits toward whichever side is ahead (one hand = right): one static clip per
        # vote, no keyframes — sliding it with position keyframes flickered in CapCut
        changes, lead = [(start, 0)], 0
        for t, side, n in C.Q3_VOTES:
            lead += n if side == 1 else -n
            changes.append((at(t), lead))
        for i, (t0, lead) in enumerate(changes):
            t1 = changes[i + 1][0] if i + 1 < len(changes) else end
            self.sticker("q3", "ball.png", t0, t1, self.W / 2 + lead * C.Q3_STEP_PX, y, animate=False)

        # tallies under each label
        for side in (0, 1):
            x = self.W / 2 + (-1 if side == 0 else 1) * (meter_w / 2 - 200)
            changes, total = [(start, 0)], 0
            for t, s, n in C.Q3_VOTES:
                if s == side:
                    total += n
                    changes.append((at(t), total))
            for i, (t0, total) in enumerate(changes):
                t1 = changes[i + 1][0] if i + 1 < len(changes) else end
                self.sticker("q3", f"n{total}.png", t0, t1, x, y + 95)

        f, p = C.Q3_FALL, C.Q3_PRO
        wobble = [(us(k * 0.15), r) for k, r in enumerate((0, -14, 11, -9, 7, -5, 3, 0))]
        self.sticker("q3", "fall.png", at(f["at"]), at(f["end"]), *f["pos"],
                     extra_keyframes=[kf_list("KFTypeRotation", wobble)])
        self.sticker("q3", "pro.png", at(p["at"]), at(p["end"]), *p["pos"], rot=-4)
        self.flush_lanes()
        self.sound("ding.wav", [at(t) for t, _, _ in C.Q3_VOTES], C.DING_VOLUME)
        self.sound("whistle.wav", [at(f["at"])], C.WHISTLE_VOLUME)
        self.sound("pop.wav", [at(p["at"])], C.POP_VOLUME)
        self.reveal("q3", "reveal.mp4", end, at(C.Q3_END, clamp=True))
        self.sound("podium.wav", [end + us(0.5)], C.PODIUM_VOLUME)

    def broll_cards(self):
        """Swap the picture under each question card for the navy b-roll; the audio is baked in."""
        kinds = {m["id"]: k for k, v in self.M.items() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}
        orig_base = next(t for t in load(os.path.join(ORIGINAL, "draft_info.json"))["tracks"] if t["type"] == "video")
        current = {s["id"]: s for s in self.d["tracks"][0]["segments"]}
        swapped = 0
        for i, (start, _, _) in enumerate(C.BROLL):
            path = into_draft("broll", f"card_{i + 1}.mp4")
            # card_N.mp4 starts where the ORIGINAL card clip's footage starts; follow that clip by id
            ob = next(s for s in orig_base["segments"] if abs(s["target_timerange"]["start"] - us(start)) < us(0.02))
            base = current.get(ob["id"])
            if base is None:
                print(f"  card {i + 1}: clip not found in the draft any more, skipped")
                continue
            w0, wdur = base["target_timerange"]["start"], base["target_timerange"]["duration"]
            src0 = ob["source_timerange"]["start"]
            mat = copy.deepcopy(self.video_mat)
            mat.update(id=uid(), path=path, material_name=f"card_{i + 1}.mp4", width=self.W, height=self.H,
                       duration=wdur, has_audio=True, local_material_id="", category_name="local")
            self.M["videos"].append(mat)
            for t in self.d["tracks"]:
                if t["type"] != "video":
                    continue
                for s in t["segments"]:
                    s0 = s["target_timerange"]["start"]
                    blurred = any(kinds.get(r) == "video_effects" for r in s["extra_material_refs"])
                    if blurred and w0 <= s0 < w0 + wdur:
                        s["material_id"] = mat["id"]
                        s["source_timerange"] = {"start": max(0, s["source_timerange"]["start"] - src0),
                                                 "duration": s["source_timerange"]["duration"]}
                        s["extra_material_refs"] = [r for r in s["extra_material_refs"] if kinds.get(r) not in CARD_DROP_REFS]
                        swapped += 1
        return swapped

    def commit(self):
        for ttype, segs in self.tracks:
            idx = len(self.d["tracks"])
            for s in segs:
                s["track_render_index"] = idx
            self.d["tracks"].append({"id": uid(), "type": ttype, "flag": 0, "attribute": 0,
                                     "name": "", "is_default_name": True, "segments": segs})
        return len(self.tracks)


def main():
    path = os.path.join(DRAFT, "draft_info.json")
    d = load(path)
    print("removed previous tracks:", strip_previous(d))
    global TIMELINE
    TIMELINE = Timeline(load(os.path.join(ORIGINAL, "draft_info.json")), d)
    b = Builder(d, load(os.path.join(PHOTO_TEMPLATE, "draft_info.json")))

    row_end = at(C.CELEB_START)  # the celebration clip takes the heads over from here
    for slot, (name, png) in enumerate(C.PEOPLE.items()):
        times = [at(s) for s, n in C.VOTES if n == name]
        if times:
            b.head(slot, png, times, row_end)
            b.counter(slot, times, row_end)
    b.sound("ding.wav", [at(s) for s, _ in C.VOTES], C.DING_VOLUME)
    b.celebration(row_end, at(C.QUESTION_END))
    b.sound("podium.wav", [at(C.CELEB_START) + us(C.PODIUM_CHIME_AT)], C.PODIUM_VOLUME)
    b.q2_word_cloud()
    b.q3_meter()
    # last: once a card shows b-roll its original footage can't be used to map times any more
    print("question-card clips swapped to b-roll:", b.broll_cards())

    n = b.commit()
    out = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    tl = os.path.join(DRAFT, "Timelines", d["id"])
    for p in [path, path + ".bak", os.path.join(tl, "draft_info.json"), os.path.join(tl, "draft_info.json.bak")]:
        if os.path.exists(os.path.dirname(p)):
            with open(p, "w") as f:
                f.write(out)
    print(f"added {n} tracks; votes:", C.counts())
    if TIMELINE.misses:
        print("WARNING: footage for these original times is no longer in the edit, left unmapped:",
              sorted(set(TIMELINE.misses)))


if __name__ == "__main__":
    main()
