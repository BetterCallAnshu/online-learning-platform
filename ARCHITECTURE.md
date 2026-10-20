# Online Learning Platform — Concepts, Architecture & Working

A reference document for the project: every concept used, how the system is
architected, and how each feature actually works. Use it as the basis for a
project report or viva preparation.

| Item            | Choice                                        |
|-----------------|-----------------------------------------------|
| Language        | Python 3.14 (any 3.10+ works)                 |
| Database        | SQLite 3 (embedded, single-file, serverless)  |
| Driver          | Standard-library `sqlite3` module             |
| UI              | CLI (dumb-terminal safe, menu driven)         |
| Dependencies    | None (standard library only)                  |
| Testing         | `unittest` with an isolated temporary database|
| Entry point     | `main.py` (`--reset` rebuilds the demo data)  |

---

## 1. Software architecture

### 1.1 Layered (3-tier) architecture

The application follows a classic layered architecture. Data only flows
downward; results and errors flow upward. No layer is allowed to skip a layer.

```
+=====================================================================+
|  PRESENTATION LAYER   cli.py                                        |
|  Role-based portals (student / instructor / admin)                  |
|  Menu loops, prompted input, formatted tables, CSV export           |
+---------------------------|-----------------------------------------+
                            |  calls service functions with plain values
                            |  catches ServiceError and prints messages
+---------------------------v-----------------------------------------+
|  BUSINESS LOGIC LAYER   services.py (write path) / reports.py (read)|
|  Validation, business rules, permissions, grading algorithms,       |
|  report SQL, all SQL statements live here or in reports.py          |
+---------------------------|-----------------------------------------+
                            |  parameterized SQL, one commit per operation
+---------------------------v-----------------------------------------+
|  DATA LAYER   db.py + schema.sql                                    |
|  Connection factory, FK enforcement, DDL (tables/views/indexes)     |
+---------------------------+-----------------------------------------+
                            |
                            v
                 learning_platform.db (SQLite file)

  shared utilities:  security.py (PBKDF2 hashing)  <-> used by services + seed
  bootstrap:         seed.py (demo data) builds the DB through services.py
  test layer:        tests/test_flows.py exercises services on a temp DB
```

### 1.2 Module responsibilities

| Module         | Layer          | Responsibility (only this)                                          |
|----------------|----------------|---------------------------------------------------------------------|
| `main.py`      | bootstrap      | Parse `--reset`, obtain/create the DB connection, start the CLI      |
| `cli.py`       | presentation   | Menus, `input()` prompts, `print_table`, CSV export, reporting UI    |
| `services.py`  | domain         | Validation, permissions, state rules, auto-grading, CRUD orchestration |
| `reports.py`   | domain (read)  | Read-only analytical queries; each report returns (headers, rows)    |
| `db.py`        | data           | `connect()`, `init_schema()`, `reset()`; enables foreign keys        |
| `schema.sql`   | data           | Declarative DDL: 12 tables, 8 indexes, 3 views                       |
| `seed.py`      | bootstrap      | Builds the demo dataset by *calling services*, never raw INSERTs     |
| `security.py`  | utility        | Salted PBKDF2 password hashing and constant-time verification        |
| `tests/…`      | verification   | End-to-end service tests on a throwaway database                     |

### 1.3 Design rules that keep it clean

- **Separation of concerns** – UI code contains zero SQL; service code contains
  zero `input()`; reports never mutate rows.
- **Single write path** – every insert/update/delete is validated inside
  `services.py`, so the CLI and the tests enforce identical business rules.
- **Fail fast** – services raise `ServiceError` with a human-readable message;
  the CLI catches it and prints it. Nothing partially written is committed
  because `conn.commit()` only runs after all statements succeeded.
- **Schema as code** – the whole database shape lives in one reviewable
  `schema.sql` with `IF NOT EXISTS` DDL, so `db.init_schema()` is idempotent.
