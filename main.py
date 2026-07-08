"""Simple CLI runner for PawPal+.

Runs the scheduling logic in `pawpal_system.py` against sample scenarios and
prints the resulting plans to the terminal. Useful as a quick smoke test and as
the CLI demo referenced in the README.

Run with:  python main.py
"""

from pawpal_system import (
    DayConstraints,
    MultiDayPlanner,
    Pet,
    Priority,
    Recurrence,
    Scheduler,
    Task,
    TaskCategory,
)


def build_sample_tasks() -> list[Task]:
    """A day's worth of care tasks for one pet."""
    return [
        Task("Morning walk", 30, Priority.HIGH, TaskCategory.WALK),
        Task("Breakfast", 15, Priority.HIGH, TaskCategory.FEEDING),
        Task("Vet meds", 10, Priority.HIGH, TaskCategory.MEDS),
        Task("Training session", 45, Priority.MEDIUM, TaskCategory.ENRICHMENT),
        Task("Evening play", 120, Priority.MEDIUM, TaskCategory.ENRICHMENT),
        Task("Grooming", 60, Priority.LOW, TaskCategory.GROOMING),
        Task("Already fed lunch", 10, Priority.LOW, TaskCategory.FEEDING, is_completed=True),
    ]


def build_sample_constraints() -> DayConstraints:
    """A 9-5 owner: free before/after work, quiet hours in the evening."""
    return DayConstraints(
        available_minutes=240,          # 4 hours of care total
        day_start="06:00",
        day_end="24:00",
        blocked_windows=[
            ("09:00", "17:00"),          # work hours
            ("20:00", "24:00"),          # quiet hours
        ],
    )


def print_plan(pet_name: str, tasks: list[Task], constraints: DayConstraints) -> None:
    plan = Scheduler().build_plan(pet_name, tasks, constraints)

    print("=" * 60)
    print(f"  Daily plan for {plan.pet_name}")
    print(f"  Working hours: {constraints.day_start}-{constraints.day_end}"
          f"  |  Effort budget: {constraints.available_minutes} min")
    if constraints.blocked_windows:
        blocks = ", ".join(f"{s}-{e}" for s, e in constraints.blocked_windows)
        print(f"  Blocked: {blocks}")
    print("=" * 60)

    if plan.entries:
        for entry in plan.entries:
            print(
                f"  {entry.start_time}  {entry.task.title:<20} "
                f"({entry.task.duration_minutes:>3} min) "
                f"[{entry.task.priority.value}]"
            )
            print(f"          ↳ {entry.reason}")
    else:
        print("  (no tasks could be scheduled)")

    if plan.skipped:
        print("-" * 60)
        print("  Skipped (no time budget or no open slot):")
        for task in plan.skipped:
            print(f"    - {task.title} ({task.duration_minutes} min, {task.priority.value})")

    print("-" * 60)
    print(f"  {plan.summary()}")
    print("=" * 60)


def print_multi_day_plan(
    pet_name: str, tasks: list[Task], constraints: DayConstraints, max_days: int
) -> None:
    result = MultiDayPlanner().build_multi_day_plan(pet_name, tasks, constraints, max_days)

    print("#" * 60)
    print(f"  Multi-day plan for {result.pet_name}  (max_days={max_days})")
    print("#" * 60)
    for i, plan in enumerate(result.days, start=1):
        print(f"\n  --- Day {i} ---")
        if plan.entries:
            for entry in plan.entries:
                print(
                    f"    {entry.start_time}  {entry.task.title:<20} "
                    f"({entry.task.duration_minutes:>3} min) [{entry.task.priority.value}]"
                )
        else:
            print("    (nothing scheduled)")

    if result.unscheduled:
        print("\n  Never scheduled within the horizon:")
        for task in result.unscheduled:
            print(f"    - {task.title} ({task.duration_minutes} min, {task.priority.value})")

    print("-" * 60)
    print(f"  {result.summary()}")
    print("#" * 60)


def print_multi_pet_plan(pets: list[Pet], constraints: DayConstraints) -> None:
    plan = Scheduler().build_multi_pet_plan(pets, constraints)

    print("#" * 60)
    print(f"  Household plan for {', '.join(p.name for p in pets)}")
    print("#" * 60)
    for entry in plan.entries:
        end = _to_minutes(entry.start_time) + entry.task.duration_minutes
        print(
            f"  {entry.start_time}-{end // 60:02d}:{end % 60:02d}  "
            f"{entry.task.pet_name:<7} {entry.task.title:<16} "
            f"({entry.task.duration_minutes:>3} min) [{entry.task.priority.value}]"
        )
    if plan.skipped:
        print("  Skipped:")
        for task in plan.skipped:
            print(f"    - {task.pet_name}: {task.title} ({task.duration_minutes} min)")
    print("-" * 60)
    print(f"  {plan.summary()}  (single shared timeline -> no time conflicts)")
    print("#" * 60)


def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def main() -> None:
    pet_name = "Mochi"
    constraints = build_sample_constraints()

    # Single-day demo.
    print_plan(pet_name, build_sample_tasks(), constraints)

    # Multi-day demo: a tight 90-min budget forces the day's tasks to spill
    # across several days; a 3-day cap bounds the horizon.
    print()
    tight_budget = DayConstraints(
        available_minutes=90,
        day_start=constraints.day_start,
        day_end=constraints.day_end,
        blocked_windows=list(constraints.blocked_windows),
    )
    print_multi_day_plan(pet_name, build_sample_tasks(), tight_budget, max_days=3)

    # Multi-pet demo: two pets pooled onto one timeline -> no overlaps.
    print()
    rex = Pet("Rex", "dog", tasks=[
        Task("Walk", 30, Priority.HIGH, TaskCategory.WALK),
        Task("Meds", 15, Priority.HIGH, TaskCategory.MEDS),
    ])
    bella = Pet("Bella", "cat", tasks=[
        Task("Feed", 10, Priority.HIGH, TaskCategory.FEEDING),
        Task("Play", 40, Priority.LOW, TaskCategory.ENRICHMENT),
    ])
    household_constraints = DayConstraints(available_minutes=240, day_start="08:00", day_end="20:00")
    print_multi_pet_plan([rex, bella], household_constraints)

    # Recurrence demo: a DAILY walk recurs every day; a WEEKLY grooming is due
    # only on day 1 (index 0) and would return on day 8. A ONCE vet visit is a
    # one-off. Shown over an 8-day horizon.
    print()
    recurring_tasks = [
        Task("Daily walk", 30, Priority.HIGH, TaskCategory.WALK, recurrence=Recurrence.DAILY),
        Task("Weekly grooming", 45, Priority.MEDIUM, TaskCategory.GROOMING, recurrence=Recurrence.WEEKLY),
        Task("Vet visit (one-off)", 40, Priority.LOW, TaskCategory.MEDS, recurrence=Recurrence.ONCE),
    ]
    routine_constraints = DayConstraints(available_minutes=240, day_start="08:00", day_end="20:00")
    print_multi_day_plan("Mochi", recurring_tasks, routine_constraints, max_days=8)


if __name__ == "__main__":
    main()
