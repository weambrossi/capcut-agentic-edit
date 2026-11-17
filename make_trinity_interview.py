"""Trinity football pre-game interview: minimal two-player cut with practice B-roll.

Reference example for the `interview-cut` style; the pipeline lives in interview_kit.py.
Interleaves Luke (#99, MVI_9702) and Nolan (#11, MVI_9703) answer by answer. The off-camera
questions play over B-roll; answers stay on the speaker's face.

    python3 make_trinity_interview.py --preview    # one frame per shot -> out/trinity_interview/preview_*.jpg
    python3 make_trinity_interview.py              # render out/trinity_interview/trinity_interview.mp4
    python3 make_trinity_interview.py --verify     # render, then transcript + A/V sync check
"""
from interview_kit import Edit

LUKE, NOLAN = "MVI_9702", "MVI_9703"
TRINITY_GOLD = (233, 190, 72)

EDL = [
    # Open: location shot with nat sound, then the first question over a second location shot
    dict(note="TRINITY sign", v="MVI_9688", vin=2.0, dur=2.6),
    dict(note="Q: name, class year, position", a=LUKE, ain=6.30, aout=8.80, v="MVI_9690", vin=3.0),
    dict(note="Luke intro", a=LUKE, ain=8.92, aout=15.15,
         lower=("Luke Pickard", "Defensive End  ·  Class of 2026")),
    dict(note="Nolan intro", a=NOLAN, ain=4.05, aout=9.95,
         lower=("Nolan O’Brien", "Receiver  ·  Class of 2026")),
    # One word
    dict(note="Q: one word for tomorrow", a=NOLAN, ain=10.30, aout=13.90, v="MVI_9678", vin=0.5),
    dict(note="Nolan: Prepare", a=NOLAN, ain=13.95, aout=15.60),
    dict(note="Luke: finally", a=LUKE, ain=24.05, aout=30.50),
    dict(note="Luke cont. over #99 at practice", a=LUKE, ain=30.50, aout=33.80, v="MVI_9670", vin=0.4),
    dict(note="Luke cont. over helmets", a=LUKE, ain=33.80, aout=37.20, v="MVI_9657", vin=6.0),
    dict(note="Luke: payback", a=LUKE, ain=37.20, aout=42.90),
    # Ritual
    dict(note="Q: pregame ritual", a=NOLAN, ain=15.92, aout=19.08, v="MVI_9689", vin=3.0),
    dict(note="Nolan: walk the field", a=NOLAN, ain=19.18, aout=22.75),
    dict(note="Nolan cont. over #11 walking up", a=NOLAN, ain=22.75, aout=26.15, v="MVI_9652", vin=12.5),
    dict(note="Nolan: first one on the field", a=NOLAN, ain=26.15, aout=28.95),
    dict(note="Luke: no ritual", a=LUKE, ain=48.40, aout=49.85),
    dict(note="Luke: breakfast, over #17 & #7 walking up", a=LUKE, ain=63.88, aout=69.76, v="MVI_9653", vin=1.0),
    # Hype song
    dict(note="Q: hype song, over #41 on the bench", a=NOLAN, ain=30.25, aout=33.55, v="MVI_9683", vin=1.0),
    dict(note="Luke: Rick Ross & Lil Wayne", a=LUKE, ain=52.65, aout=59.62),
    dict(note="Nolan: Rocky theme song", a=NOLAN, ain=33.70, aout=36.20),
    # Close
    dict(note="Outro: team watching", v="MVI_9691", vin=4.0, dur=4.5),
]

if __name__ == "__main__":
    Edit(src_dir="~/Desktop/sports video/trinity football/nov13-practice",
         name="trinity_interview", accent=TRINITY_GOLD).main(EDL)
