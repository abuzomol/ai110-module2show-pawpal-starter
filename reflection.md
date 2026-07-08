# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

The initial UML (in `diagrams/uml.mmd`) was organized by responsibility into
four layers:

- **Value objects (enums):** `Priority`, `TaskCategory`, `Recurrence` — closed
  sets that prevent invalid states over free-form strings.
- **Entities (plain data holders):** `Owner`, `OwnerPreferences`, `Pet`, `Task` —
  no logic, just data, so they are trivial to construct and test.
- **Constraints:** `DayConstraints` — bundles time available, working hours, and
  blocked windows into a single object instead of loose parameters.
- **Engine + output:** `Scheduler` (with a `SchedulingStrategy` interface so the
  ordering algorithm can be swapped) producing a `Plan` composed of `PlanEntry`
  objects, each carrying a start time and a human-readable reason.

The guiding decision was to keep **data separate from the algorithm**: entities
hold state, the `Scheduler` service holds behavior. This kept scheduling
testable in isolation.

**b. Design changes**

Yes — the design grew several times as new requirements surfaced, and each change
was made additively so existing tested code stayed untouched:

- **Working hours / blocked windows.** Originally `fits()` only checked a minute
  budget. To support 9-to-5 hours and quiet hours, I added `day_end` and a
  `DayConstraints.next_free_start` timeline helper, and merged selection +
  placement in `build_plan` (removing `_select`) because whether a task "fits"
  now depends on *where* it lands, not just a running total.
- **Multi-day + recurrence.** Added a `MultiDayPlanner` layer on top of the
  single-day `Scheduler` rather than complicating the scheduler. It handles
  carry-over (with a `max_days` cap) and re-injects `daily`/`weekly` tasks.
- **Multi-pet.** Added a `pet_name` field to `Task` and pooled all pets' tasks
  onto one timeline, which reuses the single-timeline no-overlap guarantee.

The UML was updated after each change so it matches the final code.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers two *independent* kinds of constraint, and a task must
satisfy both to be scheduled:

- **Effort budget** (`available_minutes`) — the total minutes of care the owner
  can give in a day, shared across all pets.
- **Timeline** — the working-hours window (`day_start`/`day_end`) minus any
  `blocked_windows` such as work hours or quiet hours.

Within that, tasks are ordered by **priority first, then shorter duration**. I
decided priority mattered most because the scenario is about a busy owner staying
consistent with important care (meds, feeding, walks) — so high-priority tasks
should claim time before optional ones. The shorter-duration tie-break is a
secondary goal: it fits more tasks into the same budget.

**b. Tradeoffs**

Placement is **greedy and forward-only**: the clock never rewinds, so a task
pushed past a blocked window does not leave an earlier gap that a later, shorter
task could backfill. This can occasionally leave a small gap unused.

That tradeoff is reasonable here because a real owner works through the day in
order, and greedy priority-first placement is predictable and easy to explain
(every entry has a plain-language reason). An optimal gap-filling packer would be
more complex and harder to justify to a user — and if it were ever needed, it
could be added as another `SchedulingStrategy` without touching the rest.

---

## 3. AI Collaboration

**a. How you used AI**

I used AI across the whole workflow: drafting the initial UML from the scenario,
converting it into Python stubs, implementing the scheduling logic, and writing
tests. It was especially useful as a *design sounding board* — I asked pointed
"does the code actually do X?" questions (e.g. "does it support closed working
hours?", "can two tasks be scheduled at the same time?", "have you checked for
recurrence?"), and the most helpful ones forced a concrete check against the code
rather than a vague answer. Those questions repeatedly surfaced gaps between what
the model *claimed* and what the code actually did.

**b. Judgment and verification**

The clearest example was a failing test. When I first added start-time tests, one
failed because I had assumed two equal-priority tasks would keep their input
order — but the strategy deliberately reorders by duration. The right response was
**not** to weaken the scheduler to match my wrong assumption, but to fix the test
to assert the strategy's actual (correct) behavior.

More generally I verified suggestions by *running* them, not trusting them:
`pytest` after every change (ending at 38 passing tests), a `python main.py` CLI
demo to eyeball real output, and Streamlit's `AppTest` harness to confirm the UI
loads and generates a plan without exceptions. I also wrote a small script to
mathematically check for overlapping time intervals, which is how the cross-pet
scheduling conflict was confirmed before it was fixed.

---

## 4. Testing and Verification

**a. What you tested**

The suite in `tests/test_scheduler.py` (38 tests) covers each scheduling behavior:

- **Sorting** — priority order, the shorter-duration tie-break, and sort stability.
- **Filtering** — tasks skipped when the effort budget runs out, and completed
  tasks excluded from scheduling entirely.
- **Working hours** — a task that would cross `day_end` is skipped; a task ending
  exactly at the boundary is allowed; a task overlapping a blocked window is
  pushed past it (including cascading across multiple windows).
- **Multi-day** — carry-over of unfinished tasks, the `max_days` cap, and the
  no-progress stop for a task that can never fit.
- **Recurrence** — `daily` every day, `weekly` on the right days, and missed
  occurrences lapsing without piling up.
- **Multi-pet** — a regression test asserting **no overlapping entries**, plus
  pet tagging, household-wide priority ordering, and no mutation of caller data.

These matter because scheduling is the heart of the app; a subtle ordering or
budget bug would silently produce a wrong plan that still *looks* plausible.

**b. Confidence**

I am fairly confident in the core behaviors: they are pinned by tests, the single
shared timeline makes overlaps structurally impossible, and I verified the output
by hand via the CLI and the Streamlit `AppTest` harness.

Edge cases I would test next with more time: tasks that span midnight; per-pet or
per-slot capacity (letting some tasks genuinely run in parallel); weekly tasks
anchored to a real calendar weekday rather than a day index; and per-occurrence
completion for recurring tasks (right now one `is_completed` flag applies to all
days).

---

## 5. Reflection

**a. What went well**

- This problem was clear compared to other problems in tinkers. So I had fun really vibe-coding and chatting with Claude.

**b. What you would improve**

- I would optimize for task allocation by allowing different scheduling strategies. Also, yearly tasks can be added with fixed appointment with animal doctors.

**c. Key takeaway**

- Claude is really good about iterating the tasks from simple to more complex. The separation of code from data to logic and allowing for iterative designing phases is something to be amazed and admired. I can't write such good quality code in one day like with Claude.