#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 处理模块：
  - 音频转录（OpenAI Whisper）
  - 课堂总结解析 → 结构化复习计划 JSON（GPT-4o）
  - 月度复习计划聚合
"""

import json
import os
import re
from pathlib import Path
from datetime import date
from config_runtime import get_runtime_config

# ─── 配置加载 ──────────────────────────────────────────────────────────────────
def _load_config() -> dict:
  return get_runtime_config()


def _provider_name() -> str:
    return str(_load_config().get("provider", "openai") or "openai")


def _usage_dict(response, *, provider: str | None = None, model_fallback: str = "") -> dict:
    usage = getattr(response, "usage", None)
    return {
        "provider": str(provider or _provider_name()),
        "model": str(getattr(response, "model", "") or model_fallback or _get_chat_model()),
        "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
    }


def _get_client():
    """返回当前配置的 AI 服务商客户端（兼容 OpenAI SDK）。"""
    from openai import OpenAI
    cfg = _load_config()
    provider = cfg.get("provider", "openai")

    if provider == "deepseek":
        key = cfg.get("deepseek_api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise RuntimeError("未找到 DeepSeek API Key，请在设置页面配置。")
        return OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")

    elif provider == "mimo":
        key = cfg.get("mimo_api_key", "") or os.environ.get("MIMO_API_KEY", "")
        base_url = cfg.get("mimo_base_url", "").strip()
        if not key:
            raise RuntimeError("未找到 MiMo API Key，请在设置页面配置。")
        if not base_url:
            raise RuntimeError("未配置 MiMo Base URL，请在设置页面填写接口地址。")
        return OpenAI(api_key=key, base_url=base_url)

    elif provider == "n1n":
        key = cfg.get("n1n_api_key", "") or os.environ.get("N1N_API_KEY", "")
        base_url = cfg.get("n1n_base_url", "https://api.n1n.ai/v1").strip()
        if not key:
            raise RuntimeError("未找到 N1N API Key，请在设置页面配置。")
        return OpenAI(api_key=key, base_url=base_url)

    else:  # openai（默认）
        key = cfg.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError(
                "未找到 OpenAI API Key。\n"
                "请在设置页面配置 openai_api_key，"
                "或设置环境变量 OPENAI_API_KEY。"
            )
        return OpenAI(api_key=key)


def _get_chat_model() -> str:
    """返回当前服务商对应的对话模型名称。"""
    cfg = _load_config()
    provider = cfg.get("provider", "openai")
    if provider == "deepseek":
        return cfg.get("deepseek_model", "deepseek-chat")
    elif provider == "mimo":
        return cfg.get("mimo_model", "MiMo-7B-RL")
    elif provider == "n1n":
        return cfg.get("n1n_model", "gpt-4o")
    return "gpt-4o"


def _get_whisper_client():
    """音频转录专用客户端（仅支持 OpenAI Whisper）。"""
    from openai import OpenAI
    cfg = _load_config()
    key = cfg.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "音频转录功能需要 OpenAI API Key（Whisper）。\n"
            "请在设置页面配置 OpenAI API Key。"
        )
    return OpenAI(api_key=key)


# ─── 生成复习计划的提示词 ───────────────────────────────────────────────────────
PLAN_SYSTEM_PROMPT = """你是一位专业的初中学科辅导老师，擅长把课堂反馈整理成高质量课后复习计划。
你将收到课堂总结与元信息，必须返回一个可直接用于 PDF 生成的结构化 JSON。

【最高优先级：固定工作流（每次都必须严格执行）】
1) 复习节点固定为 5 天：第1天、第2天、第7天、第14天、第30天。
2) 每个复习日都必须完整覆盖整节课全部核心知识点，不能把 5 天拆成各自只复习一部分。
3) 每天复习时长控制在 10-20 分钟。
4) 题型以填空题为主，选择题为辅；选择题只承担三类功能：
   - 检查基础记忆
   - 辨析易混概念
   - 纠正常见错误
5) 必须保留“上课金句回顾”与“课堂原话回放”模块。
6) 课堂原话使用比例控制在 10%-15%，只保留高价值句子，不可过多。
7) 严禁把“作业布置”当成题目本体，不得出现“本节课布置了哪些作业/题号”等提问。
8) 每个复习日标题必须包含实际日期，按“第0天=本次生成日期”计算：
   - day1 = 第0天+1
   - day2 = 第0天+2
   - day7 = 第0天+7
   - day14 = 第0天+14
   - day30 = 第0天+30
9) 每个复习日要有差异化复习重点，但都要覆盖全课：
   - 第1天：框架回忆
   - 第2天：方法巩固
   - 第7天：题型迁移
   - 第14天：口述提问强化
   - 第30天：综合总复盘
