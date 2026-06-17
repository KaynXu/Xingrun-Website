from __future__ import annotations

from pathlib import Path

from review_plan_workflow.schemas import normalize_final_review_plan
from review_plan_templates.generate_review_pdfs import build_lesson_filename_part, normalize_portable_text, render_review_plan_pdf


DEFAULT_FINAL_REMINDERS = [
    "每一个复习日都要完整复习整节课内容。",
    "先回忆课堂原话，再完成当天填空与选择。",
    "遇到不会的题先回看课堂总结，再补做口头复述。",
]
BAD_QUOTE_PATTERNS = (
    "每一个复习日",
    "完整复习整节课内容",
    "请完成以上",
    "对照答案自检",
    "完成当天",
    "完成以上填空",
    "完成标准",
    "使用说明",
    "复习计划",
    "正确率≥",
    "正确率>=",
    "填空题全部正确",
    "能独立",
)


def _clean_text(value: object, default: str = "") -> str:
    text = normalize_portable_text(str(value or "").strip())
    return text or default


def _dedupe_clean_lines(values: object) -> list[str]:
    lines: list[str] = []
    if not isinstance(values, list):
        return lines
    for value in values:
        text = _clean_text(value)
        if text and text not in lines:
            lines.append(text)
    return lines


def _is_real_class_quote(value: object) -> bool:
    text = _clean_text(value)
    if not text:
        return False
    return not any(pattern in text for pattern in BAD_QUOTE_PATTERNS)


def _dedupe_real_quotes(values: object) -> list[str]:
    return [text for text in _dedupe_clean_lines(values) if _is_real_class_quote(text)]


def _append_blank_once(blanks: list[tuple[str, str]], text: object, answer: object = "") -> None:
    clean_text = _clean_text(text)
    if not clean_text:
        return
    for existing_text, _existing_answer in blanks:
        if _clean_text(existing_text) == clean_text:
            return
    blanks.append((clean_text, _clean_text(answer, "见课堂笔记")))


def _append_task_once(tasks: list[str], text: object) -> None:
    clean_text = _clean_text(text)
    if clean_text and clean_text not in tasks:
        tasks.append(clean_text)


def _promote_active_recall(active_recall: object, tasks: list[str], blanks: list[tuple[str, str]]) -> None:
    if isinstance(active_recall, str):
        _append_task_once(tasks, active_recall)
        return
    if not isinstance(active_recall, dict):
        return

    for field in ("instructions", "instruction", "question", "prompt", "expected", "content"):
        value = active_recall.get(field)
        if isinstance(value, list):
            for item in value:
                _append_task_once(tasks, item)
        else:
            _append_task_once(tasks, value)

    for blank in active_recall.get("blanks", []) if isinstance(active_recall.get("blanks"), list) else []:
        if isinstance(blank, dict):
            _append_blank_once(blanks, blank.get("label") or blank.get("text") or blank.get("stem"), blank.get("answer"))

    for item in active_recall.get("items", []) if isinstance(active_recall.get("items"), list) else []:
        if not isinstance(item, dict):
            _append_task_once(tasks, item)
            continue
        _append_task_once(tasks, item.get("instruction") or item.get("question") or item.get("prompt") or item.get("stem"))
        for blank in item.get("blanks", []) if isinstance(item.get("blanks"), list) else []:
            if not isinstance(blank, dict):
                _append_blank_once(blanks, blank)
                continue
            _append_blank_once(blanks, blank.get("label") or blank.get("text") or blank.get("stem"), blank.get("answer"))


def collect_plan_quotes(plan_data: dict) -> list[str]:
    quotes: list[str] = []
    for text in _dedupe_real_quotes(plan_data.get("quotes")):
        quotes.append(text)
    for text in _dedupe_real_quotes(plan_data.get("lesson_info", {}).get("quotes")):
        if text not in quotes:
            quotes.append(text)
    for day_data in plan_data.get("days", []):
        for text in _dedupe_real_quotes(day_data.get("quotes")):
            if text not in quotes:
                quotes.append(text)
    return quotes[:5]


