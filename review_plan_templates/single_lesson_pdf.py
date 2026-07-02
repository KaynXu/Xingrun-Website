from __future__ import annotations

import re
from pathlib import Path

from review_plan_workflow.schemas import normalize_final_review_plan
from review_plan_templates.generate_review_pdfs import make_safe_filename_part, normalize_portable_text_preserving_latex, render_review_plan_pdf


DEFAULT_FINAL_REMINDERS = [
    "每一个复习日都要完整复习整节课内容。",
    "先回忆课堂原话，再完成当天填空与选择。",
    "遇到不会的题先回看课堂总结，再补做口头复述。",
]
ONE_DAY_FINAL_REMINDERS = [
    "当天课后复习要完整扫过课堂主线。",
    "先回忆核心方法，再完成填空、选择和自查。",
    "把错题原因记录下来，方便老师下次讲评。",
]
ONE_DAY_GENERIC_LABELS = {
    "第1天",
    "第1天复习",
    "当天复现",
}
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
GENERIC_TOPICS = {
    "",
    "课后",
    "课程",
    "复习",
    "课后复习",
    "本课内容",
    "数学课程",
    "数学",
    "语文",
    "英语",
    "物理",
    "化学",
    "生物",
    "历史",
    "地理",
    "政治",
}
QUESTION_TASK_PREFIXES = ("选择题", "填空题", "判断题", "简答题", "计算题", "解答题", "口述题", "选择诊断")
QUESTION_TASK_PATTERNS = (
    "下列说法正确的是",
    "下列理解",
    "以下正确的是",
    "以下错误的是",
    "下列哪",
    "关于“",
)


def _clean_text(value: object, default: str = "") -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return default
    text = normalize_portable_text_preserving_latex(str(value or "").strip())
    return text or default


def _is_one_day_generic_label(value: object) -> bool:
    compact = re.sub(r"\s+", "", _clean_text(value))
    return compact in ONE_DAY_GENERIC_LABELS or (compact.startswith("第1天") and "集中复习" in compact)


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


def _looks_like_question_stem(value: object) -> bool:
    text = _clean_text(value)
    if not text:
        return False
    stripped = text.lstrip("-•· ").strip()
    if stripped.startswith(QUESTION_TASK_PREFIXES):
        return True
    return ("（ ）" in stripped or "( )" in stripped) and any(pattern in stripped for pattern in QUESTION_TASK_PATTERNS)


def _append_execution_task_once(tasks: list[str], text: object) -> None:
    clean_text = _clean_text(text)
    if not clean_text or _is_completion_standard(clean_text) or _looks_like_question_stem(clean_text):
        return
    _append_task_once(tasks, clean_text)


def _is_completion_standard(value: object) -> bool:
    text = _clean_text(value)
    if not text:
        return False
    return (
        text.startswith(("能", "完成后", "正确率", "自查"))
        or "完成标准" in text
        or "对照答案" in text
        or "全部正确" in text
    )


def _compact_instruction_with_blanks(instruction: object, blanks: object) -> str:
    parts = [_clean_text(instruction)]
    if isinstance(blanks, list):
        blank_texts = []
        for blank in blanks:
            if isinstance(blank, dict):
                blank_texts.append(_clean_text(blank.get("label") or blank.get("text") or blank.get("stem")))
            else:
                blank_texts.append(_clean_text(blank))
        blank_texts = [text for text in blank_texts if text]
        if blank_texts:
            parts.append("；".join(blank_texts))
    return " ".join(part for part in parts if part).strip()


def _first_string_field(data: dict, fields: tuple[str, ...]) -> object:
    for field in fields:
        value = data.get(field)
        if isinstance(value, str) and _clean_text(value):
            return value
    return ""


def _append_active_recall_entry(cards: list[str], value: object) -> None:
    if isinstance(value, str):
        _append_task_once(cards, value)
        return
    if isinstance(value, list):
        for item in value:
            _append_active_recall_entry(cards, item)
        return
    if not isinstance(value, dict):
        return

    intro = _clean_text(value.get("intro"))
    if intro:
        _append_task_once(cards, intro)

    steps = value.get("steps")
    if isinstance(steps, list):
        for step in steps:
            _append_active_recall_entry(cards, step)
    else:
        _append_task_once(cards, steps)

    primary = _first_string_field(
        value,
        ("instruction", "instructions", "question", "prompt", "stem", "text", "expected"),
    )
    card = _compact_instruction_with_blanks(primary, value.get("blanks"))
    if value.get("answer_ref"):
        card = f"{card}（口述后对照参考答案）" if card else "口述后对照参考答案。"
    _append_task_once(cards, card)

    for field in ("instructions", "content", "items", "cards"):
        nested = value.get(field)
        if nested is primary:
            continue
        if isinstance(nested, (dict, list)):
            _append_active_recall_entry(cards, nested)


