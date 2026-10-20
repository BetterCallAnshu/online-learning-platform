"""Demo data for the Online Learning Platform.

Run `python main.py --reset` to wipe the database and rebuild this dataset.
"""

from security import hash_password
from services import (
    add_lesson,
    add_module,
    add_question,
    create_assessment,
    create_course,
    create_instructor,
    create_student,
    enroll,
    grade_submission,
    mark_lesson_complete,
    submit_assignment,
    take_quiz,
    update_course,
)

ADMIN_EMAIL = "admin@learnhub.io"
ADMIN_PASSWORD = "admin123"


def is_seeded(conn):
    return conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0] > 0


def _build_course(conn, instructor_id, title, description, category, level, price,
                  content, status="Published"):
    course_id = create_course(
        conn, instructor_id, title, description, category, level, price, status
    )
    lesson_ids = []
    for module_title, lessons in content:
        module_id = add_module(conn, course_id, module_title)
        for lesson_title, content_type, url, duration in lessons:
            lesson_ids.append(
                add_lesson(conn, module_id, lesson_title, content_type, url, duration)
            )
    return course_id, lesson_ids


def _build_quiz(conn, course_id, title, questions, weight=1.0, due_date=None):
    assessment_id = create_assessment(
        conn, course_id, title, "quiz", max_score=100, weight=weight, due_date=due_date
    )
    question_ids = [
        add_question(conn, assessment_id, prompt, options, correct, points)
        for prompt, options, correct, points in questions
    ]
    return assessment_id, question_ids


def _answers(question_ids, letters):
    return {qid: letter for qid, letter in zip(question_ids, letters) if letter}


