import datetime as dt

import streamlit as st

from pawpal_system import (
    DayConstraints,
    MultiDayPlanner,
    Priority,
    Recurrence,
    Task,
    TaskCategory,
)

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption(
    "A pet-care planning assistant. Add pets and tasks, set the day's constraints, "
    "and generate a conflict-free plan across one or more days."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt(t: dt.time) -> str:
    """datetime.time -> 'HH:MM' string used by the scheduler."""
    return t.strftime("%H:%M")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "pets" not in st.session_state:
    st.session_state.pets = [{"name": "Mochi", "species": "cat"}]
if "tasks" not in st.session_state:
    st.session_state.tasks = []            # list of dicts, each tagged with a pet
if "blocked_windows" not in st.session_state:
    st.session_state.blocked_windows = []  # list of (start_str, end_str)


# ---------------------------------------------------------------------------
# Owner + pets
# ---------------------------------------------------------------------------
st.subheader("Owner & Pets")
owner_name = st.text_input("Owner name", value="Jordan")

pc1, pc2, pc3 = st.columns([2, 2, 1])
with pc1:
    new_pet_name = st.text_input("Pet name", value="", key="new_pet_name")
with pc2:
    new_pet_species = st.selectbox("Species", ["dog", "cat", "other"], key="new_pet_species")
with pc3:
    st.write("")
    st.write("")
    if st.button("Add pet"):
        name = new_pet_name.strip()
        if not name:
            st.warning("Enter a pet name.")
        elif any(p["name"] == name for p in st.session_state.pets):
            st.warning(f"A pet named {name} already exists.")
        else:
            st.session_state.pets.append({"name": name, "species": new_pet_species})

if st.session_state.pets:
    for i, pet in enumerate(st.session_state.pets):
        row, btn = st.columns([4, 1])
        row.write(f"🐾 **{pet['name']}** ({pet['species']})")
        if btn.button("Remove", key=f"rm_pet_{i}"):
            removed = st.session_state.pets.pop(i)
            # Drop that pet's tasks too, so no orphaned tasks remain.
            st.session_state.tasks = [
                t for t in st.session_state.tasks if t["pet"] != removed["name"]
            ]
            st.rerun()
else:
    st.info("Add at least one pet to start planning.")

st.divider()

# ---------------------------------------------------------------------------
# Day constraints
# ---------------------------------------------------------------------------
st.subheader("Day Constraints")
c1, c2, c3 = st.columns(3)
with c1:
    day_start = st.time_input("Day start", value=dt.time(8, 0))
with c2:
    day_end = st.time_input("Day end", value=dt.time(20, 0))
with c3:
    available_minutes = st.number_input(
        "Effort budget (min)", min_value=0, max_value=1440, value=240,
        help="Total minutes of care per day, shared across all pets. Independent "
             "of the working-hours window.",
    )

st.markdown("**Blocked windows** — times to keep free (e.g. work hours, quiet hours).")
b1, b2, b3 = st.columns([2, 2, 1])
with b1:
    block_start = st.time_input("Block start", value=dt.time(9, 0), key="block_start")
with b2:
    block_end = st.time_input("Block end", value=dt.time(17, 0), key="block_end")
with b3:
    st.write("")
    st.write("")
    if st.button("Add block"):
        if _fmt(block_end) > _fmt(block_start):
            st.session_state.blocked_windows.append((_fmt(block_start), _fmt(block_end)))
        else:
            st.warning("Block end must be after block start.")

if st.session_state.blocked_windows:
    for i, (bs, be) in enumerate(st.session_state.blocked_windows):
        row, btn = st.columns([4, 1])
        row.write(f"⛔ {bs} – {be}")
        if btn.button("Remove", key=f"rm_block_{i}"):
            st.session_state.blocked_windows.pop(i)
            st.rerun()
else:
    st.caption("No blocked windows. The whole day-start→day-end window is available.")

st.markdown("**Planning horizon**")
max_days = st.number_input(
    "Days to plan", min_value=1, max_value=30, value=1,
    help="1 = today only. More than 1 enables carry-over of unfinished one-off "
         "tasks and recurring (daily/weekly) tasks across days.",
)

st.divider()

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
st.subheader("Tasks")

pet_names = [p["name"] for p in st.session_state.pets]
if not pet_names:
    st.info("Add a pet above before adding tasks.")
else:
    t1, t2, t3 = st.columns(3)
    with t1:
        task_pet = st.selectbox("Pet", pet_names)
    with t2:
        task_title = st.text_input("Task title", value="Morning walk")
    with t3:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)

    t4, t5, t6 = st.columns(3)
    with t4:
        priority = st.selectbox("Priority", [p.value for p in Priority], index=2)
    with t5:
        category = st.selectbox("Category", [c.value for c in TaskCategory])
    with t6:
        recurrence = st.selectbox(
            "Recurrence", [r.value for r in Recurrence],
            help="daily = every day; weekly = every 7th day of the horizon.",
        )

    is_completed = st.checkbox("Already completed")

    if st.button("Add task"):
        st.session_state.tasks.append(
            {
                "pet": task_pet,
                "title": task_title,
                "duration_minutes": int(duration),
                "priority": priority,
                "category": category,
                "recurrence": recurrence,
                "is_completed": is_completed,
            }
        )

