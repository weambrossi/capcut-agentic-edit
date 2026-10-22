# PRD: Learn From Previous Edits

Status: Draft · Owner: Ethan · Last updated: 2026-10-22

## 1. Problem

Claude produces a first cut in one of my styles (funny edit, promo video, …). I then fix it by hand
in CapCut: I shorten clips, move cuts, restyle captions, tone down zooms, swap sound effects. Those
fixes are the clearest signal of what my style actually is, but today they are lost. The next edit
repeats the same mistakes, and the only way to improve a style is to rewrite its `SKILL.md` from
memory.

## 2. Goals

- Capture Claude's original edit and my revised version of the same project.
- Compare them and list the meaningful differences in plain language.
- Turn differences that look like **recurring preferences** into proposed changes to the style's
  rules.
- Let me accept, edit or reject every proposal. Nothing changes a style without my approval.
- Keep every change to a style versioned and restorable.

## 3. Non-goals

- Automatically rewriting styles without review.
- Learning from edits that have no Claude-generated original (that's a later "import" feature).
- Frame-level visual understanding of footage (what is *in* a shot). This PRD works on timeline
  structure: clips, timing, text, effects, audio.
- Supporting editors other than CapCut in the first version. The data model should not rule them
  out.
- Training or fine-tuning a model. Learning lives in the style's Markdown rules.

## 4. Key distinction: one-time decisions vs. recurring preferences

Most manual changes are about *this* video: a bad take removed, a joke that didn't land cut, a
caption typo fixed. Only some reflect how I always want things. The system must treat every
difference as one-time by default and only propose a rule when there is evidence it recurs.

Signals that a change is a **recurring preference**:

- The same kind of change appears in **two or more** projects of the same style (e.g. zoom punches
  reduced from ~8 % to ~4 % in three edits).
- The change contradicts an explicit rule in the style (rule says "1–3 s shots", I consistently
  stretch them to 3–4 s).
- It is systematic within one project: applied to most instances, not one (every caption moved
  down, not one caption).
- I mark it as "always do this" during review.

Signals that a change is **one-time**:

- It touches content, not form: which take, which line, which joke, spelling.
- It affects a single instance in a single project.
- It reverses itself in another project.

Proposals show this evidence ("seen in 3 of 4 funny edits since Oct") so I can judge.

## 5. User stories

1. As the editor, after Claude builds a draft, I want its original timeline saved automatically so I
   don't have to remember to snapshot it.
2. After I finish revising in CapCut, I want to tell the system "this is my final version" with one
   action.
3. I want a readable summary of what I changed: "Shortened 9 of 14 clips by 0.4 s on average",
   "Removed all whoosh SFX", "Captions moved from top third to bottom".
4. I want to see which of those changes the system thinks are habits and why.
5. I want each proposed rule change shown as a before/after of the style section it touches, so I
   can accept, edit the wording, or reject it.
6. I want rejected proposals remembered so the same suggestion doesn't keep coming back.
7. I want to see the history of a style's rules and restore an earlier version.

## 6. Proposed workflow

1. **Generate.** Claude builds a draft using style *S*. The pipeline writes an *edit record* with the
   style (and the style file's git revision), source media, and a snapshot of the generated
   timeline.
2. **Revise.** I edit the draft in CapCut as usual.
3. **Capture.** I mark the edit as revised (dashboard button or a Claude command). The system
   snapshots the revised timeline into the same edit record.
4. **Compare.** A timeline diff aligns clips between the two snapshots and computes differences.
5. **Interpret.** Differences are summarised and classified (content vs. form, one instance vs.
   systematic). Claude turns form-level, systematic differences into candidate observations.
6. **Aggregate.** Observations are matched against earlier edit records for the same style to find
   recurring patterns.
7. **Propose.** For each pattern strong enough to act on, Claude drafts a change to a specific
   section of `SKILL.md` (e.g. *Pacing & Transitions*).
8. **Review.** In the dashboard I accept, edit or reject each proposal.
9. **Apply.** Accepted changes are written to the style's section through the existing lossless
   section editor and committed to git with a message linking the edit records.

## 7. UX requirements

- A new **Edits** area in the dashboard listing edit records: project, style, date, status
  (generated / revised / reviewed).
- Edit detail: side-by-side summary of original vs. revised (duration, clip count, average shot
  length, caption count, SFX count), then the list of differences grouped by category.
- A **Suggestions** view per style (could live on the style's Overview or History tab) with pending
  proposals: the rule text before/after, the evidence, and Accept / Edit / Reject.
- Rejected suggestions can be reopened from a "Dismissed" list.
- The History tab gains **Restore** for a revision, which itself goes through review.
- Same visual language as the current dashboard: no new heavy components, clear empty states
  ("No edits recorded yet. Edits are recorded when Claude builds a draft.").

## 8. Functional requirements

| # | Requirement |
|---|-------------|
| F1 | Store an edit record when Claude creates a CapCut draft or renders a video with a style. |
| F2 | Snapshot the generated timeline (`draft_info.json` for CapCut drafts) into the record. |
| F3 | Capture the revised timeline from the same CapCut draft folder on request. Refuse if CapCut is open (it rewrites the file on exit). |
| F4 | Normalise both snapshots into a common timeline model (§10). |
| F5 | Align clips between versions and compute differences for each category in §11. |
| F6 | Classify each difference as content or form and as single or systematic. |
| F7 | Aggregate form-level differences across records of the same style. |
| F8 | Generate rule proposals that target one `##` section of the style file, with evidence. |
| F9 | Review UI to accept (optionally after editing), reject, or defer each proposal. |
| F10 | Apply accepted proposals via the section editor; commit to git with record ids in the message. |
| F11 | Remember rejected proposals and suppress near-duplicates. |
| F12 | Restore an earlier style revision through the same review flow. |

## 9. Potential architecture

```
Claude edit (MCP / make_*.py)
        │ writes
        ▼
edits/<id>/record.json ──── original.json (normalised timeline)
        │                   revised.json
        ▼
diff engine (deterministic, Python or Node)
        │ differences.json
        ▼
interpreter (Claude): classify + summarise → observations.json
        │
        ▼
aggregator: match observations across a style's records → proposals.json
        │
        ▼
dashboard review → accepted → section editor → SKILL.md + git commit
```

- **Diff engine is deterministic code**, not an LLM, so differences are reproducible and testable.
- **Claude is used for interpretation and wording**: deciding whether a difference is a content
  choice, and writing the rule text in the style's voice.
- **Storage** is files in the repo, like `references/`: small JSON is committed; large raw
  snapshots can be gitignored if they grow (open question).
- **Integration points that already exist**: `backups/` already holds `draft_info.json` snapshots
  of the 1008 project; `add_vote_heads.py` already parses tracks, segments and materials; the
  dashboard already has lossless section editing and git history.

## 10. Data and versioning

Edit record (`edits/<id>/record.json`):

```json
{
  "id": "2026-10-22-funny-1008",
  "style": "funny-edit",
  "styleRevision": "<git sha of SKILL.md when generated>",
  "editor": "capcut",
  "draftPath": "~/Movies/CapCut/User Data/Projects/com.lveditor.draft/1008",
  "createdAt": "…",
  "revisedAt": "…",
  "status": "generated | revised | reviewed",
  "original": "original.json",
  "revised": "revised.json"
}
```

Normalised timeline: canvas size, fps, duration, and per track a list of items with `start`, `end`,
`type` (video, image, text, sticker, audio, effect), `source` (media path + source in/out),
`speed`, and type-specific properties (text content/font/size/position/animation, effect name and
intensity, audio volume/fades, keyframes such as zoom scale).

Versioning:
- Every applied proposal is a git commit touching one style file.
- A proposal stores the style revision it was generated against; if the section changed since,
  it must be regenerated (same conflict rule as the section editor).
- Proposals and decisions (`proposals.json`) are kept so dismissed suggestions stay dismissed.

## 11. Timeline comparison strategy

1. **Normalise** both versions to the model above (microseconds → seconds, resolve material ids to
   file paths).
2. **Align clips** by source media + overlapping source time range, falling back to order and
   timeline position. Unmatched originals are *removed*, unmatched revised clips are *added*
   (restored footage when the source range was available to the generator but unused).
3. **Per category**, compute differences:
   - *Clip duration & pacing*: per-clip trim deltas, average/median shot length, total duration.
   - *Cuts & transitions*: cut positions moved, transitions added/removed/changed, speed changes.
   - *Captions*: text edits (content), font/size/colour/position/animation changes (form), timing.
   - *Zoom intensity*: keyframed scale and punch-in amounts.
   - *Sound effects*: added/removed/moved SFX, volume changes, by SFX type.
   - *Music placement*: music in/out points, ducking, volume, fades.
   - *Removed or restored footage*.
4. **Summarise** into counts and averages per category before any LLM step.
5. **Thresholds** filter noise (e.g. trims under 2 frames, volume changes under 1 dB).

## 12. Relationship to existing skills

- Proposals target the five rule sections the dashboard already understands (Format, Pacing &
  Transitions, Captions & Typography, Sound, Color & Visual Effects) or another existing section.
- Changes go through `replaceSection`, so the rest of `SKILL.md` and its `references.md` are
  untouched.
- When editing skills exist (caption generation, audio mixing), a proposal may target the skill's
  configuration instead of the style. Out of scope until per-style skill configuration exists.
- Reference videos and learned rules are complementary: references show what I like in others'
  work; learned rules capture what I correct in Claude's work.

## 13. Risks and edge cases

- **Overfitting to one project.** Mitigated by requiring recurrence (§4) and human review.
- **CapCut format changes.** `draft_info.json` is undocumented and changes between versions; keep
  the parser isolated and tested against stored fixtures.
- **CapCut overwriting files.** Capture must refuse while CapCut is running.
- **Draft re-used or duplicated.** A record must pin the draft folder and verify it's the same
  project (draft id).
- **Edits that are mostly re-done.** If alignment matches few clips, report "too different to
  compare" instead of noisy differences.
- **Python-rendered edits** (e.g. `make_rent_a_dent.py`) have no CapCut timeline; their "timeline"
  is the `SHOTS`/`TEXTS` tables. Support later, or require exporting a timeline JSON.
- **Conflicting preferences** across styles: a change seen in funny edits must not leak into promo.
- **Rule bloat.** Proposals should prefer editing an existing bullet over appending new ones.
- **Privacy.** Records contain media paths and caption text; keep them local unless committed
  deliberately.

## 14. Milestones

| Phase | Scope | Issue |
|-------|-------|-------|
| 1 | Save original edit metadata and generated timeline | [#1](https://github.com/weambrossi/capcut-agentic-edit/issues/1) Save original edit metadata |
| 2 | Capture revised timeline from CapCut | [#2](https://github.com/weambrossi/capcut-agentic-edit/issues/2) Capture revised timelines |
| 3 | Normalise + compare timelines | [#3](https://github.com/weambrossi/capcut-agentic-edit/issues/3) Compare original and revised edits |
| 4 | Classify differences, recurring vs one-time | [#4](https://github.com/weambrossi/capcut-agentic-edit/issues/4) Identify meaningful changes |
| 5 | Draft rule proposals with evidence | [#5](https://github.com/weambrossi/capcut-agentic-edit/issues/5) Generate proposed style improvements |
| 6 | Review UI | [#6](https://github.com/weambrossi/capcut-agentic-edit/issues/6) Build approval/rejection interface |
| 7 | Apply accepted changes + commit | [#7](https://github.com/weambrossi/capcut-agentic-edit/issues/7) Apply approved changes to style rules |
| 8 | Version history restore | [#8](https://github.com/weambrossi/capcut-agentic-edit/issues/8) Version and restore previous rules |

## 15. Acceptance criteria (feature complete)

- Building a draft with a style creates an edit record with the generated timeline, without extra
  steps from me.
- Marking it revised captures my CapCut changes; the comparison lists differences per category
  that match what I actually changed in a hand-checked test project.
- A change I make in only one project is never proposed as a rule unless I ask.
- A change I make consistently across ≥2 projects of a style is proposed, with evidence.
- No style file changes until I accept; accepted changes appear in the style's History as a commit.
- I can restore any earlier version of a style's rules.

## 16. Open questions

1. Where do edit records live: committed in `edits/`, or local only with an opt-in commit?
2. How do we detect "Claude finished building a draft" reliably: wrap `capcut_save_draft`, or an
   explicit "record this edit" step in each style's Process section?
3. Which CapCut versions/draft profiles must be supported (`capcut_legacy` today)?
4. What thresholds define "systematic" within one project (e.g. ≥60 % of instances)?
5. Should proposals be generated on demand or after each revised capture?
6. How should Python-rendered edits expose a comparable timeline?
7. Should learned preferences be written into the main rule sections or a separate "Learned"
   section that's easier to audit?