10) 知识点加练按天固定规则：
   - 第1/2天：填空+选择混合
   - 第7/14天：老师提问口述卡片
   - 第30天：填空+选择混合

【内容质量硬性要求】
- 所有 type="body" 与 type="fill" 的 text 必须是本节课具体内容，禁止模板占位词。
- 禁止出现“板块一/板块X/（具体题目）/（按实际填写）/（板块名）/正确答案”等元描述。
- 每道填空题都要可直接印刷给学生使用，读题后能明确考查点。
- 每个 type="fill" 的题目都必须包含 "answer"，且答案简洁明确。

【输出格式要求】
- 只返回合法 JSON，不要输出额外说明。
- 使用 ____ 表示空格（4条下划线）。
- days 必须严格只包含 day=1,2,7,14,30 五项。
- 每天必须有 self_test_phrase。
- 第1/2/7天使用 type="day1" + steps；每个节点 3 个步骤，步骤3至少 6 道题。
- 第14/30天使用 type="daily" + items，但仍必须覆盖全课全部核心知识点。
- questions 至少 15 道，覆盖全部 key_categories，且每题有明确 answer。

【JSON 结构】
{
  "lesson_info": {
    "subject": "科目",
    "grade": "年级",
    "topic": "本节主题",
    "key_categories": ["最多6个核心知识板块"],
    "group_a": ["前半板块名称，可用于兼容展示"],
    "group_b": ["后半板块名称，可用于兼容展示"]
  },
  "weak_points_summary": "学生薄弱点简述",
  "days": [
    {
      "day": 1,
      "label": "课后第1天复习（YYYY-MM-DD）",
      "time": "10-20分钟",
      "type": "day1",
      "steps": [
        {
          "step_label": "⏱ 第1步（2-4分钟）",
          "title": "复习目标/复习聚焦",
          "items": [{"type": "body", "text": "..."}, {"type": "fill", "text": "...", "answer": "..."}]
        },
        {
          "step_label": "⏱ 第2步（4-8分钟）",
          "title": "全课覆盖清单+执行清单",
          "items": [{"type": "fill", "text": "...", "answer": "..."}]
        },
        {
          "step_label": "⏱ 第3步（4-8分钟）",
          "title": "填空主任务+选择辅助+知识点加练/口述卡片+课堂原话回放",
          "items": [{"type": "fill", "text": "...", "answer": "..."}]
        }
      ],
      "self_test_phrase": "出发口令：..."
    },
    {
      "day": 14,
      "label": "课后第14天复习（YYYY-MM-DD）",
      "time": "10-20分钟",
      "type": "daily",
      "items": [{"type": "body", "text": "..."}, {"type": "fill", "text": "...", "answer": "..."}],
      "self_test_phrase": "出发口令：..."
    }
  ],
  "questions": [
    {"question": "...", "answer": "...", "category": "...", "day": 1}
  ],
  "weekly_review_prompts": ["...", "...", "...", "..."]
}
"""

# ─── 复习风格附加提示词 ────────────────────────────────────────────────────────
PROMPT_STYLE_ADDONS = {
    "B": """
【三问法要求】
每个复习节点（第1/2/7/14/30天）的 items 内容必须围绕三个维度展开，三条填空分别对应：
① 是什么：清晰定义或描述该知识点（填空形式）
② 为什么：解释原理或背后的逻辑（填空形式）
③ 怎么用：给出具体的使用场景或做题步骤（填空形式）
例如：① 一次函数定义：自变量x的最高次数为____，且k____0
     ② k>0时图像递增，是因为____
     ③ 遇到"两点求解析式"：第一步____，第二步____
""",
    "C": """
【考题格式导向要求】
每个复习节点聚焦一种考题题型，填空内容呈现该题型的解题框架：
- 在 items 开头用 body 类型注明题型，如"📝 [填空题·斜率判断]"
- 后续填空直接对应解题步骤模板
- 最后一条填空指出该题型最常见的失分点，格式：⚠️ 易错点：____
例如：📝 [解答题·待定系数法]
看到"已知图像过两点" → 第一步必须____，第二步列____元方程组
⚠️ 易错点：____
""",
    "D": """
【对话自测要求】
每个复习节点用"老师提问→学生回答"的对话链呈现：
- body 类型 item 写老师的问题，fill 类型 item 写学生需要填写的答案
- 问题之间自然衔接，由浅入深，每个节点包含2-3轮对话
- 格式：老师问：[具体问题]？→ 你答：____
例如：
  {"type":"body","text":"👩‍🏫 老师问：一次函数 y=kx+b 中，k 的作用是什么？"}
  {"type":"fill","text":"→ 你答：k 表示____，决定图像____"}
  {"type":"body","text":"👩‍🏫 老师追问：如果 k<0，图像是什么走向？"}
  {"type":"fill","text":"→ 你答：从左____到右____（递____）"}