if st.session_state.tasks:
    st.write("Current tasks:")
    st.table(st.session_state.tasks)
    if st.button("Clear all tasks"):
        st.session_state.tasks = []
        st.rerun()
else:
    st.info("No tasks yet. Add one above.")

st.divider()

# ---------------------------------------------------------------------------
# Generate plan
# ---------------------------------------------------------------------------
st.subheader("Build Plan")

if st.button("Generate plan", type="primary"):
    if not st.session_state.tasks:
        st.warning("Add at least one task first.")
    else:
        # Pool every pet's tasks into one tagged list. Feeding this to the
        # multi-day planner gives multi-pet + multi-day + recurrence at once,
        # all on a single shared timeline (so no two tasks ever overlap).
        tasks = [
            Task(
                title=t["title"],
                duration_minutes=t["duration_minutes"],
                priority=Priority(t["priority"]),
                category=TaskCategory(t["category"]),
                recurrence=Recurrence(t["recurrence"]),
                is_completed=t["is_completed"],
                pet_name=t["pet"],
            )
            for t in st.session_state.tasks
        ]

        constraints = DayConstraints(
            available_minutes=int(available_minutes),
            day_start=_fmt(day_start),
            day_end=_fmt(day_end),
            blocked_windows=list(st.session_state.blocked_windows),
        )

        household = owner_name.strip() or "Household"
        result = MultiDayPlanner().build_multi_day_plan(
            household, tasks, constraints, max_days=int(max_days)
        )

        st.success(result.summary())

        if not result.days:
            st.info("No tasks could be scheduled with the current constraints.")

        multi_day = int(max_days) > 1
        for i, plan in enumerate(result.days, start=1):
            st.markdown(f"### 🗓️ Day {i}" if multi_day else "### 🗓️ Daily plan")
            st.table(
                [
                    {
                        "Time": e.start_time,
                        "Pet": e.task.pet_name,
                        "Task": e.task.title,
                        "Duration": f"{e.task.duration_minutes} min",
                        "Priority": e.task.priority.value,
                        "Repeats": e.task.recurrence.value,
                        "Why": e.reason,
                    }
                    for e in plan.entries
                ]
            )

        if result.unscheduled:
            st.markdown("### ⏭️ Not scheduled")
            st.caption(
                "One-off tasks that never fit the effort budget or the available "
                "time windows within the horizon."
            )
            for t in result.unscheduled:
                who = f"{t.pet_name}: " if t.pet_name else ""
                st.write(f"- **{who}{t.title}** ({t.duration_minutes} min, {t.priority.value})")