- **Seed through the API** – `seed.py` reuses the same business functions, which
  proves the rules and makes the demo data internally consistent.

---

## 2. How a request flows (lifecycle)

Generic pipeline for every user action:

```
user choice
  -> CLI helper reads/validates raw input (types, ranges, y/n)
  -> services.<operation>(conn, ...) called
       -> guard clauses (_require) validate business rules
       -> one or more parameterized SQL statements executed
       -> conn.commit()  (atomic unit)
       -> rows returned as sqlite3.Row
  -> CLI formats rows with print_table / choose_row
  -> any ServiceError is caught once and displayed
```

### 2.1 Worked example — authentication

1. Login screen reads email and password (`ask`, `ask_password`).
2. `services.authenticate` lowercases the email, then tries one indexed
   `SELECT ... WHERE email = ?` per role table (admins, instructors, students).
3. If a row matches, `security.verify_password` re-derives the PBKDF2 hash from
   the stored salt and compares with `hmac.compare_digest` (timing-safe).
4. The service returns a session dict `{"role", "id", "name", "email"}`; the CLI
   dispatches to the matching portal menu. Wrong email/password simply returns
   `None`.

### 2.2 Worked example — enrolling in a course

1. `services.enroll(student_id, course_id)`:
   - course must exist and have `status = 'Published'` (`_require`);
   - existing enrollment is looked up by the pair (student, course):
     a `Dropped` enrollment is *reactivated*, an active one is rejected;
   - otherwise a new `enrollments` row is inserted (status defaults to
     `Active`).
2. The `UNIQUE (student_id, course_id)` constraint is the database-level
   backstop for the same rule.

### 2.3 Worked example — quiz submission (auto-grading)

1. Guards: assessment must be a `quiz`, the student must be enrolled, no prior
   submission may exist (`UNIQUE (assessment_id, student_id)`), the quiz must
   already have questions.
2. For each question the answer letter is normalized (only `A–D` counts;
   anything else is stored as `NULL`), compared with `correct_option`, and
   matching points are accumulated.
3. Score calculation:

   ```
   score = round( earned_points / total_points * max_score, 2 )
   ```

4. One `INSERT` into `submissions` plus one batched
   `executemany` into `submission_answers` (selected option + is_correct), all
   committed together — a failed insert cannot leave a half-graded attempt.
5. The result dict (score, correct count) is displayed instantly, and the
   answers are reviewable later through `get_answer_review`.

### 2.4 Worked example — assignment grading

1. **Student:** `submit_assignment` enforces enrollment and ≥ 20 characters; a
   resubmission *updates* the pending row and resets feedback, but is blocked
   once a score exists.
2. **Instructor:** `list_pending_grading` (optionally filtered by instructor) is
   the grading queue; `grade_submission` re-validates `0 ≤ score ≤ max_score`,
   writes score + feedback + `graded_at`. Weighted averages then include the
   item automatically.

### 2.5 Worked example — automatic course completion

`mark_lesson_complete` inserts into `lesson_progress` (guarded by the
`UNIQUE (enrollment_id, lesson_id)`), then `_sync_course_completion(course_id)`
recomputes, for *every* enrollment of that course, whether
`lessons_done == lessons_total` and flips the enrollment status between
`Active` and `Completed`. The same sync runs after a lesson/module is added or
deleted, so adding new content to a finished course correctly reopens it.

---

## 3. Database design

### 3.1 ER diagram

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
               |          |          (junction:
                *          *           resolves students *───* courses)
          submission_answers

