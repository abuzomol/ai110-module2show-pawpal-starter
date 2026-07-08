"""Tests for PawPal+ scheduling behavior (README: 'Smarter Scheduling')."""

import pytest

from pawpal_system import (
    DayConstraints,
    MultiDayPlanner,
    Pet,
    Plan,
    PlanEntry,
    PriorityFirstStrategy,
    Priority,
    Recurrence,
    Scheduler,
    Task,
)


def _to_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _find_overlaps(plan):
    """Return pairs of entry titles whose [start, end) intervals overlap."""
    ivs = [
        (_to_min(e.start_time), _to_min(e.start_time) + e.task.duration_minutes, e.task.title)
        for e in plan.entries
    ]
    clashes = []
    for i in range(len(ivs)):
        for j in range(i + 1, len(ivs)):
            a, b = ivs[i], ivs[j]
            if a[0] < b[1] and b[0] < a[1]:
                clashes.append((a[2], b[2]))
    return clashes


def make_task(title, minutes, priority=Priority.MEDIUM, completed=False):
    return Task(
        title=title,
        duration_minutes=minutes,
        priority=priority,
        is_completed=completed,
    )


# --------------------------------------------------------------------------
# Priority weighting
# --------------------------------------------------------------------------
def test_priority_weight_orders_high_above_low():
    assert (
        make_task("a", 10, Priority.HIGH).priority_weight()
        > make_task("b", 10, Priority.LOW).priority_weight()
    )


# --------------------------------------------------------------------------
# Strategy: ordering (sorting)
# --------------------------------------------------------------------------
def test_strategy_sorts_high_priority_first():
    tasks = [
        make_task("low", 10, Priority.LOW),
        make_task("high", 10, Priority.HIGH),
        make_task("med", 10, Priority.MEDIUM),
    ]
    ordered = PriorityFirstStrategy().order(tasks)
    assert [t.title for t in ordered] == ["high", "med", "low"]


def test_strategy_tie_breaks_by_shorter_duration():
    tasks = [
        make_task("long", 60, Priority.HIGH),
        make_task("short", 15, Priority.HIGH),
    ]
    ordered = PriorityFirstStrategy().order(tasks)
    assert [t.title for t in ordered] == ["short", "long"]


def test_strategy_is_stable_for_full_ties():
    tasks = [
        make_task("first", 20, Priority.MEDIUM),
        make_task("second", 20, Priority.MEDIUM),
    ]
    ordered = PriorityFirstStrategy().order(tasks)
    assert [t.title for t in ordered] == ["first", "second"]


# --------------------------------------------------------------------------
# Scheduler: selection / filtering by time budget
# --------------------------------------------------------------------------
def test_all_tasks_fit_within_budget():
    tasks = [make_task("walk", 20), make_task("feed", 10)]
    plan = Scheduler().build_plan("Mochi", tasks, DayConstraints(available_minutes=60))
    assert len(plan.entries) == 2
    assert plan.skipped == []


def test_low_priority_task_skipped_when_time_runs_out():
    tasks = [
        make_task("meds", 30, Priority.HIGH),
        make_task("walk", 30, Priority.HIGH),
        make_task("play", 30, Priority.LOW),
    ]
    plan = Scheduler().build_plan("Mochi", tasks, DayConstraints(available_minutes=60))
    scheduled = [e.task.title for e in plan.entries]
    assert scheduled == ["meds", "walk"]
    assert [t.title for t in plan.skipped] == ["play"]


def test_shorter_task_still_fits_after_a_miss():
    # 'big' (50) is tried first and skipped at a 60 budget after 'walk' (20);
    # the later 'snack' (10) should still be picked up.
    tasks = [
        make_task("walk", 20, Priority.HIGH),
        make_task("big", 50, Priority.MEDIUM),
        make_task("snack", 10, Priority.MEDIUM),
    ]
    plan = Scheduler().build_plan("Mochi", tasks, DayConstraints(available_minutes=60))
    scheduled = [e.task.title for e in plan.entries]
    assert scheduled == ["walk", "snack"]
    assert [t.title for t in plan.skipped] == ["big"]


def test_completed_tasks_are_never_scheduled():
    tasks = [
        make_task("done", 10, Priority.HIGH, completed=True),
        make_task("todo", 10, Priority.LOW),
    ]
    plan = Scheduler().build_plan("Mochi", tasks, DayConstraints(available_minutes=60))
    titles = [e.task.title for e in plan.entries]
    assert titles == ["todo"]
    assert "done" not in [t.title for t in plan.skipped]


