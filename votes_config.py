"""Shared settings for the question graphics in project "1008 funniest".

Every time here is measured on the ORIGINAL 1008 timeline. The builder maps each one to the same
moment of footage in "1008 funniest", so trims and moves made there in CapCut are followed.
"""

# slot order matches the sticker preview. Real names live in the gitignored votes_names_local.py
# (NAMES = {"Person 1": "...", ...}); without it the placeholders are shown.
PEOPLE = {
    "Person 1": "sticker_1.png",
    "Person 2": "sticker_2.png",
    "Person 3": "sticker_3.png",
    "Person 4": "sticker_4.png",
}
# (timeline seconds, name) — each time a name is said
VOTES = [
    (9.12, "Person 4"),
    (9.77, "Person 2"),
    (11.24, "Person 1"),
    (12.17, "Person 2"),
    (12.94, "Person 1"),
    (15.00, "Person 1"),
    (17.57, "Person 1"),
    (18.87, "Person 1"),
    (20.10, "Person 2"),
    (21.30, "Person 2"),
    (25.06, "Person 3"),
    (28.19, "Person 2"),
]
try:
    from votes_names_local import NAMES
except ImportError:
    NAMES = {}
PEOPLE = {NAMES.get(n, n): f for n, f in PEOPLE.items()}
VOTES = [(t, NAMES.get(n, n)) for t, n in VOTES]

QUESTION_END = 32.27     # next question starts here
CELEB_START = 29.30      # podium celebration covers CELEB_START → QUESTION_END

# top-row layout on the 1920x1080 canvas
HEAD_PX = 230            # head height
ROW_Y_PX = 150           # head row centre, pixels from the top
SLOT_SPACING_PX = 430
HEAD_DX_PX = -28.8       # head sits slightly left of the slot centre
COUNTER_DX_PX = 125      # counter offset to the right of the slot centre
COUNTER_DY_PX = 43       # counter sits slightly below the head centre
COUNTER_SIZE = 12.0      # CapCut text size

# sound effects (CapCut clip volume, 1.0 = unchanged)
DING_VOLUME = 0.35
PODIUM_VOLUME = 0.45
PODIUM_CHIME_AT = 0.8    # seconds into the celebration


# b-roll behind the question cards: (card start on the timeline, raw clip, start second in that clip)
BROLL_DIR = "/Users/ethanambrossi/Desktop/sports video raw"
BROLL = [
    (0.00, "00074.MTS", 4.0),    # intro + "who's the funniest"
    (32.27, "00077.MTS", 0.0),   # "describe the team in 3 words"
    (57.30, "00072.MTS", 0.5),   # "flip flops or one hand"
]
# slight blur + deep team-navy duotone
BROLL_LOOK = ("gblur=sigma=6,hue=s=0.3,eq=contrast=1.05:brightness=-0.02,"
              "colorchannelmixer=rr=0.45:gg=0.6:bb=0.9,"
              "colorlevels=romin=0.02:gomin=0.04:bomin=0.12:romax=0.7:gomax=0.78:bomax=0.95")


# ---- question 2: "describe the team in 3 words" word cloud ----
# word -> (centre x, centre y, rotation degrees, fill colour) along the top of the frame
Q2_WORDS = {
    # row 1
    "SCRAPPY": (304, 104, -4, "gold"),
    "GRITTY": (794, 118, 3, "white"),
    "INTENSE": (1266, 104, -3, "sky"),
    "CLOSE": (1722, 118, 3, "white"),
    # row 2
    "PLAYFUL": (241, 242, 4, "sky"),
    "ENERGETIC": (944, 256, -2, "gold"),
    "CREATIVE": (1663, 242, 4, "white"),
}
# (timeline seconds, word) — a word repeated within one answer counts once
Q2_EVENTS = [
    (36.08, "SCRAPPY"),
    (36.93, "SCRAPPY"),
    (38.78, "GRITTY"),
    (40.43, "INTENSE"),
    (45.67, "INTENSE"),
    (46.71, "PLAYFUL"),
    (48.09, "ENERGETIC"),
    (50.03, "ENERGETIC"),
    (52.65, "CREATIVE"),     # the clip Whisper heard as "Readers!"
    (53.68, "CLOSE"),
]
Q2_GAG = dict(word="SCRUFFY?", at=42.40, x_at=42.95, end=44.30, pos=(900, 255, 2))
Q2_WORD_PX = 86          # sticker height for a word said once
Q2_GROW = 1.3            # size multiplier each extra time a word is said
Q2_REVEAL_START = 55.00
Q2_END = 57.30           # "flip flops" card starts

# ---- question 3: flip flops vs one hand tug-of-war ----
Q3_SIDES = ("FLIP FLOPS", "ONE HAND")
# (timeline seconds, side index, votes) — 0 = flip flops, 1 = one hand
Q3_VOTES = [
    (60.70, 1, 2),       # two players say "one hand behind my back" together
    (67.08, 1, 1),
    (71.00, 0, 1),
    (72.76, 0, 1),
    (81.40, 1, 1),
    (84.60, 0, 1),
]
Q3_METER_START = 60.30   # right as the card ends
Q3_METER_Y_PX = 115
Q3_STEP_PX = 90          # how far the ball moves per vote of lead (max lead 3 stays on the bar)
Q3_FALL = dict(at=80.47, end=82.20, pos=(1620, 470))     # "I think I would fall" 📉 + slide whistle
Q3_PRO = dict(at=86.30, end=88.07, pos=(1560, 450))      # "I wear them every day" badge
Q3_REVEAL_START = 90.20
Q3_END = 92.966

# extra sound effect volumes
POP_VOLUME = 0.4
BUZZER_VOLUME = 0.3
WHISTLE_VOLUME = 0.35


def q2_counts():
    return {w: sum(1 for _, x in Q2_EVENTS if x == w) for w in Q2_WORDS}


def q3_counts():
    return [sum(n for _, s, n in Q3_VOTES if s == i) for i in range(2)]


def counts():
    return {n: sum(1 for _, v in VOTES if v == n) for n in PEOPLE}


def slot_x(slot, width=1920):
    return width / 2 + (slot - 1.5) * SLOT_SPACING_PX
