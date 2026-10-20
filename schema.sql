PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS admins (
    admin_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS instructors (
    instructor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    expertise     TEXT NOT NULL DEFAULT '',
    bio           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS students (
    student_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    joined_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS courses (
    course_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL,
    level         TEXT NOT NULL CHECK (level IN ('Beginner', 'Intermediate', 'Advanced')),
    price         REAL NOT NULL DEFAULT 0 CHECK (price >= 0),
    status        TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft', 'Published', 'Archived')),
    instructor_id INTEGER NOT NULL REFERENCES instructors (instructor_id) ON DELETE RESTRICT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS modules (
    module_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses (course_id) ON DELETE CASCADE,
    title     TEXT NOT NULL,
    position  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS lessons (
    lesson_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id    INTEGER NOT NULL REFERENCES modules (module_id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK (content_type IN ('video', 'reading', 'exercise')),
    content_url  TEXT NOT NULL DEFAULT '',
    duration_min INTEGER NOT NULL DEFAULT 0 CHECK (duration_min >= 0),
    position     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES students (student_id) ON DELETE CASCADE,
    course_id     INTEGER NOT NULL REFERENCES courses (course_id) ON DELETE CASCADE,
    enrolled_at   TEXT NOT NULL DEFAULT (datetime('now')),
    status        TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Completed', 'Dropped')),
    UNIQUE (student_id, course_id)
);

CREATE TABLE IF NOT EXISTS lesson_progress (
    progress_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL REFERENCES enrollments (enrollment_id) ON DELETE CASCADE,
    lesson_id     INTEGER NOT NULL REFERENCES lessons (lesson_id) ON DELETE CASCADE,
    completed_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (enrollment_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     INTEGER NOT NULL REFERENCES courses (course_id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('quiz', 'assignment')),
    max_score     REAL NOT NULL DEFAULT 100 CHECK (max_score > 0),
    weight        REAL NOT NULL DEFAULT 1 CHECK (weight > 0),
    due_date      TEXT,
    instructions  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS questions (
    question_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id  INTEGER NOT NULL REFERENCES assessments (assessment_id) ON DELETE CASCADE,
    prompt         TEXT NOT NULL,
    option_a       TEXT NOT NULL,
    option_b       TEXT NOT NULL,
    option_c       TEXT NOT NULL,
    option_d       TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK (correct_option IN ('A', 'B', 'C', 'D')),
    points         REAL NOT NULL DEFAULT 1 CHECK (points > 0)
);

CREATE TABLE IF NOT EXISTS submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments (assessment_id) ON DELETE CASCADE,
    student_id    INTEGER NOT NULL REFERENCES students (student_id) ON DELETE CASCADE,
    submitted_at  TEXT NOT NULL DEFAULT (datetime('now')),
    content       TEXT NOT NULL DEFAULT '',
    score         REAL CHECK (score IS NULL OR score >= 0),
    feedback      TEXT NOT NULL DEFAULT '',
    graded_at     TEXT,
    UNIQUE (assessment_id, student_id)
);

CREATE TABLE IF NOT EXISTS submission_answers (
    answer_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id   INTEGER NOT NULL REFERENCES submissions (submission_id) ON DELETE CASCADE,
    question_id     INTEGER NOT NULL REFERENCES questions (question_id) ON DELETE CASCADE,
    selected_option TEXT CHECK (selected_option IS NULL OR selected_option IN ('A', 'B', 'C', 'D')),
    is_correct      INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    UNIQUE (submission_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_courses_instructor ON courses (instructor_id);
CREATE INDEX IF NOT EXISTS idx_modules_course ON modules (course_id);
CREATE INDEX IF NOT EXISTS idx_lessons_module ON lessons (module_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments (course_id);
CREATE INDEX IF NOT EXISTS idx_progress_enrollment ON lesson_progress (enrollment_id);
CREATE INDEX IF NOT EXISTS idx_assessments_course ON assessments (course_id);
CREATE INDEX IF NOT EXISTS idx_submissions_assessment ON submissions (assessment_id);
CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions (student_id);

CREATE VIEW IF NOT EXISTS v_course_stats AS
SELECT c.course_id,
       c.title,
       c.category,
       c.price,
       c.status,
       i.full_name AS instructor,
       (SELECT COUNT(*) FROM enrollments e
         WHERE e.course_id = c.course_id AND e.status IN ('Active', 'Completed')) AS active_students,
       (SELECT COUNT(*) FROM modules m
         JOIN lessons l ON l.module_id = m.module_id
        WHERE m.course_id = c.course_id) AS total_lessons,
       (SELECT COUNT(*) FROM assessments a WHERE a.course_id = c.course_id) AS total_assessments
  FROM courses c
  JOIN instructors i ON i.instructor_id = c.instructor_id;

CREATE VIEW IF NOT EXISTS v_student_progress AS
SELECT e.enrollment_id,
       e.student_id,
       s.full_name AS student,
       s.email,
       e.course_id,
       c.title AS course,
       e.status AS enrollment_status,
       e.enrolled_at,
       (SELECT COUNT(*) FROM lesson_progress lp
         WHERE lp.enrollment_id = e.enrollment_id) AS lessons_done,
       (SELECT COUNT(*) FROM modules m
         JOIN lessons l ON l.module_id = m.module_id
        WHERE m.course_id = c.course_id) AS lessons_total
  FROM enrollments e
  JOIN students s ON s.student_id = e.student_id
  JOIN courses c ON c.course_id = e.course_id;

CREATE VIEW IF NOT EXISTS v_assessment_results AS
SELECT sub.submission_id,
       sub.assessment_id,
       a.title AS assessment,
       a.kind,
       a.weight,
       a.max_score,
       a.course_id,
       c.title AS course,
       sub.student_id,
       s.full_name AS student,
       sub.score,
       CASE WHEN sub.score IS NULL THEN NULL
            ELSE ROUND(sub.score * 100.0 / a.max_score, 1) END AS percent,
       sub.submitted_at,
       sub.graded_at
  FROM submissions sub
  JOIN assessments a ON a.assessment_id = sub.assessment_id
  JOIN courses c ON c.course_id = a.course_id
  JOIN students s ON s.student_id = sub.student_id;