# --------------------------------------------------------------------------
# Scheduler: start-time assignment
# --------------------------------------------------------------------------
def test_start_times_are_sequential_from_day_start():
    tasks = [make_task("a", 30, Priority.HIGH), make_task("b", 15, Priority.HIGH)]
    plan = Scheduler().build_plan(
        "Mochi", tasks, DayConstraints(available_minutes=120, day_start="08:00")
    )
    # First entry starts at day_start; each subsequent entry starts after the
    # previous one's duration (order is decided by the strategy, not input).
    assert plan.entries[0].start_time == "08:00"
    expected = 8 * 60 + plan.entries[0].task.duration_minutes
    assert plan.entries[1].start_time == f"{expected // 60:02d}:{expected % 60:02d}"


# --------------------------------------------------------------------------
# Explanations / summary
# --------------------------------------------------------------------------
def test_each_entry_has_a_reason():
    tasks = [make_task("walk", 20, Priority.HIGH)]
    plan = Scheduler().build_plan("Mochi", tasks, DayConstraints())
    reason = plan.entries[0].reason
    assert "high" in reason and "20 min" in reason and "08:00" in reason


def test_summary_reports_counts_and_skips():
    tasks = [
        make_task("a", 40, Priority.HIGH),
        make_task("b", 40, Priority.LOW),
    ]
    plan = Scheduler().build_plan("Mochi", tasks, DayConstraints(available_minutes=50))
    summary = plan.summary()
    assert "1 task(s) scheduled" in summary
    assert "1 skipped" in summary


def test_total_minutes_sums_scheduled_only():
    tasks = [
        make_task("a", 40, Priority.HIGH),
        make_task("b", 40, Priority.LOW),
    ]
    plan = Scheduler().build_plan("Mochi", tasks, DayConstraints(available_minutes=50))
    assert plan.total_minutes() == 40


# --------------------------------------------------------------------------
# Edge cases
# --------------------------------------------------------------------------
def test_empty_task_list_produces_empty_plan():
    plan = Scheduler().build_plan("Mochi", [], DayConstraints())
    assert plan.entries == []
    assert plan.skipped == []
    assert "0 task(s) scheduled" in plan.summary()


def test_task_longer_than_budget_is_skipped():
    tasks = [make_task("marathon", 300, Priority.HIGH)]
    plan = Scheduler().build_plan("Mochi", tasks, DayConstraints(available_minutes=60))
    assert plan.entries == []
    assert [t.title for t in plan.skipped] == ["marathon"]


# --------------------------------------------------------------------------
# Working hours (day_start / day_end)
# --------------------------------------------------------------------------
def test_task_that_would_cross_day_end_is_skipped():
    # 9:00-17:00 window = 480 min of hours, but a generous effort budget so the
    # timeline (not the budget) is what rejects the task.
    tasks = [make_task("long_groom", 90, Priority.HIGH)]
    constraints = DayConstraints(
        available_minutes=600, day_start="16:00", day_end="17:00"
    )
    plan = Scheduler().build_plan("Mochi", tasks, constraints)
    assert plan.entries == []
    assert [t.title for t in plan.skipped] == ["long_groom"]


def test_task_that_ends_exactly_at_day_end_is_allowed():
    tasks = [make_task("walk", 60, Priority.HIGH)]
    constraints = DayConstraints(
        available_minutes=600, day_start="16:00", day_end="17:00"
    )
    plan = Scheduler().build_plan("Mochi", tasks, constraints)
    assert [e.task.title for e in plan.entries] == ["walk"]
    assert plan.entries[0].start_time == "16:00"


# --------------------------------------------------------------------------
# Blocked windows (e.g. a lunch hour kept free)
# --------------------------------------------------------------------------
def test_task_is_pushed_past_a_blocked_window():
    # Lunch 12:00-13:00 is blocked. A 30-min task starting from 11:45 cannot sit
    # across noon, so it is placed at 13:00.
    tasks = [make_task("play", 30, Priority.HIGH)]
    constraints = DayConstraints(
        available_minutes=600,
        day_start="11:45",
        day_end="18:00",
        blocked_windows=[("12:00", "13:00")],
    )
    plan = Scheduler().build_plan("Mochi", tasks, constraints)
    assert plan.entries[0].start_time == "13:00"


def test_task_fits_before_blocked_window_when_it_can():
    # A 15-min task from 11:45 ends at 12:00 exactly — it may sit before lunch.
    tasks = [make_task("snack", 15, Priority.HIGH)]
    constraints = DayConstraints(
        available_minutes=600,
        day_start="11:45",
        day_end="18:00",
        blocked_windows=[("12:00", "13:00")],
    )
    plan = Scheduler().build_plan("Mochi", tasks, constraints)
    assert plan.entries[0].start_time == "11:45"


