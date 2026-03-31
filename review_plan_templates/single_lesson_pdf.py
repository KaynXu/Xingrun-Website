from __future__ import annotations

from pathlib import Path

from review_plan_templates.generate_review_pdfs import normalize_portable_text, render_review_plan_pdf


DEFAULT_FINAL_REMINDERS = [
    "每一个复习日都要完整复习整节课内容。",
    "先回忆课堂原话，再完成当天填空与选择。",
    "遇到不会的题先回看课堂总结，再补做口头复述。",
]


def _clean_text(value: object, default: str = "") -> str:
    text = normalize_portable_text(str(value or "").strip())
    return text or default


def collect_plan_quotes(plan_data: dict) -> list[str]:
    quotes: list[str] = []
    for day_data in plan_data.get("days", []):
        phrase = _clean_text(day_data.get("self_test_phrase"))
        if phrase:
            quotes.append(phrase)
        for step in day_data.get("steps", []):
            for item in step.get("items", []):
                if item.get("type") == "body":
                    text = _clean_text(item.get("text"))
                    if text and text not in quotes:
                        quotes.append(text)
        for item in day_data.get("items", []):
            if item.get("type") == "body":
                text = _clean_text(item.get("text"))
                if text and text not in quotes:
                    quotes.append(text)
    return quotes[:6] or ["每一个复习日都要完整复习整节课内容。"]


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
    day_number = int(day_data.get("day") or 0) or 1
    tasks: list[str] = []
    blanks: list[tuple[str, str]] = []

    for step in day_data.get("steps", []):
        title = _clean_text(step.get("title"))
        if title:
            tasks.append(title)
        for item in step.get("items", []):
            text = _clean_text(item.get("text"))
            if item.get("type") == "fill" and text:
                blanks.append((text, _clean_text(item.get("answer"), "见课堂笔记")))
            elif item.get("type") == "body" and text:
                tasks.append(text)

    for item in day_data.get("items", []):
        text = _clean_text(item.get("text"))
        if item.get("type") == "fill" and text:
            blanks.append((text, _clean_text(item.get("answer"), "见课堂笔记")))
        elif text:
            tasks.append(text)

    phrase = _clean_text(day_data.get("self_test_phrase"))
    if phrase:
        tasks.append(phrase)

    task_values = tasks[:4] or [f"完整复习{topic or '本课内容'}并复述关键方法。"]
    blank_values = blanks[:6] or [(f"第{day_number}天请回忆{topic or '本课内容'}中的关键空格。", "见课堂笔记")]

    choice_source = question_pool[(day_number - 1) % len(question_pool)]
    quote_values = [phrase] if phrase else [task_values[0]]

    return {
        "offset": day_number,
        "day": f"第{day_number}天",
        "focus": _clean_text(day_data.get("theme") or day_data.get("label"), f"聚焦复习{topic or '本课内容'}"),
        "goal": f"完整回顾{topic or '本课内容'}，并复述关键方法与易错点。",
        "tasks": task_values,
        "blanks": blank_values,
        "choices": [choice_source],
        "quotes": quote_values,
    }


def adapt_plan_to_review_template(plan_data: dict) -> tuple[dict, list[dict], list[str]]:
    lesson_info = plan_data.get("lesson_info", {})
    topic = _clean_text(lesson_info.get("topic"), "课后")
    weak_points = _clean_text(plan_data.get("weak_points_summary"))
    full_review_topics = [_clean_text(item) for item in (lesson_info.get("key_categories", []) or []) if _clean_text(item)]
    lesson = {
        "title": f"{topic}复习计划",
        "subtitle": "",
        "audience": "老师发给学生使用",
        "duration": "每次 10-20 分钟",
        "core_points": [weak_points] if weak_points else [],
        "full_review_topics": full_review_topics or [topic],
        "quotes": collect_plan_quotes(plan_data),
    }
    question_pool = _question_pool(plan_data)
    days = [adapt_day(day_data, question_pool, topic) for day_data in plan_data.get("days", [])]
    if not days:
        days = [adapt_day({"day": 1, "label": "第1天", "items": []}, question_pool, topic)]
    reminders = list(DEFAULT_FINAL_REMINDERS)
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
        knowledge_sections={},
    )