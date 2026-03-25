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

# ─── 配置加载 ──────────────────────────────────────────────────────────────────
def _load_config() -> dict:
    cfg_path = Path(__file__).parent / "config.json"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


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
PLAN_SYSTEM_PROMPT = """你是一位专业的初中学科辅导老师，擅长为学生制作高质量的课后复习计划。
你将收到一份课堂总结，需要返回一个结构化的 8 天填空题复习讲义 JSON。

【输出格式要求】
- 只返回合法 JSON，不要任何额外说明。
- 使用 ____ 表示需要学生填写的空格（每个空格 4 条下划线）。
- 每个填空题句子要有足够的上下文，让学生知道要填什么。
- 自测口令要简洁有力，让学生在开始做题前大声背诵。
- 题库 questions 每道题要有明确答案。

【JSON 结构】
{
  "lesson_info": {
    "subject": "科目",
    "grade": "年级",
    "topic": "本节主题",
    "key_categories": ["最多6个核心知识板块名称"]
  },
  "weak_points_summary": "学生薄弱点简述（1-2句话）",
  "days": [
    {
      "day": 1,
      "label": "学后第1天复习",
      "time": "4–5分钟",
      "type": "day1",
      "steps": [
        {
          "step_label": "⏱ 第1步（1分钟）",
          "title": "口头回忆各大板块",
          "items": [
            {"type": "body", "text": "这节课主要学了哪几块内容？"},
            {"type": "fill", "text": "① ____ ② ____ ③ ____ ④ ____"}
          ]
        },
        {
          "step_label": "⏱ 第2步（2分钟）",
          "title": "翻笔记，看关键提醒",
          "items": [
            {"type": "fill", "text": "① ____（最重要的注意点）"},
            {"type": "fill", "text": "② ____"},
            {"type": "fill", "text": "③ ____"}
          ]
        },
        {
          "step_label": "⏱ 第3步（1–2分钟）",
          "title": "口头自测",
          "items": [
            {"type": "fill", "text": "Q1：（具体自测题）答：____"},
            {"type": "fill", "text": "Q2：（具体自测题）答：____"},
            {"type": "fill", "text": "Q3：（具体自测题）答：____"},
            {"type": "fill", "text": "Q4：（具体自测题）答：____"}
          ]
        }
      ],
      "self_test_phrase": "出发口令：「完整背诵句，基于本节重点」"
    },
    {
      "day": 2,
      "label": "第2天 每日一练前复习",
      "time": "3分钟",
      "theme": "第一个核心板块主题",
      "type": "daily",
      "items": [
        {"type": "body", "text": "📌 今天做题前先记这几条："},
        {"type": "fill", "text": "① ____"},
        {"type": "fill", "text": "② ____"},
        {"type": "fill", "text": "③ ____"}
      ],
      "self_test_phrase": "出发口令：「...」"
    }
  ],
  "questions": [
    {
      "question": "具体问题（适合口头自问）",
      "answer": "简洁明确的答案",
      "category": "所属知识类别",
      "day": 1
    }
  ],
  "weekly_review_prompts": [
    "这周哪个知识点最容易忘？",
    "哪天的复习最有效？原因是",
    "下周做题前要额外注意：",
    "我需要老师再讲一遍的是："
  ]
}

【天数安排规则】
- 第1天：总复盘，用上面三步格式，全面覆盖本节所有板块。
- 第2天到第8天：每天只聚焦一个主题，用日常练习前复习格式（daily type）。主题从 key_categories 中取，依次展开。
- 如果 key_categories 少于7个，可以合并或留到月度复习。
- 每天结束都要有「出发口令」。

【题库规则】
- questions 要包含至少 10 道题，覆盖全部 key_categories。
- 每道题要有具体、清晰的答案。
- 难度均衡，不要太难或太简单。
"""

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


# ─── 音频转录 ──────────────────────────────────────────────────────────────────
def transcribe_audio(audio_path: str) -> str:
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
    return response


# ─── 课堂总结解析 ──────────────────────────────────────────────────────────────
def parse_and_generate_plan(
    summary_text: str,
    subject: str = "",
    grade: str = "",
    topic: str = "",
    weak_points: str = "",
    lesson_date: str = "",
) -> dict:
    """
    将自由格式课堂总结（文本）解析为结构化复习计划 JSON。
    返回 plan dict，可直接传入 pdf_engine 生成 PDF，或存入数据库。
    """
    client = _get_client()

    # 构建用户消息
    meta_parts = []
    if subject:   meta_parts.append(f"科目：{subject}")
    if grade:     meta_parts.append(f"年级：{grade}")
    if topic:     meta_parts.append(f"本节课主题：{topic}")
    if weak_points: meta_parts.append(f"学生薄弱点：{weak_points}")
    if lesson_date: meta_parts.append(f"上课日期：{lesson_date}")
    
    meta_block = "\n".join(meta_parts)
    user_msg = f"{meta_block}\n\n课堂总结：\n{summary_text}"

    print("正在生成复习计划（AI处理中）...")
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
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
    return plan


# ─── 月度复习计划聚合 ──────────────────────────────────────────────────────────
def generate_monthly_plan(lessons, month_str: str) -> dict:
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
    return plan
