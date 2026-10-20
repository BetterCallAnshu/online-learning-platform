"""Command line interface for the Online Learning Platform."""

import csv
import re
from datetime import datetime
from pathlib import Path

import reports
import services
from services import ServiceError

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "exports"
LINE = "=" * 78


# ---------------------------------------------------------------------------
# Input and display helpers
# ---------------------------------------------------------------------------

def header(title):
    print(f"\n{LINE}\n{title}\n{LINE}")


def ask(prompt, default=None):
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw:
            return raw
        if default is not None:
            return default
        print("This field is required.")


def ask_optional(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw if raw else default


def ask_password(prompt="Password"):
    # Plain input so password entry works in every terminal/IDE. The value is
    # still stored only as a salted PBKDF2 hash.
    return input(f"{prompt}: ").strip()


def ask_int(prompt, minimum=None, maximum=None, default=None):
    while True:
        raw = ask(prompt, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            print("Enter a whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Enter a number >= {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"Enter a number <= {maximum}.")
            continue
        return value


def ask_float(prompt, minimum=None, maximum=None, default=None):
    while True:
        raw = ask(prompt, default)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            print("Enter a number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Enter a number >= {minimum:g}.")
            continue
        if maximum is not None and value > maximum:
            print(f"Enter a number <= {maximum:g}.")
            continue
        return value


def ask_choice(prompt, choices, default=None):
    while True:
        raw = ask(f"{prompt} ({'/'.join(choices)})", default)
        for choice in choices:
            if str(choice).lower() == str(raw).lower():
                return choice
        print("Choose one of: " + ", ".join(map(str, choices)))


def confirm(prompt, default="n"):
    return ask(f"{prompt} (y/n)", default).lower().startswith("y")


def menu(items, prompt="Select an option"):
    for index, item in enumerate(items, 1):
        print(f"  {index}. {item}")
    while True:
        raw = input(f"{prompt}: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return int(raw)
        print("Invalid choice.")


def choose_row(rows, label, prompt="Select a row (0 to cancel)"):
    for index, row in enumerate(rows, 1):
        print(f"{index:>3}. {label(row)}")
    while True:
        raw = input(f"{prompt}: ").strip()
        if raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1]
        print("Invalid selection.")


def _cell(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:.1f}"
    text = str(value)
    if len(text) >= 19 and text[4:5] == "-" and text[10:11] == " ":
        return text[:10]
    if len(text) > 60:
        return text[:57] + "..."
    return text


def print_table(headers, rows):
    rows = [list(row) for row in rows]
    if not rows:
        print("(no records)")
        return
    data = [[_cell(value) for value in row] for row in rows]
    widths = []
    for index, title in enumerate(headers):
        widths.append(max(len(str(title)), *(len(row[index]) for row in data)))
    print("  ".join(str(title).ljust(widths[index]) for index, title in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in data:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def pause():
    input("\nPress Enter to continue...")


def money(value):
    return f"${value:,.2f}"


def scalar(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def export_csv(name, headers, rows):
    EXPORT_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    path = EXPORT_DIR / f"{slug}-{datetime.now():%Y%m%d-%H%M%S}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows([list(row) for row in rows])
    print(f"Exported to {path}")


# ---------------------------------------------------------------------------
# Entry point and authentication
# ---------------------------------------------------------------------------

def run(conn):
    while True:
        header("ONLINE LEARNING PLATFORM")
        choice = menu(["Log in", "Register as a student", "Exit"])
        if choice == 1:
            user = login(conn)
            if not user:
                continue
            if user["role"] == "student":
                student_menu(conn, user)
            elif user["role"] == "instructor":
                instructor_menu(conn, user)
            else:
                admin_menu(conn, user)
        elif choice == 2:
            register_student(conn)
        else:
            print("Goodbye.")
            return


def login(conn):
    header("Log in")
    email = ask("Email")
    password = ask_password()
    user = services.authenticate(conn, email, password)
    if not user:
        print("Invalid email or password.")
        pause()
        return None
    print(f"\nWelcome, {user['name']} ({user['role']}).")
    return user


def register_student(conn):
    header("Create a student account")
    name = ask("Full name")
    email = ask("Email")
    password = ask_password()
    try:
        student_id = services.create_student(conn, name, email, password)
    except ServiceError as error:
        print(f"Error: {error}")
        pause()
        return
    print(f"\nAccount created (student id {student_id}). You can log in now.")
    pause()


# ---------------------------------------------------------------------------
# Student portal
# ---------------------------------------------------------------------------

def student_menu(conn, user):
    while True:
        header(f"Student portal - {user['name']}")
        choice = menu([
            "Browse the course catalog",
            "My courses",
            "Open a course",
            "My grades and transcript",
            "Update my profile",
            "Log out",
        ])
        if choice == 1:
            browse_catalog(conn, user)
        elif choice == 2:
            show_my_courses(conn, user)
        elif choice == 3:
            open_course(conn, user)
        elif choice == 4:
            show_my_grades(conn, user)
        elif choice == 5:
            update_profile(conn, user)
        else:
            return


def browse_catalog(conn, user):
    header("Course catalog")
    search = ask_optional("Search by title, description or instructor")
    categories = services.list_categories(conn)
    if categories:
        print("Categories: " + ", ".join(categories))
    category = ask_optional("Filter by category")
    courses = services.list_courses(conn, search, category, status="Published")
    if not courses:
        print("No published courses matched your search.")
        pause()
        return
    print_table(
        ["Course", "Instructor", "Category", "Level", "Price", "Learners"],
        [(c["title"], c["instructor"], c["category"], c["level"],
          money(c["price"]), c["enrolled"]) for c in courses],
    )
    course = choose_row(courses, lambda c: f"{c['title']} - {c['instructor']}")
    if not course:
        return
    show_course_detail(conn, course["course_id"])
    enrollment = services.get_enrollment(conn, user["id"], course["course_id"])
    if enrollment and enrollment["status"] != "Dropped":
        print(f"\nYou are already enrolled ({enrollment['status']}).")
        pause()
        return
    if confirm("\nEnroll in this course?"):
        try:
            services.enroll(conn, user["id"], course["course_id"])
            print("Enrolled. Open the course from 'My courses' to start learning.")
        except ServiceError as error:
            print(f"Error: {error}")
    pause()


def show_course_detail(conn, course_id):
    course = services.get_course(conn, course_id)
    header(course["title"])
    print(f"Instructor : {course['instructor']}")
    print(f"Category   : {course['category']} | Level: {course['level']} | "
          f"Price: {money(course['price'])} | Status: {course['status']}")
    print(f"\n{course['description']}")
    curriculum = services.get_curriculum(conn, course_id)
    assessments = services.list_assessments(conn, course_id)
    print(f"\nCurriculum ({services.count_lessons(conn, course_id)} lessons, "
          f"{len(assessments)} assessments):")
    for entry in curriculum:
        module = entry["module"]
        print(f"  Module {module['position']}: {module['title']} "
              f"({len(entry['lessons'])} lessons)")
        for lesson in entry["lessons"]:
            print(f"      - {lesson['title']} ({lesson['content_type']}, "
                  f"{lesson['duration_min']} min)")


def show_my_courses(conn, user):
    header("My courses")
    courses = services.my_courses(conn, user["id"])
    if not courses:
        print("You are not enrolled in any courses yet.")
        pause()
        return
    rows = []
    for course in courses:
        percent = services.progress_percent(course["done_lessons"], course["total_lessons"])
        rows.append((
            course["title"], course["instructor"], course["level"],
            course["enrollment_status"],
            f"{percent}% ({course['done_lessons']}/{course['total_lessons']})",
            course["enrolled_at"],
        ))
    print_table(["Course", "Instructor", "Level", "Status", "Progress", "Enrolled"], rows)
    pause()


def open_course(conn, user):
    courses = services.my_courses(conn, user["id"])
    if not courses:
        print("You are not enrolled in any courses yet.")
        pause()
        return

    def label(course):
        percent = services.progress_percent(course["done_lessons"], course["total_lessons"])
        return f"{course['title']} - {percent}% complete"

    header("Open a course")
    course = choose_row(courses, label)
    if not course:
        return
    enrollment = services.get_enrollment(conn, user["id"], course["course_id"])
    while True:
        done = len(services.completed_lesson_ids(conn, enrollment["enrollment_id"]))
        total = services.count_lessons(conn, course["course_id"])
        percent = services.progress_percent(done, total)
        header(f"{course['title']} - {percent}% complete")
        choice = menu([
            "View lessons",
            "Mark a lesson complete",
            "Mark a lesson incomplete",
            "Assessments and submissions",
            "Back",
        ])
        if choice == 1:
            show_lessons(conn, course["course_id"], enrollment["enrollment_id"])
            pause()
        elif choice == 2:
            mark_lesson(conn, user, course, enrollment, complete=True)
        elif choice == 3:
            mark_lesson(conn, user, course, enrollment, complete=False)
        elif choice == 4:
            student_assessments(conn, user, course)
        else:
            return


def show_lessons(conn, course_id, enrollment_id):
    completed = services.completed_lesson_ids(conn, enrollment_id)
    curriculum = services.get_curriculum(conn, course_id)
    if not curriculum:
        print("This course has no content yet.")
        return
    print()
    for entry in curriculum:
        module = entry["module"]
        print(f"Module {module['position']}: {module['title']}")
        for lesson in entry["lessons"]:
            mark = "[x]" if lesson["lesson_id"] in completed else "[ ]"
            print(f"  {mark} #{lesson['lesson_id']:<3} {lesson['title']} "
                  f"({lesson['content_type']}, {lesson['duration_min']} min)")
            if lesson["content_url"]:
                print(f"          {lesson['content_url']}")
        print()


def mark_lesson(conn, user, course, enrollment, complete):
    show_lessons(conn, course["course_id"], enrollment["enrollment_id"])
    lessons = all_lessons(conn, course["course_id"])
    if not lessons:
        print("There are no lessons to update.")
        pause()
        return
    lesson = choose_row(
        lessons, lambda l: f"#{l['lesson_id']} {l['title']} ({l['content_type']})"
    )
    if not lesson:
        return
    try:
        if complete:
            created = services.mark_lesson_complete(conn, user["id"], lesson["lesson_id"])
            print("Lesson marked complete." if created else "That lesson was already complete.")
        else:
            services.mark_lesson_incomplete(conn, user["id"], lesson["lesson_id"])
            print("Lesson marked incomplete.")
    except ServiceError as error:
        print(f"Error: {error}")
    pause()


def all_lessons(conn, course_id):
    return [
        lesson
        for entry in services.get_curriculum(conn, course_id)
        for lesson in entry["lessons"]
    ]


def student_assessments(conn, user, course):
    while True:
        header(f"Assessments - {course['title']}")
        assessments = services.list_assessments(conn, course["course_id"])
        if not assessments:
            print("This course has no assessments yet.")
            pause()
            return
        table_rows = []
        for a in assessments:
            submission = services.get_submission(
                conn, user["id"], a["assessment_id"]
            )
            if submission is None:
                mine = "-"
            elif submission["score"] is None:
                mine = "pending"
            else:
                mine = f"{submission['score']:g}/{a['max_score']:g}"
            table_rows.append(
                (a["assessment_id"], a["title"], a["kind"], a["max_score"],
                 a["weight"], a["due_date"], a["question_count"], mine)
            )
        print_table(
            ["ID", "Assessment", "Type", "Max", "Weight", "Due", "Questions", "My Score"],
            table_rows,
        )
        choice = menu(["Open an assessment", "Back"])
        if choice == 2:
            return
        assessment = choose_row(
            assessments,
            lambda a: f"{a['title']} ({a['kind']}, due {a['due_date'] or 'open'})",
        )
        if not assessment:
            continue
        if assessment["kind"] == "quiz":
            take_quiz_ui(conn, user, assessment)
        else:
            submit_assignment_ui(conn, user, assessment)


def take_quiz_ui(conn, user, assessment):
    header(assessment["title"])
    submission = services.get_submission(conn, user["id"], assessment["assessment_id"])
    if submission:
        print(f"Already submitted. Score: {submission['score']:g} / "
              f"{assessment['max_score']:g}.")
        if confirm("Review your answers?"):
            show_quiz_review(conn, submission["submission_id"])
            pause()
        else:
            pause()
        return
    questions = services.list_questions(conn, assessment["assessment_id"])
    if not questions:
        print("This quiz has no questions yet.")
        pause()
        return
    if assessment["instructions"]:
        print(assessment["instructions"])
    print(f"{len(questions)} questions | max score {assessment['max_score']:g} | "
          f"due {assessment['due_date'] or 'open'}")
    answers = {}
    for index, question in enumerate(questions, 1):
        print(f"\nQ{index}. {question['prompt']} ({question['points']:g} pts)")
        for letter, option in zip(
            "ABCD",
            (question["option_a"], question["option_b"],
             question["option_c"], question["option_d"]),
        ):
            print(f"   {letter}) {option}")
        while True:
            answer = input("Answer (A-D, blank to skip): ").strip().upper()
            if answer in ("", "A", "B", "C", "D"):
                break
            print("Enter A, B, C, D or leave blank.")
        if answer:
            answers[question["question_id"]] = answer
    if not confirm("\nSubmit this quiz?"):
        print("Quiz not submitted.")
        pause()
        return
    try:
        result = services.take_quiz(conn, user["id"], assessment["assessment_id"], answers)
    except ServiceError as error:
        print(f"Error: {error}")
        pause()
        return
    print(f"\nSubmitted. Score: {result['score']:g} / {result['max_score']:g} "
          f"({result['correct']}/{result['total']} correct).")
    if confirm("Review the correct answers?"):
        show_quiz_review(conn, result["submission_id"])
    pause()


def show_quiz_review(conn, submission_id):
    rows = services.get_answer_review(conn, submission_id)
    print_table(
        ["Question", "Your answer", "Correct", "Result"],
        [(r["prompt"], r["selected_option"], r["correct_option"],
          "correct" if r["is_correct"] else "wrong") for r in rows],
    )


def submit_assignment_ui(conn, user, assessment):
    header(assessment["title"])
    submission = services.get_submission(conn, user["id"], assessment["assessment_id"])
    if submission and submission["score"] is not None:
        print(f"Graded: {submission['score']:g} / {assessment['max_score']:g}")
        if submission["feedback"]:
            print(f"Feedback: {submission['feedback']}")
        pause()
        return
    if assessment["instructions"]:
        print(assessment["instructions"])
    print(f"\nMax score: {assessment['max_score']:g} | "
          f"Due: {assessment['due_date'] or 'open'}")
    if submission:
        print("\nYour current pending submission:")
        print(submission["content"])
        print("\nYou may resubmit until the assignment is graded.")
    print("\nWrite your submission. Finish with a single '.' on its own line.")
    print("Press Enter on an empty line to cancel.")
    lines = []
    while True:
        line = input("> ")
        if line.strip() == ".":
            break
        if not lines and not line.strip():
            lines = []
            break
        lines.append(line)
    content = "\n".join(lines).strip()
    if not content:
        print("Submission cancelled.")
        pause()
        return
    try:
        _, created = services.submit_assignment(
            conn, user["id"], assessment["assessment_id"], content
        )
    except ServiceError as error:
        print(f"Error: {error}")
        pause()
        return
    print("Assignment submitted." if created else "Submission updated.")
    print("It will appear in your grades once your instructor grades it.")
    pause()


def show_my_grades(conn, user):
    header("My grades and transcript")
    grades = services.student_grades(conn, user["id"])
    if not grades:
        print("You have no submissions yet.")
        pause()
        return
    print_table(
        ["Course", "Assessment", "Type", "Score", "Max", "Percent", "Feedback"],
        [(g["course"], g["assessment"], g["kind"], g["score"], g["max_score"],
          None if g["score"] is None else round(g["score"] * 100 / g["max_score"], 1),
          g["feedback"]) for g in grades],
    )
    averages = services.course_averages(conn, user["id"])
    if averages:
        print("\nWeighted course averages (graded work only):")
        print_table(
            ["Course", "Average %"],
            [(row["course"], row["average"]) for row in averages],
        )
    pause()


def update_profile(conn, user):
    header("Update my profile")
    current = conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (user["id"],)
    ).fetchone()
    name = ask("Full name", current["full_name"])
    email = ask("Email", current["email"])
    try:
        services.update_student_profile(conn, user["id"], name, email)
    except ServiceError as error:
        print(f"Error: {error}")
        pause()
        return
    user["name"] = name
    user["email"] = email
    print("Profile updated.")
    pause()


# ---------------------------------------------------------------------------
# Instructor portal
# ---------------------------------------------------------------------------

def instructor_menu(conn, user):
    while True:
        header(f"Instructor portal - {user['name']}")
        choice = menu([
            "My courses",
            "Manage course content",
            "Manage assessments",
            "Grade submissions",
            "Course analytics",
            "Log out",
        ])
        if choice == 1:
            list_instructor_courses(conn, user)
        elif choice == 2:
            course = pick_instructor_course(conn, user)
            if course:
                manage_content(conn, course)
        elif choice == 3:
            course = pick_instructor_course(conn, user)
            if course:
                manage_assessments(conn, course)
        elif choice == 4:
            grading_center(conn, user)
        elif choice == 5:
            course = pick_instructor_course(conn, user)
            if course:
                course_analytics(conn, course)
        else:
            return


def list_instructor_courses(conn, user):
    header("My courses")
    courses = [c for c in services.list_courses(conn) if c["instructor_id"] == user["id"]]
    if not courses:
        print("You do not have any courses yet. Ask an administrator to assign one.")
        pause()
        return
    print_table(
        ["ID", "Course", "Category", "Level", "Price", "Status", "Learners", "Lessons"],
        [(c["course_id"], c["title"], c["category"], c["level"], money(c["price"]),
          c["status"], c["enrolled"], c["lessons"]) for c in courses],
    )
    pause()


def pick_instructor_course(conn, user):
    courses = [c for c in services.list_courses(conn) if c["instructor_id"] == user["id"]]
    if not courses:
        print("You do not have any courses yet.")
        pause()
        return None
    header("Choose a course")
    return choose_row(
        courses,
        lambda c: f"{c['title']} ({c['status']}, {c['enrolled']} learners)",
    )


def manage_content(conn, course):
    while True:
        header(f"Manage content - {course['title']}")
        curriculum = services.get_curriculum(conn, course["course_id"])
        if not curriculum:
            print("No modules yet.")
        for entry in curriculum:
            module = entry["module"]
            print(f"Module {module['position']}: {module['title']}")
            for lesson in entry["lessons"]:
                print(f"   #{lesson['lesson_id']:<3} {lesson['title']} "
                      f"({lesson['content_type']}, {lesson['duration_min']} min)")
        choice = menu([
            "Add a module",
            "Add a lesson",
            "Edit a lesson",
            "Delete a lesson",
            "Delete a module",
            "Back",
        ])
        if choice == 1:
            title = ask("Module title")
            try:
                services.add_module(conn, course["course_id"], title)
                print("Module added.")
            except ServiceError as error:
                print(f"Error: {error}")
            pause()
        elif choice == 2:
            if not curriculum:
                print("Add a module first.")
                pause()
                continue
            modules = [entry["module"] for entry in curriculum]
            module = choose_row(modules, lambda m: f"Module {m['position']}: {m['title']}")
            if not module:
                continue
            title = ask("Lesson title")
            content_type = ask_choice(
                "Content type", services.CONTENT_TYPES, "reading"
            )
            url = ask_optional("Content URL")
            duration = ask_int("Duration (minutes)", minimum=0, default=10)
            try:
                services.add_lesson(
                    conn, module["module_id"], title, content_type, url, duration
                )
                print("Lesson added.")
            except ServiceError as error:
                print(f"Error: {error}")
            pause()
        elif choice == 3:
            lessons = all_lessons(conn, course["course_id"])
            lesson = choose_row(
                lessons, lambda l: f"#{l['lesson_id']} {l['title']}"
            ) if lessons else None
            if not lesson:
                print("No lessons available.")
                pause()
                continue
            title = ask("Title", lesson["title"])
            content_type = ask_choice(
                "Content type", services.CONTENT_TYPES, lesson["content_type"]
            )
            url = ask_optional("Content URL", lesson["content_url"])
            duration = ask_int(
                "Duration (minutes)", minimum=0, default=lesson["duration_min"]
            )
            try:
                services.update_lesson(
                    conn, lesson["lesson_id"], title=title,
                    content_type=content_type, content_url=url,
                    duration_min=duration,
                )
                print("Lesson updated.")
            except ServiceError as error:
                print(f"Error: {error}")
            pause()
        elif choice == 4:
            lessons = all_lessons(conn, course["course_id"])
            lesson = choose_row(
                lessons, lambda l: f"#{l['lesson_id']} {l['title']}"
            ) if lessons else None
            if lesson and confirm(f"Delete '{lesson['title']}'?"):
                services.delete_lesson(conn, lesson["lesson_id"])
                print("Lesson deleted.")
            pause()
        elif choice == 5:
            modules = [entry["module"] for entry in curriculum]
            module = choose_row(modules, lambda m: f"{m['title']}") if modules else None
            if module and confirm(f"Delete module '{module['title']}' and its lessons?"):
                services.delete_module(conn, module["module_id"])
                print("Module deleted.")
            pause()
        else:
            return


def manage_assessments(conn, course):
    while True:
        header(f"Manage assessments - {course['title']}")
        assessments = services.list_assessments(conn, course["course_id"])
        print_table(
            ["ID", "Assessment", "Type", "Max", "Weight", "Due", "Questions", "Submissions"],
            [(a["assessment_id"], a["title"], a["kind"], a["max_score"], a["weight"],
              a["due_date"], a["question_count"], a["submission_count"])
             for a in assessments],
        )
        choice = menu([
            "Create an assessment",
            "Add quiz questions",
            "Preview quiz questions",
            "View course gradebook",
            "Back",
        ])
        if choice == 1:
            create_assessment_ui(conn, course)
        elif choice == 2:
            quizzes = [a for a in assessments if a["kind"] == "quiz"]
            if not quizzes:
                print("Create a quiz first.")
                pause()
                continue
            assessment = choose_row(quizzes, lambda a: a["title"])
            if assessment:
                add_questions_ui(conn, assessment)
        elif choice == 3:
            quizzes = [a for a in assessments if a["kind"] == "quiz"]
            assessment = choose_row(quizzes, lambda a: a["title"]) if quizzes else None
            if assessment:
                preview_questions(conn, assessment)
        elif choice == 4:
            show_gradebook(conn, course)
        else:
            return


def create_assessment_ui(conn, course):
    header("Create an assessment")
    title = ask("Title")
    kind = ask_choice("Type", ("quiz", "assignment"), "quiz")
    weight = ask_float("Weight", minimum=0.1, default=1.0)
    due = ask_optional("Due date (YYYY-MM-DD)")
    instructions = ask_optional("Instructions")
    max_score = 100.0
    if kind == "assignment":
        max_score = ask_float("Max score", minimum=1, default=100)
    try:
        assessment_id = services.create_assessment(
            conn, course["course_id"], title, kind, max_score, weight, due, instructions
        )
    except ServiceError as error:
        print(f"Error: {error}")
        pause()
        return
    print(f"Assessment created (#{assessment_id}).")
    pause()


def add_questions_ui(conn, assessment):
    header(f"Add questions - {assessment['title']}")
    while True:
        prompt = ask("Question prompt")
        options = []
        for letter in "ABCD":
            options.append(ask(f"Option {letter}"))
        correct = ask_choice("Correct option", ("A", "B", "C", "D"))
        points = ask_float("Points", minimum=0.1, default=1)
        try:
            services.add_question(conn, assessment["assessment_id"], prompt, options,
                                  correct, points)
            print("Question added.")
        except ServiceError as error:
            print(f"Error: {error}")
        if not confirm("Add another question?"):
            return


def preview_questions(conn, assessment):
    header(f"Questions - {assessment['title']}")
    questions = services.list_questions(conn, assessment["assessment_id"])
    if not questions:
        print("No questions yet.")
        pause()
        return
    for index, question in enumerate(questions, 1):
        print(f"\nQ{index}. {question['prompt']} ({question['points']:g} pts)")
        for letter, option in zip(
            "ABCD",
            (question["option_a"], question["option_b"],
             question["option_c"], question["option_d"]),
        ):
            marker = "*" if letter == question["correct_option"] else " "
            print(f" {marker} {letter}) {option}")
    pause()


def show_gradebook(conn, course):
    header(f"Gradebook - {course['title']}")
    rows = services.course_gradebook(conn, course["course_id"])
    if not rows:
        print("No submissions yet.")
        pause()
        return
    print_table(
        ["Assessment", "Type", "Student", "Score", "Max", "Percent", "Graded"],
        [(r["assessment"], r["kind"], r["student"], r["score"], r["max_score"],
          r["percent"], r["graded_at"]) for r in rows],
    )
    pause()


def grading_center(conn, user):
    header("Grade submissions")
    pending = services.list_pending_grading(conn, user["id"])
    if not pending:
        print("Nothing is waiting to be graded.")
        pause()
        return
    print_table(
        ["ID", "Student", "Assessment", "Course", "Max", "Submitted"],
        [(p["submission_id"], p["student"], p["assessment"], p["course"],
          p["max_score"], p["submitted_at"]) for p in pending],
    )
    submission = choose_row(
        pending,
        lambda p: f"#{p['submission_id']} {p['student']} - {p['assessment']}",
    )
    if not submission:
        return
    header(f"Submission #{submission['submission_id']}")
    print(f"Student    : {submission['student']}")
    print(f"Assessment : {submission['assessment']} ({submission['course']})")
    print(f"Submitted  : {submission['submitted_at']}")
    print(f"\n{submission['content']}\n")
    score = ask_float(
        "Score", minimum=0, maximum=submission["max_score"]
    )
    feedback = ask_optional("Feedback")
    services.grade_submission(conn, submission["submission_id"], score, feedback)
    print("Submission graded.")
    pause()


def course_analytics(conn, course):
    header(f"Course analytics - {course['title']}")
    roster = services.course_roster(conn, course["course_id"])
    if roster:
        print_table(
            ["Student", "Email", "Status", "Progress", "Done", "Total", "Enrolled"],
            [(r["student"], r["email"], r["enrollment_status"],
              f"{services.progress_percent(r['lessons_done'], r['lessons_total'])}%",
              r["lessons_done"], r["lessons_total"], r["enrolled_at"])
             for r in roster],
        )
    else:
        print("No students enrolled yet.")
    headers, rows = reports.course_assessment_performance(conn, course["course_id"])
    print("\nAssessment performance:")
    print_table(headers, rows)
    pause()


# ---------------------------------------------------------------------------
# Admin portal
# ---------------------------------------------------------------------------

def admin_menu(conn, user):
    while True:
        header(f"Administration - {user['name']}")
        choice = menu([
            "Dashboard",
            "Manage courses",
            "Manage instructors",
            "Manage students",
            "Reports and exports",
            "Log out",
        ])
        if choice == 1:
            show_dashboard(conn)
        elif choice == 2:
            manage_courses(conn)
        elif choice == 3:
            manage_instructors(conn)
        elif choice == 4:
            manage_students(conn)
        elif choice == 5:
            reports_menu(conn)
        else:
            return


def show_dashboard(conn):
    header("Platform dashboard")
    metrics = [
        ("Students", scalar(conn, "SELECT COUNT(*) FROM students")),
        ("Instructors", scalar(conn, "SELECT COUNT(*) FROM instructors")),
        ("Courses", scalar(conn, "SELECT COUNT(*) FROM courses")),
        ("Published courses", scalar(conn, "SELECT COUNT(*) FROM courses WHERE status = 'Published'")),
        ("Enrollments", scalar(conn, "SELECT COUNT(*) FROM enrollments WHERE status IN ('Active','Completed')")),
        ("Completed enrollments", scalar(conn, "SELECT COUNT(*) FROM enrollments WHERE status = 'Completed'")),
        ("Submissions", scalar(conn, "SELECT COUNT(*) FROM submissions")),
        ("Waiting to be graded", scalar(conn, "SELECT COUNT(*) FROM submissions WHERE score IS NULL")),
        ("Gross revenue", money(scalar(
            conn,
            "SELECT COALESCE(SUM(c.price), 0) FROM enrollments e "
            "JOIN courses c ON c.course_id = e.course_id "
            "WHERE e.status IN ('Active','Completed')",
        ))),
    ]
    print_table(["Metric", "Value"], metrics)
    pause()


def manage_courses(conn):
    while True:
        header("Manage courses")
        courses = services.list_courses(conn)
        print_table(
            ["ID", "Course", "Instructor", "Category", "Level", "Price", "Status", "Learners"],
            [(c["course_id"], c["title"], c["instructor"], c["category"], c["level"],
              money(c["price"]), c["status"], c["enrolled"]) for c in courses],
        )
        choice = menu([
            "Create a course",
            "Edit a course",
            "Manage course content",
            "Manage assessments",
            "Back",
        ])
        if choice == 1:
            create_course_ui(conn)
        elif choice == 2:
            course = choose_row(courses, lambda c: f"{c['title']} ({c['status']})")
            if course:
                edit_course_ui(conn, course)
        elif choice == 3:
            course = choose_row(courses, lambda c: c["title"])
            if course:
                manage_content(conn, course)
        elif choice == 4:
            course = choose_row(courses, lambda c: c["title"])
            if course:
                manage_assessments(conn, course)
        else:
            return


def create_course_ui(conn):
    header("Create a course")
    instructors = services.list_instructors(conn)
    if not instructors:
        print("Create an instructor first.")
        pause()
        return
    instructor = choose_row(
        instructors, lambda i: f"{i['full_name']} ({i['expertise'] or 'no expertise listed'})"
    )
    if not instructor:
        return
    title = ask("Title")
    description = ask_optional("Description")
    category = ask_optional("Category", "General")
    level = ask_choice("Level", services.COURSE_LEVELS, "Beginner")
    price = ask_float("Price", minimum=0, default=0)
    status = ask_choice("Status", services.COURSE_STATUSES, "Draft")
    try:
        course_id = services.create_course(
            conn, instructor["instructor_id"], title, description,
            category, level, price, status,
        )
    except ServiceError as error:
        print(f"Error: {error}")
        pause()
        return
    print(f"Course created (#{course_id}).")
    pause()


def edit_course_ui(conn, course):
    header(f"Edit course - {course['title']}")
    title = ask("Title", course["title"])
    description = ask("Description", course["description"])
    category = ask("Category", course["category"])
    level = ask_choice("Level", services.COURSE_LEVELS, course["level"])
    price = ask_float("Price", minimum=0, default=f"{course['price']:g}")
    status = ask_choice("Status", services.COURSE_STATUSES, course["status"])
    try:
        services.update_course(
            conn, course["course_id"], title=title, description=description,
            category=category, level=level, price=price, status=status,
        )
    except ServiceError as error:
        print(f"Error: {error}")
        pause()
        return
    print("Course updated.")
    pause()


def manage_instructors(conn):
    while True:
        header("Manage instructors")
        instructors = services.list_instructors(conn)
        print_table(
            ["ID", "Instructor", "Email", "Expertise", "Courses", "Students"],
            [(i["instructor_id"], i["full_name"], i["email"], i["expertise"],
              i["courses"], i["students"]) for i in instructors],
        )
        choice = menu(["Add an instructor", "Back"])
        if choice == 2:
            return
        name = ask("Full name")
        email = ask("Email")
        expertise = ask_optional("Expertise")
        password = ask_password("Temporary password")
        try:
            instructor_id = services.create_instructor(
                conn, name, email, password, expertise
            )
        except ServiceError as error:
            print(f"Error: {error}")
            pause()
            continue
        print(f"Instructor created (#{instructor_id}). Share the temporary password securely.")
        pause()


def manage_students(conn):
    while True:
        header("Manage students")
        search = ask_optional("Search by name or email (blank for all)")
        students = services.list_students(conn, search)
        print_table(
            ["ID", "Student", "Email", "Courses", "Joined"],
            [(s["student_id"], s["full_name"], s["email"], s["courses"],
              s["joined_at"]) for s in students],
        )
        choice = menu(["Add a student", "Edit a student profile", "Back"])
        if choice == 3:
            return
        if choice == 1:
            name = ask("Full name")
            email = ask("Email")
            password = ask_password("Temporary password")
            try:
                student_id = services.create_student(conn, name, email, password)
            except ServiceError as error:
                print(f"Error: {error}")
            else:
                print(f"Student created (#{student_id}).")
            pause()
        else:
            student = choose_row(students, lambda s: f"{s['full_name']} <{s['email']}>")
            if not student:
                continue
            name = ask("Full name", student["full_name"])
            email = ask("Email", student["email"])
            try:
                services.update_student_profile(conn, student["student_id"], name, email)
                print("Profile updated.")
            except ServiceError as error:
                print(f"Error: {error}")
            pause()


def reports_menu(conn):
    available = [
        ("Enrollment summary", reports.enrollment_summary),
        ("Learner progress", reports.learner_progress),
        ("Assessment performance", reports.assessment_performance),
        ("Top students", reports.top_students),
        ("Instructor workload", reports.instructor_workload),
        ("Revenue by category", reports.revenue_by_category),
        ("Pending grading queue", reports.pending_grading),
    ]
    while True:
        header("Reports")
        choice = menu([name for name, _ in available] + ["Back"])
        if choice == len(available) + 1:
            return
        name, report = available[choice - 1]
        headers, rows = report(conn)
        header(name)
        print_table(headers, rows)
        if rows and confirm("Export this report to CSV?"):
            export_csv(name, headers, rows)
        pause()
