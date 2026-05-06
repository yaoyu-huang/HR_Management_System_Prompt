from datetime import datetime
from db import get_conn


VALID_STATUSES = [
    "Applied",
    "Interview Scheduled",
    "Interviewed",
    "Offer",
    "Hired",
    "Rejected",
]

STATUS_LABELS = {
    "Applied": "已投递",
    "Interview Scheduled": "已安排面试",
    "Interviewed": "已完成面试",
    "Offer": "已发 Offer",
    "Hired": "已录用",
    "Rejected": "未通过",
}

SORT_MAP = {
    "created_desc": "created_at DESC",
    "created_asc": "created_at ASC",
    "name_asc": "name ASC",
    "name_desc": "name DESC",
}

JOB_PUBLISH_CHANNEL_OPTIONS = ["官网", "BOSS直聘", "牛客", "实习僧"]

VALID_JOB_STATUSES = ["Open", "Paused", "Closed", "Filled"]

JOB_STATUS_LABELS = {
    "Open": "招聘中",
    "Paused": "暂停",
    "Closed": "已关闭",
    "Filled": "已满编",
}


def normalize_job_publish_channels(selected):
    """按固定顺序保存已勾选的发布渠道。"""
    chosen = set(selected or [])
    return ",".join(c for c in JOB_PUBLISH_CHANNEL_OPTIONS if c in chosen)


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_input_datetime(dt_text):
    parsed = datetime.fromisoformat(dt_text)
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def list_candidates(job_id=None):
    conn = get_conn()
    if job_id is not None:
        rows = conn.execute(
            """
            SELECT c.id, c.name, c.email, c.role, c.status, c.created_at, c.job_id,
                   j.title AS job_title
            FROM candidates c
            LEFT JOIN jobs j ON j.id = c.job_id
            WHERE c.job_id = ?
            ORDER BY c.id DESC
            """,
            (job_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT c.id, c.name, c.email, c.role, c.status, c.created_at, c.job_id,
                   j.title AS job_title
            FROM candidates c
            LEFT JOIN jobs j ON j.id = c.job_id
            ORDER BY c.id DESC
            """
        ).fetchall()
    conn.close()
    return rows


def query_candidates(q="", status="", sort="created_desc", job_id=None):
    conn = get_conn()
    where = []
    params = []
    if q:
        where.append("(c.name LIKE ? OR c.email LIKE ? OR c.role LIKE ? OR j.title LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    if status:
        where.append("c.status = ?")
        params.append(status)
    if job_id is not None:
        where.append("c.job_id = ?")
        params.append(job_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_sql = SORT_MAP.get(sort, "created_at DESC").replace("created_at", "c.created_at").replace(
        "name", "c.name"
    )
    rows = conn.execute(
        f"""
        SELECT c.id, c.name, c.email, c.role, c.status, c.created_at, c.job_id,
               j.title AS job_title
        FROM candidates c
        LEFT JOIN jobs j ON j.id = c.job_id
        {where_sql}
        ORDER BY {order_sql}
        """,
        params,
    ).fetchall()
    conn.close()
    return rows


def list_interviewers():
    conn = get_conn()
    rows = conn.execute("SELECT id, name, email FROM interviewers ORDER BY id ASC").fetchall()
    conn.close()
    return rows


def list_interviews():
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT i.id, c.name AS candidate_name, iv.name AS interviewer_name,
               i.interview_at, i.mode, i.location_or_link, i.created_at
        FROM interviews i
        JOIN candidates c ON c.id = i.candidate_id
        JOIN interviewers iv ON iv.id = i.interviewer_id
        ORDER BY i.interview_at DESC
        """
    ).fetchall()
    conn.close()
    return rows


def query_interviews(q="", mode="", sort="created_desc", job_id=None):
    conn = get_conn()
    where = []
    params = []
    if q:
        where.append("(c.name LIKE ? OR iv.name LIKE ? OR i.location_or_link LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if mode:
        where.append("i.mode = ?")
        params.append(mode)
    if job_id is not None:
        where.append("c.job_id = ?")
        params.append(job_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_sql = "i.created_at DESC" if sort == "created_desc" else "i.created_at ASC"
    rows = conn.execute(
        f"""
        SELECT i.id, c.name AS candidate_name, iv.name AS interviewer_name,
               i.interview_at, i.mode, i.location_or_link, i.created_at
        FROM interviews i
        JOIN candidates c ON c.id = i.candidate_id
        JOIN interviewers iv ON iv.id = i.interviewer_id
        {where_sql}
        ORDER BY {order_sql}
        """,
        params,
    ).fetchall()
    conn.close()
    return rows


def list_notifications(limit=50):
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT n.id, c.name AS candidate_name, n.target_email, n.type, n.subject, n.body, n.sent_at
        FROM notifications n
        LEFT JOIN candidates c ON c.id = n.candidate_id
        ORDER BY n.sent_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def query_notifications(q="", type_filter="", sort="created_desc", job_id=None):
    conn = get_conn()
    where = []
    params = []
    if q:
        where.append("(n.target_email LIKE ? OR n.subject LIKE ? OR c.name LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if type_filter:
        where.append("n.type = ?")
        params.append(type_filter)
    if job_id is not None:
        where.append("c.job_id = ?")
        params.append(job_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_sql = "n.sent_at DESC" if sort == "created_desc" else "n.sent_at ASC"
    rows = conn.execute(
        f"""
        SELECT n.id, c.name AS candidate_name, n.target_email, n.type, n.subject, n.body, n.sent_at
        FROM notifications n
        LEFT JOIN candidates c ON c.id = n.candidate_id
        {where_sql}
        ORDER BY {order_sql}
        """,
        params,
    ).fetchall()
    conn.close()
    return rows


def schedule_interview(candidate_id, interviewer_id, interview_at, mode, location_or_link):
    conn = get_conn()
    now = now_text()
    interview_at_fmt = normalize_input_datetime(interview_at)

    conn.execute(
        """
        INSERT INTO interviews (candidate_id, interviewer_id, interview_at, mode, location_or_link, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (candidate_id, interviewer_id, interview_at_fmt, mode, location_or_link, now),
    )

    conn.execute(
        "UPDATE candidates SET status = ? WHERE id = ?",
        ("Interview Scheduled", candidate_id),
    )

    candidate = conn.execute(
        "SELECT name, email, role FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    interviewer = conn.execute(
        "SELECT name, email FROM interviewers WHERE id = ?", (interviewer_id,)
    ).fetchone()

    mode_text = "线上" if mode == "Online" else "线下"
    candidate_subject = f"面试安排通知 - {candidate['role']}"
    candidate_body = (
        f"{candidate['name']}，您好。您的面试已安排在 {interview_at_fmt}。"
        f"面试官：{interviewer['name']}；方式：{mode_text}；地点/链接：{location_or_link}。"
    )
    interviewer_subject = f"面试任务通知 - {candidate['name']}"
    interviewer_body = (
        f"{interviewer['name']}，您好。您有一场与 {candidate['name']} 的面试，"
        f"时间：{interview_at_fmt}；方式：{mode_text}；地点/链接：{location_or_link}。"
    )

    conn.execute(
        """
        INSERT INTO notifications (candidate_id, target_email, type, subject, body, sent_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (candidate_id, candidate["email"], "面试安排", candidate_subject, candidate_body, now),
    )
    conn.execute(
        """
        INSERT INTO notifications (candidate_id, target_email, type, subject, body, sent_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (candidate_id, interviewer["email"], "面试官通知", interviewer_subject, interviewer_body, now),
    )

    conn.commit()
    conn.close()


def update_candidate_status(candidate_id, new_status):
    if new_status not in VALID_STATUSES:
        raise ValueError("状态不合法")

    conn = get_conn()
    now = now_text()

    candidate = conn.execute(
        "SELECT name, email, role, status FROM candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()

    if candidate is None:
        conn.close()
        raise ValueError("候选人不存在")

    old_status = candidate["status"]
    conn.execute("UPDATE candidates SET status = ? WHERE id = ?", (new_status, candidate_id))

    old_status_text = STATUS_LABELS.get(old_status, old_status)
    new_status_text = STATUS_LABELS.get(new_status, new_status)
    subject = f"应聘状态更新 - {candidate['role']}"
    body = (
        f"{candidate['name']}，您好。您的应聘状态已从“{old_status_text}”更新为“{new_status_text}”。"
    )

    conn.execute(
        """
        INSERT INTO notifications (candidate_id, target_email, type, subject, body, sent_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (candidate_id, candidate["email"], "状态更新", subject, body, now),
    )

    conn.commit()
    conn.close()


def update_candidate_job_and_role(candidate_id, job_id, role):
    role = (role or "").strip()
    if not role:
        raise ValueError("应聘说明不能为空")
    if not job_id:
        raise ValueError("请选择系统职位")

    conn = get_conn()
    cand = conn.execute("SELECT id, email FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not cand:
        conn.close()
        raise ValueError("候选人不存在")

    job = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise ValueError("职位不存在")

    dup = conn.execute(
        "SELECT 1 FROM candidates WHERE email = ? AND job_id = ? AND id != ?",
        (cand["email"], job_id, candidate_id),
    ).fetchone()
    if dup:
        conn.close()
        raise ValueError("该邮箱在此系统职位下已有其他候选人记录")

    conn.execute(
        "UPDATE candidates SET job_id = ?, role = ? WHERE id = ?",
        (job_id, role, candidate_id),
    )
    conn.commit()
    conn.close()


def generate_monthly_report(month_str):
    start = datetime.fromisoformat(month_str + "-01")
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)

    start_iso = start.strftime("%Y-%m-%d %H:%M:%S")
    end_iso = end.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    cur = conn.cursor()

    new_candidates = cur.execute(
        "SELECT COUNT(*) AS c FROM candidates WHERE created_at >= ? AND created_at < ?",
        (start_iso, end_iso),
    ).fetchone()["c"]

    interviews = cur.execute(
        "SELECT COUNT(*) AS c FROM interviews WHERE interview_at >= ? AND interview_at < ?",
        (start_iso, end_iso),
    ).fetchone()["c"]

    offers = cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM candidates
        WHERE status = 'Offer' AND created_at >= ? AND created_at < ?
        """,
        (start_iso, end_iso),
    ).fetchone()["c"]

    hired = cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM candidates
        WHERE status = 'Hired' AND created_at >= ? AND created_at < ?
        """,
        (start_iso, end_iso),
    ).fetchone()["c"]

    rejected = cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM candidates
        WHERE status = 'Rejected' AND created_at >= ? AND created_at < ?
        """,
        (start_iso, end_iso),
    ).fetchone()["c"]

    conn.close()

    interview_rate = (interviews / new_candidates * 100) if new_candidates else 0.0
    offer_rate = (offers / interviews * 100) if interviews else 0.0
    hire_rate = (hired / offers * 100) if offers else 0.0

    return {
        "month": month_str,
        "new_candidates": new_candidates,
        "interviews": interviews,
        "offers": offers,
        "hired": hired,
        "rejected": rejected,
        "interview_rate": round(interview_rate, 2),
        "offer_rate": round(offer_rate, 2),
        "hire_rate": round(hire_rate, 2),
    }


def import_candidates_from_rows(rows, job_id):
    if not job_id:
        raise ValueError("请选择候选人归属职位")

    conn = get_conn()
    exists_job = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not exists_job:
        conn.close()
        raise ValueError("归属职位不存在")

    inserted = 0
    skipped = 0
    now = now_text()
    errors = []

    for idx, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        email = (row.get("email") or "").strip()
        role = (row.get("role") or "").strip()
        status = (row.get("status") or "Applied").strip()

        if not name or not email or not role:
            skipped += 1
            errors.append({"line": idx, "reason": "缺少 name/email/role 必填字段"})
            continue
        if status not in VALID_STATUSES:
            status = "Applied"

        exists = conn.execute(
            "SELECT 1 FROM candidates WHERE email = ? AND job_id = ?",
            (email, job_id),
        ).fetchone()
        if exists:
            skipped += 1
            errors.append({"line": idx, "reason": "该职位下候选人邮箱已存在"})
            continue

        conn.execute(
            """
            INSERT INTO candidates (name, email, role, status, created_at, job_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, email, role, status, now, job_id),
        )
        inserted += 1

    conn.commit()
    conn.close()
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def get_job(job_id):
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id, title, department, location, keywords, description, status, created_at,
               publish_channels, hc, filled_count
        FROM jobs WHERE id = ?
        """,
        (job_id,),
    ).fetchone()
    conn.close()
    return row


def list_jobs():
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, title, department, location, keywords, description, status, created_at,
               publish_channels, hc, filled_count
        FROM jobs
        ORDER BY created_at DESC
        """
    ).fetchall()
    conn.close()
    return rows


def list_job_pipeline_overviews():
    """各职位 HC、在招状态及候选人阶段分布。"""
    conn = get_conn()
    jobs = conn.execute(
        """
        SELECT id, title, department, status, hc, filled_count
        FROM jobs
        ORDER BY created_at DESC
        """
    ).fetchall()
    out = []
    for job in jobs:
        counts = {s: 0 for s in VALID_STATUSES}
        agg = conn.execute(
            """
            SELECT status, COUNT(*) AS c
            FROM candidates
            WHERE job_id = ?
            GROUP BY status
            """,
            (job["id"],),
        ).fetchall()
        for r in agg:
            if r["status"] in counts:
                counts[r["status"]] = r["c"]
        total = sum(counts.values())
        out.append(
            {
                "job": job,
                "status_counts": counts,
                "candidate_total": total,
            }
        )
    conn.close()
    return out


def query_jobs(q="", status="", sort="created_desc"):
    conn = get_conn()
    where = []
    params = []
    if q:
        where.append("(title LIKE ? OR department LIKE ? OR location LIKE ? OR keywords LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    if status:
        where.append("status = ?")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_sql = "created_at DESC" if sort == "created_desc" else "created_at ASC"
    rows = conn.execute(
        f"""
        SELECT id, title, department, location, keywords, description, status, created_at,
               publish_channels, hc, filled_count
        FROM jobs
        {where_sql}
        ORDER BY {order_sql}
        """,
        params,
    ).fetchall()
    conn.close()
    return rows


def create_job(title, department, location, keywords, description, status, publish_channels, hc, filled_count):
    if status not in VALID_JOB_STATUSES:
        raise ValueError("职位状态不合法")
    if hc < 1:
        raise ValueError("HC 至少为 1")
    if filled_count < 0:
        raise ValueError("已招人数不能为负")
    if filled_count > hc:
        raise ValueError("已招人数不能大于 HC")

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO jobs (
            title, department, location, keywords, description, status, created_at,
            publish_channels, hc, filled_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            department,
            location,
            keywords,
            description,
            status,
            now_text(),
            publish_channels,
            hc,
            filled_count,
        ),
    )
    conn.commit()
    conn.close()


def update_job_recruitment(job_id, hc, filled_count, status):
    if status not in VALID_JOB_STATUSES:
        raise ValueError("职位状态不合法")
    if hc < 1:
        raise ValueError("HC 至少为 1")
    if filled_count < 0:
        raise ValueError("已招人数不能为负")
    if filled_count > hc:
        raise ValueError("已招人数不能大于 HC")

    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not exists:
        conn.close()
        raise ValueError("职位不存在")

    conn.execute(
        """
        UPDATE jobs SET hc = ?, filled_count = ?, status = ?
        WHERE id = ?
        """,
        (hc, filled_count, status, job_id),
    )
    conn.commit()
    conn.close()


def update_job_full(
    job_id,
    title,
    department,
    location,
    keywords,
    description,
    status,
    publish_channels,
    hc,
    filled_count,
):
    if status not in VALID_JOB_STATUSES:
        raise ValueError("职位状态不合法")
    if hc < 1:
        raise ValueError("HC 至少为 1")
    if filled_count < 0:
        raise ValueError("已招人数不能为负")
    if filled_count > hc:
        raise ValueError("已招人数不能大于 HC")

    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not exists:
        conn.close()
        raise ValueError("职位不存在")

    conn.execute(
        """
        UPDATE jobs SET
            title = ?, department = ?, location = ?, keywords = ?, description = ?,
            status = ?, publish_channels = ?, hc = ?, filled_count = ?
        WHERE id = ?
        """,
        (
            title,
            department,
            location,
            keywords,
            description,
            status,
            publish_channels,
            hc,
            filled_count,
            job_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_job(job_id):
    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not exists:
        conn.close()
        raise ValueError("职位不存在")

    conn.execute("DELETE FROM resume_screenings WHERE job_id = ?", (job_id,))
    conn.execute("UPDATE candidates SET job_id = NULL WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


def run_resume_screening(candidate_name, candidate_email, job_id, resume_text):
    conn = get_conn()
    job = conn.execute(
        "SELECT id, title, keywords FROM jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    if not job:
        conn.close()
        raise ValueError("职位不存在")

    keywords = [k.strip() for k in job["keywords"].split(",") if k.strip()]
    lowered_resume = resume_text.lower()
    matched = [k for k in keywords if k.lower() in lowered_resume]
    score = round((len(matched) / len(keywords) * 100), 2) if keywords else 0.0
    result = "通过初筛" if score >= 55 else "待人工复核"

    conn.execute(
        """
        INSERT INTO resume_screenings
        (candidate_name, candidate_email, job_id, resume_text, score, result, matched_keywords, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_name,
            candidate_email,
            job_id,
            resume_text,
            score,
            result,
            ",".join(matched),
            now_text(),
        ),
    )
    conn.commit()
    conn.close()
    return {"score": score, "result": result, "matched_keywords": matched, "job_title": job["title"]}


def query_resume_screenings(q="", result_filter="", sort="created_desc", job_id=None):
    conn = get_conn()
    where = []
    params = []
    if q:
        where.append("(r.candidate_name LIKE ? OR r.candidate_email LIKE ? OR j.title LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if result_filter:
        where.append("r.result = ?")
        params.append(result_filter)
    if job_id is not None:
        where.append("r.job_id = ?")
        params.append(job_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_sql = "r.created_at DESC" if sort == "created_desc" else "r.created_at ASC"
    rows = conn.execute(
        f"""
        SELECT r.id, r.candidate_name, r.candidate_email, r.score, r.result,
               r.matched_keywords, r.created_at, j.title AS job_title
        FROM resume_screenings r
        JOIN jobs j ON j.id = r.job_id
        {where_sql}
        ORDER BY {order_sql}
        """,
        params,
    ).fetchall()
    conn.close()
    return rows


def get_admin_user(username):
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id, username, password, failed_attempts, locked_until, updated_at
        FROM admin_users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()
    conn.close()
    return row


def update_admin_login_success(username):
    conn = get_conn()
    conn.execute(
        "UPDATE admin_users SET failed_attempts = 0, locked_until = NULL, updated_at = ? WHERE username = ?",
        (now_text(), username),
    )
    conn.commit()
    conn.close()


def update_admin_login_failed(username, lock_until):
    conn = get_conn()
    conn.execute(
        """
        UPDATE admin_users
        SET failed_attempts = failed_attempts + 1, locked_until = ?, updated_at = ?
        WHERE username = ?
        """,
        (lock_until, now_text(), username),
    )
    conn.commit()
    conn.close()


def reset_admin_failed_attempts(username):
    conn = get_conn()
    conn.execute(
        "UPDATE admin_users SET failed_attempts = 0, locked_until = NULL, updated_at = ? WHERE username = ?",
        (now_text(), username),
    )
    conn.commit()
    conn.close()


def update_admin_password(username, new_password):
    conn = get_conn()
    conn.execute(
        "UPDATE admin_users SET password = ?, updated_at = ? WHERE username = ?",
        (new_password, now_text(), username),
    )
    conn.commit()
    conn.close()
