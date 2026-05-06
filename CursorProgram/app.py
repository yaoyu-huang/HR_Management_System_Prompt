from datetime import datetime, timedelta
import csv
import io
import os
import secrets
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from db import init_db
from services import (
    VALID_STATUSES,
    generate_monthly_report,
    list_candidates,
    list_interviewers,
    list_jobs,
    query_candidates,
    query_interviews,
    query_jobs,
    query_notifications,
    import_candidates_from_rows,
    create_job,
    JOB_PUBLISH_CHANNEL_OPTIONS,
    normalize_job_publish_channels,
    update_job_recruitment,
    get_admin_user,
    update_admin_login_success,
    update_admin_login_failed,
    reset_admin_failed_attempts,
    update_admin_password,
    update_candidate_status,
    schedule_interview,
)
from hr_tools import (
    DEFAULT_INTERVIEW_AVAILABILITY_JSON,
    generate_touch_letter,
    run_hr_insight_pipeline,
    run_interview_coordination,
)

app = Flask(__name__)
app.secret_key = "hr-demo-secret-key"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["DEEPSEEK_API_KEY"] = os.environ.get("DEEPSEEK_API_KEY", "").strip()

AUTOMATION_DIR = Path(__file__).resolve().parent / "instance" / "automation"
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15

STATUS_LABELS = {
    "Applied": "已投递",
    "Interview Scheduled": "已安排面试",
    "Interviewed": "已完成面试",
    "Offer": "已发 Offer",
    "Hired": "已录用",
    "Rejected": "未通过",
}


@app.context_processor
def inject_common():
    def status_text(status):
        return STATUS_LABELS.get(status, status)

    def format_time(value):
        if not value:
            return "-"
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

    return {"status_text": status_text, "status_labels": STATUS_LABELS, "format_time": format_time}


def parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def paginate_rows(rows, page, page_size):
    total = len(rows)
    page_count = max((total + page_size - 1) // page_size, 1)
    page = min(max(page, 1), page_count)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": rows[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": page_count,
    }


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        remember = request.form.get("remember_login") == "on"
        admin = get_admin_user(username)
        if not admin:
            flash("用户名或密码错误。", "error")
            return render_template("login.html")

        if admin["locked_until"]:
            locked_until = datetime.fromisoformat(admin["locked_until"])
            if datetime.now() < locked_until:
                flash(f"账号已锁定，请在 {locked_until.strftime('%Y-%m-%d %H:%M:%S')} 后重试。", "error")
                return render_template("login.html")
            reset_admin_failed_attempts(username)
            admin = get_admin_user(username)

        if password == admin["password"]:
            update_admin_login_success(username)
            session.permanent = remember
            session["admin_logged_in"] = True
            session["admin_username"] = username
            flash("登录成功，欢迎进入管理后台。", "success")
            return redirect(url_for("index"))

        next_attempt = admin["failed_attempts"] + 1
        lock_until_text = None
        if next_attempt >= MAX_FAILED_ATTEMPTS:
            lock_until = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).replace(microsecond=0)
            lock_until_text = lock_until.strftime("%Y-%m-%d %H:%M:%S")
        update_admin_login_failed(username, lock_until_text)
        if lock_until_text:
            flash(f"登录失败次数过多，账号已锁定至 {lock_until_text}。", "error")
        else:
            flash(f"用户名或密码错误（第 {next_attempt} 次失败）。", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("已退出登录。", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    candidates = list_candidates()
    interviews = query_interviews()[:8]
    notifications = query_notifications()[:10]
    jobs = list_jobs()
    return render_template(
        "index.html",
        candidates=candidates,
        interviews=interviews,
        notifications=notifications,
        jobs=jobs,
    )


@app.route("/scheduler", methods=["GET", "POST"])
@login_required
def scheduler():
    if request.method == "POST":
        try:
            candidate_id = int(request.form["candidate_id"])
            interviewer_id = int(request.form["interviewer_id"])
            interview_at = request.form["interview_at"]
            mode = request.form["mode"]
            location_or_link = request.form["location_or_link"]

            schedule_interview(
                candidate_id=candidate_id,
                interviewer_id=interviewer_id,
                interview_at=interview_at,
                mode=mode,
                location_or_link=location_or_link,
            )
            flash("面试已安排，通知已自动发送。", "success")
            return redirect(url_for("scheduler"))
        except Exception as exc:
            flash(f"安排面试失败：{exc}", "error")
            return redirect(url_for("scheduler"))

    candidates = list_candidates()
    interviewers = list_interviewers()
    q = request.args.get("q", "").strip()
    mode = request.args.get("mode", "").strip()
    sort = request.args.get("sort", "created_desc").strip()
    page = parse_int(request.args.get("page"), 1)
    page_size = parse_int(request.args.get("page_size"), 10)
    interviews = query_interviews(q=q, mode=mode, sort=sort)
    paging = paginate_rows(interviews, page, page_size)
    return render_template(
        "scheduler.html",
        candidates=candidates,
        interviewers=interviewers,
        interviews=paging["items"],
        paging=paging,
        filters={"q": q, "mode": mode, "sort": sort, "page_size": page_size},
    )


@app.route("/candidates", methods=["GET", "POST"])
@login_required
def candidates_page():
    if request.method == "POST":
        try:
            candidate_id = int(request.form["candidate_id"])
            new_status = request.form["new_status"]
            update_candidate_status(candidate_id, new_status)
            flash("候选人状态已更新，通知已自动发送。", "success")
            return redirect(url_for("candidates_page"))
        except Exception as exc:
            flash(f"更新状态失败：{exc}", "error")
            return redirect(url_for("candidates_page"))

    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    sort = request.args.get("sort", "created_desc").strip()
    page = parse_int(request.args.get("page"), 1)
    page_size = parse_int(request.args.get("page_size"), 10)

    nq = request.args.get("nq", "").strip()
    ntype = request.args.get("ntype", "").strip()
    nsort = request.args.get("nsort", "created_desc").strip()
    npage = parse_int(request.args.get("npage"), 1)
    npage_size = parse_int(request.args.get("npage_size"), 10)

    candidates_all = query_candidates(q=q, status=status_filter, sort=sort)
    notifications_all = query_notifications(q=nq, type_filter=ntype, sort=nsort)
    paging = paginate_rows(candidates_all, page, page_size)
    notif_paging = paginate_rows(notifications_all, npage, npage_size)
    return render_template(
        "candidates.html",
        candidates=paging["items"],
        valid_statuses=VALID_STATUSES,
        notifications=notif_paging["items"],
        paging=paging,
        notif_paging=notif_paging,
        filters={"q": q, "status": status_filter, "sort": sort, "page_size": page_size},
        notif_filters={"nq": nq, "ntype": ntype, "nsort": nsort, "npage_size": npage_size},
    )


@app.route("/candidates/import", methods=["POST"])
@login_required
def import_candidates():
    file = request.files.get("csv_file")
    if not file or not file.filename:
        flash("请先选择 CSV 文件。", "error")
        return redirect(url_for("candidates_page"))

    try:
        payload = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(payload))
        required_headers = {"name", "email", "role"}
        if not required_headers.issubset(set(reader.fieldnames or [])):
            flash("CSV 列头必须包含：name,email,role（status 可选）。", "error")
            return redirect(url_for("candidates_page"))

        result = import_candidates_from_rows(list(reader))
        flash(
            f"导入完成：新增 {result['inserted']} 条，跳过 {result['skipped']} 条。",
            "success",
        )
        if result["errors"]:
            report_dir = os.path.join(os.getcwd(), "reports")
            os.makedirs(report_dir, exist_ok=True)
            report_name = f"candidate_import_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            report_path = os.path.join(report_dir, report_name)
            with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["line", "reason"])
                writer.writeheader()
                writer.writerows(result["errors"])
            session["last_import_error_report"] = report_name
            flash("本次导入存在异常记录，可下载错误明细报告。", "error")
    except Exception as exc:
        flash(f"导入失败：{exc}", "error")
    return redirect(url_for("candidates_page"))


