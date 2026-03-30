#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复习计划管理系统 — Web 界面 (Flask)
启动方式：双击 start.command（macOS）或 start.bat（Windows）
访问地址：http://127.0.0.1:5001
"""

import hashlib
import io
import json
import os
import re
import secrets
import threading
import webbrowser
from datetime import date, datetime
from pathlib import Path

from flask import (Flask, abort, flash, redirect, render_template,
                   request, send_file, url_for, jsonify)
from flask_cors import CORS
from config_runtime import (env_controlled_keys, env_var_for_key,
                            get_runtime_config, load_file_config,
                            write_file_config)

# ─── 路径 ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
DATA_DIR   = BASE_DIR / "data"
PDF_DIR    = DATA_DIR / "pdfs"
UPLOAD_DIR = DATA_DIR / "uploads"
CFG_PATH   = BASE_DIR / "config.json"

for _d in (DATA_DIR, PDF_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ─── Flask ────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "review_plan_local_2026"
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:8080", "http://127.0.0.1:8080",
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:3000", "http://127.0.0.1:3000",
]}})

# ─── 内部模块 ──────────────────────────────────────────────────────────────────
from lesson_manager import (
    DEFAULT_ORGANIZATION_NAME,
    approve_registration_request,
    authenticate_user,
    create_auth_session,
    create_consultation,
    create_registration_request,
    delete_class as db_delete_class,
    delete_consultation,
    delete_lesson as db_delete_lesson,
    get_class,
    get_class_teacher_user_id,
    get_class_weeks,
    get_conn,
    get_consultation,
    get_current_user,
    get_lesson,
    get_lessons_by_week,
    get_questions,
    get_user_class_ids,
    init_db,
    list_all_users,
    list_class_teacher_bindings,
    list_classes,
    list_consultation_teachers,
    list_consultations,
    list_lessons,
    list_registration_requests,
    reject_registration_request,
    save_class,
    save_lesson,
    set_class_teacher_user_id,
    set_user_class_ids,
    update_class,
    update_consultation,
    update_user_profile,
    update_user_role,
    week_label,
)
import smart_wrong_questions
import master_data

init_db()


# ─── 工具函数 ──────────────────────────────────────────────────────────────────
def get_config():
    return get_runtime_config()


def has_api_key():
    cfg = get_config()
    provider = cfg.get("provider", "openai")
    if provider == "deepseek":
        key = cfg.get("deepseek_api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
    elif provider == "mimo":
        key = cfg.get("mimo_api_key", "") or os.environ.get("MIMO_API_KEY", "")
    elif provider == "n1n":
        key = cfg.get("n1n_api_key", "") or os.environ.get("N1N_API_KEY", "")
    else:
        key = cfg.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    return bool(key.strip())


def _extract_field(text, field):
    m = re.search(rf"(?:^|\n)\s*{re.escape(field)}\s*[：:]\s*(.+)", text)
    return m.group(1).strip() if m else ""


def _get_all_months():
    lessons = list_lessons()
    return sorted(
        set(l["date"][:7] for l in lessons if l.get("date")), reverse=True
    )


def _get_monthly_pdfs():
    """返回 {month_str: filename} 的已有月度 PDF 列表。"""
    result = {}
    for p in PDF_DIR.glob("????-??_月度综合复习.pdf"):
        m = re.match(r"(\d{4}-\d{2})_月度综合复习\.pdf", p.name)
        if m:
            result[m.group(1)] = p.name
    return result


@app.context_processor
def inject_globals():
    return dict(
        has_key=has_api_key(),
        current_endpoint=request.endpoint,
        all_classes=list_classes(),
    )


# ─── 首页 ──────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    lessons = list_lessons()[:8]
    month_now = datetime.now().strftime("%Y-%m")
    month_count = len(list_lessons(month_now))
    total_count = len(list_lessons())
    classes = list_classes()
    return render_template(
        "index.html",
        lessons=lessons,
        month_now=month_now,
        month_count=month_count,
        total_count=total_count,
        classes=classes,
    )


# ─── 添加课程 ──────────────────────────────────────────────────────────────────
@app.route("/add", methods=["GET", "POST"])
def add_lesson():
    class_id = int(request.args.get("class_id", 0) or request.form.get("class_id", 0) or 0)
    cls = get_class(class_id) if class_id else None

    if request.method == "GET":
        return render_template("add.html", today=str(date.today()),
                               cls=cls, class_id=class_id, classes=list_classes())

    if not has_api_key():
        flash("请先在设置页面填入 API Key", "error")
        return redirect(url_for("settings"))

    class_id    = int(request.form.get("class_id", 0) or 0)
    cls         = get_class(class_id) if class_id else None
    subject     = request.form.get("subject", "").strip() or (cls["subject"] if cls else "")
    grade       = request.form.get("grade",   "").strip() or (cls["grade"]   if cls else "")
    topic       = request.form.get("topic",   "").strip()
    lesson_date = request.form.get("date", "") or str(date.today())
    weak_points = request.form.get("weak_points", "").strip()
    input_type  = request.form.get("input_type", "text")

    raw_text = ""

    if input_type == "text":
        raw_text = request.form.get("summary_text", "").strip()
        if not raw_text:
            flash("请填写课堂总结内容", "error")
            return render_template("add.html", today=str(date.today()),
                                   form=request.form, cls=cls,
                                   class_id=class_id, classes=list_classes())

    elif input_type == "file":
        file = request.files.get("upload_file")
        if not file or not file.filename:
            flash("请选择上传文件", "error")
            return render_template("add.html", today=str(date.today()),
                                   form=request.form, cls=cls,
                                   class_id=class_id, classes=list_classes())

        ext = Path(file.filename).suffix.lower()
        audio_exts = {".mp3", ".m4a", ".mp4", ".wav", ".ogg", ".webm", ".flac"}

        if ext in audio_exts:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = UPLOAD_DIR / f"audio_{ts}{ext}"
            file.save(str(save_path))

            # Whisper 限制 25MB
            if save_path.stat().st_size > 25 * 1024 * 1024:
                save_path.unlink(missing_ok=True)
                flash("音频文件过大（最大 25MB，Whisper API 限制）。请压缩后重试。", "error")
                return render_template("add.html", today=str(date.today()),
                                       form=request.form, cls=cls,
                                       class_id=class_id, classes=list_classes())
            try:
                from ai_processor import transcribe_audio
                raw_text = transcribe_audio(str(save_path))
            except Exception as e:
                flash(f"音频转录失败：{e}", "error")
                return render_template("add.html", today=str(date.today()),
                                       form=request.form, cls=cls,
                                       class_id=class_id, classes=list_classes())
            finally:
                save_path.unlink(missing_ok=True)

        elif ext in {".txt", ".md", ".text"}:
            raw_text = file.read().decode("utf-8", errors="replace")

        else:
            flash(f"不支持的文件格式 {ext}，请上传 txt/md 或音频文件", "error")
            return render_template("add.html", today=str(date.today()),
                                   form=request.form, cls=cls,
                                   class_id=class_id, classes=list_classes())
    # AI 生成计划
    try:
        from ai_processor import parse_and_generate_plan
        prompt_styles = request.form.getlist("prompt_styles")
        plan = parse_and_generate_plan(
            summary_text=raw_text,
            subject=subject, grade=grade, topic=topic,
            weak_points=weak_points, lesson_date=lesson_date,
            prompt_styles=prompt_styles,
        )
    except Exception as e:
        flash(f"AI 生成失败：{e}", "error")
        return render_template("add.html", today=str(date.today()),
                               form=request.form, cls=cls,
                               class_id=class_id, classes=list_classes())

    # 生成学生版 PDF
    pdf_path = ""
    try:
        from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf
        safe = (topic or "课程").replace("/", "-").replace(" ", "_")[:28]
        pdf_name = f"{lesson_date}_{subject}_{safe}.pdf"
        pdf_path = str(PDF_DIR / pdf_name)
        generate_single_lesson_pdf(plan, pdf_path)
    except Exception as e:
        flash(f"PDF 生成失败：{e}", "error")

    # 生成答案版 PDF
    if pdf_path:
        try:
            from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf
            answer_pdf_path = pdf_path.replace(".pdf", "_答案版.pdf")
            generate_single_lesson_pdf(plan, answer_pdf_path)
        except Exception as e:
            flash(f"答案 PDF 生成失败：{e}", "warning")

    lesson_id = save_lesson(
        date_str=lesson_date, subject=subject, grade=grade,
        topic=topic, summary=raw_text, weak_points=weak_points,
        plan=plan, pdf_path=pdf_path, class_id=class_id,
    )

    flash("复习计划已生成并保存！", "success")
    if class_id:
        return redirect(url_for("class_detail", class_id=class_id))
    return redirect(url_for("lesson_detail", lesson_id=lesson_id))


# ─── 课程列表 ──────────────────────────────────────────────────────────────────
@app.route("/lessons")
def lessons_list():
    month = request.args.get("month", "")
    lessons = list_lessons(month)
    months = _get_all_months()
    return render_template("lessons.html", lessons=lessons,
                           month=month, months=months)


# ─── 班级管理 ──────────────────────────────────────────────────────────────────
@app.route("/classes")
def classes_list():
    classes = list_classes()
    return render_template("classes.html", classes=classes)


@app.route("/classes/new", methods=["GET", "POST"])
def class_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("班级名称不能为空", "error")
            return render_template("class_form.html", cls=None, action="new")
        save_class(
            name=name,
            subject=request.form.get("subject", "").strip(),
            grade=request.form.get("grade", "").strip(),
            teacher_name=request.form.get("teacher_name", "").strip(),
            teacher_email=request.form.get("teacher_email", "").strip(),
        )
        flash(f"班级「{name}」已创建！", "success")
        return redirect(url_for("classes_list"))
    return render_template("class_form.html", cls=None, action="new")


@app.route("/classes/<int:class_id>")
def class_detail(class_id):
    cls = get_class(class_id)
    if not cls:
        abort(404)
    lessons = list_lessons(class_id=class_id)
    weeks = get_class_weeks(class_id)
    weekly_pdfs = _get_weekly_pdfs(class_id)
    # group lessons by week for display
    from datetime import datetime as dt
    def _wk(date_str):
        try:
            d = dt.strptime(date_str, "%Y-%m-%d")
            y, w, _ = d.isocalendar()
            return f"{y}-W{w:02d}"
        except Exception:
            return ""
    lessons_by_week = {}
    for l in lessons:
        wk = _wk(l.get("date", ""))
        lessons_by_week.setdefault(wk, []).append(l)
    return render_template(
        "class_detail.html",
        cls=cls,
        lessons=lessons,
        weeks=weeks,
        lessons_by_week=lessons_by_week,
        weekly_pdfs=weekly_pdfs,
        week_label=week_label,
    )


@app.route("/classes/<int:class_id>/edit", methods=["GET", "POST"])
def class_edit(class_id):
    cls = get_class(class_id)
    if not cls:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("班级名称不能为空", "error")
            return render_template("class_form.html", cls=cls, action="edit")
        update_class(
            class_id=class_id,
            name=name,
            subject=request.form.get("subject", "").strip(),
            grade=request.form.get("grade", "").strip(),
            teacher_name=request.form.get("teacher_name", "").strip(),
            teacher_email=request.form.get("teacher_email", "").strip(),
        )
        flash("班级信息已更新", "success")
        return redirect(url_for("class_detail", class_id=class_id))
    return render_template("class_form.html", cls=cls, action="edit")


@app.route("/classes/<int:class_id>/delete", methods=["POST"])
def class_delete(class_id):
    cls = get_class(class_id)
    if not cls:
        abort(404)
    db_delete_class(class_id)
    flash(f"班级「{cls['name']}」已删除（课程记录已保留）", "success")
    return redirect(url_for("classes_list"))


# ─── 周报 PDF ──────────────────────────────────────────────────────────────────
def _get_weekly_pdfs(class_id: int) -> dict:
    """Return {week_str: filename} for existing weekly PDFs of a class."""
    result = {}
    for p in PDF_DIR.glob(f"class{class_id}_????-W??_周报.pdf"):
        m = re.match(rf"class{class_id}_(\d{{4}}-W\d{{2}})_周报\.pdf", p.name)
        if m:
            result[m.group(1)] = p.name
    return result


@app.route("/classes/<int:class_id>/weekly/<week_str>", methods=["POST"])
def generate_weekly(class_id, week_str):
    if not re.match(r"^\d{4}-W\d{2}$", week_str):
        abort(400)
    cls = get_class(class_id)
    if not cls:
        abort(404)

    lessons = get_lessons_by_week(class_id, week_str)
    if not lessons:
        flash("该周暂无课程记录", "error")
        return redirect(url_for("class_detail", class_id=class_id))

    try:
        from pdf_engine import generate_weekly_pdf
        pdf_name = f"class{class_id}_{week_str}_周报.pdf"
        pdf_path = str(PDF_DIR / pdf_name)
        generate_weekly_pdf(lessons, cls, week_str, pdf_path)
    except Exception as e:
        flash(f"周报 PDF 生成失败：{e}", "error")
        return redirect(url_for("class_detail", class_id=class_id))

    flash(f"周报已生成：{week_label(week_str)}", "success")
    return redirect(url_for("class_detail", class_id=class_id))


@app.route("/classes/<int:class_id>/weekly/<week_str>/download")
def download_weekly(class_id, week_str):
    if not re.match(r"^\d{4}-W\d{2}$", week_str):
        abort(400)
    pdf_name = f"class{class_id}_{week_str}_周报.pdf"
    pdf_path = PDF_DIR / pdf_name
    if not pdf_path.exists():
        abort(404)
    return send_file(str(pdf_path), as_attachment=True, download_name=pdf_name)


@app.route("/classes/<int:class_id>/weekly/<week_str>/view")
def view_weekly(class_id, week_str):
    if not re.match(r"^\d{4}-W\d{2}$", week_str):
        abort(400)
    pdf_name = f"class{class_id}_{week_str}_周报.pdf"
    pdf_path = PDF_DIR / pdf_name
    if not pdf_path.exists():
        abort(404)
    return send_file(str(pdf_path), mimetype="application/pdf",
                     download_name=pdf_name)


# ─── 课程详情 ──────────────────────────────────────────────────────────────────
@app.route("/lessons/<int:lesson_id>")
def lesson_detail(lesson_id):
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    questions = get_questions(lesson_id=lesson_id)
    cats = {}
    for q in questions:
        cats.setdefault(q.get("category") or "综合", []).append(q)

    # plan days summary for display
    plan = lesson.get("plan") or {}
    days = plan.get("days", [])

    # 检查答案版 PDF 是否存在
    has_answer_pdf = False
    if lesson.get("pdf_path"):
        answer_path = lesson["pdf_path"].replace(".pdf", "_答案版.pdf")
        has_answer_pdf = Path(answer_path).exists()

    return render_template(
        "lesson_detail.html",
        lesson=lesson,
        question_cats=cats,
        total_q=len(questions),
        days=days,
        has_answer_pdf=has_answer_pdf,
    )


# ─── 删除课程 ──────────────────────────────────────────────────────────────────
@app.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
def delete_lesson(lesson_id):
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    pdf_path = lesson.get("pdf_path", "")
    if pdf_path and Path(pdf_path).exists():
        Path(pdf_path).unlink(missing_ok=True)
    answer_pdf = pdf_path.replace(".pdf", "_答案版.pdf") if pdf_path else ""
    if answer_pdf and Path(answer_pdf).exists():
        Path(answer_pdf).unlink(missing_ok=True)
    db_delete_lesson(lesson_id)
    flash("课程已删除", "success")
    return redirect(url_for("lessons_list"))


# ─── PDF 查看 / 下载 ────────────────────────────────────────────────────────────
@app.route("/pdf/<int:lesson_id>")
@app.route("/api/pdf/<int:lesson_id>")
def serve_pdf(lesson_id):
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    pdf_path = lesson.get("pdf_path", "")
    if not pdf_path or not Path(pdf_path).exists():
        abort(404)
    return send_file(pdf_path, mimetype="application/pdf",
                     download_name=Path(pdf_path).name)


@app.route("/pdf/download/<int:lesson_id>")
@app.route("/api/pdf/download/<int:lesson_id>")
def download_pdf(lesson_id):
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    pdf_path = lesson.get("pdf_path", "")
    if not pdf_path or not Path(pdf_path).exists():
        abort(404)
    return send_file(pdf_path, as_attachment=True,
                     download_name=Path(pdf_path).name)


@app.route("/pdf/answer/<int:lesson_id>")
@app.route("/api/pdf/answer/<int:lesson_id>")
def serve_answer_pdf(lesson_id):
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    pdf_path = lesson.get("pdf_path", "")
    if not pdf_path:
        abort(404)
    answer_path = pdf_path.replace(".pdf", "_答案版.pdf")
    if not Path(answer_path).exists():
        abort(404)
    return send_file(answer_path, mimetype="application/pdf",
                     download_name=Path(answer_path).name)


@app.route("/pdf/download/answer/<int:lesson_id>")
@app.route("/api/pdf/download/answer/<int:lesson_id>")
def download_answer_pdf(lesson_id):
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    pdf_path = lesson.get("pdf_path", "")
    if not pdf_path:
        abort(404)
    answer_path = pdf_path.replace(".pdf", "_答案版.pdf")
    if not Path(answer_path).exists():
        abort(404)
    return send_file(answer_path, as_attachment=True,
                     download_name=Path(answer_path).name)


# ─── 月度复习 ──────────────────────────────────────────────────────────────────
@app.route("/monthly", methods=["GET", "POST"])
def monthly():
    months = _get_all_months()
    month_now = datetime.now().strftime("%Y-%m")
    monthly_pdfs = _get_monthly_pdfs()

    if request.method == "GET":
        lessons_by_month = {m: len(list_lessons(m)) for m in months}
        return render_template("monthly.html", months=months,
                               month_now=month_now, monthly_pdfs=monthly_pdfs,
                               lessons_by_month=lessons_by_month)

    if not has_api_key():
        flash("请先在设置页面填入 OpenAI API Key", "error")
        return redirect(url_for("settings"))

    month_str = request.form.get("month", month_now)
    lessons = list_lessons(month_str)
    if not lessons:
        flash(f"{month_str} 没有课程记录，请先添加课程。", "error")
        return render_template("monthly.html", months=months,
                               month_now=month_now, monthly_pdfs=monthly_pdfs)

    lesson_dicts = [{
        "date":        l["date"],
        "subject":     l["subject"] or "",
        "grade":       l["grade"] or "",
        "topic":       l["topic"] or "",
        "summary":     (l["summary"] or "")[:800],
        "weak_points": l["weak_points"] or "",
    } for l in lessons]

    try:
        from ai_processor import generate_monthly_plan
        plan = generate_monthly_plan(lesson_dicts, month_str)
    except Exception as e:
        flash(f"AI 生成失败：{e}", "error")
        return render_template("monthly.html", months=months,
                               month_now=month_now, monthly_pdfs=monthly_pdfs)

    try:
        from pdf_engine import generate_monthly_pdf
        pdf_name = f"{month_str}_月度综合复习.pdf"
        pdf_path = str(PDF_DIR / pdf_name)
        generate_monthly_pdf(plan, pdf_path)
    except Exception as e:
        flash(f"PDF 生成失败：{e}", "error")
        return render_template("monthly.html", months=months,
                               month_now=month_now, monthly_pdfs=monthly_pdfs)

    flash(f"{month_str} 月度复习 PDF 已生成！", "success")
    monthly_pdfs = _get_monthly_pdfs()
    lessons_by_month = {m: len(list_lessons(m)) for m in months}
    return render_template("monthly.html", months=months,
                           month_now=month_now, monthly_pdfs=monthly_pdfs,
                           lessons_by_month=lessons_by_month)


@app.route("/monthly/download/<month_str>")
def download_monthly_pdf(month_str):
    if not re.match(r"^\d{4}-\d{2}$", month_str):
        abort(400)
    pdf_name = f"{month_str}_月度综合复习.pdf"
    pdf_path = PDF_DIR / pdf_name
    if not pdf_path.exists():
        abort(404)
    return send_file(str(pdf_path), as_attachment=True,
                     download_name=pdf_name)


@app.route("/monthly/view/<month_str>")
def view_monthly_pdf(month_str):
    if not re.match(r"^\d{4}-\d{2}$", month_str):
        abort(400)
    pdf_name = f"{month_str}_月度综合复习.pdf"
    pdf_path = PDF_DIR / pdf_name
    if not pdf_path.exists():
        abort(404)
    return send_file(str(pdf_path), mimetype="application/pdf",
                     download_name=pdf_name)


# ─── 题库 ──────────────────────────────────────────────────────────────────────
@app.route("/quiz")
def quiz():
    month     = request.args.get("month", "")
    lesson_id = int(request.args.get("lesson_id", 0))
    questions = get_questions(lesson_id=lesson_id, month_str=month)
    cats = {}
    for q in questions:
        cats.setdefault(q.get("category") or "综合", []).append(q)
    return render_template(
        "quiz.html",
        question_cats=cats,
        total_q=len(questions),
        months=_get_all_months(),
        all_lessons=list_lessons(),
        month=month,
        lesson_id=lesson_id,
    )


# ─── 设置 ──────────────────────────────────────────────────────────────────────
@app.route("/settings", methods=["GET", "POST"])
def settings():
    cfg = get_config()
    controlled_keys = env_controlled_keys()

    def _mask(key):
        if len(key) > 12:
            return key[:8] + "..." + key[-4:]
        return "*" * len(key) if key else ""

    if request.method == "POST":
        file_cfg = load_file_config()

        if "provider" not in controlled_keys:
            file_cfg["provider"] = request.form.get("provider", "openai").strip()

        openai_key = request.form.get("openai_api_key", "").strip()
        if openai_key and "openai_api_key" not in controlled_keys:
            file_cfg["openai_api_key"] = openai_key

        deepseek_key = request.form.get("deepseek_api_key", "").strip()
        if deepseek_key and "deepseek_api_key" not in controlled_keys:
            file_cfg["deepseek_api_key"] = deepseek_key

        mimo_key = request.form.get("mimo_api_key", "").strip()
        if mimo_key and "mimo_api_key" not in controlled_keys:
            file_cfg["mimo_api_key"] = mimo_key

        mimo_base_url = request.form.get("mimo_base_url", "").strip()
        if mimo_base_url and "mimo_base_url" not in controlled_keys:
            file_cfg["mimo_base_url"] = mimo_base_url

        n1n_key = request.form.get("n1n_api_key", "").strip()
        if n1n_key and "n1n_api_key" not in controlled_keys:
            file_cfg["n1n_api_key"] = n1n_key

        n1n_base_url = request.form.get("n1n_base_url", "").strip()
        if n1n_base_url and "n1n_base_url" not in controlled_keys:
            file_cfg["n1n_base_url"] = n1n_base_url

        write_file_config(file_cfg)
        if controlled_keys:
            flash("部分设置由环境变量控制，页面保存不会覆盖这些字段。", "info")
        flash("设置已保存！", "success")
        return redirect(url_for("settings"))

    controlled_env = {
        key: env_var_for_key(key)
        for key in controlled_keys
        if env_var_for_key(key)
    }

    return render_template(
        "settings.html",
        provider=cfg.get("provider", "openai"),
        openai_key_set=bool(cfg.get("openai_api_key", "")),
        openai_masked=_mask(cfg.get("openai_api_key", "")),
        deepseek_key_set=bool(cfg.get("deepseek_api_key", "")),
        deepseek_masked=_mask(cfg.get("deepseek_api_key", "")),
        mimo_key_set=bool(cfg.get("mimo_api_key", "")),
        mimo_masked=_mask(cfg.get("mimo_api_key", "")),
        mimo_base_url=cfg.get("mimo_base_url", ""),
        n1n_key_set=bool(cfg.get("n1n_api_key", "")),
        n1n_masked=_mask(cfg.get("n1n_api_key", "")),
        n1n_base_url=cfg.get("n1n_base_url", "https://api.n1n.ai/v1"),
        controlled_env=controlled_env,
    )


# ─── JSON API ──────────────────────────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    user, error = authenticate_user(username=username, password=password)
    if not user:
        return jsonify({"error": error}), 401
    token = create_auth_session(user["id"])
    return jsonify({"token": token, "user": user})


@app.route("/api/register-request", methods=["POST"])
def api_register_request():
    data = request.json or {}
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    password = data.get("password", "").strip()
    organization_name = data.get("organization_name", "").strip() or DEFAULT_ORGANIZATION_NAME

    if not username or not display_name or not password:
        return jsonify({"error": "请填写完整的注册信息"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码至少需要 6 位"}), 400
    if organization_name != DEFAULT_ORGANIZATION_NAME:
        return jsonify({"error": "当前仅支持加入星润Starain"}), 400
    try:
        item = create_registration_request(
            username=username,
            display_name=display_name,
            password=password,
            organization_name=organization_name,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"id": item["id"], "status": item["status"]}), 201


def _require_auth():
    token = request.headers.get("X-Auth-Token", "").strip()
    user = get_current_user(token)
    if not user:
        return None, (jsonify({"error": "未授权"}), 401)
    return user, None


def _require_staff():
    user, error = _require_auth()
    if error:
        return None, error
    if user.get("role") not in {"owner", "admin"}:
        return None, (jsonify({"error": "无权限"}), 403)
    return user, None


def _require_owner():
    user, error = _require_auth()
    if error:
        return None, error
    if user.get("role") != "owner":
        return None, (jsonify({"error": "无权限"}), 403)
    return user, None


@app.route("/api/me", methods=["GET"])
def api_me():
    user, error = _require_auth()
    if error:
        return error
    return jsonify(user)


@app.route("/api/profile", methods=["PUT"])
def api_profile_update():
    user, error = _require_auth()
    if error:
        return error
    data = request.json or {}
    new_username = data.get("username", "").strip()
    new_display_name = data.get("display_name", "").strip()
    if not new_username or not new_display_name:
        return jsonify({"error": "用户名和昵称不能为空"}), 400
    try:
        update_user_profile(user["id"], new_username, new_display_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"ok": True})


@app.route("/api/admin/registration-requests", methods=["GET"])
def api_admin_registration_requests():
    _, error = _require_owner()
    if error:
        return error
    return jsonify({"items": list_registration_requests("pending")})


@app.route("/api/admin/registration-requests/<int:request_id>/approve", methods=["POST"])
def api_admin_registration_request_approve(request_id):
    user, error = _require_owner()
    if error:
        return error
    try:
        approved = approve_registration_request(request_id=request_id, reviewer_id=user["id"])
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"ok": True, "user": approved})


@app.route("/api/admin/registration-requests/<int:request_id>/reject", methods=["POST"])
def api_admin_registration_request_reject(request_id):
    user, error = _require_owner()
    if error:
        return error
    try:
        reject_registration_request(request_id=request_id, reviewer_id=user["id"])
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"ok": True})


@app.route("/api/admin/users", methods=["GET"])
def api_admin_users():
    _, error = _require_staff()
    if error:
        return error
    users = list_all_users()
    return jsonify([{"id": u["id"], "name": u["display_name"], "org": u["organization_name"], "role": u["role"]} for u in users])


@app.route("/api/admin/users/<int:user_id>/role", methods=["PUT"])
def api_admin_user_role_set(user_id):
    _, error = _require_owner()
    if error:
        return error
    data = request.json or {}
    role = data.get("role")
    if role not in ("admin", "member"):
        return jsonify({"error": "role must be admin or member"}), 400
    update_user_role(user_id, role)
    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:user_id>/classes", methods=["GET"])
def api_admin_user_classes_get(user_id):
    _, error = _require_staff()
    if error:
        return error
    return jsonify({"class_ids": get_user_class_ids(user_id)})


@app.route("/api/admin/users/<int:user_id>/classes", methods=["PUT"])
def api_admin_user_classes_set(user_id):
    _, error = _require_staff()
    if error:
        return error
    data = request.json or {}
    class_ids = data.get("class_ids", [])
    if not isinstance(class_ids, list):
        return jsonify({"error": "class_ids must be a list"}), 400
    try:
        set_user_class_ids(user_id, class_ids)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True})


@app.route("/api/master-data/mappings/wrong-questions", methods=["GET"])
def api_master_data_wrong_question_mapping_queue():
    _, error = _require_staff()
    if error:
        return error
    status = (request.args.get("status") or "").strip() or None
    return jsonify({"items": master_data.list_wrong_question_mapping_queue(status=status)})


@app.route("/api/master-data/mappings/wrong-questions/<record_id>", methods=["PUT"])
def api_master_data_wrong_question_mapping_resolve(record_id):
    user, error = _require_staff()
    if error:
        return error
    payload = request.json or {}
    try:
        resolved = master_data.resolve_wrong_question_mapping(
            actor_user_id=user["id"],
            record_id=record_id,
            teacher_user_id=payload.get("teacher_user_id"),
            class_id=payload.get("class_id"),
            mapping_status=(payload.get("mapping_status") or "mapped").strip() or "mapped",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(resolved)


@app.route("/api/master-data/users/<int:user_id>/aliases", methods=["GET"])
def api_master_data_user_aliases_get(user_id):
    _, error = _require_staff()
    if error:
        return error
    try:
        return jsonify({"aliases": master_data.list_user_aliases(user_id)})
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404


@app.route("/api/master-data/users/<int:user_id>/aliases", methods=["PUT"])
def api_master_data_user_aliases_put(user_id):
    user, error = _require_staff()
    if error:
        return error
    payload = request.json or {}
    aliases = payload.get("aliases", [])
    if not isinstance(aliases, list):
        return jsonify({"error": "aliases must be a list"}), 400
    try:
        updated_aliases = master_data.set_user_aliases(
            actor_user_id=user["id"],
            user_id=user_id,
            aliases=aliases,
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"aliases": updated_aliases})


@app.route("/api/master-data/classes/<int:class_id>/aliases", methods=["GET"])
def api_master_data_class_aliases_get(class_id):
    _, error = _require_staff()
    if error:
        return error
    try:
        return jsonify({"aliases": master_data.list_class_aliases(class_id)})
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404


@app.route("/api/master-data/classes/<int:class_id>/aliases", methods=["PUT"])
def api_master_data_class_aliases_put(class_id):
    user, error = _require_staff()
    if error:
        return error
    payload = request.json or {}
    aliases = payload.get("aliases", [])
    if not isinstance(aliases, list):
        return jsonify({"error": "aliases must be a list"}), 400
    try:
        updated_aliases = master_data.set_class_aliases(
            actor_user_id=user["id"],
            class_id=class_id,
            aliases=aliases,
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"aliases": updated_aliases})


@app.route("/api/wrong-questions", methods=["GET"])
def api_wrong_questions_list():
    _, error = _require_staff()
    if error:
        return error
    try:
        return jsonify(smart_wrong_questions.fetch_wrong_question_records(request.args))
    except smart_wrong_questions.WrongQuestionProxyError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@app.route("/api/wrong-questions/summary/export", methods=["GET"])
def api_wrong_question_summary_export():
    _, error = _require_staff()
    if error:
        return error
    try:
        export_result = smart_wrong_questions.export_wrong_question_summary(request.args)
    except smart_wrong_questions.WrongQuestionProxyError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return send_file(
        io.BytesIO(export_result["content"]),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=export_result["filename"],
    )


@app.route("/api/wrong-questions/<record_id>", methods=["GET"])
def api_wrong_question_detail(record_id):
    _, error = _require_staff()
    if error:
        return error
    try:
        return jsonify(smart_wrong_questions.fetch_wrong_question_record(record_id, request.args))
    except smart_wrong_questions.WrongQuestionProxyError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@app.route("/api/wrong-questions/<record_id>/review", methods=["PUT"])
def api_wrong_question_review_save(record_id):
    _, error = _require_staff()
    if error:
        return error
    try:
        return jsonify(
            smart_wrong_questions.save_wrong_question_review(record_id, request.args, request.json or {})
        )
    except smart_wrong_questions.WrongQuestionProxyError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@app.route("/api/consultations", methods=["GET"])
def api_consultations_list():
    _, error = _require_auth()
    if error:
        return error
    return jsonify(list_consultations(query=request.args.get("q", "")))


@app.route("/api/consultation-teachers", methods=["GET"])
def api_consultation_teachers():
    _, error = _require_auth()
    if error:
        return error
    return jsonify(list_consultation_teachers())


@app.route("/api/consultations/<int:consultation_id>", methods=["GET"])
def api_consultation_get(consultation_id):
    _, error = _require_auth()
    if error:
        return error
    item = get_consultation(consultation_id)
    if not item:
        return jsonify({"error": "not found"}), 404
    return jsonify(item)


@app.route("/api/consultations", methods=["POST"])
def api_consultation_create():
    _, error = _require_auth()
    if error:
        return error
    item = create_consultation(request.json or {})
    return jsonify(item), 201


@app.route("/api/consultations/<int:consultation_id>", methods=["PUT"])
def api_consultation_update(consultation_id):
    _, error = _require_owner()
    if error:
        return error
    item = update_consultation(consultation_id, request.json or {})
    if not item:
        return jsonify({"error": "not found"}), 404
    return jsonify(item)


@app.route("/api/consultations/<int:consultation_id>", methods=["DELETE"])
def api_consultation_delete(consultation_id):
    _, error = _require_owner()
    if error:
        return error
    deleted = delete_consultation(consultation_id)
    if not deleted:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/stats")
def api_stats():
    _, error = _require_auth()
    if error:
        return error
    month_now = datetime.now().strftime("%Y-%m")
    all_lessons = list_lessons()
    total_pdfs = sum(1 for l in all_lessons if l.get("pdf_path") and Path(l["pdf_path"]).exists())
    with get_conn() as conn:
        total_questions = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    return jsonify({
        "total_lessons": len(all_lessons),
        "month_lessons": len(list_lessons(month_now)),
        "total_pdfs": total_pdfs,
        "total_questions": total_questions,
    })


@app.route("/api/classes", methods=["GET"])
def api_classes_list():
    _, error = _require_auth()
    if error:
        return error
    return jsonify(list_classes())


@app.route("/api/classes", methods=["POST"])
def api_class_create():
    _, error = _require_staff()
    if error:
        return error
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "班级名称不能为空"}), 400
    cid = save_class(
        name=name,
        subject=data.get("subject", "").strip(),
        grade=data.get("grade", "").strip(),
        teacher_name=data.get("teacher_name", "").strip(),
        teacher_email=data.get("teacher_email", "").strip(),
    )
    return jsonify({"id": cid, "name": name}), 201


@app.route("/api/classes/teacher-bindings", methods=["GET"])
def api_class_teacher_bindings_list():
    _, error = _require_staff()
    if error:
        return error
    return jsonify({"teacher_bindings": list_class_teacher_bindings()})


@app.route("/api/classes/<int:class_id>", methods=["GET"])
def api_class_get(class_id):
    _, error = _require_auth()
    if error:
        return error
    cls = get_class(class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    lessons = list_lessons(class_id=class_id)
    return jsonify({**cls, "lessons": lessons})


@app.route("/api/classes/<int:class_id>/teacher", methods=["PUT"])
def api_class_teacher_set(class_id):
    _, error = _require_staff()
    if error:
        return error
    data = request.json or {}
    teacher_user_id = data.get("teacher_user_id")
    try:
        set_class_teacher_user_id(class_id, teacher_user_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        message = str(exc)
        status_code = 404 if message in {"class not found", "user not found"} else 400
        return jsonify({"error": message}), status_code
    return jsonify({"ok": True, "teacher_user_id": get_class_teacher_user_id(class_id)})


@app.route("/api/classes/<int:class_id>", methods=["PUT"])
def api_class_update(class_id):
    _, error = _require_staff()
    if error:
        return error
    cls = get_class(class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "班级名称不能为空"}), 400
    teacher_name = None
    if "teacher_name" in data:
        teacher_name = (data.get("teacher_name") or "").strip()
    teacher_email = None
    if "teacher_email" in data:
        teacher_email = (data.get("teacher_email") or "").strip()
    update_class(
        class_id=class_id,
        name=name,
        subject=data.get("subject", "").strip(),
        grade=data.get("grade", "").strip(),
        teacher_name=teacher_name,
        teacher_email=teacher_email,
    )
    return jsonify({"ok": True})


@app.route("/api/classes/<int:class_id>", methods=["DELETE"])
def api_class_delete(class_id):
    _, error = _require_staff()
    if error:
        return error
    cls = get_class(class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    db_delete_class(class_id)
    return jsonify({"ok": True})


@app.route("/api/lessons", methods=["GET"])
def api_lessons_list():
    _, error = _require_auth()
    if error:
        return error
    month = request.args.get("month", "")
    class_id = request.args.get("class_id", 0, type=int)
    return jsonify(list_lessons(month_str=month if month else None,
                                class_id=class_id if class_id else None))


@app.route("/api/lessons/<int:lesson_id>", methods=["GET"])
def api_lesson_get(lesson_id):
    _, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson:
        return jsonify({"error": "not found"}), 404
    questions = get_questions(lesson_id=lesson_id)
    return jsonify({**lesson, "questions": questions})


@app.route("/api/lessons/<int:lesson_id>", methods=["DELETE"])
def api_lesson_delete(lesson_id):
    _, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson:
        return jsonify({"error": "not found"}), 404
    pdf_path = lesson.get("pdf_path", "")
    if pdf_path and Path(pdf_path).exists():
        Path(pdf_path).unlink(missing_ok=True)
    db_delete_lesson(lesson_id)
    return jsonify({"ok": True})


@app.route("/api/lessons", methods=["POST"])
def api_lesson_create():
    _, error = _require_auth()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "系统 API Key 未配置，请联系管理员"}), 400
    
    if request.is_json:
        data = request.json or {}
    else:
        data = request.form or {}
        
    lesson_date = data.get("date") or str(date.today())
    class_id    = int(data.get("class_id") or 0)
    cls         = get_class(class_id) if class_id else None
    subject     = data.get("subject", "").strip() or (cls["subject"] if cls else "")
    grade       = data.get("grade", "").strip() or (cls["grade"] if cls else "")
    topic       = data.get("topic", "").strip()
    weak_points = data.get("weak_points", "").strip()
    
    input_type = data.get("input_type", "text")
    raw_text = ""
    
    if input_type == "text" or request.is_json:
        raw_text = data.get("summary_text", "").strip()
        if not raw_text:
            return jsonify({"error": "请填写课堂总结内容"}), 400
    else:
        file = request.files.get("upload_file")
        if not file or not file.filename:
            return jsonify({"error": "请上传音频或文本文件"}), 400
        
        ext = Path(file.filename).suffix.lower()
        if ext in {".mp3", ".m4a", ".mp4", ".wav", ".ogg", ".webm", ".flac"}:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = UPLOAD_DIR / f"audio_{ts}{ext}"
            file.save(str(save_path))
            
            if save_path.stat().st_size > 25 * 1024 * 1024:
                save_path.unlink(missing_ok=True)
                return jsonify({"error": "音频文件过大（最大 25MB）"}), 400
                
            try:
                from ai_processor import transcribe_audio
                raw_text = transcribe_audio(str(save_path))
            except Exception as e:
                save_path.unlink(missing_ok=True)
                return jsonify({"error": f"音频转录失败：{e}"}), 500
            save_path.unlink(missing_ok=True)
        elif ext in {".txt", ".md", ".text"}:
            raw_text = file.read().decode("utf-8", errors="replace")
        else:
            return jsonify({"error": f"不支持的文件格式 {ext}"}), 400

    if not raw_text:
        return jsonify({"error": "提取的总结内容为空"}), 400

    try:
        from ai_processor import parse_and_generate_plan
        plan = parse_and_generate_plan(
            summary_text=raw_text, subject=subject, grade=grade,
            topic=topic, weak_points=weak_points, lesson_date=lesson_date,
        )
    except Exception as e:
        return jsonify({"error": f"AI 生成失败：{e}"}), 500
    pdf_path = ""
    try:
        from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf
        safe = (topic or "课程").replace("/", "-").replace(" ", "_")[:28]
        pdf_name = f"{lesson_date}_{subject}_{safe}.pdf"
        pdf_path = str(PDF_DIR / pdf_name)
        generate_single_lesson_pdf(plan, pdf_path)
    except Exception:
        pass
    lesson_id = save_lesson(
        date_str=lesson_date, subject=subject, grade=grade,
        topic=topic, summary=raw_text, weak_points=weak_points,
        plan=plan, pdf_path=pdf_path, class_id=class_id,
    )
    return jsonify({"id": lesson_id, "success": True}), 201


@app.route("/api/quiz", methods=["GET"])
def api_quiz():
    _, error = _require_auth()
    if error:
        return error
    month     = request.args.get("month", "")
    lesson_id = request.args.get("lesson_id", 0, type=int)
    questions = get_questions(lesson_id=lesson_id if lesson_id else None,
                              month_str=month if month else None)
    cats = {}
    for q in questions:
        cats.setdefault(q.get("category") or "综合", []).append(q)
    return jsonify({"total": len(questions), "categories": cats})


@app.route("/api/monthly", methods=["GET"])
def api_monthly_list():
    _, error = _require_auth()
    if error:
        return error
    months = _get_all_months()
    monthly_pdfs = _get_monthly_pdfs()
    return jsonify({
        "months": [{"month": m, "count": len(list_lessons(m)),
                    "has_pdf": m in monthly_pdfs} for m in months]
    })


@app.route("/api/monthly/generate", methods=["POST"])
def api_monthly_generate():
    _, error = _require_auth()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "请先在设置页面填入 API Key"}), 400
    data = request.json or {}
    month_str = data.get("month") or datetime.now().strftime("%Y-%m")
    lessons = list_lessons(month_str)
    if not lessons:
        return jsonify({"error": f"{month_str} 没有课程记录"}), 400
    lesson_dicts = [{"date": l["date"], "subject": l["subject"] or "",
                     "grade": l["grade"] or "", "topic": l["topic"] or "",
                     "summary": (l["summary"] or "")[:800],
                     "weak_points": l["weak_points"] or ""} for l in lessons]
    try:
        from ai_processor import generate_monthly_plan
        plan = generate_monthly_plan(lesson_dicts, month_str)
        from pdf_engine import generate_monthly_pdf
        pdf_name = f"{month_str}_月度综合复习.pdf"
        generate_monthly_pdf(plan, str(PDF_DIR / pdf_name))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True, "filename": pdf_name})


@app.route("/api/analyze", methods=["POST"])
def api_analyze_text():
    _, error = _require_auth()
    if error:
        return error
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "请提供文本内容"}), 400
    try:
        from ai_processor import _get_client, _get_chat_model
        client = _get_client()
        resp = client.chat.completions.create(
            model=_get_chat_model(),
            messages=[
                {"role": "system", "content": (
                    "你是教学助手。根据课堂笔记提取关键信息，以JSON格式返回，"
                    "包含三个字段：subject（科目，如语文/数学/英语等，若无法判断则为空字符串）、"
                    "topic（本节课主题，简短概括，不超过20字）、"
                    "weak_points（学生薄弱点，若无明显提及则为空字符串）。只返回JSON，不要其他文字。"
                )},
                {"role": "user", "content": f"课堂笔记：\n{text}"},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        result = json.loads(raw)
        return jsonify({
            "subject": result.get("subject", ""),
            "topic": result.get("topic", ""),
            "weak_points": result.get("weak_points", ""),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    _, error = _require_auth()
    if error:
        return error
    cfg = get_config()
    controlled_keys = env_controlled_keys()
    def _mask(k):
        return (k[:4] + "..." + k[-4:]) if len(k) > 8 else ("*" * len(k) if k else "")
    return jsonify({
        "provider": cfg.get("provider", "openai"),
        "openai_set": bool(cfg.get("openai_api_key")),
        "openai_masked": _mask(cfg.get("openai_api_key", "")),
        "deepseek_set": bool(cfg.get("deepseek_api_key")),
        "deepseek_masked": _mask(cfg.get("deepseek_api_key", "")),
        "mimo_set": bool(cfg.get("mimo_api_key")),
        "mimo_masked": _mask(cfg.get("mimo_api_key", "")),
        "mimo_base_url": cfg.get("mimo_base_url", ""),
        "n1n_set": bool(cfg.get("n1n_api_key")),
        "n1n_masked": _mask(cfg.get("n1n_api_key", "")),
        "n1n_base_url": cfg.get("n1n_base_url", "https://api.n1n.ai/v1"),
        "controlled_keys": sorted(controlled_keys),
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_save():
    _, error = _require_auth()
    if error:
        return error
    cfg = load_file_config()
    data = request.json or {}
    controlled_keys = env_controlled_keys()
    if "provider" in data and "provider" not in controlled_keys:
        cfg["provider"] = data["provider"].strip()
    for key in ("openai_api_key", "deepseek_api_key", "mimo_api_key", "mimo_base_url", "n1n_api_key", "n1n_base_url"):
        if data.get(key) and key not in controlled_keys:
            cfg[key] = data[key].strip()
    write_file_config(cfg)
    return jsonify({"ok": True, "controlled_keys": sorted(controlled_keys)})


# ─── 启动 ──────────────────────────────────────────────────────────────────────
def _open_browser():
    import time
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5001")


if __name__ == "__main__":
    init_db()
    threading.Thread(target=_open_browser, daemon=True).start()
    print("\n" + "=" * 50)
    print("  📚 复习计划管理系统已启动")
    print("  浏览器即将自动打开")
    print("  地址：http://127.0.0.1:5001")
    print("  按 Ctrl+C 关闭程序")
    print("=" * 50 + "\n")
    app.run(host="127.0.0.1", port=5001, debug=False)
