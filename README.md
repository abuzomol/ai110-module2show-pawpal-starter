# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Running the CLI demo (`python main.py`) produces a single-day plan for a 9-to-5
owner (free 06:00–09:00, work 09:00–17:00 blocked, quiet hours 20:00–24:00,
240-minute effort budget):

```
============================================================
  Daily plan for Mochi
  Working hours: 06:00-24:00  |  Effort budget: 240 min
  Blocked: 09:00-17:00, 20:00-24:00
============================================================
  06:00  Vet meds             ( 10 min) [high]
          ↳ high priority, 10 min — scheduled at 06:00
  06:10  Breakfast            ( 15 min) [high]
          ↳ high priority, 15 min — scheduled at 06:10
  06:25  Morning walk         ( 30 min) [high]
          ↳ high priority, 30 min — scheduled at 06:25
  06:55  Training session     ( 45 min) [medium]
          ↳ medium priority, 45 min — scheduled at 06:55
  17:00  Evening play         (120 min) [medium]
          ↳ medium priority, 120 min — scheduled at 17:00
------------------------------------------------------------
  Skipped (no time budget or no open slot):
    - Grooming (60 min, low)
------------------------------------------------------------
  5 task(s) scheduled (220 min), 1 skipped for time
============================================================
```

Notice the scheduler's decisions: high-priority tasks fill the morning free
window back-to-back, **Evening play (120 min) is pushed clear across the 8-hour
work block to 17:00**, and Grooming is dropped once the effort budget runs out.

`main.py` also demonstrates the **multi-day** planner (carry-over + a `max_days`
cap), **multi-pet** household scheduling (all pets pooled onto one conflict-free
timeline), and **recurring** tasks (a daily walk recurs every day; a weekly
grooming returns on day 1 and day 8).

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
collected 38 items

tests/test_scheduler.py ......................................    [100%]

============================== 38 passed in 0.05s ==============================
```

## 📐 Smarter Scheduling

All scheduling logic lives in `pawpal_system.py`; behaviors are covered by the
tests in `tests/test_scheduler.py`.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `PriorityFirstStrategy.order` | Highest priority first; ties broken by shorter duration (fits more tasks). Stable sort → deterministic. |
| Filtering | `Scheduler.build_plan`, `DayConstraints.fits` | Two independent limits: an effort budget (`available_minutes`) and the working-hours timeline. A task is skipped if it fails either. |
| Conflict handling | `Scheduler.build_plan`, `Scheduler.build_multi_pet_plan` | Tasks are placed on one forward-only timeline, so entries never overlap. Multiple pets are pooled onto that single timeline → no cross-pet clashes. |
| Working hours | `DayConstraints.next_free_start` | `day_start`/`day_end` plus `blocked_windows` (e.g. work hours, quiet hours). A task that would overlap a block is pushed past it, or skipped if no slot remains. |
| Recurring tasks | `MultiDayPlanner.build_multi_day_plan`, `_is_due` | `daily` recurs every day; `weekly` on day 0, 7, 14…. Missed occurrences lapse (no pile-up). |
| Carry-over | `MultiDayPlanner.build_multi_day_plan` | Unfinished one-off tasks roll to the next day; a `max_days` cap bounds the horizon so a never-fitting task can't carry over forever. |

## 📸 Demo Walkthrough

Run the Streamlit app with `streamlit run app.py`, then:

1. **Owner & Pets** — enter the owner's name and add one or more pets (e.g. Mochi, Rex). Removing a pet also removes its tasks.
2. **Day Constraints** — set the working-hours window (day start/end) and the daily effort budget. Add *blocked windows* for times to keep free, such as 09:00–17:00 work hours or evening quiet hours.
3. **Planning horizon** — choose *Days to plan*. Leave it at 1 for a single day, or increase it to enable carry-over of unfinished tasks and recurring tasks across days.
4. **Tasks** — for each task pick the pet, title, duration, priority, category, and recurrence (`once`/`daily`/`weekly`). Mark a task completed to exclude it. Added tasks appear in a table.
5. **Generate plan** — the app pools every pet's tasks onto one shared timeline and builds the plan. Each day's schedule shows the time, pet, task, recurrence, and a short *why* for each entry, followed by any tasks that couldn't be scheduled.

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