@app.route("/candidates/import-template")
@login_required
def import_template():
    payload = "name,email,role,status\n张三,zhangsan@example.com,招聘专员,Applied\n"
    return send_file(
        io.BytesIO(payload.encode("utf-8-sig")),
        as_attachment=True,
        download_name="candidate_import_template.csv",
        mimetype="text/csv",
    )


@app.route("/candidates/import-error-report")
@login_required
def import_error_report():
    report_name = session.get("last_import_error_report")
    if not report_name:
        flash("暂无可下载的错误明细报告。", "error")
        return redirect(url_for("candidates_page"))
    report_path = os.path.join(os.getcwd(), "reports", report_name)
    if not os.path.exists(report_path):
        flash("错误明细报告已失效。", "error")
        return redirect(url_for("candidates_page"))
    return send_file(report_path, as_attachment=True, download_name=report_name)


@app.route("/jobs", methods=["GET", "POST"])
@login_required
def jobs_page():
    if request.method == "POST":
        try:
            channels = normalize_job_publish_channels(request.form.getlist("publish_channels"))
            create_job(
                title=request.form.get("title", "").strip(),
                department=request.form.get("department", "").strip(),
                location=request.form.get("location", "").strip(),
                keywords=request.form.get("keywords", "").strip(),
                description=request.form.get("description", "").strip(),
                status=request.form.get("status", "Open").strip(),
                publish_channels=channels,
                hc=parse_int(request.form.get("hc"), 1),
                filled_count=parse_int(request.form.get("filled_count"), 0),
            )
            flash("职位已发布。", "success")
            return redirect(url_for("jobs_page"))
        except Exception as exc:
            flash(f"发布职位失败：{exc}", "error")
            return redirect(url_for("jobs_page"))

    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    sort = request.args.get("sort", "created_desc").strip()
    page = parse_int(request.args.get("page"), 1)
    page_size = parse_int(request.args.get("page_size"), 10)
    rows = query_jobs(q=q, status=status_filter, sort=sort)
    paging = paginate_rows(rows, page, page_size)
    return render_template(
        "jobs.html",
        jobs=paging["items"],
        paging=paging,
        filters={"q": q, "status": status_filter, "sort": sort, "page_size": page_size},
        job_publish_channel_options=JOB_PUBLISH_CHANNEL_OPTIONS,
    )