admins  (independent authentication entity)
```

### 3.2 Tables

| Table                | Purpose                                                            |
|----------------------|--------------------------------------------------------------------|
| `admins`             | Platform administrators                                            |
| `instructors`        | Course authors, expertise, credentials                             |
| `students`           | Learner accounts                                                   |
| `courses`            | Title, description, category, level, price, status, owner          |
| `modules`            | Ordered sections inside a course                                   |
| `lessons`            | Video/reading/exercise content inside a module                     |
| `enrollments`        | Junction table: student ↔ course + status + timestamps             |
| `lesson_progress`    | Junction table: completed lessons per enrollment                   |
| `assessments`        | Quizzes/assignments with weight, due date, max score               |
| `questions`          | Four options, correct letter, points                               |
| `submissions`        | One attempt per (assessment, student), score, feedback, graded_at  |
| `submission_answers` | Per-question answer audit trail                                    |

### 3.3 Views (stored, read-only queries)

| View                    | Removes repeated SQL for…                                        |
|-------------------------|------------------------------------------------------------------|
| `v_course_stats`        | Course row + instructor name + counts of learners/lessons/assessments |
| `v_student_progress`    | Enrollment + student + course + `lessons_done` / `lessons_total` |
| `v_assessment_results`  | Submission + assessment + course + student + computed `percent`  |

Services (`course_roster`, `course_gradebook`) and reports both read them, so
the "progress numerator/denominator" logic exists in exactly one place.

### 3.4 Indexes

Eight secondary indexes on the join/filter columns (`courses.instructor_id`,
`modules.course_id`, `lessons.module_id`, `enrollments.course_id`,
`lesson_progress.enrollment_id`, `assessments.course_id`,
`submissions.assessment_id`, `submissions.student_id`) keep the dashboard and
report queries from scanning full tables as data grows.

### 3.5 Integrity enforced by the database itself

| Rule                                             | Mechanism                                |
|--------------------------------------------------|------------------------------------------|
| No duplicate enrollments / attempts              | `UNIQUE (student_id, course_id)`, `UNIQUE (assessment_id, student_id)` |
| Valid domain values (level, status, types, A–D)  | `CHECK` constraints                      |
| Non-negative price/score/points/duration         | `CHECK` constraints                      |
| Every lesson belongs to a real module/course     | Foreign keys + `PRAGMA foreign_keys = ON`|
| Deleting a course removes its content cleanly    | `ON DELETE CASCADE`                      |
| Detectable completion progress                   | `UNIQUE (enrollment_id, lesson_id)`      |
| Instructor with courses cannot vanish            | `ON DELETE RESTRICT`                     |
| Default timestamps without application code      | `DEFAULT (datetime('now'))`              |

Attribute order/dates are stored as ISO-8601 `TEXT`, which sorts correctly with
lexicographic comparisons — no special date type needed.

---

## 4. DBMS concepts used

1. **Relational model & 3NF** — every table stores one fact per row; repeating
   lists were broken into child tables.
2. **Many-to-many resolution** — `students ⇄ courses` resolved via the
   `enrollments` junction; `enrollments ⇄ lessons` via `lesson_progress`
   (progress belongs to the *relationship*, not to either side alone).
3. **Surrogate primary keys** with `AUTOINCREMENT` for stable IDs.
4. **Referential integrity** — foreign keys everywhere, enforced per connection
   (`PRAGMA foreign_keys = ON`) because SQLite makes it per-connection.
5. **Referential actions** — `CASCADE` for content the course owns,
   `RESTRICT` where history must survive.
6. **Unique constraints as business rules** (no double enrollment, one attempt
   per assessment, one progress row per lesson).
7. **CHECK domains** — invalid states are unrepresentable at the DB level.
8. **DDL vs DML separation** — declarative `schema.sql` vs runtime queries.
9. **Idempotent schema phase** — `CREATE TABLE IF NOT EXISTS` lets `main.py`
   upgrade/reopen safely.
10. **Views** as a virtual-table abstraction over repeated joins.
11. **Joins** — inner joins everywhere, `LEFT JOIN` where a course must appear
    with zero enrollments/submissions in reports.
12. **Correlated subqueries** — per-course/per-instructor counters used in list
    queries.
13. **Conditional aggregation** — `SUM(CASE WHEN … END)` for revenue,
    completed enrollments, and average percentages without multiple scans.
14. **GROUP BY / ORDER BY (incl. ordering by alias and boolean expression
    `status = 'Published' DESC`)** for report sorting.
15. **Parameterized statements** (`?` placeholders) — SQL injection prevention;
    user text is always a *value*, never concatenated SQL.
16. **Transactions** — services commit once per logical action; SQLite wraps the
    statement set so partial writes never persist.
17. **Embedded/serverless database** — a file engine, no service/process to
    install; connections are cheap and closed explicitly.
18. **Batch operations** — `executemany` for quiz answer rows.
19. **Row access by column name** — `row_factory = sqlite3.Row` gives
    near-dict ergonomics while staying driver-native.
20. **Data lifecycle management** — seeding inserts demo data; `--reset` drops
    the file and rebuilds it, proving the schema is reproducible.

---

## 5. Python concepts used

1. **Modules & layering** — one concern per file; an import graph that never
   cycles (`seed → services → security/db`, `cli → services/reports`).
2. **Custom exception** — `class ServiceError(Exception)` turns domain failures
   into data the UI can display.
3. **Guard-clause validation** — the `_require(condition, message)` helper
   implements "precondition → raise" in one line.
4. **Role dispatch** — `authenticate()` iterates role tables; `run()` switches
   on the returned role.
5. **`sqlite3.Row`** — attribute-style access (`row["title"]`) instead of tuple
   indices.
6. **Transactions** — explicit `commit()` at the end of each service function,
   `conn.close()` in `finally`.
7. ****`kwargs` whitelisting** — `update_course(course_id, **fields)` filters an
   allow-listed key set before building the dynamic `UPDATE`; identifiers are
   never taken from user input (safe dynamic SQL).
8. **`executemany`**, **comprehensions**, **generator unpacking**
   (`max(len(h), *(…))`), **zip** pairing options/letters, **f-strings**,
   driven formatting (`%g`).
9. **`hashlib.pbkdf2_hmac` + `secrets.token_hex` + `hmac.compare_digest`** —
   KDF crypto with a random salt and timing-safe verification.
10. **`pathlib`** — locating `schema.sql` relative to `__file__`, DB reset,
    export folder creation.
11. **`csv` writer with `utf-8-sig`** — BOM so Excel opens exports correctly.
12. **`re`** — slugifying report names for filenames.
13. **`datetime`** — timestamped export names, seed due dates.
14. **`argparse`** — the `--reset` maintenance flag instead of an ad-hoc script.
15. **`tempfile.TemporaryDirectory`** — throwaway test databases.
16. **`unittest`** — class fixtures (`setUpClass`/`tearDownClass`),
    `assertRaises`, positive + negative cases, idempotency test.
17. **Monkeypatch-safe CLI** — every point of input flows through `input()`
    helpers, which is why the smoke tests can script sessions.

---

## 6. Security concepts

| Concept                | Implementation                                                    |
|------------------------|-------------------------------------------------------------------|
| Salted password hashing| PBKDF2-HMAC-SHA256, 120 000 iterations, 16-byte random salt        |
| Hash storage format    | `pbkdf2$<iterations>$<salt-hex>$<digest-hex>` — self-describing     |
| Timing-safe compare    | `hmac.compare_digest` instead of `==`                              |
| SQL injection defense  | Every query parameterized; dynamic SQL uses whitelisted names only |
| Authorization          | Role decided by the account table (can't be forged by the client); instructor queries filter `instructor_id`; admin action only in the admin portal |
| Least privilege in data| `ON DELETE RESTRICT` keeps accounts with live courses              |
| Password minimums      | Registration enforces ≥ 6 characters (see `create_student`)        |
| No secrets on disk     | Demo passwords exist only as hashes; no token/PII beyond emails    |

Authentication (who you are) is separated from authorization (what your role
may do); the CLI only decides *which menu* to show — the services still verify
enrollment/ownership before any mutation.

---

## 7. Business rules and where they live

| Rule                                                        | Enforced in                  |
|-------------------------------------------------------------|------------------------------|
| Only `Published` courses can be enrolled                    | `services.enroll`            |
| One active enrollment per student per course                | service check + `UNIQUE`     |
| Only enrolled students may submit/attempt                   | `take_quiz`, `submit_assignment` |
| One quiz attempt per student per quiz                       | service check + `UNIQUE`     |
| Assignments resubmittable until graded only                 | `submit_assignment`          |
| Quiz answers auto-graded by points                          | `take_quiz`                  |
| Instructor scoring bounded by `0 … max_score`               | `grade_submission`           |
| Enrollment completes automatically at 100% lessons          | `_sync_course_completion`    |
| Adding/removing lessons re-evaluates completion             | `add_lesson`/`delete_lesson` |
| Students must supply ≥ 6-char passwords, valid emails       | `create_student`/`create_instructor` |
| Instructors only grade their own courses' submissions       | `list_pending_grading(instructor_id)` |

---

## 8. Key algorithms

**Progress percent**

```python
percent = 0 if total == 0 else round(done * 100 / total)
```

**Weighted course average** — SQL accumulates the sums, Python divides:

```
avg_course = Σ( score/max_score * 100 * weight ) / Σ( weight )
```

**Completion synchronization** (per course, after any lesson change)

```
for each Active/Completed enrollment:
    done = COUNT(lesson_progress)
    total= COUNT(lessons of course)
    status = 'Completed' if done == total and total else 'Active'