def test_blocked_window_cascades_to_following_tasks():
    # First task pushed to after lunch; the next task stacks after it.
    tasks = [
        make_task("first", 30, Priority.HIGH),
        make_task("second", 30, Priority.HIGH),
    ]
    constraints = DayConstraints(
        available_minutes=600,
        day_start="11:45",
        day_end="18:00",
        blocked_windows=[("12:00", "13:00")],
    )
    plan = Scheduler().build_plan("Mochi", tasks, constraints)
    starts = [e.start_time for e in plan.entries]
    assert starts == ["13:00", "13:30"]


def test_task_skipped_when_only_slot_is_after_day_end():
    # Blocked window eats the tail of the day, leaving no room for a 60-min task.
    tasks = [make_task("evening_walk", 60, Priority.HIGH)]
    constraints = DayConstraints(
        available_minutes=600,
        day_start="16:00",
        day_end="17:30",
        blocked_windows=[("16:00", "17:00")],
    )
    plan = Scheduler().build_plan("Mochi", tasks, constraints)
    assert plan.entries == []
    assert [t.title for t in plan.skipped] == ["evening_walk"]


def test_full_day_with_work_hours_and_quiet_hours():
    # A realistic day for a 9-5 owner:
    #   06:00-09:00  free (before work)
    #   09:00-17:00  BLOCKED (work hours)
    #   17:00-20:00  free (after work)
    #   20:00-24:00  BLOCKED (quiet hours, till end of day)
    # All tasks share HIGH priority, so the strategy orders them by ascending
    # duration -> placement order is: morning_walk, feeding, training,
    # evening_play, bedtime_meds.
    tasks = [
        make_task("morning_walk", 30, Priority.HIGH),
        make_task("feeding", 45, Priority.HIGH),
        make_task("training", 60, Priority.HIGH),
        make_task("evening_play", 120, Priority.HIGH),
        make_task("bedtime_meds", 150, Priority.HIGH),
    ]
    constraints = DayConstraints(
        available_minutes=600,
        day_start="06:00",
        day_end="24:00",
        blocked_windows=[("09:00", "17:00"), ("20:00", "24:00")],
    )
    plan = Scheduler().build_plan("Mochi", tasks, constraints)

    starts = {e.task.title: e.start_time for e in plan.entries}

    # Morning free window fills up back-to-back before work.
    assert starts["morning_walk"] == "06:00"
    assert starts["feeding"] == "06:30"
    assert starts["training"] == "07:15"  # ends 08:15, still before 09:00

    # evening_play can't finish before the 09:00 work block, so it is pushed
    # clear across the whole workday to the 17:00 free window.
    assert starts["evening_play"] == "17:00"  # 17:00-19:00

    # bedtime_meds (150 min) can't finish before quiet hours start at 20:00,
    # and quiet hours run to end of day -> no slot -> skipped.
    assert [t.title for t in plan.skipped] == ["bedtime_meds"]
    assert len(plan.entries) == 4


# --------------------------------------------------------------------------
# Multi-day planner (carry-over with a max_days cap)
# --------------------------------------------------------------------------
def test_backlog_carries_over_to_the_next_day():
    # Budget fits 2 of 3 tasks per day; the 3rd rolls to day 2.
    tasks = [
        make_task("a", 30, Priority.HIGH),
        make_task("b", 30, Priority.HIGH),
        make_task("c", 30, Priority.HIGH),
    ]
    constraints = DayConstraints(available_minutes=60)
    result = MultiDayPlanner().build_multi_day_plan("Mochi", tasks, constraints, max_days=7)

    assert len(result.days) == 2
    assert [e.task.title for e in result.days[0].entries] == ["a", "b"]
    assert [e.task.title for e in result.days[1].entries] == ["c"]
    assert result.unscheduled == []


def test_finishes_early_when_all_tasks_fit_in_one_day():
    tasks = [make_task("a", 20, Priority.HIGH), make_task("b", 20, Priority.HIGH)]
    constraints = DayConstraints(available_minutes=120)
    result = MultiDayPlanner().build_multi_day_plan("Mochi", tasks, constraints, max_days=5)

    assert len(result.days) == 1  # stops as soon as the backlog is empty
    assert result.unscheduled == []


