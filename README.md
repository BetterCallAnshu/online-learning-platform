# Online Learning Platform

A complete **Database Management System** for an online learning platform, built
with **Python 3** and **SQLite** using the standard library only — no
dependencies, no server, no setup.

The system manages courses, enrollments, progress tracking and assessments, and
includes full **content management** tools for administrators and instructors.

> Full technical documentation (every concept used, architecture diagrams,
> request lifecycles and key algorithms) is in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Table of contents

- [Highlights](#highlights)
- [Demo accounts](#demo-accounts)
- [Quick start](#quick-start)
- [Sample screens](#sample-screens)
- [Feature tour](#feature-tour)
- [Project structure](#project-structure)
- [Architecture](#architecture)
- [Database design](#database-design)
- [Reports and CSV export](#reports-and-csv-export)
- [Testing](#testing)
- [Security](#security)
- [Concepts used](#concepts-used)
- [Roadmap](#roadmap)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Highlights

- **Three role-based portals** — student, instructor and administrator, each
  with its own menu and permissions.
- **Course content management** — ordered modules and lessons (video, reading,
  exercise) that instructors or admins can create, edit and delete.
- **Progress tracking** — per-lesson completion, live percentage, and
  enrollments that flip to `Completed` automatically at 100%.
- **Assessments** — auto-graded multiple-choice quizzes (instant score and
  answer review) plus written assignments with manual instructor grading.
- **Weighted gradebook** — assessments carry a weight, so a course average
  reflects what the instructor intended.
- **Seven analytical reports** with one-click **CSV export** for Excel.
- **Production-style data integrity** — foreign keys, unique constraints,
  `CHECK` domains, indexes and views, all enforced by SQLite itself.
- **Secure accounts** — salted PBKDF2-HMAC-SHA256 password hashing and
  constant-time verification; every SQL statement is parameterized.
- **Seeded demo dataset** — realistic courses, learners, submissions and
  grades so every screen has meaningful data on first run.

---

## Demo accounts

| Role       | Email             | Password      |
|------------|-------------------|---------------|
| Admin      | admin@learnhub.io | admin123      |
| Instructor | maya@learnhub.io  | instructor123 |
| Instructor | alan@learnhub.io  | instructor123 |
| Instructor | priya@learnhub.io | instructor123 |
| Student    | sam@student.io    | student123    |
| Student    | lena@student.io   | student123    |
| Student    | tom@student.io    | student123    |
| Student    | rina@student.io   | student123    |
| Student    | diego@student.io  | student123    |
| Student    | ava@student.io    | student123    |

New students can also self-register from the login screen.

---

## Quick start

**Requirements:** Python 3.10 or newer (developed on 3.14). SQLite ships with
Python, so there is nothing else to install.

```powershell
git clone git@github.com:BetterCallAnshu/online-learning-platform.git
cd online-learning-platform
python main.py
```

The first run creates `learning_platform.db`, loads the demo dataset and opens
the login menu.

Useful commands:

```powershell
python main.py                    # start the application
python main.py --reset            # rebuild the database and demo data
python -m unittest discover -s tests -v   # run the test suite
```

---

## Sample screens

Course catalog (student view):

```
Course                        Category         Level         Price      Learners
----------------------------  ---------------  ------------  ---------  --------
Python for Data Analysis      Data Science     Beginner      $49.00     4
Modern Web Development        Web Development  Intermediate  $79.00     3
SQL and Database Design       Databases        Beginner      $39.00     3
```

Assessment workspace (instructor view):

```
ID  Assessment             Type        Max  Weight  Due         Questions  Submissions
--  ---------------------  ----------  ---  ------  ----------  ---------  -----------
4   Landing Page Build     assignment  100  2       2026-12-05  0          2
3   HTML and CSS Basics    quiz        100  1       2026-11-20  4          3
```

Auto-graded quiz result (student view):

```
Submitted. Score: 100 / 100 (4/4 correct).

Question                                  Your answer  Correct  Result
----------------------------------------  -----------  -------  -------
Which tag creates the largest heading?    B            B        correct
Which CSS property sets the text colour?  C            C        correct
What is the default flex-direction?       A            A        correct
What does document.querySelector return?  A            A        correct
```

Analytical report (admin view):

```
Course                        Category         Status     Enrollments  Completed  Revenue
----------------------------  ---------------  ---------  -----------  ---------  -------
Python for Data Analysis      Data Science     Published  4            1          196
Modern Web Development        Web Development  Published  3            0          237
SQL and Database Design       Databases        Published  3            0          117
Machine Learning Foundations  Data Science     Draft      0            0          0
```

---

## Feature tour

### Student portal
- Browse and search the published catalog by keyword or category
- Enroll in courses and track progress on a personal dashboard
- Work through the curriculum and mark lessons complete or incomplete
- Take quizzes with instant auto-grading and a full answer review
- Submit written assignments, resubmit until graded
- Read scores, instructor feedback and weighted course averages
- Register an account and update the profile

### Instructor portal
- Manage owned courses: modules, lessons, types, durations and links
- Create quizzes and assignments with weights, due dates and instructions
- Author multiple-choice questions with the correct answer and point values
- Grade pending submissions with feedback
- Review the class roster, per-learner progress and assessment statistics

### Admin portal
- Dashboard with live counts, enrollments and gross revenue
- Create, edit, publish or archive any course and assign its instructor
- Add instructors and students, edit student profiles
- Manage content and assessments for every course
- Run seven reports and export any of them to CSV

### Suggested walkthrough
1. Sign in as `admin@learnhub.io` and open the **Dashboard** and **Reports**.
2. Sign in as `maya@learnhub.io`, open **Grade submissions** and grade Ava's
   pending "Data Cleaning Project".
3. Sign in as `diego@student.io`, open *Modern Web Development*, complete a
   lesson and check the updated progress.
4. Back as admin, publish the draft course *Machine Learning Foundations* and
   enroll in it as a student.

---

## Project structure

```
online-learning-platform/
├── main.py             entry point and CLI flags (--reset)
├── cli.py              menus, prompts, table rendering, CSV export
├── services.py         business logic, validation and permissions
├── reports.py          read-only analytical SQL
├── db.py               connection factory, schema loading, reset
├── schema.sql          12 tables, 8 indexes, 3 views
├── seed.py             realistic demo dataset (built through services)
├── security.py         PBKDF2 password hashing
├── tests/
│   └── test_flows.py   end-to-end service tests
├── ARCHITECTURE.md     concepts, architecture and working of every part
├── README.md           this file
└── learning_platform.db  SQLite database (created on first run)
```

The CLI never talks to the database directly. It calls `services.py`, which owns
the business rules and the SQL. That is why the automated tests exercise exactly
the same code path as the application.

---

## Architecture

```
+=====================================================================+
|  PRESENTATION   cli.py      role-based portals, tables, CSV export   |
+---------------------------|-----------------------------------------+
                            |  validated calls, ServiceError results
+---------------------------v-----------------------------------------+
|  BUSINESS LOGIC  services.py (write)  /  reports.py (read)           |
|  rules, permissions, auto-grading, completion state machine         |
+---------------------------|-----------------------------------------+
                            |  parameterized SQL, one commit per action
+---------------------------v-----------------------------------------+
|  PERSISTENCE  db.py + schema.sql   connection, FK enforcement, DDL   |
+---------------------------+-----------------------------------------+
                            v
                  learning_platform.db (SQLite)
```

- **Presentation layer** — input handling and presentation only; no SQL, no
  business rules.
- **Business logic layer** — every validation, permission check and state
  transition, plus all write SQL. Failures raise a `ServiceError` with a
  readable message.
- **Data layer** — connection management, foreign-key enforcement and the
  declarative schema.
- **Reporting layer** — pure read-only queries, each returning headers and rows
  for table rendering and CSV export.

Detailed flows (login, enrollment, quiz grading, course completion) are
documented in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Database design

```
instructors 1───* courses 1───* modules 1───* lessons
                    |                              |
                    | 1                            | 1
                    *                              *
               assessments                    lesson_progress
                |        |                          |
             1 *        * 1                        | *
               |        |                          |
           questions  submissions *───1 enrollments *───1 students
               |          |
               *          *
        submission_answers
```

### Tables

| Table                | Purpose                                                            |
|----------------------|--------------------------------------------------------------------|
| `admins`             | Platform administrators                                            |
| `instructors`        | Course authors, expertise, credentials                             |
| `students`           | Learner accounts                                                   |
| `courses`            | Title, description, category, level, price, status, owner          |
| `modules`            | Ordered sections inside a course                                   |
| `lessons`            | Video/reading/exercise content inside a module                     |
| `enrollments`        | Junction table: student ↔ course, with status and timestamps       |
| `lesson_progress`    | Junction table: completed lessons per enrollment                   |
| `assessments`        | Quizzes and assignments with weight, due date and max score        |
| `questions`          | Four options, correct answer and points                            |
| `submissions`        | One attempt per student per assessment, with score and feedback    |
| `submission_answers` | Per-question answer audit trail                                    |

### Views

| View                   | Purpose                                                    |
|------------------------|------------------------------------------------------------|
| `v_course_stats`       | Course + instructor + learner/lesson/assessment counts     |
| `v_student_progress`   | Enrollment progress numerator and denominator              |
| `v_assessment_results` | Submissions joined to assessments, courses and students     |

### Integrity enforced by the database

- Foreign keys on every relationship, enforced with `PRAGMA foreign_keys = ON`
- `UNIQUE (student_id, course_id)` — no duplicate enrollments
- `UNIQUE (assessment_id, student_id)` — one attempt per assessment
- `UNIQUE (enrollment_id, lesson_id)` — one progress row per lesson
- `CHECK` constraints on levels, statuses, content types, answer options and
  non-negative prices, scores, points and durations
- `ON DELETE CASCADE` for course content, `ON DELETE RESTRICT` for instructors
  who still own courses

---

## Reports and CSV export

Admins get seven reports, each rendered as an aligned table and exportable to
`exports/<report>-<timestamp>.csv` (UTF-8 with BOM, so Excel opens it cleanly):

| Report                  | Answers                                                        |
|-------------------------|----------------------------------------------------------------|
| Enrollment summary      | How many learners, completions and revenue per course         |
| Learner progress        | Who is falling behind, ranked by percentage complete           |
| Assessment performance  | Submissions, average, highest and lowest percentage per item   |
| Top students            | Best averages across graded work                               |
| Instructor workload     | Courses, learners, assessments and ungraded queue per teacher  |
| Revenue by category     | Where the money comes from                                      |
| Pending grading queue   | What is still waiting for a score                               |

---

## Testing

```powershell
python -m unittest discover -s tests -v
```

```
Ran 8 tests in 3.1s

OK
```

Each run creates a throwaway SQLite database in a temporary directory and loads
the real seed data, so the tests exercise production code paths. Covered:

- seeding produces the expected catalogue, staff and learner accounts
- authentication works for all three roles and rejects a wrong password
- enrolling, completing every lesson and the automatic `Completed` status
- quiz auto-grading, perfect scores and the one-attempt rule
- assignment grading, feedback and weighted course averages
- negative paths: duplicate enrollment, repeat attempt, unenrolled submission,
  out-of-range grade
- every report returns rows
- seeding is idempotent, so startup is always safe

---

## Security

- Passwords are stored as **salted PBKDF2-HMAC-SHA256** hashes
  (120,000 iterations, 16-byte random salt) in a self-describing
  `pbkdf2$iterations$salt$digest` format, and compared with
  `hmac.compare_digest` to avoid timing leaks.
- Every query uses **parameterized placeholders**, so user input can never be
  interpreted as SQL.
- Role and ownership are re-checked in the service layer; the menus are a
  convenience, not the security boundary.
- No credentials, keys or tokens are stored in the repository.
- Input is validated at the boundary and again in the domain layer.

---

## Concepts used

**DBMS:** relational modelling and 3NF, junction tables, surrogate primary keys,
foreign keys and referential actions, `UNIQUE` / `CHECK` / `NOT NULL` /
`DEFAULT` constraints, transactions and atomicity, inner and left joins,
correlated subqueries, conditional aggregation with `CASE`, `GROUP BY` and
`ORDER BY`, views as reusable read models, secondary indexes, parameterized
statements, DDL/DML separation, idempotent schema management, embedded
serverless databases and seeding.

**Python:** modular layering and separation of concerns, custom exceptions and
fail-fast guard clauses, `sqlite3.Row` access, `executemany` batching, explicit
transactions, safe dynamic SQL built from allow-lists, `pathlib`, `csv`,
`re`, `datetime`, `argparse`, `tempfile`, `unittest` fixtures, and
`hashlib` / `secrets` / `hmac` cryptography.

**Design:** layered architecture, role-based access control, thin UI, business
logic in the domain layer, data-driven reports, dependency-free delivery and
test isolation.

---




## Troubleshooting

**Password characters are visible while typing.** This is intentional: the
prompt uses plain input so it works in every terminal and IDE. Passwords are
still stored only as hashes.

**The database looks empty or the demo data is gone.** Rebuild it:

```powershell
python main.py --reset
```

**"database is locked".** Another `main.py` instance is still running and
holding the SQLite file. Close the other window and retry.

**Where is my data?** In `learning_platform.db` next to `main.py`. Deleting it
and running `python main.py` recreates everything from scratch.

---