""",
    "E": """
【遗忘清单要求】
每个复习节点以"核查清单"形式呈现，不要普通填空，改为：
- 第一条 body 类型 item 写"✅ 今天快速核查，你还记得吗？"
- 后续每条 fill 类型 item 用"☐"开头，一句话描述一个关键点，末尾加【易错】或【常考】标注
- 每个节点列出3-5条，精准指向该天主题的核心记忆点
例如：
  {"type":"body","text":"✅ 今天快速核查，你还记得吗？"}
  {"type":"fill","text":"☐ k的符号决定图像____方向（____为正，____为负）【易错】"}
  {"type":"fill","text":"☐ b=0 时函数图像过____，叫____函数【常考】"}
""",
}


def _build_system_prompt(styles: list) -> str:
    """根据选中的风格列表，在基础提示词后追加附加要求。"""
    base = PLAN_SYSTEM_PROMPT
    if not styles:
        return base
    addon_parts = []
    style_names = {"B": "三问法", "C": "考题格式", "D": "对话自测", "E": "遗忘清单"}
    for s in styles:
        if s in PROMPT_STYLE_ADDONS:
            addon_parts.append(PROMPT_STYLE_ADDONS[s])
    if not addon_parts:
        return base
    names = "、".join(style_names.get(s, s) for s in styles if s in PROMPT_STYLE_ADDONS)
    header = f"\n\n【本次选用的教学风格：{names}】\n以下是各风格的具体要求，生成时需严格遵守："
    return base + header + "\n".join(addon_parts)


MONTHLY_SYSTEM_PROMPT = """你是一位专业的初中学科辅导老师。
你将收到本月全部课堂总结（多节课），需要生成一份月度综合复习计划 JSON。

【月度复习计划特点】
- 聚焦本月所有课程的核心知识点
- 优先处理多节课中反复出现的薄弱点
- 生成 14 天的每日复习安排（前2天总复盘，后面分知识板块）
- 题库要覆盖全月所有知识点

【输出格式】与单节课相同，但：
- lesson_info.topic = "X月综合复习"
- key_categories 来自所有课程知识点的合并与提炼
- days 安排 14 天（day 1-2 为month_day1 类型，day 3-14 为daily类型）
- questions 至少 20 道，覆盖全月

只返回合法 JSON，不要额外说明。
"""


CONSULTATION_BATCH_SYSTEM_PROMPT = """你是咨询记录整理助手。
你只能输出 JSON，不要输出额外说明。

请把输入文本拆成 items 数组，每一项都必须是：
- action: 只能是 create 或 update
- target_id: 只有文本中明确出现记录 ID 时才允许填写整数，否则必须是 null
- reason: 简短说明判断依据
- fields: 只能包含以下字段中的一部分：
    date
    parent_wechat_name
    child_name
    grade
    receiving_teacher
    teacher_id
    consultation_subject
    need_detail
    source_channel
    source_channel_note
    screenshot
    follow_up_status
    follow_up_note
- warnings: 字符串数组

