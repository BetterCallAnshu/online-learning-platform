"""End-to-end tests for the service layer (run: python -m unittest discover -s tests)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
import reports
import seed
import services


class PlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.conn = db.connect(Path(cls.tmp.name) / "test.db")
        db.init_schema(cls.conn)
        seed.seed(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.tmp.cleanup()

    def _new_student(self, email):
        return services.create_student(self.conn, "Test Learner", email, "secret123")

    def _published_course(self, title):
        for course in services.list_courses(self.conn, search=title):
            if course["title"] == title:
                return course
        self.fail(f"Course not found: {title}")

    def _lesson_ids(self, course_id):
        return [
            lesson["lesson_id"]
            for entry in services.get_curriculum(self.conn, course_id)
            for lesson in entry["lessons"]
        ]

    def test_seed_creates_expected_records(self):
        for email in (
            "sam@student.io", "lena@student.io", "tom@student.io",
            "rina@student.io", "diego@student.io", "ava@student.io",
        ):
            self.assertIsNotNone(
                self.conn.execute(
                    "SELECT 1 FROM students WHERE email = ?", (email,)
                ).fetchone()
            )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM instructors").fetchone()[0], 3
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0], 4
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0], 6
        )

    def test_authentication_and_roles(self):
        admin = services.authenticate(self.conn, "admin@learnhub.io", "admin123")
        self.assertEqual(admin["role"], "admin")
        instructor = services.authenticate(
            self.conn, "maya@learnhub.io", "instructor123"
        )
        self.assertEqual(instructor["role"], "instructor")
        student = services.authenticate(self.conn, "sam@student.io", "student123")
        self.assertEqual(student["role"], "student")
        self.assertIsNone(
            services.authenticate(self.conn, "sam@student.io", "wrong-password")
        )

    def test_enrollment_progress_and_completion(self):
        student_id = self._new_student("progress@test.io")
        course = self._published_course("SQL and Database Design")
        services.enroll(self.conn, student_id, course["course_id"])
        with self.assertRaises(services.ServiceError):
            services.enroll(self.conn, student_id, course["course_id"])

        lessons = self._lesson_ids(course["course_id"])
        for lesson_id in lessons:
            services.mark_lesson_complete(self.conn, student_id, lesson_id)

        enrollment = services.get_enrollment(self.conn, student_id, course["course_id"])
        self.assertEqual(enrollment["status"], "Completed")
        mine = {c["course_id"]: c for c in services.my_courses(self.conn, student_id)}
        self.assertEqual(mine[course["course_id"]]["done_lessons"], len(lessons))

    def test_quiz_is_auto_graded(self):
        student_id = self._new_student("quiz@test.io")
        course = self._published_course("Python for Data Analysis")
        services.enroll(self.conn, student_id, course["course_id"])
        quiz = next(
            a for a in services.list_assessments(self.conn, course["course_id"])
            if a["kind"] == "quiz"
        )
        questions = services.list_questions(self.conn, quiz["assessment_id"])
        answers = {q["question_id"]: q["correct_option"] for q in questions}
        result = services.take_quiz(
            self.conn, student_id, quiz["assessment_id"], answers
        )
        self.assertEqual(result["score"], quiz["max_score"])
        self.assertEqual(result["correct"], len(questions))

        with self.assertRaises(services.ServiceError):
            services.take_quiz(self.conn, student_id, quiz["assessment_id"], answers)

    def test_assignment_grading_and_weighted_average(self):
        student_id = self._new_student("grade@test.io")
        course = self._published_course("Python for Data Analysis")
        services.enroll(self.conn, student_id, course["course_id"])
        assignment = next(
            a for a in services.list_assessments(self.conn, course["course_id"])
            if a["kind"] == "assignment"
        )
        submission_id, created = services.submit_assignment(
            self.conn, student_id, assignment["assessment_id"],
            "A detailed description of the cleaning steps I performed on the dataset.",
        )
        self.assertTrue(created)
        services.grade_submission(self.conn, submission_id, 77, "Good work.")
        averages = services.course_averages(self.conn, student_id)
        self.assertEqual(averages[0]["average"], 77.0)

        with self.assertRaises(services.ServiceError):
            services.grade_submission(self.conn, submission_id, 200)

    def test_unenrolled_student_cannot_submit(self):
        student_id = self._new_student("outsider@test.io")
        course = self._published_course("Modern Web Development")
        quiz = next(
            a for a in services.list_assessments(self.conn, course["course_id"])
            if a["kind"] == "quiz"
        )
        with self.assertRaises(services.ServiceError):
            services.take_quiz(self.conn, student_id, quiz["assessment_id"], {})

    def test_reports_return_rows(self):
        for report in (
            reports.enrollment_summary,
            reports.learner_progress,
            reports.assessment_performance,
            reports.top_students,
            reports.instructor_workload,
            reports.revenue_by_category,
            reports.pending_grading,
        ):
            headers, rows = report(self.conn)
            self.assertTrue(headers)
            self.assertGreater(len(rows), 0, report.__name__)

    def test_seed_is_idempotent(self):
        self.assertFalse(seed.seed(self.conn))


if __name__ == "__main__":
    unittest.main()
