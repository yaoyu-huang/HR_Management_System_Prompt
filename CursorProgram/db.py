import sqlite3
from datetime import datetime, timedelta

DB_PATH = "hr_demo.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_jobs_schema(conn):
    """为已存在的 jobs 表补齐发布渠道、HC 等字段（SQLite 无 IF NOT EXISTS 列语法）。"""
    cur = conn.cursor()
    rows = cur.execute("PRAGMA table_info(jobs)").fetchall()
    names = {r[1] for r in rows}
    if "publish_channels" not in names:
        cur.execute("ALTER TABLE jobs ADD COLUMN publish_channels TEXT NOT NULL DEFAULT ''")
    if "hc" not in names:
        cur.execute("ALTER TABLE jobs ADD COLUMN hc INTEGER NOT NULL DEFAULT 1")
    if "filled_count" not in names:
        cur.execute("ALTER TABLE jobs ADD COLUMN filled_count INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS interviewers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            interviewer_id INTEGER NOT NULL,
            interview_at TEXT NOT NULL,
            mode TEXT NOT NULL,
            location_or_link TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(id),
            FOREIGN KEY(interviewer_id) REFERENCES interviewers(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            target_email TEXT NOT NULL,
            type TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            department TEXT NOT NULL,
            location TEXT NOT NULL,
            keywords TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            publish_channels TEXT NOT NULL DEFAULT '',
            hc INTEGER NOT NULL DEFAULT 1,
            filled_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_screenings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT NOT NULL,
            candidate_email TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            resume_text TEXT NOT NULL,
            score REAL NOT NULL,
            result TEXT NOT NULL,
            matched_keywords TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    ensure_jobs_schema(conn)
    normalize_existing_timestamps(conn)
    seed_data_if_empty(conn)
    seed_admin_if_empty(conn)
    conn.close()


def format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def normalize_existing_timestamps(conn):
    cur = conn.cursor()
    table_columns = {
        "candidates": "created_at",
        "interviews": "interview_at",
        "notifications": "sent_at",
    }
    for table, column in table_columns.items():
        rows = cur.execute(f"SELECT id, {column} AS dt FROM {table}").fetchall()
        for row in rows:
            normalized = normalize_datetime_text(row["dt"])
            if normalized and normalized != row["dt"]:
                cur.execute(
                    f"UPDATE {table} SET {column} = ? WHERE id = ?",
                    (normalized, row["id"]),
                )
    conn.commit()


def normalize_datetime_text(text):
    if not text:
        return text
    try:
        parsed = datetime.fromisoformat(text)
        return format_dt(parsed)
    except ValueError:
        return text


def seed_data_if_empty(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS count FROM candidates")
    candidate_count = cur.fetchone()["count"]
    if candidate_count > 0:
        return

    now = datetime.now()
    sample_candidates = [
        ("Alice Chen", "alice@example.com", "Data Analyst", "Applied", format_dt(now - timedelta(days=21))),
        ("Bob Li", "bob@example.com", "HR Specialist", "Interview Scheduled", format_dt(now - timedelta(days=15))),
        ("Cindy Wang", "cindy@example.com", "Recruiter", "Interviewed", format_dt(now - timedelta(days=10))),
        ("David Zhou", "david@example.com", "People Ops", "Offer", format_dt(now - timedelta(days=7))),
        ("Eva Xu", "eva@example.com", "HRBP", "Hired", format_dt(now - timedelta(days=3))),
    ]
    cur.executemany(
        "INSERT INTO candidates (name, email, role, status, created_at) VALUES (?, ?, ?, ?, ?)",
        sample_candidates,
    )

    sample_interviewers = [
        ("Iris Manager", "iris.manager@example.com"),
        ("Ken Lead", "ken.lead@example.com"),
        ("Luna Director", "luna.director@example.com"),
    ]
    cur.executemany(
        "INSERT INTO interviewers (name, email) VALUES (?, ?)",
        sample_interviewers,
    )

    sample_jobs = [
        (
            "招聘专员",
            "人力资源部",
            "上海",
            "招聘,面试,人才库,沟通,Excel",
            "负责招聘全流程，包括发布职位、筛选简历、安排面试与人才库维护。",
            "Open",
            format_dt(now - timedelta(days=5)),
            "官网,BOSS直聘",
            2,
            0,
        ),
        (
            "HRBP",
            "人力资源部",
            "深圳",
            "组织发展,绩效,员工关系,沟通,数据分析",
            "支持业务部门组织发展、绩效管理和员工关系。",
            "Open",
            format_dt(now - timedelta(days=2)),
            "牛客,实习僧",
            1,
            0,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO jobs (
            title, department, location, keywords, description, status, created_at,
            publish_channels, hc, filled_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sample_jobs,
    )

    conn.commit()


def seed_admin_if_empty(conn):
    cur = conn.cursor()
    exists = cur.execute(
        "SELECT 1 FROM admin_users WHERE username = ?",
        ("admin",),
    ).fetchone()
    if exists:
        return
    cur.execute(
        """
        INSERT INTO admin_users (username, password, failed_attempts, locked_until, updated_at)
        VALUES (?, ?, 0, NULL, ?)
        """,
        ("admin", "Admin@123", format_dt(datetime.now())),
    )
    conn.commit()
