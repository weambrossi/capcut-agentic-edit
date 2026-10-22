---
name: promo-video
description: Make a short promotional / ad video in my style – 30 s vertical 9:16, question hook, title card, one punchy caption per shot, zoom punch + flash on every cut, yellow CTA pill end card. Use when the user asks for a promo, ad, trailer, announcement, launch or "get people to book/buy/sign up" video.
---

# Promo video

Reference implementation: `make_rent_a_dent.py` (Rent-a-Dent). Copy it as the starting point for
a new promo and change the `SHOTS`, `TEXTS`, `PUNCHES`, `FLASHES` tables and the audio plan.

## Format

- 1080×1920, 30 fps, ~30 s. Export H.264 CRF 18, AAC 192k, `+faststart`.
- Landscape footage sits large in the middle over a blurred, darkened copy of itself
  (`compose_landscape`); vertical footage fills the frame (`compose_fill`).

## Structure

| Time | Beat |
|------|------|
| 0–3 s | **Hook**: question to the viewer ("Is your birthday coming up?") then the answer ("Let us handle it."). Gag allowed (smash zoom). |
| 3–5.5 s | **Title card**: small tracked "INTRODUCING", huge brand name in yellow, one-line tagline. Blurred photo slowly pushing in behind. |
| 5.5–26 s | **Proof**: one short caption per shot, 2–4 words ("We show up.", "Crowd approved.", "No mics. No backing track."). |
| last ~3.5 s | **End card**: brand name, `Service · Service · Service` line, CTA in a yellow pill ("DM us to book"), optional joke aside. |

## Visual style

- Font **Avenir Next** (Bold; Heavy for the brand name). Brand yellow `(255, 214, 10)`, white
  text otherwise, dark text on the yellow pill.
- **Soft drop shadow, not outlines.** Captions fade + rise in over 0.22 s with a slight scale settle.
- Main captions sit in the top third (y≈300–330); lyric/quote captions at the bottom (y≈1600) in a
  translucent black rounded box.
- On every cut: zoom punch (6–8 %, 0.35 s decay) and a white flash (40 %, 0.15 s). A small shake on
  the biggest moments.

## Sound

- Music with a recognisable hook under the intro, a record scratch into the title card, then the
  footage's own audio carries the middle.
- Whoosh 0.15 s before each cut (gain ~0.15), boom on the hook gag and the end card, ding when the
  CTA appears.
- RMS-normalise every clip to ~0.12, short fades on every edit, soft-clip the final mix.

## Process

1. Ask for brand name, offer, CTA and the footage/song paths if not given.
2. Draft the `TEXTS` copy and shot list as a table for approval before rendering.
3. `--preview` 4–6 key frames, check them, then render the full video to `out/`.