严格规则：
1. 只有文本中明确出现 ID 182、记录182、#182 这类显式记录 ID 时，action 才能是 update。
2. 没有显式记录 ID 时，必须输出 action=create 且 target_id=null。
3. 不要编造记录 ID。
4. 如果一段文本信息不足，可以保留 fields 的部分字段，不要补全虚构内容。
5. 顶层返回 {"items": [...], "warnings": [...]}。
"""


# ─── 音频转录 ──────────────────────────────────────────────────────────────────
def transcribe_audio(audio_path: str, *, include_usage: bool = False):
    """使用 OpenAI Whisper 转录音频文件，返回转录文本。"""
    client = _get_whisper_client()
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"音频文件不存在：{audio_path}")
    
    supported = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac"}
    if audio_path.suffix.lower() not in supported:
        raise ValueError(f"不支持的音频格式：{audio_path.suffix}（支持：{', '.join(supported)}）")
    
    print(f"正在转录音频：{audio_path.name} ...")
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="zh",
            response_format="text",
        )
    print("转录完成。")
    transcription = str(response)
    if include_usage:
        return transcription, _usage_dict(
            response,
            provider="openai",
            model_fallback="whisper-1",
        )
    return transcription


# ─── 课堂总结解析 ──────────────────────────────────────────────────────────────
def parse_and_generate_plan(
    summary_text: str,
    subject: str = "",
    grade: str = "",
    topic: str = "",
    weak_points: str = "",
    lesson_date: str = "",
    prompt_styles: list = None,
    include_usage: bool = False,
):
    """
    将自由格式课堂总结（文本）解析为结构化复习计划 JSON。
    返回 plan dict，可直接传入 pdf_engine 生成 PDF，或存入数据库。
    """
    client = _get_client()

    # 构建用户消息
    meta_parts = [f"生成日期（第0天）：{date.today().isoformat()}"]
    if subject:   meta_parts.append(f"科目：{subject}")
    if grade:     meta_parts.append(f"年级：{grade}")
    if topic:     meta_parts.append(f"本节课主题：{topic}")
    if weak_points: meta_parts.append(f"学生薄弱点：{weak_points}")
    if lesson_date: meta_parts.append(f"上课日期：{lesson_date}")
    
    meta_block = "\n".join(meta_parts)
    user_msg = f"{meta_block}\n\n课堂总结：\n{summary_text}"

    print("正在生成复习计划（AI处理中）...")
    system_prompt = _build_system_prompt(prompt_styles or [])
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    plan = json.loads(raw)
    
    # 补充日期
    if lesson_date and "lesson_info" in plan:
        plan["lesson_info"]["date"] = lesson_date
    else:
        plan.setdefault("lesson_info", {}).setdefault("date", str(date.today()))
    
    print("复习计划生成完成。")
    if include_usage:
        return plan, _usage_dict(response)
    return plan


def parse_consultation_batch_text(raw_text: str, *, include_usage: bool = False):
    client = _get_client()
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": CONSULTATION_BATCH_SYSTEM_PROMPT},
            {"role": "user", "content": str(raw_text or "")},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    payload = json.loads(response.choices[0].message.content)
    if not isinstance(payload.get("items"), list):
        raise RuntimeError("咨询记录批量解析返回了无效结果")
    parsed = {
        "items": payload.get("items", []),
        "warnings": payload.get("warnings", []),
    }
    if include_usage:
        return parsed, _usage_dict(response)
    return parsed


# ─── 月度复习计划聚合 ──────────────────────────────────────────────────────────
def generate_teacher_feedback_draft(
    *,
    lesson: dict,
    students: list[dict],
    custom_templates: list[dict],
    include_usage: bool = False,
):
    client = _get_client()
    plan_json = json.dumps(lesson.get("plan") or {}, ensure_ascii=False)
    student_block = json.dumps(
        {"students": students, "custom_templates": custom_templates},
        ensure_ascii=False,
    )
    system_prompt = (
        "你是一名负责生成家校沟通课后反馈的教研助理。"
        "输出纯文本，不要 Markdown，不要项目符号。"
        "每位学生输出四段：本周课堂重点、这节课的作用、课堂状态、家长配合建议。"
        "本周课堂重点必须控制在20个中文字符以内。"
        "“这节课的作用”要结合复习计划与课堂内容，识别它更偏向思维训练帮助，还是更偏向中考、小升初、高考等考试帮助，并用家校沟通口吻写清楚。"
        "“课堂状态”必须优先参考学生的 selected_template_label、selected_template_guidance 和 remark。"
        "“家长配合建议”必须结合 selected_template_guidance、remark 和复习计划给出可执行建议。"
        "每位学生都以“学生姓名：”开头。"
        "只输出已选择状态模板的学生，学生与学生之间空一行。"
    )
    user_prompt = (
        f"课程信息：{lesson.get('subject', '')} {lesson.get('grade', '')} {lesson.get('topic', '')}\n"
        f"课堂总结：{lesson.get('summary', '')}\n"
        f"复习计划JSON：{plan_json}\n"
        f"学生输入：{student_block}"
    )
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    merged_text = (response.choices[0].message.content or "").strip()
    if include_usage:
        return merged_text, _usage_dict(response)
    return merged_text


def generate_monthly_plan(lessons, month_str: str, *, include_usage: bool = False):
    """
    给定本月所有 lesson 记录列表，生成月度综合复习计划。
    每个 lesson dict 应包含 summary、topic、subject、grade、weak_points 等字段。
    """
    client = _get_client()

    # 构建月度摘要
    parts = [f"月份：{month_str}\n共 {len(lessons)} 节课\n"]
    for i, lesson in enumerate(lessons, 1):
        parts.append(
            f"【第{i}课 {lesson.get('date','')}】\n"
            f"主题：{lesson.get('topic','')}\n"
            f"薄弱点：{lesson.get('weak_points','')}\n"
            f"总结摘要：{lesson.get('summary','')[:800]}\n"
        )
    combined = "\n---\n".join(parts)

    print(f"正在生成 {month_str} 月度复习计划（AI处理中）...")
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": MONTHLY_SYSTEM_PROMPT},
            {"role": "user",   "content": combined},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    plan = json.loads(response.choices[0].message.content)
    plan.setdefault("lesson_info", {})["month"] = month_str
    plan["lesson_info"]["topic"] = f"{month_str} 综合复习"
    print("月度复习计划生成完成。")
    if include_usage:
        return plan, _usage_dict(response)
    return plan