def seed(conn):
    if is_seeded(conn):
        return False

    conn.execute(
        "INSERT INTO admins (full_name, email, password_hash) VALUES (?, ?, ?)",
        ("Platform Admin", ADMIN_EMAIL, hash_password(ADMIN_PASSWORD)),
    )
    conn.commit()

    maya = create_instructor(
        conn, "Dr. Maya Chen", "maya@learnhub.io", "instructor123",
        "Python, Data Science, Machine Learning",
    )
    alan = create_instructor(
        conn, "Alan Reid", "alan@learnhub.io", "instructor123",
        "HTML, CSS, JavaScript",
    )
    priya = create_instructor(
        conn, "Priya Nair", "priya@learnhub.io", "instructor123",
        "SQL, Database Design, Cloud",
    )

    students = {}
    for name, email in (
        ("Sam Carter", "sam@student.io"),
        ("Lena Ortiz", "lena@student.io"),
        ("Tom Baker", "tom@student.io"),
        ("Rina Patel", "rina@student.io"),
        ("Diego Silva", "diego@student.io"),
        ("Ava Kim", "ava@student.io"),
    ):
        students[email] = create_student(conn, name, email, "student123")

    # -- Course 1: Python for Data Analysis --------------------------------
    c1, c1_lessons = _build_course(
        conn, maya,
        "Python for Data Analysis",
        "Go from Python basics to cleaning, exploring and visualising real datasets.",
        "Data Science", "Beginner", 49.0,
        [
            ("Getting Started", [
                ("Installing Python and Jupyter", "reading", "https://learnhub.example/py/setup", 20),
                ("Python Refresher", "video", "https://learnhub.example/py/refresher", 35),
            ]),
            ("Working with Data", [
                ("NumPy Arrays", "video", "https://learnhub.example/py/numpy", 45),
                ("Pandas DataFrames", "video", "https://learnhub.example/py/pandas", 50),
                ("Cleaning Messy Data", "exercise", "https://learnhub.example/py/cleaning", 30),
            ]),
            ("Analysis in Practice", [
                ("Exploratory Data Analysis", "video", "https://learnhub.example/py/eda", 40),
                ("Final Project Walkthrough", "video", "https://learnhub.example/py/project", 25),
            ]),
        ],
    )
    c1_quiz, c1_qids = _build_quiz(
        conn, c1, "Python and Pandas Check",
        [
            ("Which library provides the DataFrame structure?",
             ["NumPy", "Pandas", "Matplotlib", "Seaborn"], "B", 2),
            ("Which function reads a CSV file into a DataFrame?",
             ["read_csv", "load_csv", "open_csv", "csv_read"], "A", 2),
            ("How are missing numeric values usually represented in pandas?",
             ["0", "The text NULL", "NaN", "An empty string"], "C", 2),
            ("What does df.head() return by default?",
             ["The first five rows", "The last five rows", "Column names only",
              "The DataFrame shape"], "A", 2),
            ("Which method removes rows that contain missing values?",
             ["fillna", "dropna", "replace", "isnull"], "B", 2),
        ],
        weight=1.0, due_date="2026-11-15",
    )
    c1_assignment = create_assessment(
        conn, c1, "Data Cleaning Project", "assignment", max_score=100, weight=2.0,
        due_date="2026-11-30",
        instructions="Clean the provided sales dataset and explain each cleaning step.",
    )

    # -- Course 2: Modern Web Development ----------------------------------
    c2, c2_lessons = _build_course(
        conn, alan,
        "Modern Web Development",
        "Build responsive websites with semantic HTML, modern CSS and JavaScript.",
        "Web Development", "Intermediate", 79.0,
        [
            ("HTML and CSS Foundations", [
                ("Semantic HTML", "reading", "https://learnhub.example/web/html", 25),
                ("Flexbox Layouts", "video", "https://learnhub.example/web/flexbox", 40),
            ]),
            ("JavaScript Essentials", [
                ("DOM Basics", "video", "https://learnhub.example/web/dom", 35),
                ("Events and Forms", "exercise", "https://learnhub.example/web/events", 30),
            ]),
            ("Shipping Your Site", [
                ("Responsive Design", "reading", "https://learnhub.example/web/responsive", 25),
                ("Deploying with Netlify", "video", "https://learnhub.example/web/deploy", 20),
            ]),
        ],
    )
    c2_quiz, c2_qids = _build_quiz(
        conn, c2, "HTML and CSS Basics",
        [
            ("Which tag creates the largest heading?",
             ["<head>", "<h1>", "<header>", "<title>"], "B", 2),
            ("Which CSS property sets the text colour?",
             ["font-style", "background", "color", "text-align"], "C", 2),
            ("What is the default flex-direction?",
             ["row", "column", "row-reverse", "wrap"], "A", 2),
            ("What does document.querySelector return?",
             ["The first matching element", "All matching elements",
              "An HTML string", "A boolean"], "A", 2),
        ],
        weight=1.0, due_date="2026-11-20",
    )
    c2_assignment = create_assessment(
        conn, c2, "Landing Page Build", "assignment", max_score=100, weight=2.0,
        due_date="2026-12-05",
        instructions="Build a responsive landing page and submit a link plus a short write-up.",
    )

    # -- Course 3: SQL and Database Design ---------------------------------
    c3, c3_lessons = _build_course(
        conn, priya,
        "SQL and Database Design",
        "Learn relational modelling, joins, aggregation and schema normalisation.",
        "Databases", "Beginner", 39.0,
        [
            ("Relational Foundations", [
                ("Tables, Rows and Keys", "reading", "https://learnhub.example/sql/tables", 20),
                ("Writing SELECT Queries", "video", "https://learnhub.example/sql/select", 35),
            ]),
            ("Joins and Aggregates", [
                ("INNER and LEFT JOIN", "video", "https://learnhub.example/sql/joins", 40),
                ("GROUP BY and HAVING", "video", "https://learnhub.example/sql/group", 30),
            ]),
            ("Schema Design", [
                ("Normalisation: 1NF to 3NF", "reading", "https://learnhub.example/sql/normal", 30),
                ("Indexing Basics", "reading", "https://learnhub.example/sql/indexes", 25),
            ]),
        ],
    )
    c3_quiz, c3_qids = _build_quiz(
        conn, c3, "SQL Joins Quiz",
        [
            ("Which join keeps every row from the left table?",
             ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"], "B", 2.5),
            ("Which clause filters grouped rows?",
             ["WHERE", "HAVING", "ORDER BY", "LIMIT"], "B", 2.5),
            ("Which property must a primary key have?",
             ["It may be null", "Unique and not null",
              "Duplicate values are allowed", "It must be text"], "B", 2.5),
            ("Third normal form removes which dependencies?",
             ["Duplicate rows", "Partial and transitive dependencies",
              "Indexes", "Views"], "B", 2.5),
        ],
        weight=1.0, due_date="2026-11-18",
    )
    c3_assignment = create_assessment(
        conn, c3, "Design a Normalised Schema", "assignment", max_score=100, weight=2.0,
        due_date="2026-12-10",
        instructions="Model a library system in 3NF and submit your CREATE TABLE statements.",
    )

    # -- Course 4: draft course --------------------------------------------
    _build_course(
        conn, maya,
        "Machine Learning Foundations",
        "A forthcoming introduction to supervised and unsupervised learning.",
        "Data Science", "Advanced", 99.0,
        [
            ("Foundations", [
                ("What is Machine Learning?", "reading", "https://learnhub.example/ml/intro", 20),
                ("Supervised vs Unsupervised", "video", "https://learnhub.example/ml/types", 30),
            ]),
        ],
        status="Draft",
    )

    # -- Enrollments and lesson progress -----------------------------------
    plans = [
        ("sam@student.io", c1, 3),
        ("sam@student.io", c3, 2),
        ("lena@student.io", c1, 4),
        ("lena@student.io", c2, 2),
        ("tom@student.io", c3, 3),
        ("rina@student.io", c1, 7),
        ("rina@student.io", c2, 3),
        ("rina@student.io", c3, 4),
        ("diego@student.io", c2, 5),
        ("ava@student.io", c1, 2),
    ]
    lessons_by_course = {c1: c1_lessons, c2: c2_lessons, c3: c3_lessons}
    for email, course_id, completed in plans:
        # Enroll twice on purpose is avoided: the plans list has unique pairs.
        enroll(conn, students[email], course_id)
        for lesson_id in lessons_by_course[course_id][:completed]:
            mark_lesson_complete(conn, students[email], lesson_id)

    # -- Quizzes (auto-graded) ---------------------------------------------
    take_quiz(conn, students["sam@student.io"], c1_quiz,
              _answers(c1_qids, ["B", "A", "C", "A", "B"]))
    take_quiz(conn, students["lena@student.io"], c1_quiz,
              _answers(c1_qids, ["B", "C", "C", "A", "B"]))
    take_quiz(conn, students["rina@student.io"], c1_quiz,
              _answers(c1_qids, ["B", "A", "C", "A", "B"]))
    take_quiz(conn, students["ava@student.io"], c1_quiz,
              _answers(c1_qids, ["C", "A", "C", "B", "B"]))

    take_quiz(conn, students["lena@student.io"], c2_quiz,
              _answers(c2_qids, ["B", "C", "B", "A"]))
    take_quiz(conn, students["diego@student.io"], c2_quiz,
              _answers(c2_qids, ["B", "C", "A", "A"]))
    take_quiz(conn, students["rina@student.io"], c2_quiz,
              _answers(c2_qids, ["B", "B", "A", "A"]))

    take_quiz(conn, students["tom@student.io"], c3_quiz,
              _answers(c3_qids, ["A", "B", "B", "A"]))
    take_quiz(conn, students["rina@student.io"], c3_quiz,
              _answers(c3_qids, ["B", "B", "B", "B"]))
    take_quiz(conn, students["sam@student.io"], c3_quiz,
              _answers(c3_qids, ["B", "B", "A", "D"]))

    # -- Assignments --------------------------------------------------------
    sid, _ = submit_assignment(
        conn, students["sam@student.io"], c1_assignment,
        "I removed duplicate order rows, filled missing quantities with the median, "
        "and converted dates to ISO format before computing monthly revenue.",
    )
    grade_submission(conn, sid, 92, "Clear explanation and correct handling of dates.")

    sid, _ = submit_assignment(
        conn, students["rina@student.io"], c1_assignment,
        "The dataset had 312 duplicate rows. I dropped them, normalised currency text, "
        "and documented every transformation in a notebook with before/after samples.",
    )
    grade_submission(conn, sid, 95, "Excellent, well-documented cleaning pipeline.")

    sid, _ = submit_assignment(
        conn, students["lena@student.io"], c2_assignment,
        "My landing page uses flexbox and two media queries. It passes the mobile and "
        "desktop layout checks and is deployed on Netlify at the link in my notes.",
    )
    grade_submission(conn, sid, 85, "Nice responsive layout; tighten the heading spacing.")

    submit_assignment(
        conn, students["diego@student.io"], c2_assignment,
        "I built a three-section landing page with a sticky header and a responsive "
        "pricing grid. Deployment link: learnhub-demo.example.netlify.app",
    )
    submit_assignment(
        conn, students["ava@student.io"], c1_assignment,
        "I investigated missing values in the sales dataset and compared mean versus "
        "median imputation for the quantity column.",
    )

    sid, _ = submit_assignment(
        conn, students["rina@student.io"], c3_assignment,
        "I modelled books, authors, members and loans with bridge tables. The schema is "
        "in 3NF and includes foreign keys with ON DELETE rules for each relationship.",
    )
    grade_submission(conn, sid, 90, "Solid model; consider a separate fines table.")

    submit_assignment(
        conn, students["tom@student.io"], c3_assignment,
        "My schema uses four tables: members, books, loans and fines. I described the "
        "primary keys and the foreign key from loans to both members and books.",
    )

    return True
