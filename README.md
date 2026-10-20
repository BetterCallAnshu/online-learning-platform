# Online Learning Platform

A database management system for an online learning platform. It handles
courses, enrollments, progress tracking and assessments, with content
management tools for administrators and instructors.

Built with **Python 3** and **SQLite** using only the standard library: no
installation, no external packages, no server to configure.

## Features

### Student portal
- Browse and search the published course catalog by category
- Enroll in courses and view a personalized "My courses" dashboard
- Follow the curriculum (video, reading and exercise lessons)
- Mark lessons complete/incomplete; enrollment completes automatically at 100%
- Take multiple-choice quizzes and get instant auto-graded scores
- Submit assignments and resubmit until they are graded
- Review quiz answers, grades, instructor feedback and weighted course averages
- Register an account and update the profile

### Instructor portal
- View owned courses, learners, lessons and status
- Manage content: add/edit/delete modules and lessons
- Create quizzes and assignments with weights and due dates
- Author quiz questions with four options and a correct answer
- Grade pending assignment submissions with feedback
- View the course roster, per-learner progress and assessment statistics

### Admin portal
- Platform dashboard with live counts and gross revenue
- Create and edit courses, publish/archive them and assign instructors
- Add instructors and students, edit student profiles
- Manage content and assessments for any course
- Seven reports with CSV export:
  - Enrollment summary
  - Learner progress
  - Assessment performance
  - Top students
  - Instructor workload
  - Revenue by category
  - Pending grading queue

## Quick start

```powershell
cd D:\OnlineLearningPlatform
python main.py
```

The first run creates `learning_platform.db`, loads the demo dataset and opens
the login menu. To wipe everything and rebuild the demo data:

```powershell
python main.py --reset
```

Python 3.10+ is recommended (developed and tested on Python 3.14).

## Demo accounts

| Role       | Email               | Password        |
|------------|---------------------|-----------------|
| Admin      | admin@learnhub.io   | admin123        |
| Instructor | maya@learnhub.io    | instructor123   |
| Instructor | alan@learnhub.io    | instructor123   |
| Instructor | priya@learnhub.io   | instructor123   |
| Student    | sam@student.io      | student123      |
| Student    | lena@student.io     | student123      |
| Student    | tom@student.io      | student123      |
| Student    | rina@student.io     | student123      |
| Student    | diego@student.io    | student123      |
| Student    | ava@student.io      | student123      |

Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes, never as plain text.

### Suggested tour
1. Log in as **admin@learnhub.io** and open *Dashboard*, then *Manage courses*
   and *Reports and exports*.
2. Log in as **maya@learnhub.io**, open *Grade submissions* - Ava's
   "Data Cleaning Project" is waiting - then *Course analytics*.
3. Log in as **diego@student.io**, open *Modern Web Development*, mark a lesson
   complete, view assessments, and check *My grades and transcript*.
4. Log in as **admin@learnhub.io** and publish *Machine Learning Foundations*
   (currently a draft), then enroll in it as a student.

## Project structure

```
OnlineLearningPlatform/
├── main.py           entry point and CLI arguments (--reset)
├── cli.py            menus, prompts, tables, CSV export
├── services.py       business logic and validation (no UI code)
├── reports.py        read-only SQL reports
├── db.py             connection handling and schema loading
├── schema.sql        tables, constraints, indexes and views
├── seed.py           realistic demo dataset
├── security.py       PBKDF2 password hashing
├── tests/
│   └── test_flows.py end-to-end service tests
├── exports/          generated CSV reports (created on demand)
└── learning_platform.db
```

The CLI only talks to `services.py`; the tests exercise the same service layer,
so both use identical business rules.

## Database design

### Entity relationships

```
instructors 1 --- * courses 1 --- * modules 1 --- * lessons
                        |                              |
                        | 1                            | 1
                        *                              *
                   assessments                       lesson_progress
                     |     |                              |
                     | 1   | 1                            | *
                     *     *                              |
                questions  submissions * --- 1 enrollments * --- 1 students
                     |          |
                     | 1        | *
                     *          *
              submission_answers
```

- A **student** enrolls in many **courses** through **enrollments**.
- Each **enrollment** owns its **lesson_progress** rows, so progress is
  per-learner and lessons can be reordered without corrupting completion.
- A **course** contains ordered **modules** and **lessons** (content management).
- A **course** has **assessments** (quizzes/assignments); quizzes own
  **questions**, and every attempt is a **submission**.
- **submission_answers** stores each selected option and whether it was correct,
  which powers quiz review and audit trails.

### Tables

| Table              | Purpose                                                        |
|--------------------|----------------------------------------------------------------|
| `admins`           | Platform administrators                                        |
| `instructors`      | Course authors, expertise and credentials                      |
| `students`         | Learner accounts                                               |
| `courses`          | Catalog entries with level, price and Draft/Published/Archived |
| `modules`          | Ordered sections inside a course                               |
| `lessons`          | Video/reading/exercise content inside a module                 |
| `enrollments`      | Student-course link with Active/Completed/Dropped status       |
| `lesson_progress`  | Completed lessons per enrollment                               |
| `assessments`      | Quizzes and assignments with weight, due date and max score    |
| `questions`        | Quiz questions with four options, correct answer and points    |
| `submissions`      | One attempt per student per assessment, with score/feedback    |
| `submission_answers` | Per-question answers and correctness                        |

### Views

- `v_course_stats` - course, instructor, learner count, lesson/assessment counts
- `v_student_progress` - per-enrollment completion numerator and denominator
- `v_assessment_results` - submissions joined to assessment and student data

### Integrity rules enforced by the database
- Foreign keys are enabled on every connection (`PRAGMA foreign_keys = ON`).
- `UNIQUE (student_id, course_id)` prevents duplicate enrollments.
- `UNIQUE (assessment_id, student_id)` prevents duplicate quiz attempts.
- `CHECK` constraints restrict levels, statuses, lesson types, answer options
  and non-negative prices/scores.
- `ON DELETE CASCADE` cleans up modules, lessons, progress and submissions;
  instructors with courses cannot be deleted (`ON DELETE RESTRICT`).

Business rules in `services.py` complement these constraints: only published
courses can be enrolled in, only enrolled students can submit, assignments
cannot be regraded by students, quiz answers are auto-scored by points, and
enrollment status flips to `Completed` when every lesson is done.

## Reports and exports

Open *Reports and exports* as an admin. Each report renders as an aligned table;
you can export the current result to `exports/<report>-<timestamp>.csv`
(UTF-8 with BOM, so Excel opens it correctly).

## Tests

```powershell
python -m unittest discover -s tests -v
```

The suite covers seeding, authentication across all three roles, enrollment and
completion, quiz auto-grading, assignment grading and weighted averages,
authorization failures, report output and seed idempotency. Each run uses an
isolated temporary database.

## Security and SQL practices
- Parameterized queries throughout (`?` placeholders) to prevent SQL injection.
- Salted PBKDF2 password hashes with constant-time comparison.
- Role-based menus and server-side permission checks in the service layer.
- Aggregates, multi-table joins, subqueries, `CASE`, `GROUP BY`, `HAVING`
  semantics via filtered aggregates, views, indexes and `EXPLAIN`-friendly
  schema design.

## Notes and limitations
- This is a single-user CLI application; SQLite serializes writes.
- Lesson content is represented by URLs/metadata rather than file hosting.
- Payment is recorded as a course price at enrollment time; there is no payment
  gateway integration.
- Deleting a course is intentionally not exposed in the UI; archive it instead.