def _active_recall_cards(active_recall: object) -> list[str]:
    if isinstance(active_recall, str):
        text = _clean_text(active_recall)
        return [text] if text else []
    if not isinstance(active_recall, dict):
        return []

    cards: list[str] = []
    _append_active_recall_entry(cards, active_recall)

    top_level_card = _compact_instruction_with_blanks("", active_recall.get("blanks"))
    if top_level_card:
        _append_task_once(cards, top_level_card)

    for item in active_recall.get("items", []) if isinstance(active_recall.get("items"), list) else []:
        if not isinstance(item, dict):
            _append_task_once(cards, item)
            continue
        card = _compact_instruction_with_blanks(
            item.get("instruction") or item.get("question") or item.get("prompt") or item.get("stem"),
            item.get("blanks"),
        )
        if item.get("answer_ref"):
            card = f"{card}（口述后对照参考答案）" if card else "口述后对照参考答案。"
        _append_task_once(cards, card)
    return cards


def _lesson_title_from_topic(topic: str) -> str:
    clean_topic = _clean_visible_topic(re.sub(r"(课后)?复习计划$", "", _clean_text(topic, "课后")).strip())
    if clean_topic.endswith("复习"):
        return f"{clean_topic}计划"
    return f"{clean_topic}复习计划"


def _strip_review_plan_suffix(value: object) -> str:
    return re.sub(r"(课后)?复习计划$", "", _clean_text(value)).strip()


def _clean_visible_topic(value: object) -> str:
    text = _strip_review_plan_suffix(value)
    text = re.sub(r"[（(][^（）()]*?(?:待确认|需确认|需要确认)[^（）()]*?[）)]", "", text)
    text = re.sub(r"[，,、；;]?\s*(?:待确认|需确认|需要确认)\s*$", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" -—，,、；;")
    return text


def _is_generic_topic(value: object) -> bool:
    return _strip_review_plan_suffix(value).replace(" ", "") in GENERIC_TOPICS


def _first_non_generic_line(values: object) -> str:
    for text in _dedupe_clean_lines(values):
        if not _is_generic_topic(text):
            return text
    return ""


def _resolve_lesson_topic(plan_data: dict, lesson_info: dict) -> str:
    for value in (
        lesson_info.get("topic"),
        plan_data.get("topic"),
        plan_data.get("lesson_topic"),
        plan_data.get("plan_title"),
        plan_data.get("title"),
    ):
        topic = _clean_visible_topic(value)
        if topic and not _is_generic_topic(topic):
            return topic
    topic = _first_non_generic_line(lesson_info.get("key_categories")) or _first_non_generic_line(plan_data.get("full_review_topics"))
    if topic:
        return topic
    subject = _clean_text(lesson_info.get("subject") or plan_data.get("subject"), "课程")
    return f"{subject}复习"


def _append_explicit_tasks(tasks: list[str], day_data: dict) -> None:
    for field in ("tasks", "task_list", "checklist", "execution_checklist"):
        values = day_data.get(field)
        if isinstance(values, list):
            for value in values:
                if isinstance(value, dict):
                    _append_execution_task_once(tasks, value.get("text") or value.get("task") or value.get("instruction"))
                else:
                    _append_execution_task_once(tasks, value)
        else:
            _append_execution_task_once(tasks, values)


def _synthesized_tasks(day_data: dict, topic: str, method_cards: list[str], choices: list[dict]) -> list[str]:
    tasks: list[str] = []
    goal = _clean_text(day_data.get("goal") or day_data.get("review_goal"))
    focus = _clean_text(day_data.get("focus") or day_data.get("review_focus") or day_data.get("theme") or day_data.get("label"))
    if goal:
        _append_task_once(tasks, f"用2分钟口头复述今日目标：{goal}")
    if focus:
        _append_task_once(tasks, f"回看课堂笔记中与“{focus}”相关的例题入口和易错点。")
    _append_task_once(tasks, "完成当天填空题；遇到公式题，先写适用条件和等号成立条件，再代入。")
    if choices:
        _append_task_once(tasks, "完成选择题，并口头说明每个错误选项错在哪里。")
    if method_cards:
        _append_task_once(tasks, "完成课堂方法复盘卡片，用自己的话复述关键步骤。")
    phrase = _clean_text(day_data.get("self_test_phrase") or day_data.get("completion_standard"))
    if phrase and not _is_completion_standard(phrase):
        _append_task_once(tasks, f"最后自查：{phrase}")
    return tasks or [f"完整复习{topic or '本课内容'}并复述关键方法。"]