def extract_knowledge_sections(plan_data: dict) -> dict:
    source = plan_data.get("knowledge_sections")
    if not isinstance(source, dict):
        return {}
    normalized: dict = {}
    for day, sections in source.items():
        day_key = _clean_text(day)
        if not day_key or not isinstance(sections, list):
            continue
        normalized_sections = []
        for section in sections:
            if isinstance(section, dict):
                normalized_sections.append(section)
        if normalized_sections:
            normalized[day_key] = normalized_sections
    return normalized


def _default_choice(topic: str, day_number: int) -> dict:
    return {
        "question": f"第{day_number}天关于{topic or '本课内容'}的自测题，最该先复述哪一步？",
        "options": [
            "A. 先回忆整节课的核心方法",
            "B. 直接跳到最后一道题",
            "C. 只看答案不复盘过程",
            "D. 只记零散结论不看结构",
        ],
        "answer": "A",
    }


def _question_pool(plan_data: dict) -> list[dict]:
    topic = _clean_text(plan_data.get("lesson_info", {}).get("topic"), "本课内容")
    pool: list[dict] = []
    for question in plan_data.get("questions", []):
        question_text = _clean_text(question.get("question"))
        answer_text = _clean_text(question.get("answer"), "先完整复述本课方法，再回到题目。")
        if not question_text:
            continue
        pool.append(
            {
                "question": question_text,
                "options": [
                    f"A. {answer_text}",
                    "B. 只看结果不看过程",
                    "C. 跳过课堂原话直接猜",
                    "D. 只做最后一题",
                ],
                "answer": "A",
            }
        )
    if not pool:
        pool.append(_default_choice(topic, 1))
    return pool


def adapt_day(day_data: dict, question_pool: list[dict], topic: str) -> dict:
    day_number = int(day_data.get("day") or day_data.get("day_number") or 0) or 1
    tasks: list[str] = []
    blanks: list[tuple[str, str]] = []

    for step in day_data.get("steps", []):
        title = _clean_text(step.get("title"))
        if title:
            tasks.append(title)
        for item in step.get("items", []):
            text = _clean_text(item.get("text"))
            if item.get("type") == "fill" and text:
                _append_blank_once(blanks, text, item.get("answer"))
            elif item.get("type") == "body" and text:
                tasks.append(text)

    for item in day_data.get("items", []):
        text = _clean_text(item.get("text"))
        if item.get("type") == "fill" and text:
            _append_blank_once(blanks, text, item.get("answer"))
        elif text:
            tasks.append(text)

    for field in ("goal", "focus"):
        text = _clean_text(day_data.get(field))
        if text and text not in tasks:
            tasks.append(text)

    active_recall = day_data.get("active_recall")
    _promote_active_recall(active_recall, tasks, blanks)

    for blank in day_data.get("blanks", []) if isinstance(day_data.get("blanks"), list) else []:
        if isinstance(blank, dict):
            text = _clean_text(blank.get("text"))
            answer = _clean_text(blank.get("answer"), "见课堂笔记")
        elif isinstance(blank, (list, tuple)) and blank:
            text = _clean_text(blank[0])
            answer = _clean_text(blank[1] if len(blank) > 1 else "", "见课堂笔记")
        else:
            text = _clean_text(blank)
            answer = "见课堂笔记"
        if text:
            _append_blank_once(blanks, text, answer)

    phrase = _clean_text(day_data.get("self_test_phrase"))
    if phrase:
        tasks.append(phrase)
    elif isinstance(active_recall, dict):
        phrase = _clean_text(active_recall.get("expected") or active_recall.get("instructions"))
        if phrase:
            tasks.append(phrase)

    task_values = tasks[:5] or [f"完整复习{topic or '本课内容'}并复述关键方法。"]
    blank_values = blanks[:7] or [(f"第{day_number}天请回忆{topic or '本课内容'}中的关键空格。", "见课堂笔记")]

    explicit_choices: list[dict] = []
    for choice in day_data.get("choices", []) if isinstance(day_data.get("choices"), list) else []:
        if not isinstance(choice, dict):
            continue
        question = _clean_text(choice.get("question") or choice.get("stem"))
        options = _dedupe_clean_lines(choice.get("options"))
        answer = _clean_text(choice.get("answer"), "A")
        if question and options:
            explicit_choices.append({"question": question, "options": options, "answer": answer})

    if explicit_choices:
        choice_values = explicit_choices[:2]
    else:
        choice_values = [question_pool[(day_number - 1) % len(question_pool)]]
    quote_values = _dedupe_real_quotes(day_data.get("quotes"))
    if phrase and _is_real_class_quote(phrase) and phrase not in quote_values:
        quote_values.append(phrase)

    return {
        "offset": day_number,
        "day": f"第{day_number}天",
        "focus": _clean_text(
            day_data.get("focus") or day_data.get("review_focus") or day_data.get("theme") or day_data.get("label"),
            f"聚焦复习{topic or '本课内容'}",
        ),
        "goal": _clean_text(
            day_data.get("goal") or day_data.get("review_goal"),
            f"完整回顾{topic or '本课内容'}，并复述关键方法与易错点。",
        ),
        "tasks": task_values,
        "blanks": blank_values,
        "choices": choice_values,
        "quotes": quote_values,
    }


