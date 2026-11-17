---
name: interview-cut
description: Make a clean, minimal interview edit in my style – one or more people answering the same off-camera questions, cut answer by answer, questions laid over B-roll, name/role lower thirds, straight cuts, no music or captions. Use when the user asks to cut up an interview, Q&A, player/athlete/team interviews, a "get to know" piece, testimonials or vox pops, or to "make interviews ready to post".
metadata:
  kind: style
  source: custom
---

# Interview cut

Toolkit: `interview_kit.py`. Reference edit: `make_trinity_interview.py`, two football players
with practice B-roll. Copy the reference, replace the `EDL` and the `Edit(...)` arguments, and keep
the pipeline in the kit. Don't fork it.

## Finding the footage

- Interviews are usually the **longest clips with a static, centred subject**. When the user says
  "the last N videos", sort the clips by name or date and confirm by looking at frames.
- Everything else in the shoot folder is the B-roll pool.

## Structure

1. **Open** on about 2.5 s of an establishing shot (a sign, the venue, the location) with its
   natural sound, then play the first question over a second establishing shot.
2. **Intros:** each person says their name and role, on camera, with a lower third.
3. **Topics in the order they were asked.** For each question:
   - Play the question **once**, over B-roll, taken from whichever take has the cleanest delivery.
   - Then each person's answer, back to back. Put the short or punchy answer first and the longer
     one second. If one answer is a single word, it always goes first.
4. **Close** on a light line or a smile, then about 4.5 s of B-roll with natural sound and a 0.6 s
   fade to black.

Aim for 60–90 s with two people. Add roughly 30 s for each extra person.

## Cutting

- Cut out setup chatter ("how's my hair"), stutters and restarts ("I would say— I would say X"),
  and the interviewer's reactions ("Nice", "Let's go"). Keep only the questions.
- End each answer on its strongest line. Drop trailing filler ("so yeah, for sure", "I think it's
  called…, I don't know").
- Cut only on sentence boundaries. Run `python3 interview_kit.py words <clip>`: it prints each
  sentence with in and out points snapped to the nearest real silence, plus every word's timing
  for cuts inside a sentence (dropping a stutter). Start from those numbers, never raw Whisper
  timestamps, which can be several hundred ms off. A soft last word ("…ready to go") can read as
  silence, so if the `--verify` transcript drops it, add about 0.2–0.4 s to that out-point.
- To join two non-adjacent parts of one answer, put B-roll over the second part so the jump cut
  doesn't show.
- The kit renders every shot to an exact number of frames and trims its audio to match. Without
  that, the picture drifts behind the sound. Don't bypass it.

## B-roll

Run `python3 interview_kit.py sheet <footage dir>` for 3 frames per clip, then
`sheet <dir> CLIP --every 2` on the candidates to find exact in-points.

- **Match B-roll to the speaker.** While someone talks, show *them*: their jersey number, their
  name on a sign, them at work. Look for shots of the people together too, but don't force one if
  none exists.
- **Close-ups over wides.** People walking toward the camera at mid or close range, details
  (helmets, gear, hands, signage). Avoid wide shots where people are tiny.
- **Sharp, well-lit clips only.** Skip grainy low-light, night and dusk shots unless that's all
  there is. Lighting usually improves on later clips in a shoot, so check those first.
- **Steady sections only.** Skip the first ~0.5 s if the camera is still settling, and avoid
  pans and focus hunts.
- Use B-roll over the questions, once or twice inside long answers (more than about 6 s), and
  anywhere it hides a jump. Keep the speaker's face on screen for punchlines and the last line of
  each answer.
- Don't reuse a B-roll clip, and don't put two similar shots back to back.

## Look and sound

- Output at the interview footage's frame rate, 1920×1080 (pass `size=(1080, 1920)` for vertical).
  Straight cuts only, with a 0.6 s fade from and to black at the very start and end. No zooms,
  flashes or transitions.
- **Lower thirds** on each person's first appearance only: name in Avenir Next Demi Bold, role
  line in Medium, a thin accent bar in the team or brand colour (`accent=`, white if there's none),
  and a soft shadow. They appear 0.4 s into the shot, hold 3.6 s, then fade out.
  - **Role line:** only what they said on camera (position, title, class year), with `  ·  `
    between items.
  - **Spelling:** a name heard in the audio is a guess. Ask the user to confirm it before you
    call the edit finished.
- No captions, music or SFX unless asked.
- **Even levels:** the kit matches every interview shot to −20 LUFS before the mix, because
  off-camera questions are usually much louder than the answers and speakers differ. B-roll
  natural sound sits 12 dB under speech. The mix is lifted to −16 LUFS with a −1.5 dBFS peak
  limiter, a static gain with no pumping.
- **Don't let the next line bleed in:** an out-point must end before the interviewer (or the
  speaker) starts the next question, even a single word like "Hype song". If the next line follows
  closely, cut in the gap between them.

## Process

1. Find the interviews and run `words` on each.
2. Write the paper edit: the ordered quotes with in and out points, grouped by question.
3. Run `sheet`, then pick B-roll with the rules above.
4. Run `--preview` and look at every `preview_*.jpg` and `preview_lower_*.jpg`.
5. Render with `--verify`. Read the transcript for clipped words or stray interviewer lines, and
   confirm the sync line says OK.
6. Send the user the mp4 path and the names to confirm. Expect B-roll notes, and swap shots
   in the EDL.

## Reference videos

Before planning an edit, read [references.md](references.md): the user's inspiration videos for
this style and what they like about each.
