# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agent Workflow (SF7)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**
I asked Claude code the following Prompts: 
+ Read the scenario and generate for me uml diagrams for classes that can be stored in diagrams/uml.mmd file. Show me your logic as a senior software engineer.

Claude did pretty well in organizing the following classes: Owner, OwnerPreferences, Pet, and Task. These containers are for data and the logic is good. Other helpful classes and enumeration type of classes are also made which for now I have no issue with them.

+ Generate the stubs files as suggested in README. Preferably, have them all in logic.py file. Next I will connect this file with app.py to be run by streamlit later.

Claude generated the code stub without deep logic and let me inspect the TODO tasks. 

+ For now go ahead and implement the scheduling logic and produce the tests in a folder called tests, that can be run by pytest as shown in README.

Claude presented 14 cases testing different varieties of scheduling with low, high and medium, plus checking for the stability of sorting as well checking if the tasks are completed. 

One thing I noticed is that Claude made a wrong logic first before making the test I asked for. After doing the test, the logic fell apart in the function Schedular.

+ What is the expected output of test_start_times_are_sequential_from_day_start(). Can you print out the expected value after schedular?

I made this test to inspect in more details the output format of the schedular. It turns out the timer uses minutes, so that's why 8 hours were converted into minutes first before adding the remainder.

+ Does the logic allow for a user to specify the closed hours i.e. working hours say from 9-5 in a day?

The answer is No. The logic is done by just allowing start time. In order to implement locked hours we need start and end logic to be added.

+ Before that what are the TODO lists?

I was ahead in my questioning and Claude was going to fix that as well. 

+ Please go ahead and finish the remaining task. 

Claude added a blocked hours logic to the code where start and ends are pairs of input. The blocked hours are made into list of start and ends. 

+ logic seems legit, but I wanted to double check the tests, so asked for this: 

```Now add a test where the day starts at 6:00, free hours from 6:00 to 9:00am, followed by work hours that are blocked from 9:00 to 17:00am, and then free hours again from 17:00 to 20:00pm. Quiet hours from 20:00 till end of the day i.e. 20:00-00:00 next day.```.

The output just as I predicted, wonderful use of AI.

+ Now connect the code with app.py.

+ generate a main.py for simple run of pawpal_system.py logic and test the output in main.py by printing the output to the terminal.

+ Is there any feature for mark complete to a task? Also is there a logic for postponing a task that couldn't be scheduled in day 1 to enter day 2?

AI suggested to build multi-day planner on top of a single day planner where skipped tasks are placed into other days. A cap is suggested to drop runaway tasks.

+ Yes, implement multi-day planner with the one with max_days cap.

The code works fine, and both test cases and main.py are implemented. No problem except the conflict of scheduling same time for different pets.

+ Does the code allows if two tasks for the same pet (or different pets) are scheduled at the same time? Can such conflict occurs?

Answer: No for single pet, Yes for different pets. Claude suggested to remove conflict to pool all tasks into a single build_plan.

+ Yes, do the merge into one timeline i.e. pool all pets tasks into a single build_plan.

+ Have you checked for recurrence tasks?

Claude asked for a good question, what should happen for a recurring task that couldn't be scheduled. The answer was to let is disappear and appears fresh next time it occurs.
**What did the agent do?**

The answers are shown above. 

**What did you have to verify or fix manually?**

I verified few things manually like one or two test cases, and also made a run to app.py.





---

## Prompt Comparison (SF11)

> Compare two different prompts (or two different models) on the same task.

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | | |
| **Prompt** | | |
| **Response summary** | | |
| **What was useful** | | |
| **Problems noticed** | | |
| **Decision** | | |

**Which approach did you use in your final implementation and why?**

<!-- Your conclusion -->
