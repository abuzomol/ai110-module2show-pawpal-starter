"""PawPal+ domain model and scheduling engine.

Structure mirrors diagrams/uml.mmd:
  - Value objects (enums): Priority, TaskCategory, Recurrence
  - Entities (data holders): Owner, OwnerPreferences, Pet, Task
  - Constraints: DayConstraints
  - Engine (strategy pattern): SchedulingStrategy, PriorityFirstStrategy, Scheduler
  - Output: Plan, PlanEntry

Data holders and the scheduling algorithm are implemented and unit-tested.
Scheduling respects two independent constraints:
  - an effort budget (`available_minutes`), and
  - a timeline (`day_start`/`day_end` working hours + `blocked_windows`).
Next step: connect Scheduler.build_plan() to app.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum


# ---------------------------------------------------------------------------
# Small time helpers ("HH:MM" <-> minutes since midnight)
# ---------------------------------------------------------------------------
def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _to_hhmm(total_minutes: int) -> str:
    total_minutes %= 24 * 60
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


# ---------------------------------------------------------------------------
# Value objects (closed sets)
# ---------------------------------------------------------------------------
class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCategory(Enum):
    WALK = "walk"
    FEEDING = "feeding"
    MEDS = "meds"
    ENRICHMENT = "enrichment"
    GROOMING = "grooming"
    OTHER = "other"


class Recurrence(Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


# ---------------------------------------------------------------------------
# Entities (plain data holders)
# ---------------------------------------------------------------------------
@dataclass
class OwnerPreferences:
    available_minutes: int = 240
    day_start: str = "08:00"
    day_end: str = "20:00"
    quiet_hours: list[str] = field(default_factory=list)


@dataclass
class Owner:
    name: str
    pets: list["Pet"] = field(default_factory=list)
    preferences: OwnerPreferences = field(default_factory=OwnerPreferences)

    def add_pet(self, pet: "Pet") -> None:
        self.pets.append(pet)


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    category: TaskCategory = TaskCategory.OTHER
    recurrence: Recurrence = Recurrence.ONCE
    is_completed: bool = False
    pet_name: str = ""  # set when pooling several pets into one plan

    def priority_weight(self) -> int:
        """Numeric weight for sorting (higher = more important)."""
        return {Priority.LOW: 1, Priority.MEDIUM: 2, Priority.HIGH: 3}[self.priority]


@dataclass
class Pet:
    name: str
    species: str
    breed: str = ""
    age_years: int = 0
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)


# ---------------------------------------------------------------------------
# Constraints passed into scheduling
# ---------------------------------------------------------------------------
@dataclass
class DayConstraints:
    """Scheduling constraints for a single day.

    Two independent limits must both be satisfied for a task to be scheduled:
      - `available_minutes`: total effort budget (sum of durations).
      - the timeline `day_start`..`day_end` (working hours), minus any
        `blocked_windows` — each an ("HH:MM", "HH:MM") start/end pair, e.g.
        [("12:00", "13:00")] to keep a lunch hour free.
    """

    available_minutes: int = 240
    day_start: str = "08:00"
    day_end: str = "20:00"
    blocked_windows: list[tuple[str, str]] = field(default_factory=list)

    def fits(self, minutes_used: int, task: Task) -> bool:
        """Return True if `task` still fits within the effort budget."""
        return minutes_used + task.duration_minutes <= self.available_minutes

    def next_free_start(self, earliest: int, duration: int) -> int | None:
        """Earliest start (minutes since midnight) >= `earliest` where a task of
        `duration` fits inside working hours without overlapping a blocked
        window. Returns None if it cannot fit before `day_end`.
        """
        day_end = _to_minutes(self.day_end)
        windows = sorted(
            (_to_minutes(s), _to_minutes(e)) for s, e in self.blocked_windows
        )
        start = max(earliest, _to_minutes(self.day_start))
        while start + duration <= day_end:
            # Jump past the first blocked window this task would overlap.
            blocker_end = None
            for w_start, w_end in windows:
                if start < w_end and w_start < start + duration:  # overlap
                    blocker_end = w_end
                    break
            if blocker_end is None:
                return start
            start = blocker_end  # retry after the window that blocked us
        return None


# ---------------------------------------------------------------------------
# Scheduling engine (Strategy pattern)
# ---------------------------------------------------------------------------
class SchedulingStrategy:
    """Interface: defines how the candidate tasks are ordered before selection."""

    def order(self, tasks: list[Task]) -> list[Task]:
        raise NotImplementedError


class PriorityFirstStrategy(SchedulingStrategy):
    def order(self, tasks: list[Task]) -> list[Task]:
        # Highest priority first; tie-break by shorter duration so more tasks
        # fit within the same time budget. Stable sort keeps input order for
        # full ties, which makes the result deterministic and testable.
        return sorted(
            tasks,
            key=lambda t: (-t.priority_weight(), t.duration_minutes),
        )


@dataclass
class Scheduler:
    strategy: SchedulingStrategy = field(default_factory=PriorityFirstStrategy)

    def build_plan(self, pet_name: str, tasks: list[Task], constraints: DayConstraints) -> "Plan":
        """Produce a daily Plan from candidate tasks + constraints.

        Flow:
          1. drop already-completed tasks (nothing to schedule)
          2. order the rest via the strategy
          3. walk the ordered tasks, placing each on the timeline: it is
             scheduled only if it fits BOTH the effort budget and an open slot
             within working hours; otherwise it is skipped.

        Placement is greedy and forward-only: `clock` never rewinds, so a task
        that lands after a blocked window does not leave earlier gaps to be
        backfilled by later tasks. A task that cannot be placed is skipped, but
        later (shorter) tasks are still tried.
        """
        candidates = [t for t in tasks if not t.is_completed]
        ordered = self.strategy.order(candidates)

        entries: list[PlanEntry] = []
        skipped: list[Task] = []
        minutes_used = 0
        clock = _to_minutes(constraints.day_start)
        for task in ordered:
            if not constraints.fits(minutes_used, task):
                skipped.append(task)  # over the effort budget
                continue
            start = constraints.next_free_start(clock, task.duration_minutes)
            if start is None:
                skipped.append(task)  # no open slot in working hours
                continue
            entry = PlanEntry(task=task, start_time=_to_hhmm(start), reason="")
            entry.reason = self._explain(entry)
            entries.append(entry)
            clock = start + task.duration_minutes
            minutes_used += task.duration_minutes

        return Plan(pet_name=pet_name, entries=entries, skipped=skipped)

    def build_multi_pet_plan(
        self,
        pets: list["Pet"],
        constraints: DayConstraints,
        household_name: str = "Household",
    ) -> "Plan":
        """Schedule several pets' tasks on ONE shared timeline.

        All pets' tasks are pooled into a single build_plan call, so they are
        placed sequentially on one owner timeline. Because a single plan never
        overlaps its own entries, this guarantees no two tasks (same pet or
        different pets) are scheduled at the same time. Ordering is by priority
        across the whole household, and `available_minutes` is the owner's total
        budget for everyone combined.

        Each pooled task is tagged with its pet's name (via `Task.pet_name`) so
        the resulting entries and skipped list say which pet each task is for.
        """
        pooled = [
            replace(task, pet_name=pet.name)
            for pet in pets
            for task in pet.tasks
        ]
        return self.build_plan(household_name, pooled, constraints)

    def _explain(self, entry: "PlanEntry") -> str:
        """Human-readable reason this task landed where it did."""
        task = entry.task
        who = f"{task.pet_name}: " if task.pet_name else ""
        return (
            f"{who}{task.priority.value} priority, {task.duration_minutes} min "
            f"— scheduled at {entry.start_time}"
        )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
@dataclass
class PlanEntry:
    task: Task
    start_time: str
    reason: str = ""


@dataclass
class Plan:
    pet_name: str
    entries: list[PlanEntry] = field(default_factory=list)
    skipped: list[Task] = field(default_factory=list)

    def total_minutes(self) -> int:
        return sum(entry.task.duration_minutes for entry in self.entries)

    def summary(self) -> str:
        """One-line overview of the plan (used by the UI / explanations)."""
        line = (
            f"{len(self.entries)} task(s) scheduled "
            f"({self.total_minutes()} min)"
        )
        if self.skipped:
            line += f", {len(self.skipped)} skipped for time"
        return line


# ---------------------------------------------------------------------------
# Multi-day planning (carry-over + recurrence, with a max_days cap)
# ---------------------------------------------------------------------------
def _is_due(task: Task, day_index: int) -> bool:
    """Whether a recurring task should be (re-)scheduled on `day_index` (0-based).

    DAILY  -> every day.
    WEEKLY -> day 0, 7, 14, ... of the planning horizon (day-index based).
    ONCE tasks are handled via the carry-over backlog, not this function.
    """
    if task.recurrence is Recurrence.DAILY:
        return True
    if task.recurrence is Recurrence.WEEKLY:
        return day_index % 7 == 0
    return False


def _no_recurrence_due_in(recurring: list[Task], from_day: int, max_days: int) -> bool:
    """True if no recurring task is due on any day in [from_day, max_days)."""
    return not any(
        _is_due(task, day)
        for day in range(from_day, max_days)
        for task in recurring
    )


@dataclass
class MultiDayPlan:
    """Result of planning across several days.

    `days[i]` is the single-day Plan for day i+1. `unscheduled` holds tasks that
    never fit within the horizon — either the backlog outlived `max_days`, or a
    task can never fit the daily constraints at all (e.g. longer than the budget).
    """

    pet_name: str
    days: list[Plan] = field(default_factory=list)
    unscheduled: list[Task] = field(default_factory=list)

    def summary(self) -> str:
        scheduled = sum(len(p.entries) for p in self.days)
        line = f"{scheduled} task(s) scheduled across {len(self.days)} day(s)"
        if self.unscheduled:
            line += f", {len(self.unscheduled)} left unscheduled"
        return line


@dataclass
class MultiDayPlanner:
    """Runs the single-day Scheduler across multiple days.

    Two kinds of task are handled differently:
      - ONCE tasks form a carry-over backlog: if not placed, they roll into the
        next day and keep trying until scheduled or the horizon ends.
      - DAILY/WEEKLY tasks are re-injected fresh on each day they are due. A
        recurring instance that does not fit simply LAPSES (it is not carried
        over and does not pile up) — it reappears on its next due day.

    Termination — the loop stops at the first of:
      1. nothing left to do — the carry-over backlog is empty AND no recurring
         task is due on any remaining day, or
      2. a day schedules nothing and no future day could help (identical daily
         constraints, and no recurrence is due later), or
      3. `max_days` is reached (the safety cap that bounds the horizon and
         prevents an ever-growing backlog from carrying over forever).

    Only leftover ONCE tasks end up in `unscheduled`; lapsed recurring instances
    do not (by design they are expected to recur, not to accumulate).
    """

    scheduler: Scheduler = field(default_factory=Scheduler)

    def build_multi_day_plan(
        self,
        pet_name: str,
        tasks: list[Task],
        constraints: DayConstraints,
        max_days: int = 7,
    ) -> MultiDayPlan:
        if max_days < 1:
            raise ValueError("max_days must be at least 1")

        # Drop completed tasks up front; split recurring from one-off.
        active = [t for t in tasks if not t.is_completed]
        recurring = [t for t in active if t.recurrence is not Recurrence.ONCE]
        carryover = [t for t in active if t.recurrence is Recurrence.ONCE]
        days: list[Plan] = []

        for day_index in range(max_days):
            due_today = [t for t in recurring if _is_due(t, day_index)]
            todays_tasks = due_today + carryover

            if not todays_tasks:
                # Nothing due and no backlog. Stop only if the future is empty
                # too; otherwise skip ahead to the next recurring due day.
                if _no_recurrence_due_in(recurring, day_index + 1, max_days):
                    break
                continue

            plan = self.scheduler.build_plan(pet_name, todays_tasks, constraints)

            if not plan.entries:
                # Nothing fit today. Recurring instances lapse; the backlog is
                # unchanged. Stop only if no future day could place the backlog.
                if _no_recurrence_due_in(recurring, day_index + 1, max_days):
                    break
                continue

            days.append(plan)
            # Carry over only the ONCE tasks that were skipped; recurring lapse.
            carryover = [t for t in plan.skipped if t.recurrence is Recurrence.ONCE]

        # Leftover one-off tasks never placed within the horizon.
        return MultiDayPlan(pet_name=pet_name, days=days, unscheduled=carryover)
