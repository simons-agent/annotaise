# Study 1: progress goal, pace and tutorial video (design, 2026-11-25)

Decisions from the grill interview with the project lead (2026-11-25), approved for build.

## Intent

Annotators see only "N registros concluídos" in Parte 2. They should see a target (150), a
pace that prevents last-day cramming (weekly first, daily second), a reason to go beyond
150, and the tutorial video before they start.

## Decisions

1. Pace: weekly target first, daily second, both recomputed from what is missing and the
   time left until the labeling's `final_date` (15 Dec for the first push).
2. In Parte 1 the pace counts the remaining Parte 1 records plus the 150 of Parte 2.
3. After 150 the bar targets the next milestone (target + k * step; step 50). No pace
   lines once the target is reached.
4. After `final_date` the pace lines disappear; nothing says "closed". Moving `final_date`
   brings them back. Counting continues until the form is really closed.
5. Co-authorship as a text line only (top 3 by quality-checked Parte 2 records); no rank,
   no leaderboard. Everyone is acknowledged (as the video says); the form says "complete
   150 records to complete your participation".
6. Full block on the home card of the goal part; compact line in the answer header.
7. Video: the first YouTube link in the guide renders as a privacy-enhanced embed
   (youtube-nocookie.com) in a collapsible bar, open until the first record is
   submitted, closed afterwards. Guide page: open.
8. Invitation e-mail: clickable YouTube thumbnail plus the plain link (Gmail strips iframes).

## Build

- `Labeling.answer_target` and `Labeling.milestone_step` (nullable positive ints).
- `labeling/parts.py: goal(labeling, user, today)`: finds the goal labeling (this one or a
  later joined part with `answer_target`), returns `{target, done, next_milestone,
  to_go, deadline, days_left, per_week, per_day}` or None. `per_week = ceil(to_go /
  ceil(days_left / 7))`, `per_day = ceil(to_go / days_left)`, `days_left` counts today;
  both None when `to_go == 0` or the deadline has passed.
- `goal` is added to `parts.progress` (answer page) and to the annotator dashboard rows.
- Frontend: `GoalBlock` on the card (Parte 1 card: its own 45-record bar plus the pace
  line; Parte 2 card: bar toward target/milestone plus pace), compact header line in
  Parte 2 (Parte 1 keeps "Registro x de 45"), `TutorialVideo` in the guide panel, the
  guide page and the anonymous page.
- Study config (privdev-mappings `labeling_settings`): Parte 2 gets `answer_target=150`,
  `milestone_step=50`, `final_date=2026-12-15`.

My calls: rounding up; no pace after the target is reached; days counted in server local date.