def adapt_plan_to_review_template(plan_data: dict) -> tuple[dict, list[dict], list[str]]:
    plan_data = normalize_final_review_plan(plan_data)
    lesson_info = plan_data.get("lesson_info", {})
    topic = _clean_text(lesson_info.get("topic") or plan_data.get("topic"), "课后")
    weak_points = _clean_text(plan_data.get("weak_points_summary"))
    full_review_topics = _dedupe_clean_lines(lesson_info.get("key_categories"))
    for text in _dedupe_clean_lines(plan_data.get("full_review_topics")):
        if text not in full_review_topics:
            full_review_topics.append(text)
    lesson = {
        "title": f"{topic}复习计划",
        "subtitle": "",
        "audience": "老师发给学生使用",
        "duration": "每次 10-20 分钟",
        "base_date": _clean_text(lesson_info.get("date") or plan_data.get("lesson_date")),
        "core_points": [weak_points] if weak_points else [],
        "full_review_topics": full_review_topics or [topic],
        "quotes": collect_plan_quotes(plan_data),
    }
    question_pool = _question_pool(plan_data)
    days = [adapt_day(day_data, question_pool, topic) for day_data in plan_data.get("days", [])]
    if not days:
        days = [adapt_day({"day": 1, "label": "第1天", "items": []}, question_pool, topic)]
    reminders = _dedupe_clean_lines(plan_data.get("final_reminder_lines")) or list(DEFAULT_FINAL_REMINDERS)
    return lesson, days, reminders


def generate_single_lesson_pdf(plan_data: dict, output_path: str) -> str:
    lesson, days, reminders = adapt_plan_to_review_template(plan_data)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return render_review_plan_pdf(
        lesson=lesson,
        days=days,
        final_reminder_lines=reminders,
        output_path=str(output),
        variant_key="cn",
        knowledge_sections=extract_knowledge_sections(plan_data),
        base_date=lesson.get("base_date"),
    )


def build_single_lesson_pdf_filename(plan_data: dict, *, suffix: str = "") -> str:
    lesson, _, _ = adapt_plan_to_review_template(plan_data)
    stem = build_lesson_filename_part(lesson)
    suffix = str(suffix or "").strip()
    if suffix:
        stem = f"{stem}-{suffix}"
    return f"{stem}.pdf"