def test_max_days_cap_limits_horizon_and_reports_unscheduled():
    # 5 tasks, 1 per day; a 2-day cap should schedule 2 and leave 3 unscheduled.
    tasks = [make_task(f"t{i}", 40, Priority.HIGH) for i in range(5)]
    constraints = DayConstraints(available_minutes=40)  # only 1 task/day
    result = MultiDayPlanner().build_multi_day_plan("Mochi", tasks, constraints, max_days=2)

    assert len(result.days) == 2
    assert sum(len(p.entries) for p in result.days) == 2
    assert len(result.unscheduled) == 3


def test_task_that_never_fits_stops_the_loop_and_is_unscheduled():
    # A 300-min task can never fit a 60-min budget: the first day schedules
    # nothing, so the loop stops immediately instead of looping max_days times.
    tasks = [make_task("marathon", 300, Priority.HIGH)]
    constraints = DayConstraints(available_minutes=60)
    result = MultiDayPlanner().build_multi_day_plan("Mochi", tasks, constraints, max_days=7)

    assert result.days == []  # no productive day recorded
    assert [t.title for t in result.unscheduled] == ["marathon"]


def test_completed_tasks_are_not_reported_as_unscheduled():
    # If the loop stops on day 1 (unschedulable task present), completed tasks
    # must not leak into the unscheduled list.
    tasks = [
        make_task("done", 10, Priority.HIGH, completed=True),
        make_task("marathon", 300, Priority.HIGH),
    ]
    constraints = DayConstraints(available_minutes=60)
    result = MultiDayPlanner().build_multi_day_plan("Mochi", tasks, constraints, max_days=3)

    assert [t.title for t in result.unscheduled] == ["marathon"]


def test_max_days_must_be_at_least_one():
    with pytest.raises(ValueError):
        MultiDayPlanner().build_multi_day_plan(
            "Mochi", [make_task("a", 10)], DayConstraints(), max_days=0
        )


def test_multi_day_summary_reports_totals():
    tasks = [make_task(f"t{i}", 40, Priority.HIGH) for i in range(5)]
    constraints = DayConstraints(available_minutes=40)
    result = MultiDayPlanner().build_multi_day_plan("Mochi", tasks, constraints, max_days=2)
    summary = result.summary()
    assert "2 task(s) scheduled across 2 day(s)" in summary
    assert "3 left unscheduled" in summary


# --------------------------------------------------------------------------
# Multi-pet scheduling (pooled onto one shared timeline)
# --------------------------------------------------------------------------
def test_multi_pet_plan_has_no_overlapping_entries():
    # The exact scenario that overlapped when pets were scheduled separately:
    # both pets have identical tasks. Pooled onto one timeline, nothing clashes.
    rex = Pet("Rex", "dog", tasks=[make_task("walk", 30, Priority.HIGH), make_task("meds", 15, Priority.HIGH)])
    bella = Pet("Bella", "dog", tasks=[make_task("walk", 30, Priority.HIGH), make_task("meds", 15, Priority.HIGH)])
    constraints = DayConstraints(available_minutes=600, day_start="08:00", day_end="20:00")

    plan = Scheduler().build_multi_pet_plan([rex, bella], constraints)

    assert len(plan.entries) == 4
    assert _find_overlaps(plan) == []


def test_multi_pet_entries_are_tagged_with_their_pet():
    rex = Pet("Rex", "dog", tasks=[make_task("walk", 30, Priority.HIGH)])
    bella = Pet("Bella", "cat", tasks=[make_task("meds", 15, Priority.HIGH)])
    constraints = DayConstraints(available_minutes=600)

    plan = Scheduler().build_multi_pet_plan([rex, bella], constraints)

    pets_for = {e.task.title: e.task.pet_name for e in plan.entries}
    assert pets_for["walk"] == "Rex"
    assert pets_for["meds"] == "Bella"
    # The pet name also shows up in the explanation.
    meds_entry = next(e for e in plan.entries if e.task.title == "meds")
    assert "Bella:" in meds_entry.reason


def test_multi_pet_orders_by_priority_across_the_household():
    # Bella's HIGH task should be scheduled before Rex's LOW task, even though
    # Rex is listed first.
    rex = Pet("Rex", "dog", tasks=[make_task("rex_play", 20, Priority.LOW)])
    bella = Pet("Bella", "cat", tasks=[make_task("bella_meds", 20, Priority.HIGH)])
    constraints = DayConstraints(available_minutes=600)

    plan = Scheduler().build_multi_pet_plan([rex, bella], constraints)

    assert [e.task.title for e in plan.entries] == ["bella_meds", "rex_play"]