```

**Auto-grading**

```
earned = Σ points(question) where selected == correct
total  = Σ points(questions)
score  = earned/total * max_score
```

**Report fusion (example: enrollment summary)** — one scan join with `CASE`
aggregates yields enrollments, completions and revenue per course in a single
`GROUP BY`.

---

## 9. Testing architecture

- Every run creates a fresh SQLite file inside `TemporaryDirectory`, then runs
  the real `seed.seed()` — tests execute the *same* SQL the production CLI uses.
- Positive flows: seed counts, three-role authentication, enrollment →
  completion, perfect 100% quiz, grading → weighted average.
- Negative flows: duplicate enrollment, duplicate quiz attempt, foreign
  student submission, out-of-range grade all raise `ServiceError`.
- `seed.seed` is asserted idempotent, so `main.py` can seed on any startup.

Run:

```powershell
python -m unittest discover -s tests -v
```

---

## 10. Demo dataset snapshot (as seeded)

| Object                 | Count | Notes                                        |
|------------------------|-------|----------------------------------------------|
| Admins                 | 1     | admin@learnhub.io                            |
| Instructors            | 3     | Maya, Alan, Priya                            |
| Students               | 6     | Sam, Lena, Tom, Rina, Diego, Ava             |
| Courses                | 4     | 3 published + 1 draft (publish it from admin) |
| Modules / lessons      | 10 / 21 | across the four courses                    |
| Assessments / questions| 6 / 13| 3 quizzes + 3 assignments                    |
| Enrollments            | 10    | one already Completed                        |
| Submissions            | 17    | 10 auto-graded quizzes + assignments         |
| Pending grading        | 3     | for the instructor "Grade submissions" demo  |
| Gross revenue          | $550  | Σ course prices of paid enrollments          |

---

## 11. One-paragraph summary

The platform is a three-tier application inside one Python package. A
dumb-but-safe CLI captures input and renders tables; a service layer owns
every business rule (validation, permissions, auto-grading, completion state
machines); and a normalized SQLite database — 12 tables bound by foreign keys,
uniques, checks, indexes and analytic views — persists everything. Reports are
pure read-only SQL over views with `CASE` aggregations, exportable to CSV,
passwords are salted PBKDF2 hashes verified in constant time, and every query
is parameterized. The whole stack is standard-library only, reproducible via
`--reset`, and covered by end-to-end service tests wired to disposable
databases.
