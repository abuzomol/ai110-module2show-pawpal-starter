import datetime as dt

import streamlit as st

from logic import (
    DayConstraints,
    Priority,
    Scheduler,
    Task,
    TaskCategory,
)

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption("A pet-care planning assistant. Add tasks, set your day's constraints, and generate a plan.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt(t: dt.time) -> str:
    """datetime.time -> 'HH:MM' string used by the scheduler."""
    return t.strftime("%H:%M")


# Session state
if "tasks" not in st.session_state:
    st.session_state.tasks = []          # list of dicts
if "blocked_windows" not in st.session_state:
    st.session_state.blocked_windows = []  # list of (start_str, end_str)


# ---------------------------------------------------------------------------
# Owner + pet
# ---------------------------------------------------------------------------
st.subheader("Owner & Pet")
col_o, col_p = st.columns(2)
with col_o:
    owner_name = st.text_input("Owner name", value="Jordan")
with col_p:
    pet_name = st.text_input("Pet name", value="Mochi")

col_s, col_b, col_a = st.columns(3)
with col_s:
    species = st.selectbox("Species", ["dog", "cat", "other"])
with col_b:
    breed = st.text_input("Breed", value="")
with col_a:
    age_years = st.number_input("Age (years)", min_value=0, max_value=40, value=3)

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
        help="Total minutes of care you can give today, independent of the working-hours window.",
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

st.divider()

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
st.subheader("Tasks")
t1, t2, t3 = st.columns(3)
with t1:
    task_title = st.text_input("Task title", value="Morning walk")
with t2:
    duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
with t3:
    priority = st.selectbox("Priority", [p.value for p in Priority], index=2)

t4, t5 = st.columns(2)
with t4:
    category = st.selectbox("Category", [c.value for c in TaskCategory])
with t5:
    st.write("")
    st.write("")
    is_completed = st.checkbox("Already completed")

if st.button("Add task"):
    st.session_state.tasks.append(
        {
            "title": task_title,
            "duration_minutes": int(duration),
            "priority": priority,
            "category": category,
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
# Generate schedule
# ---------------------------------------------------------------------------
st.subheader("Build Schedule")

if st.button("Generate schedule", type="primary"):
    if not st.session_state.tasks:
        st.warning("Add at least one task first.")
    else:
        # Convert UI dicts -> domain Task objects.
        tasks = [
            Task(
                title=t["title"],
                duration_minutes=t["duration_minutes"],
                priority=Priority(t["priority"]),
                category=TaskCategory(t["category"]),
                is_completed=t["is_completed"],
            )
            for t in st.session_state.tasks
        ]

        constraints = DayConstraints(
            available_minutes=int(available_minutes),
            day_start=_fmt(day_start),
            day_end=_fmt(day_end),
            blocked_windows=list(st.session_state.blocked_windows),
        )

        plan = Scheduler().build_plan(pet_name, tasks, constraints)

        st.success(plan.summary())

        if plan.entries:
            st.markdown(f"### 🗓️ Daily plan for {plan.pet_name}")
            st.table(
                [
                    {
                        "Time": e.start_time,
                        "Task": e.task.title,
                        "Duration": f"{e.task.duration_minutes} min",
                        "Priority": e.task.priority.value,
                        "Why": e.reason,
                    }
                    for e in plan.entries
                ]
            )
        else:
            st.info("No tasks could be scheduled with the current constraints.")

        if plan.skipped:
            st.markdown("### ⏭️ Skipped")
            st.caption("Didn't fit the effort budget or the available time windows.")
            for t in plan.skipped:
                st.write(f"- **{t.title}** ({t.duration_minutes} min, {t.priority.value})")