@app.route("/jobs/<int:job_id>/update", methods=["POST"])
@login_required
def job_update_row(job_id):
    try:
        update_job_recruitment(
            job_id,
            hc=parse_int(request.form.get("hc"), 1),
            filled_count=parse_int(request.form.get("filled_count"), 0),
            status=request.form.get("status", "Open").strip(),
        )
        flash("职位招聘状态已更新。", "success")
    except Exception as exc:
        flash(f"更新失败：{exc}", "error")
    return redirect(
        url_for(
            "jobs_page",
            q=request.args.get("q", ""),
            status=request.args.get("status", ""),
            sort=request.args.get("sort", "created_desc"),
            page_size=parse_int(request.args.get("page_size"), 10),
            page=parse_int(request.args.get("page"), 1),
        )
    )


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old_password = request.form.get("old_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        username = session.get("admin_username", "admin")
        admin = get_admin_user(username)
        if not admin or old_password != admin["password"]:
            flash("原密码错误。", "error")
            return redirect(url_for("change_password"))
        if len(new_password) < 8:
            flash("新密码至少 8 位。", "error")
            return redirect(url_for("change_password"))
        if new_password != confirm_password:
            flash("新密码与确认密码不一致。", "error")
            return redirect(url_for("change_password"))
        update_admin_password(username, new_password)
        flash("密码修改成功。", "success")
        return redirect(url_for("change_password"))
    return render_template("change_password.html")


@app.route("/automation")
@login_required
def automation_hub():
    return render_template(
        "automation_hub.html",
        llm_configured=bool(app.config.get("DEEPSEEK_API_KEY")),
    )


@app.route("/automation/interview-schedule", methods=["GET", "POST"])
@login_required
def automation_interview():
    result = None
    ics_token = None
    availability_json = DEFAULT_INTERVIEW_AVAILABILITY_JSON.strip()
    if request.method == "POST":
        availability_json = request.form.get("availability_json", "").strip() or availability_json
        candidate_name = request.form.get("candidate_name", "").strip() or "候选人"
        role = request.form.get("role", "").strip() or "岗位"
        company = request.form.get("company", "").strip() or "本公司"
        top_n = parse_int(request.form.get("top_n"), 3)
        top_n = min(max(top_n, 1), 10)

        result = run_interview_coordination(availability_json, candidate_name, role, company, top_n=top_n)
        if result.get("ok"):
            try:
                AUTOMATION_DIR.mkdir(parents=True, exist_ok=True)
                token = secrets.token_hex(16)
                (AUTOMATION_DIR / f"{token}.ics").write_bytes(result["ics_bytes"])
                ics_token = token
            except OSError as exc:
                result = {"ok": False, "error": f"写入 ICS 失败：{exc}"}

    return render_template(
        "automation_interview.html",
        availability_json=availability_json,
        candidate_name=request.form.get("candidate_name", "").strip() or "王候选人",
        role=request.form.get("role", "").strip() or "高级后端工程师",
        company=request.form.get("company", "").strip() or "示例科技有限公司",
        top_n=parse_int(request.form.get("top_n"), 3) if request.method == "POST" else 3,
        result=result,
        ics_token=ics_token,
    )


@app.route("/automation/download/ics/<token>")
@login_required
def automation_download_ics(token):
    t = (token or "").lower()
    if len(t) != 32 or any(c not in "0123456789abcdef" for c in t):
        flash("下载链接无效。", "error")
        return redirect(url_for("automation_interview"))
    path = AUTOMATION_DIR / f"{t}.ics"
    if not path.is_file():
        flash("文件不存在或已过期，请先在上一页重新生成。", "error")
        return redirect(url_for("automation_interview"))
    return send_file(
        path,
        as_attachment=True,
        download_name="interview_options.ics",
        mimetype="text/calendar",
    )


@app.route("/automation/candidate-touch", methods=["GET", "POST"])
@login_required
def automation_touch():
    letter = None
    defaults = {
        "name": "张三",
        "role": "前端开发",
        "hr_feedback": "技术底子不错，但沟通太闷，且期望薪资超出部门预算",
        "decision": "淘汰",
    }
    if request.method == "POST":
        defaults = {
            "name": request.form.get("name", "").strip() or "候选人",
            "role": request.form.get("role", "").strip() or "岗位",
            "hr_feedback": request.form.get("hr_feedback", "").strip(),
            "decision": request.form.get("decision", "淘汰").strip() or "淘汰",
        }
        if not defaults["hr_feedback"]:
            flash("请填写 HR 面评。", "error")
        else:
            try:
                letter = generate_touch_letter(
                    app.config["DEEPSEEK_API_KEY"],
                    defaults["name"],
                    defaults["role"],
                    defaults["hr_feedback"],
                    defaults["decision"],
                )
            except (ValueError, RuntimeError) as exc:
                flash(str(exc), "error")
    return render_template("automation_touch.html", letter=letter, defaults=defaults)


@app.route("/automation/hr-insight", methods=["GET", "POST"])
@login_required
def automation_insight():
    steps = insight = report = conv_table = None
    avg_cycle = None
    if request.method == "POST" and request.form.get("run"):
        try:
            res = run_hr_insight_pipeline(app.config["DEEPSEEK_API_KEY"], n_rows=100)
            steps = "\n".join(res["steps"])
            insight = res["insight"]
            conv_table = res["conv_table"]
            avg_cycle = res["avg_cycle"]
            report = res["report"]
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
    return render_template(
        "automation_insight.html",
        steps=steps,
        insight=insight,
        conv_table=conv_table,
        avg_cycle=avg_cycle,
        report=report,
    )


@app.route("/report", methods=["GET", "POST"])
@login_required
def report_page():
    report = None
    selected_month = datetime.now().strftime("%Y-%m")
    if request.method == "POST":
        selected_month = request.form["month"]
        try:
            report = generate_monthly_report(selected_month)
        except Exception as exc:
            flash(f"生成月报失败：{exc}", "error")
            return redirect(url_for("report_page"))

    return render_template("report.html", report=report, selected_month=selected_month)


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
