"""Tests for PawPal+ scheduling behavior (README: 'Smarter Scheduling')."""

import pytest

from logic import (
    DayConstraints,
    Plan,
    PlanEntry,
    PriorityFirstStrategy,
    Priority,
    Scheduler,
    Task,
)


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
