---
name: funny-edit
description: Make a funny / meme-style edit in my style – fast cuts, punch zooms, smash zoom on a face, SFX hits (boom, whoosh, ding, buzzer), pop-in stickers and counters, confetti payoffs. Use when the user asks for a funny, meme, comedic, hype or "roast" edit, or a team/friends video with votes or reactions.
---

# Funny edit

Reference implementations: `make_celebration.py`, `make_q23.py`, `add_vote_heads.py` (1008
funniest) and the intro/outro gags in `make_rent_a_dent.py`. Reuse their helpers instead of
rewriting them.

## Workflow

1. Transcribe the footage (`whisper-cli`) and find the beats: punchlines, names said, reactions.
   Put every timed moment in a config module like `votes_config.py`, not inline in the renderer.
2. Plan the gags as a timeline table (time → gag → SFX) and show it to the user before building.
3. Render graphics in Python, preview frames, then place them in the CapCut draft (MCP tools or
   draft patching with CapCut closed).

## Visual style

- Fonts: **Arial Black** for big words, Arial Bold for small; thick stroke (6–8 px) in navy
  `(14, 22, 52)`. Accent gold `(255, 200, 40)`, base navy `(24, 38, 84)`.
- Everything **pops in** with `ease_out_back` (overshoot ~1.2–2.2), never a plain fade.
- Big reveal = blurred + darkened background, then the payoff (podium, title, counters) rises in,
  with pulsing gold glow and confetti cannons (`make_confetti`, `draw_confetti`).
- Face gags: slow push, then a **smash zoom** onto one face in ~0.2 s with contrast/saturation
  lift and a vignette (`deep_fry`, `vignette` in `make_rent_a_dent.py`), plus a short shake.
- People appear as cut-out head stickers (`stickers/`) with `x{n}` counters next to them.

## Sound

- Hit on every gag: **boom** under smash zooms, **whoosh** 0.15 s before cuts, **ding** per point
  or counter tick, **buzzer** for wrong answers, **pop** for stickers appearing, **podium** chime
  for the win. Synth versions live in `make_sfx.py` / `assets/sfx/`, and `synth_boom`,
  `synth_whoosh`, `synth_scratch` are in `make_rent_a_dent.py`.
- A record scratch on the music right before a hard cut or reveal.
- Keep dialogue on top: RMS-normalise clips (~0.12) and duck SFX to 0.15–0.5 gain.

## Pacing

- Shots 1–3 s; a zoom punch (6–8 %, 0.35 s decay) on every cut.
- Let the punchline breathe ~0.5 s after the hit before cutting again.
- End on the payoff (winner, reaction), not a fade-out.