def _day_meta_texts(day_data: dict) -> set[str]:
    fields = ("goal", "review_goal", "focus", "review_focus", "completion_standard", "self_test_phrase")
    return {_clean_text(day_data.get(field)) for field in fields if _clean_text(day_data.get(field))}


def _is_printable_task(text: str, meta_texts: set[str]) -> bool:
    clean_text = _clean_text(text)
    return bool(clean_text and clean_text not in meta_texts and not _is_completion_standard(clean_text))


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


def _question_pool(plan_data: dict) -> list[dict]:
    pool: list[dict] = []
    for question in plan_data.get("questions", []):
        question_text = _clean_text(question.get("question"))
        options = _dedupe_clean_lines(question.get("options"))
        if not question_text or len(options) < 2:
            continue
        pool.append(
            {
                "question": question_text,
                "options": options,
                "answer": _clean_text(question.get("answer"), "A"),
            }
        )
    return pool


def adapt_day(day_data: dict, question_pool: list[dict], topic: str) -> dict:
    day_number = int(day_data.get("day") or day_data.get("day_number") or 0) or 1
    tasks: list[str] = []
    blanks: list[tuple[str, str]] = []
    method_cards = _active_recall_cards(day_data.get("active_recall"))
    meta_texts = _day_meta_texts(day_data)
    _append_explicit_tasks(tasks, day_data)

    for step in day_data.get("steps", []):
        title = _clean_text(step.get("title"))
        if title:
            tasks.append(title)
        for item in step.get("items", []):
            text = _clean_text(item.get("text"))
            if item.get("type") == "fill" and text:
                _append_blank_once(blanks, text, item.get("answer"))
            elif item.get("type") == "body" and _is_printable_task(text, meta_texts):
                _append_execution_task_once(tasks, text)

    for item in day_data.get("items", []):
        text = _clean_text(item.get("text"))
        if item.get("type") == "fill" and text:
            _append_blank_once(blanks, text, item.get("answer"))
        elif _is_printable_task(text, meta_texts):
            _append_execution_task_once(tasks, text)

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
    if phrase and not _is_completion_standard(phrase):
        _append_execution_task_once(tasks, phrase)

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
        choice_values = explicit_choices
    elif question_pool:
        choice_values = [question_pool[(day_number - 1) % len(question_pool)]]
    else:
        choice_values = []

    task_values = tasks[:5] if tasks else _synthesized_tasks(day_data, topic, method_cards, choice_values)[:5]
    blank_values = blanks or [(f"第{day_number}天请回忆{topic or '本课内容'}中的关键空格。", "见课堂笔记")]
    quote_values = _dedupe_real_quotes(day_data.get("quotes"))
    if phrase and _is_real_class_quote(phrase) and phrase not in quote_values:
        quote_values.append(phrase)

    return {
        "offset": day_number,
        "day": _clean_text(day_data.get("label") or day_data.get("day_label"), f"第{day_number}天"),
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
        "method_cards": method_cards,
        "quotes": quote_values,
    }


def adapt_plan_to_review_template(plan_data: dict) -> tuple[dict, list[dict], list[str]]:
    plan_data = normalize_final_review_plan(plan_data)
    lesson_info = plan_data.get("lesson_info", {})
    topic = _resolve_lesson_topic(plan_data, lesson_info)
    weak_points = _clean_text(plan_data.get("weak_points_summary"))
    full_review_topics = _dedupe_clean_lines(lesson_info.get("key_categories"))
    for text in _dedupe_clean_lines(plan_data.get("full_review_topics")):
        if text not in full_review_topics:
            full_review_topics.append(text)
    lesson = {
        "title": _lesson_title_from_topic(topic),
        "subtitle": "",
        "subject": _clean_text(lesson_info.get("subject") or plan_data.get("subject")),
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
    one_day_plan = len(days) == 1 and int(days[0].get("offset") or 1) == 1
    if one_day_plan and _is_one_day_generic_label(days[0].get("day")):
        days[0]["day"] = "当天课后复习"
    reminders = _dedupe_clean_lines(plan_data.get("final_reminder_lines")) or list(
        ONE_DAY_FINAL_REMINDERS if one_day_plan else DEFAULT_FINAL_REMINDERS
    )
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
    title = _clean_visible_topic(lesson.get("title"))
    if _is_generic_topic(title):
        title = f"{_clean_text(lesson.get('subject'), '课程')}复习计划"
    stem = make_safe_filename_part(title, "课程复习计划", 36)
    suffix = str(suffix or "").strip()
    if suffix:
        stem = f"{stem}-{suffix}"
    return f"{stem}.pdf"
