"""Business logic for the Online Learning Platform.

Every function receives an open SQLite connection so the same code is used by
the CLI, the seed script and the automated tests.
"""

import sqlite3

from security import hash_password, verify_password

COURSE_LEVELS = ("Beginner", "Intermediate", "Advanced")
COURSE_STATUSES = ("Draft", "Published", "Archived")
CONTENT_TYPES = ("video", "reading", "exercise")

_ROLE_TABLES = (
    ("admin", "admins", "admin_id"),
    ("instructor", "instructors", "instructor_id"),
    ("student", "students", "student_id"),
)


class ServiceError(Exception):
    """Raised when a business rule is violated."""


def _require(condition, message):
    if not condition:
        raise ServiceError(message)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate(conn, email, password):
    email = (email or "").strip().lower()
    if not email or not password:
        return None
    for role, table, id_col in _ROLE_TABLES:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE email = ?", (email,)
        ).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return {
                "role": role,
                "id": row[id_col],
                "name": row["full_name"],
                "email": row["email"],
            }
    return None


# ---------------------------------------------------------------------------
# Account creation and lookups
# ---------------------------------------------------------------------------

def create_student(conn, full_name, email, password):
    name = (full_name or "").strip()
    email = (email or "").strip().lower()
    _require(name, "Full name is required.")
    _require("@" in email and "." in email.split("@")[-1], "Enter a valid email address.")
    _require(len(password or "") >= 6, "Password must be at least 6 characters.")
    try:
        cur = conn.execute(
            "INSERT INTO students (full_name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, hash_password(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ServiceError("That email address is already registered.")
    return cur.lastrowid


def create_instructor(conn, full_name, email, password, expertise=""):
    name = (full_name or "").strip()
    email = (email or "").strip().lower()
    _require(name, "Full name is required.")
    _require("@" in email and "." in email.split("@")[-1], "Enter a valid email address.")
    _require(len(password or "") >= 6, "Password must be at least 6 characters.")
    try:
        cur = conn.execute(
            "INSERT INTO instructors (full_name, email, password_hash, expertise) "
            "VALUES (?, ?, ?, ?)",
            (name, email, hash_password(password), (expertise or "").strip()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ServiceError("That email address is already registered.")
    return cur.lastrowid


def update_student_profile(conn, student_id, full_name, email):
    name = (full_name or "").strip()
    email = (email or "").strip().lower()
    _require(name, "Full name is required.")
    _require("@" in email, "Enter a valid email address.")
    try:
        conn.execute(
            "UPDATE students SET full_name = ?, email = ? WHERE student_id = ?",
            (name, email, student_id),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ServiceError("That email address is already in use.")


def list_students(conn, search=""):
    sql = """
        SELECT s.student_id, s.full_name, s.email, s.joined_at,
               (SELECT COUNT(*) FROM enrollments e
                 WHERE e.student_id = s.student_id
                   AND e.status IN ('Active', 'Completed')) AS courses
          FROM students s
    """
    params = []
    if search:
        sql += " WHERE LOWER(s.full_name) LIKE ? OR LOWER(s.email) LIKE ?"
        like = f"%{search.lower()}%"
        params += [like, like]
    sql += " ORDER BY s.full_name"
    return conn.execute(sql, params).fetchall()


def list_instructors(conn):
    return conn.execute(
        """
        SELECT i.instructor_id, i.full_name, i.email, i.expertise,
               (SELECT COUNT(*) FROM courses c
                 WHERE c.instructor_id = i.instructor_id) AS courses,
               (SELECT COUNT(*) FROM enrollments e
                 JOIN courses c ON c.course_id = e.course_id
                WHERE c.instructor_id = i.instructor_id
                  AND e.status IN ('Active', 'Completed')) AS students
          FROM instructors i
         ORDER BY i.full_name
        """
    ).fetchall()


# ---------------------------------------------------------------------------
# Courses and content
# ---------------------------------------------------------------------------

def create_course(conn, instructor_id, title, description="", category="General",
                  level="Beginner", price=0.0, status="Draft"):
    title = (title or "").strip()
    category = (category or "General").strip() or "General"
    _require(title, "Course title is required.")
    _require(level in COURSE_LEVELS, "Level must be Beginner, Intermediate or Advanced.")
    _require(status in COURSE_STATUSES, "Invalid course status.")
    _require(float(price) >= 0, "Price cannot be negative.")
    instructor = conn.execute(
        "SELECT 1 FROM instructors WHERE instructor_id = ?", (instructor_id,)
    ).fetchone()
    _require(instructor, "Instructor not found.")
    cur = conn.execute(
        """
        INSERT INTO courses (title, description, category, level, price, status, instructor_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (title, (description or "").strip(), category, level, float(price), status, instructor_id),
    )
    conn.commit()
    return cur.lastrowid


def update_course(conn, course_id, **fields):
    allowed = {"title", "description", "category", "level", "price", "status", "instructor_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    _require(updates, "Nothing to update.")
    if "status" in updates:
        _require(updates["status"] in COURSE_STATUSES, "Invalid course status.")
    if "level" in updates:
        _require(updates["level"] in COURSE_LEVELS, "Invalid course level.")
    if "price" in updates:
        _require(float(updates["price"]) >= 0, "Price cannot be negative.")
    assignments = ", ".join(f"{name} = ?" for name in updates)
    conn.execute(
        f"UPDATE courses SET {assignments} WHERE course_id = ?",
        (*updates.values(), course_id),
    )
    conn.commit()


def get_course(conn, course_id):
    return conn.execute(
        """
        SELECT c.*, i.full_name AS instructor, i.email AS instructor_email
          FROM courses c
          JOIN instructors i ON i.instructor_id = c.instructor_id
         WHERE c.course_id = ?
        """,
        (course_id,),
    ).fetchone()


def list_courses(conn, search="", category="", status=None):
    sql = """
        SELECT c.course_id, c.title, c.category, c.level, c.price, c.status,
               c.instructor_id, i.full_name AS instructor,
               (SELECT COUNT(*) FROM enrollments e
                 WHERE e.course_id = c.course_id
                   AND e.status IN ('Active', 'Completed')) AS enrolled,
               (SELECT COUNT(*) FROM modules m
                 JOIN lessons l ON l.module_id = m.module_id
                WHERE m.course_id = c.course_id) AS lessons
          FROM courses c
          JOIN instructors i ON i.instructor_id = c.instructor_id
         WHERE 1 = 1
    """
    params = []
    if search:
        sql += (" AND (LOWER(c.title) LIKE ? OR LOWER(c.description) LIKE ?"
                " OR LOWER(i.full_name) LIKE ?)")
        like = f"%{search.lower()}%"
        params += [like, like, like]
    if category:
        sql += " AND LOWER(c.category) = ?"
        params.append(category.lower())
    if status:
        sql += " AND c.status = ?"
        params.append(status)
    sql += " ORDER BY c.status = 'Published' DESC, c.title"
    return conn.execute(sql, params).fetchall()


def list_categories(conn):
    return [row[0] for row in conn.execute(
        "SELECT DISTINCT category FROM courses ORDER BY category"
    ).fetchall()]


def get_curriculum(conn, course_id):
    """Return modules in order, each with its ordered lessons."""
    modules = conn.execute(
        "SELECT * FROM modules WHERE course_id = ? ORDER BY position, module_id",
        (course_id,),
    ).fetchall()
    curriculum = []
    for module in modules:
        lessons = conn.execute(
            "SELECT * FROM lessons WHERE module_id = ? ORDER BY position, lesson_id",
            (module["module_id"],),
        ).fetchall()
        curriculum.append({"module": module, "lessons": lessons})
    return curriculum


def count_lessons(conn, course_id):
    return conn.execute(
        """
        SELECT COUNT(*) FROM modules m
          JOIN lessons l ON l.module_id = m.module_id
         WHERE m.course_id = ?
        """,
        (course_id,),
    ).fetchone()[0]


def add_module(conn, course_id, title, position=None):
    title = (title or "").strip()
    _require(title, "Module title is required.")
    _require(get_course(conn, course_id), "Course not found.")
    if position is None:
        position = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM modules WHERE course_id = ?",
            (course_id,),
        ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO modules (course_id, title, position) VALUES (?, ?, ?)",
        (course_id, title, int(position)),
    )
    conn.commit()
    return cur.lastrowid


def add_lesson(conn, module_id, title, content_type="reading", content_url="",
               duration_min=0, position=None):
    module = conn.execute(
        "SELECT * FROM modules WHERE module_id = ?", (module_id,)
    ).fetchone()
    _require(module, "Module not found.")
    title = (title or "").strip()
    _require(title, "Lesson title is required.")
    _require(content_type in CONTENT_TYPES, "Type must be video, reading or exercise.")
    _require(int(duration_min) >= 0, "Duration cannot be negative.")
    if position is None:
        position = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM lessons WHERE module_id = ?",
            (module_id,),
        ).fetchone()[0]
    cur = conn.execute(
        """
        INSERT INTO lessons (module_id, title, content_type, content_url, duration_min, position)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (module_id, title, content_type, (content_url or "").strip(),
         int(duration_min), int(position)),
    )
    conn.commit()
    _sync_course_completion(conn, module["course_id"])
    return cur.lastrowid


def update_lesson(conn, lesson_id, **fields):
    allowed = {"title", "content_type", "content_url", "duration_min"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    _require(updates, "Nothing to update.")
    if "content_type" in updates:
        _require(updates["content_type"] in CONTENT_TYPES, "Invalid lesson type.")
    assignments = ", ".join(f"{name} = ?" for name in updates)
    conn.execute(
        f"UPDATE lessons SET {assignments} WHERE lesson_id = ?",
        (*updates.values(), lesson_id),
    )
    conn.commit()


def delete_lesson(conn, lesson_id):
    lesson = get_lesson(conn, lesson_id)
    _require(lesson, "Lesson not found.")
    conn.execute("DELETE FROM lessons WHERE lesson_id = ?", (lesson_id,))
    conn.commit()
    _sync_course_completion(conn, lesson["course_id"])


def delete_module(conn, module_id):
    module = conn.execute(
        "SELECT * FROM modules WHERE module_id = ?", (module_id,)
    ).fetchone()
    _require(module, "Module not found.")
    conn.execute("DELETE FROM modules WHERE module_id = ?", (module_id,))
    conn.commit()
    _sync_course_completion(conn, module["course_id"])


def get_lesson(conn, lesson_id):
    return conn.execute(
        """
        SELECT l.*, m.course_id, m.title AS module_title
          FROM lessons l
          JOIN modules m ON m.module_id = l.module_id
         WHERE l.lesson_id = ?
        """,
        (lesson_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# Enrollment and progress
# ---------------------------------------------------------------------------

def get_enrollment(conn, student_id, course_id):
    return conn.execute(
        "SELECT * FROM enrollments WHERE student_id = ? AND course_id = ?",
        (student_id, course_id),
    ).fetchone()


def enroll(conn, student_id, course_id):
    course = get_course(conn, course_id)
    _require(course, "Course not found.")
    _require(course["status"] == "Published", "This course is not open for enrollment.")
    existing = get_enrollment(conn, student_id, course_id)
    if existing:
        if existing["status"] == "Dropped":
            conn.execute(
                "UPDATE enrollments SET status = 'Active', enrolled_at = datetime('now') "
                "WHERE enrollment_id = ?",
                (existing["enrollment_id"],),
            )
            conn.commit()
            return existing["enrollment_id"]
        raise ServiceError("You are already enrolled in this course.")
    cur = conn.execute(
        "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
        (student_id, course_id),
    )
    conn.commit()
    return cur.lastrowid


def drop_course(conn, student_id, course_id):
    enrollment = get_enrollment(conn, student_id, course_id)
    _require(enrollment, "You are not enrolled in this course.")
    conn.execute(
        "UPDATE enrollments SET status = 'Dropped' WHERE enrollment_id = ?",
        (enrollment["enrollment_id"],),
    )
    conn.commit()


def my_courses(conn, student_id):
    return conn.execute(
        """
        SELECT e.enrollment_id, e.status AS enrollment_status, e.enrolled_at,
               c.course_id, c.title, c.category, c.level,
               i.full_name AS instructor,
               (SELECT COUNT(*) FROM modules m
                 JOIN lessons l ON l.module_id = m.module_id
                WHERE m.course_id = c.course_id) AS total_lessons,
               (SELECT COUNT(*) FROM lesson_progress lp
                 WHERE lp.enrollment_id = e.enrollment_id) AS done_lessons
          FROM enrollments e
          JOIN courses c ON c.course_id = e.course_id
          JOIN instructors i ON i.instructor_id = c.instructor_id
         WHERE e.student_id = ? AND e.status IN ('Active', 'Completed')
         ORDER BY e.enrolled_at DESC, c.title
        """,
        (student_id,),
    ).fetchall()


def completed_lesson_ids(conn, enrollment_id):
    return {row[0] for row in conn.execute(
        "SELECT lesson_id FROM lesson_progress WHERE enrollment_id = ?",
        (enrollment_id,),
    ).fetchall()}


def progress_percent(done, total):
    if not total:
        return 0
    return round(done * 100 / total)


def mark_lesson_complete(conn, student_id, lesson_id):
    lesson = get_lesson(conn, lesson_id)
    _require(lesson, "Lesson not found.")
    enrollment = conn.execute(
        "SELECT * FROM enrollments WHERE student_id = ? AND course_id = ? "
        "AND status IN ('Active', 'Completed')",
        (student_id, lesson["course_id"]),
    ).fetchone()
    _require(enrollment, "You are not enrolled in this course.")
    existing = conn.execute(
        "SELECT 1 FROM lesson_progress WHERE enrollment_id = ? AND lesson_id = ?",
        (enrollment["enrollment_id"], lesson_id),
    ).fetchone()
    if existing:
        return False
    conn.execute(
        "INSERT INTO lesson_progress (enrollment_id, lesson_id) VALUES (?, ?)",
        (enrollment["enrollment_id"], lesson_id),
    )
    conn.commit()
    _sync_course_completion(conn, lesson["course_id"])
    return True


def mark_lesson_incomplete(conn, student_id, lesson_id):
    lesson = get_lesson(conn, lesson_id)
    _require(lesson, "Lesson not found.")
    enrollment = get_enrollment(conn, student_id, lesson["course_id"])
    _require(enrollment, "You are not enrolled in this course.")
    conn.execute(
        "DELETE FROM lesson_progress WHERE enrollment_id = ? AND lesson_id = ?",
        (enrollment["enrollment_id"], lesson_id),
    )
    conn.commit()
    _sync_course_completion(conn, lesson["course_id"])


def _sync_course_completion(conn, course_id):
    total = count_lessons(conn, course_id)
    enrollments = conn.execute(
        "SELECT enrollment_id FROM enrollments WHERE course_id = ? "
        "AND status IN ('Active', 'Completed')",
        (course_id,),
    ).fetchall()
    for enrollment in enrollments:
        done = conn.execute(
            "SELECT COUNT(*) FROM lesson_progress WHERE enrollment_id = ?",
            (enrollment["enrollment_id"],),
        ).fetchone()[0]
        status = "Completed" if total and done >= total else "Active"
        conn.execute(
            "UPDATE enrollments SET status = ? WHERE enrollment_id = ?",
            (status, enrollment["enrollment_id"]),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Assessments, submissions and grading
# ---------------------------------------------------------------------------

def list_assessments(conn, course_id):
    return conn.execute(
        """
        SELECT a.*,
               (SELECT COUNT(*) FROM questions q
                 WHERE q.assessment_id = a.assessment_id) AS question_count,
               (SELECT COUNT(*) FROM submissions s
                 WHERE s.assessment_id = a.assessment_id) AS submission_count
          FROM assessments a
         WHERE a.course_id = ?
         ORDER BY a.kind, a.assessment_id
        """,
        (course_id,),
    ).fetchall()


def get_assessment(conn, assessment_id):
    return conn.execute(
        "SELECT * FROM assessments WHERE assessment_id = ?", (assessment_id,)
    ).fetchone()


def create_assessment(conn, course_id, title, kind, max_score=100.0, weight=1.0,
                      due_date=None, instructions=""):
    course = get_course(conn, course_id)
    _require(course, "Course not found.")
    title = (title or "").strip()
    _require(title, "Assessment title is required.")
    _require(kind in ("quiz", "assignment"), "Type must be quiz or assignment.")
    _require(float(max_score) > 0, "Max score must be greater than zero.")
    _require(float(weight) > 0, "Weight must be greater than zero.")
    cur = conn.execute(
        """
        INSERT INTO assessments (course_id, title, kind, max_score, weight, due_date, instructions)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (course_id, title, kind, float(max_score), float(weight),
         (due_date or "").strip() or None, (instructions or "").strip()),
    )
    conn.commit()
    return cur.lastrowid


def add_question(conn, assessment_id, prompt, options, correct_option, points=1.0):
    assessment = get_assessment(conn, assessment_id)
    _require(assessment, "Assessment not found.")
    _require(assessment["kind"] == "quiz", "Questions can only be added to quizzes.")
    prompt = (prompt or "").strip()
    _require(prompt, "Question prompt is required.")
    _require(len(options) == 4 and all(str(o).strip() for o in options),
             "Provide exactly four non-empty options.")
    correct = (correct_option or "").strip().upper()
    _require(correct in ("A", "B", "C", "D"), "Correct option must be A, B, C or D.")
    _require(float(points) > 0, "Points must be greater than zero.")
    opt_a, opt_b, opt_c, opt_d = [str(o).strip() for o in options]
    cur = conn.execute(
        """
        INSERT INTO questions
            (assessment_id, prompt, option_a, option_b, option_c, option_d,
             correct_option, points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (assessment_id, prompt, opt_a, opt_b, opt_c, opt_d, correct, float(points)),
    )
    conn.commit()
    return cur.lastrowid


def list_questions(conn, assessment_id):
    return conn.execute(
        "SELECT * FROM questions WHERE assessment_id = ? ORDER BY question_id",
        (assessment_id,),
    ).fetchall()


def get_submission(conn, student_id, assessment_id):
    return conn.execute(
        "SELECT * FROM submissions WHERE student_id = ? AND assessment_id = ?",
        (student_id, assessment_id),
    ).fetchone()


def take_quiz(conn, student_id, assessment_id, answers):
    """Auto-grade a quiz. `answers` maps question_id -> 'A'..'D'."""
    assessment = get_assessment(conn, assessment_id)
    _require(assessment, "Assessment not found.")
    _require(assessment["kind"] == "quiz", "This assessment is not a quiz.")
    enrollment = get_enrollment(conn, student_id, assessment["course_id"])
    _require(enrollment and enrollment["status"] in ("Active", "Completed"),
             "You must be enrolled in this course to take the quiz.")
    _require(not get_submission(conn, student_id, assessment_id),
             "You have already submitted this quiz.")
    questions = list_questions(conn, assessment_id)
    _require(questions, "This quiz has no questions yet.")
    total_points = sum(q["points"] for q in questions)
    earned = 0.0
    records = []
    for question in questions:
        selected = (answers.get(question["question_id"]) or "").strip().upper()
        selected = selected if selected in ("A", "B", "C", "D") else None
        is_correct = selected == question["correct_option"]
        if is_correct:
            earned += question["points"]
        records.append((question["question_id"], selected, 1 if is_correct else 0))
    score = round(earned / total_points * assessment["max_score"], 2)
    cur = conn.execute(
        """
        INSERT INTO submissions (assessment_id, student_id, content, score, feedback, graded_at)
        VALUES (?, ?, '', ?, 'Auto-graded quiz.', datetime('now'))
        """,
        (assessment_id, student_id, score),
    )
    submission_id = cur.lastrowid
    conn.executemany(
        """
        INSERT INTO submission_answers (submission_id, question_id, selected_option, is_correct)
        VALUES (?, ?, ?, ?)
        """,
        [(submission_id, qid, selected, correct) for qid, selected, correct in records],
    )
    conn.commit()
    return {
        "submission_id": submission_id,
        "score": score,
        "max_score": assessment["max_score"],
        "correct": sum(1 for _, _, correct in records if correct),
        "total": len(records),
    }


def submit_assignment(conn, student_id, assessment_id, content):
    assessment = get_assessment(conn, assessment_id)
    _require(assessment, "Assessment not found.")
    _require(assessment["kind"] == "assignment", "This assessment is not an assignment.")
    enrollment = get_enrollment(conn, student_id, assessment["course_id"])
    _require(enrollment and enrollment["status"] in ("Active", "Completed"),
             "You must be enrolled in this course to submit.")
    content = (content or "").strip()
    _require(len(content) >= 20, "Your submission should be at least 20 characters.")
    existing = get_submission(conn, student_id, assessment_id)
    if existing:
        _require(existing["score"] is None, "This assignment has already been graded.")
        conn.execute(
            "UPDATE submissions SET content = ?, submitted_at = datetime('now'), feedback = '' "
            "WHERE submission_id = ?",
            (content, existing["submission_id"]),
        )
        conn.commit()
        return existing["submission_id"], False
    cur = conn.execute(
        "INSERT INTO submissions (assessment_id, student_id, content) VALUES (?, ?, ?)",
        (assessment_id, student_id, content),
    )
    conn.commit()
    return cur.lastrowid, True


def grade_submission(conn, submission_id, score, feedback=""):
    submission = conn.execute(
        """
        SELECT s.*, a.max_score
          FROM submissions s
          JOIN assessments a ON a.assessment_id = s.assessment_id
         WHERE s.submission_id = ?
        """,
        (submission_id,),
    ).fetchone()
    _require(submission, "Submission not found.")
    _require(0 <= float(score) <= submission["max_score"],
             f"Score must be between 0 and {submission['max_score']:g}.")
    conn.execute(
        "UPDATE submissions SET score = ?, feedback = ?, graded_at = datetime('now') "
        "WHERE submission_id = ?",
        (float(score), (feedback or "").strip(), submission_id),
    )
    conn.commit()


def list_pending_grading(conn, instructor_id=None):
    sql = """
        SELECT s.submission_id, s.content, s.submitted_at,
               st.full_name AS student,
               a.title AS assessment, a.max_score, a.kind,
               c.title AS course
          FROM submissions s
          JOIN assessments a ON a.assessment_id = s.assessment_id
          JOIN courses c ON c.course_id = a.course_id
          JOIN students st ON st.student_id = s.student_id
         WHERE s.score IS NULL
    """
    params = []
    if instructor_id is not None:
        sql += " AND c.instructor_id = ?"
        params.append(instructor_id)
    sql += " ORDER BY s.submitted_at"
    return conn.execute(sql, params).fetchall()


def student_grades(conn, student_id):
    return conn.execute(
        """
        SELECT c.title AS course, a.title AS assessment, a.kind,
               s.score, a.max_score, a.weight, s.feedback,
               s.submitted_at, s.graded_at
          FROM submissions s
          JOIN assessments a ON a.assessment_id = s.assessment_id
          JOIN courses c ON c.course_id = a.course_id
         WHERE s.student_id = ?
         ORDER BY c.title, a.kind DESC, a.title
        """,
        (student_id,),
    ).fetchall()


def course_averages(conn, student_id):
    rows = conn.execute(
        """
        SELECT c.course_id, c.title,
               SUM((s.score / a.max_score) * 100 * a.weight) AS weighted_points,
               SUM(a.weight) AS weights
          FROM submissions s
          JOIN assessments a ON a.assessment_id = s.assessment_id
          JOIN courses c ON c.course_id = a.course_id
         WHERE s.student_id = ? AND s.score IS NOT NULL
         GROUP BY c.course_id
         ORDER BY c.title
        """,
        (student_id,),
    ).fetchall()
    return [
        {
            "course_id": row["course_id"],
            "course": row["title"],
            "average": round(row["weighted_points"] / row["weights"], 1),
        }
        for row in rows
    ]


def get_answer_review(conn, submission_id):
    return conn.execute(
        """
        SELECT sa.question_id, q.prompt, q.correct_option,
               sa.selected_option, sa.is_correct
          FROM submission_answers sa
          JOIN questions q ON q.question_id = sa.question_id
         WHERE sa.submission_id = ?
         ORDER BY sa.question_id
        """,
        (submission_id,),
    ).fetchall()


# ---------------------------------------------------------------------------
# Instructor view of a course
# ---------------------------------------------------------------------------

def course_roster(conn, course_id):
    return conn.execute(
        """
        SELECT v.student, v.email, v.enrollment_status, v.enrolled_at,
               v.lessons_done, v.lessons_total
          FROM v_student_progress v
         WHERE v.course_id = ?
         ORDER BY v.enrollment_status, v.student
        """,
        (course_id,),
    ).fetchall()


def course_gradebook(conn, course_id):
    return conn.execute(
        """
        SELECT v.assessment, v.kind, v.student, v.score, v.max_score, v.percent,
               v.graded_at
          FROM v_assessment_results v
         WHERE v.course_id = ?
         ORDER BY v.assessment, v.student
        """,
        (course_id,),
    ).fetchall()