def test_multi_pet_budget_is_shared_across_pets():
    # 60-min budget, two 40-min tasks on different pets -> only one fits.
    rex = Pet("Rex", "dog", tasks=[make_task("rex_walk", 40, Priority.HIGH)])
    bella = Pet("Bella", "cat", tasks=[make_task("bella_walk", 40, Priority.HIGH)])
    constraints = DayConstraints(available_minutes=60)

    plan = Scheduler().build_multi_pet_plan([rex, bella], constraints)

    assert len(plan.entries) == 1
    assert len(plan.skipped) == 1


def test_build_multi_pet_plan_does_not_mutate_original_tasks():
    # Pooling tags tasks with pet_name via a copy; the caller's Pet.tasks
    # objects must stay untouched (pet_name still blank).
    task = make_task("walk", 30, Priority.HIGH)
    rex = Pet("Rex", "dog", tasks=[task])
    Scheduler().build_multi_pet_plan([rex], DayConstraints(available_minutes=600))
    assert task.pet_name == ""


# --------------------------------------------------------------------------
# Recurrence across days (DAILY / WEEKLY, missed occurrences lapse)
# --------------------------------------------------------------------------
def recurring_task(title, minutes, recurrence, priority=Priority.HIGH):
    return Task(
        title=title,
        duration_minutes=minutes,
        priority=priority,
        recurrence=recurrence,
    )


def _titles_per_day(result):
    return [[e.task.title for e in day.entries] for day in result.days]


def test_daily_task_is_scheduled_every_day():
    tasks = [recurring_task("walk", 30, Recurrence.DAILY)]
    result = MultiDayPlanner().build_multi_day_plan(
        "Mochi", tasks, DayConstraints(available_minutes=600), max_days=3
    )
    assert len(result.days) == 3
    assert _titles_per_day(result) == [["walk"], ["walk"], ["walk"]]
    assert result.unscheduled == []  # recurring tasks never become 'unscheduled'


def test_weekly_task_is_due_only_on_day_0_and_day_7():
    tasks = [recurring_task("grooming", 30, Recurrence.WEEKLY)]
    result = MultiDayPlanner().build_multi_day_plan(
        "Mochi", tasks, DayConstraints(available_minutes=600), max_days=8
    )
    # Days recorded should be exactly the two due days (empty gap days between
    # day 0 and day 7 are skipped, not recorded).
    assert len(result.days) == 2
    assert _titles_per_day(result) == [["grooming"], ["grooming"]]


def test_daily_and_once_coexist_once_carries_over_recurring_does_not():
    # DAILY 'walk' (40) + two ONCE tasks (40 each). Budget 40 => one task/day.
    # The daily walk is high priority so it wins each day; the ONCE tasks trail.
    tasks = [
        recurring_task("walk", 40, Recurrence.DAILY, Priority.HIGH),
        Task("bath", 40, Priority.LOW, recurrence=Recurrence.ONCE),
        Task("nails", 40, Priority.LOW, recurrence=Recurrence.ONCE),
    ]
    result = MultiDayPlanner().build_multi_day_plan(
        "Mochi", tasks, DayConstraints(available_minutes=40), max_days=3
    )
    # Walk every day; bath/nails never get a turn (walk always outranks them).
    assert _titles_per_day(result) == [["walk"], ["walk"], ["walk"]]
    # The two ONCE tasks are still owed at the end; the daily walk is not.
    assert sorted(t.title for t in result.unscheduled) == ["bath", "nails"]


def test_missed_daily_occurrence_lapses_and_does_not_pile_up():
    # Daily walk can NEVER fit (300 min into a 60 budget): each day's instance
    # lapses instead of accumulating. Nothing is ever scheduled, and it is not
    # reported as unscheduled (recurring tasks lapse by design).
    tasks = [recurring_task("walk", 300, Recurrence.DAILY)]
    result = MultiDayPlanner().build_multi_day_plan(
        "Mochi", tasks, DayConstraints(available_minutes=60), max_days=4
    )
    assert result.days == []
    assert result.unscheduled == []  # lapsed, not carried/piled-up


def test_is_due_helper_semantics():
    from pawpal_system import _is_due
    daily = recurring_task("d", 10, Recurrence.DAILY)
    weekly = recurring_task("w", 10, Recurrence.WEEKLY)
    once = Task("o", 10, recurrence=Recurrence.ONCE)
    assert [_is_due(daily, d) for d in range(3)] == [True, True, True]
    assert [_is_due(weekly, d) for d in [0, 1, 6, 7, 14]] == [True, False, False, True, True]
    assert _is_due(once, 0) is False  # ONCE handled via backlog, never 'due'
