# Additional video editing features

Ideas for later. No PRDs or issues yet; promote one to a PRD when it's next up.

| Feature | Priority |
|---------|----------|
| [AI editing plan](#1-ai-editing-plan) | High |
| [Automated quality control](#2-automated-quality-control) | Medium |
| [Multi-format output](#3-multi-format-output) | Medium |
| [Music and beat analysis](#4-music-and-beat-analysis) | Medium |
| [Timecoded feedback](#5-timecoded-feedback) | Medium |

## 1. AI editing plan

**Priority: High**

Before editing, Claude proposes a plan for review:

- Video structure and sequence of clips
- Which clips (and which parts of them) to use
- Music choices
- Rough timeline with timestamps
- Transitions and overall pacing

The user approves or adjusts the plan before any draft is built. Builds on the planning steps
some styles already have (the funny edit's gag table, the promo's shot list).

## 2. Automated quality control

**Priority: Medium**

Inspect a finished edit and report problems before export:

- Awkward cuts (mid-word, flash frames, jump cuts)
- Audio clipping and loudness outside target
- Captions extending past the frame or safe area
- Unintended silence
- Missing or offline media
- Other inconsistencies (mixed fonts, mismatched frame rates)

## 3. Multi-format output

**Priority: Medium**

Adapt a finished edit to other aspect ratios:

- 9:16
- 16:9
- 1:1

Reframe each shot around its subject, reposition and re-wrap captions, and adjust timing or
graphics where needed instead of plain center-cropping.

## 4. Music and beat analysis

**Priority: Medium**

Analyze a track to find:

- Beats and tempo
- Song sections (intro, verse, chorus, bridge)
- Energy changes
- Drops and transitions
- Suggested cut points

Use these to recommend cuts and effects that land on the music.

## 5. Timecoded feedback

**Priority: Medium**

Leave feedback tied to exact timestamps, e.g. "At 00:14, make this cut faster." Claude interprets
each comment and proposes or makes a targeted change at that point in the timeline.
