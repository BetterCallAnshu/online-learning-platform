"""Read-only reports used by the admin and instructor dashboards."""


def enrollment_summary(conn):
    headers = ["Course", "Category", "Status", "Enrollments", "Completed", "Revenue"]
    rows = conn.execute(
        """
        SELECT c.title, c.category, c.status,
               COUNT(e.enrollment_id) AS enrollments,
               COALESCE(SUM(CASE WHEN e.status = 'Completed' THEN 1 ELSE 0 END), 0) AS completed,
               COALESCE(SUM(CASE WHEN e.enrollment_id IS NOT NULL THEN c.price ELSE 0 END), 0) AS revenue
          FROM courses c
          LEFT JOIN enrollments e ON e.course_id = c.course_id
         GROUP BY c.course_id
         ORDER BY enrollments DESC, c.title
        """
    ).fetchall()
    return headers, rows


def learner_progress(conn):
    headers = ["Student", "Course", "Status", "Progress %", "Done", "Total", "Enrolled"]
    rows = conn.execute(
        """
        SELECT student, course, enrollment_status,
               CASE WHEN lessons_total = 0 THEN 0
                    ELSE ROUND(lessons_done * 100.0 / lessons_total, 1) END AS percent,
               lessons_done, lessons_total, enrolled_at
          FROM v_student_progress
         WHERE enrollment_status IN ('Active', 'Completed')
         ORDER BY percent ASC, student
        """
    ).fetchall()
    return headers, rows


def _assessment_stats(conn, course_id=None):
    sql = """
        SELECT a.title AS assessment, c.title AS course, a.kind,
               COUNT(s.submission_id) AS submissions,
               ROUND(AVG(CASE WHEN s.score IS NOT NULL
                              THEN s.score * 100.0 / a.max_score END), 1) AS avg_pct,
               ROUND(MAX(CASE WHEN s.score IS NOT NULL
                              THEN s.score * 100.0 / a.max_score END), 1) AS high_pct,
               ROUND(MIN(CASE WHEN s.score IS NOT NULL
                              THEN s.score * 100.0 / a.max_score END), 1) AS low_pct
          FROM assessments a
          JOIN courses c ON c.course_id = a.course_id
          LEFT JOIN submissions s ON s.assessment_id = a.assessment_id
    """
    params = []
    if course_id is not None:
        sql += " WHERE a.course_id = ?"
        params.append(course_id)
    sql += " GROUP BY a.assessment_id ORDER BY c.title, a.kind DESC, a.title"
    return conn.execute(sql, params).fetchall()


def assessment_performance(conn):
    headers = ["Assessment", "Course", "Type", "Submissions", "Avg %", "High %", "Low %"]
    return headers, _assessment_stats(conn)


def course_assessment_performance(conn, course_id):
    return _assessment_stats(conn, course_id)


def top_students(conn, limit=10):
    headers = ["Student", "Graded Items", "Average %", "Courses"]
    rows = conn.execute(
        """
        SELECT s.full_name, COUNT(v.submission_id),
               ROUND(AVG(v.percent), 1) AS average,
               COUNT(DISTINCT v.course_id)
          FROM v_assessment_results v
          JOIN students s ON s.student_id = v.student_id
         WHERE v.score IS NOT NULL
         GROUP BY s.student_id
         ORDER BY average DESC, s.full_name
         LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return headers, rows


def instructor_workload(conn):
    headers = ["Instructor", "Courses", "Students", "Assessments", "Ungraded"]
    rows = conn.execute(
        """
        SELECT i.full_name,
               (SELECT COUNT(*) FROM courses c
                 WHERE c.instructor_id = i.instructor_id) AS courses,
               (SELECT COUNT(*) FROM v_student_progress v
                 JOIN courses c ON c.course_id = v.course_id
                WHERE c.instructor_id = i.instructor_id
                  AND v.enrollment_status IN ('Active', 'Completed')) AS students,
               (SELECT COUNT(*) FROM assessments a
                 JOIN courses c ON c.course_id = a.course_id
                WHERE c.instructor_id = i.instructor_id) AS assessments,
               (SELECT COUNT(*) FROM submissions s
                 JOIN assessments a ON a.assessment_id = s.assessment_id
                 JOIN courses c ON c.course_id = a.course_id
                WHERE c.instructor_id = i.instructor_id
                  AND s.score IS NULL) AS ungraded
          FROM instructors i
         ORDER BY courses DESC, i.full_name
        """
    ).fetchall()
    return headers, rows


def revenue_by_category(conn):
    headers = ["Category", "Courses", "Enrollments", "Revenue"]
    rows = conn.execute(
        """
        SELECT c.category, COUNT(DISTINCT c.course_id),
               COUNT(e.enrollment_id),
               COALESCE(SUM(CASE WHEN e.enrollment_id IS NOT NULL
                                 THEN c.price ELSE 0 END), 0) AS revenue
          FROM courses c
          LEFT JOIN enrollments e ON e.course_id = c.course_id
         GROUP BY c.category
         ORDER BY revenue DESC, c.category
        """
    ).fetchall()
    return headers, rows


def pending_grading(conn):
    headers = ["Submission", "Student", "Assessment", "Course", "Max Score", "Submitted"]
    rows = conn.execute(
        """
        SELECT s.submission_id, st.full_name, a.title, c.title, a.max_score, s.submitted_at
          FROM submissions s
          JOIN assessments a ON a.assessment_id = s.assessment_id
          JOIN courses c ON c.course_id = a.course_id
          JOIN students st ON st.student_id = s.student_id
         WHERE s.score IS NULL
         ORDER BY s.submitted_at
        """
    ).fetchall()
    return headers, rows
