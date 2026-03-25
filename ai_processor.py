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
PLAN_SYSTEM_PROMPT = """你是一位专业的初中学科辅导老师，擅长为学生制作高质量的课后复习计划。
你将收到一份课堂总结，需要返回一个结构化的间隔复习讲义 JSON。

复习节点共5次：课后第1天、第2天、第7天、第14天、第30天。

【知识点分组规则】
请先列出本节课所有核心知识板块（key_categories，最多6个），再将其均分为两组：
- group_a = 前半部分（如6个板块取前3个，5个板块取前3个，4个板块取前2个）
- group_b = 后半部分（剩余板块）
- 第14天只复习 group_a，第30天只复习 group_b。

【⚠️ 具象化强制要求（最高优先级）】
所有 type="body" 和 type="fill" 的 text 字段，必须使用真实的、针对本节课具体内容的表述，严禁任何通用占位符。
- ❌ 禁止出现：「板块一：____」「板块X：____」「（具体题目）」「（按实际板块数填写）」「（板块名）」「正确答案」等元描述词语
- ✅ 要求：直接写出本节课真实知识点的名称和具体内容，例如：
  · 「勾股定理的公式：____」
  · 「斜率 k>0 时，图像从左到右____（递增/递减）」
  · 「Q1（待定系数法）：已知直线过点(0,1)和(2,3)，则 k=____，b=____」
- 每道填空题读完后，学生必须能立刻知道在考哪个知识点的哪个具体方面。
- 所有内容须是"可以直接印刷给学生用"的真实题目或知识点表述，生成时替换掉所有括号内的说明性占位文字。

【输出格式要求】
- 只返回合法 JSON，不要任何额外说明。
- 使用 ____ 表示需要学生填写的空格（每个空格 4 条下划线）。
- 每个填空题句子要有足够的上下文，让学生知道要填什么。
- 自测口令要简洁有力，让学生在开始做题前大声背诵。
- 第1、2、7天必须覆盖 key_categories 中所有板块，题量要充足（每天步骤3至少6道自测题）。
- 题库 questions 每道题要有明确答案。
- 每个 type="fill" 的题目必须包含 "answer" 字段，写出该处应填的正确参考答案（简洁，一行以内，多个空格用分号或斜杠分隔）。

【JSON 结构】
{
  "lesson_info": {
    "subject": "科目",
    "grade": "年级",
    "topic": "本节主题",
    "key_categories": ["最多6个核心知识板块名称"],
    "group_a": ["前50%板块名称"],
    "group_b": ["后50%板块名称"]
  },
  "weak_points_summary": "学生薄弱点简述（1-2句话）",
  "days": [
    {
      "day": 1,
      "label": "课后第1天复习",
      "time": "8–10分钟",
      "type": "day1",
      "steps": [
        {
          "step_label": "⏱ 第1步（1–2分钟）",
          "title": "口头回忆所有板块",
          "items": [
            {"type": "body", "text": "这节课学了哪几块内容？（逐一说出来）"},
            {"type": "fill", "text": "① ____ ② ____ ③ ____ ④ ____ ⑤ ____ ⑥ ____", "answer": "①一次函数定义 ②图像与性质 ③待定系数法 ④与坐标轴交点 ⑤两直线位置关系 ⑥实际应用"}
          ]
        },
        {
          "step_label": "⏱ 第2步（3–4分钟）",
          "title": "逐板块核心要点填写",
          "items": [
            {"type": "body", "text": "📌 【一次函数定义】"},
            {"type": "fill", "text": "一次函数的一般形式是 y=____，其中 k____0", "answer": "kx+b；≠"},
            {"type": "fill", "text": "当 b=0 时，叫做正比例函数，图像过____", "answer": "原点(0,0)"},
            {"type": "body", "text": "📌 【图像走势与象限】"},
            {"type": "fill", "text": "k>0 时图像从左到右____（经过第____象限）", "answer": "递增；一、三"},
            {"type": "fill", "text": "k<0 时图像从左到右____（经过第____象限）", "answer": "递减；二、四"},
            {"type": "body", "text": "📌 【待定系数法】"},
            {"type": "fill", "text": "求解析式：设 y=kx+b，把已知两点坐标分别代入，得到____元____次方程组，解出 k、b", "answer": "二；一"},
            {"type": "fill", "text": "易错提醒：代入时注意 x 和 y 不要____，每个等式只代入____个点", "answer": "写反；一"}
          ]
        },
        {
          "step_label": "⏱ 第3步（3–4分钟）",
          "title": "全面自测（每板块至少1题，共≥6道）",
          "items": [
            {"type": "fill", "text": "Q1（定义）：y=2x+3 中 k=____，b=____，图像与 y 轴交于____", "answer": "2；3；(0,3)"},
            {"type": "fill", "text": "Q2（走势）：k=-1<0，该函数图像从左到右____，经过第____、____象限", "answer": "递减；二、四"},
            {"type": "fill", "text": "Q3（待定系数）：直线过 A(0,2)和 B(3,8)，则 k=____，解析式为____", "answer": "2；y=2x+2"},
            {"type": "fill", "text": "Q4（与坐标轴）：y=3x-6 与 x 轴交点为____（令 y=0 求解）", "answer": "(2,0)"},
            {"type": "fill", "text": "Q5（两直线平行）：y=2x+1 和 y=2x-3 的斜率相同，所以两直线____", "answer": "平行"},
            {"type": "fill", "text": "Q6（综合）：已知一次函数经过(1,5)和(-1,1)，k=____，b=____，解析式为____", "answer": "2；3；y=2x+3"}
          ]
        }
      ],
      "self_test_phrase": "出发口令：「完整背诵句，基于本节全部重点」"
    },
    {
      "day": 2,
      "label": "课后第2天复习",
      "time": "8–10分钟",
      "type": "day1",
      "steps": [
        {
          "step_label": "⏱ 第1步（1–2分钟）",
          "title": "快速回忆所有板块（换角度）",
          "items": [
            {"type": "body", "text": "第2天：不看笔记，凭记忆写出每个知识板块的名称和最核心的一句结论："},
            {"type": "fill", "text": "一次函数定义 → 核心条件：y=kx+b，要求 k____0", "answer": "≠"},
            {"type": "fill", "text": "图像走势 → k>0 图像____，k<0 图像____", "answer": "递增；递减"},
            {"type": "fill", "text": "待定系数法 → 核心步骤：设____，代入____个已知点列方程组求解", "answer": "y=kx+b；两"},
            {"type": "fill", "text": "两直线平行条件 → 斜率____（相等），截距____（不等）", "answer": "相等；不等"}
          ]
        },
        {
          "step_label": "⏱ 第2步（3–4分钟）",
          "title": "各板块实战例题框架",
          "items": [
            {"type": "body", "text": "📌 遇到【求一次函数解析式】题，解题框架："},
            {"type": "fill", "text": "第一步：设 y=____；第二步：把两点坐标分别____代入；第三步：联立方程组解出 k 和 b", "answer": "kx+b；逐一"},
            {"type": "body", "text": "📌 遇到【判断两直线位置关系】题，解题框架："},
            {"type": "fill", "text": "先比较____：若____则继续判断截距；再比较截距：若____则重合，否则____", "answer": "斜率k；相等；也相等；平行"},
            {"type": "fill", "text": "最容易犯的错误：代入坐标时把 x 值和 y 值的位置____，导致方程组结果出错", "answer": "写反"}
          ]
        },
        {
          "step_label": "⏱ 第3步（3–4分钟）",
          "title": "模拟练习自测（每板块至少1题，共≥6道）",
          "items": [
            {"type": "fill", "text": "Q1（定义）：y=-3x 是____函数，也是____函数，k=____", "answer": "一次；正比例；-3"},
            {"type": "fill", "text": "Q2（图像）：y=½x-2 的图像经过第____、____象限，与 y 轴交于____", "answer": "一、三、四；(0,-2)"},
            {"type": "fill", "text": "Q3（待定系数）：直线过(2,7)和(0,3)，k=____，解析式为____", "answer": "2；y=2x+3"},
            {"type": "fill", "text": "Q4（与坐标轴）：y=2x-4 与 x 轴交点为____，与 y 轴交点为____", "answer": "(2,0)；(0,-4)"},
            {"type": "fill", "text": "Q5（平行）：与 y=3x+1 平行且过(0,-2)的直线解析式为____", "answer": "y=3x-2"},
            {"type": "fill", "text": "Q6（综合易错）：直线过(-2,0)和(0,4)，求解析式并判断经过哪几个象限：k=____，b=____，经过____象限", "answer": "2；4；一、二、三"}
          ]
        }
      ],
      "self_test_phrase": "出发口令：「...」"
    },
    {
      "day": 7,
      "label": "课后第7天复习",
      "time": "8–10分钟",
      "type": "day1",
      "steps": [
        {
          "step_label": "⏱ 第1步（1–2分钟）",
          "title": "一周后回忆与易混淆点梳理",
          "items": [
            {"type": "body", "text": "距上课整整一周，写出全部知识点名称及每个知识点最容易忘记的一条："},
            {"type": "fill", "text": "一次函数定义 → 最易忘：k 的条件是____（而非 k≥0）", "answer": "k≠0"},
            {"type": "fill", "text": "待定系数法 → 最易忘：代入两点后要____，不能只代一个点求解", "answer": "列方程组联立"},
            {"type": "fill", "text": "两直线平行 → 最易忘：平行要求斜率相等，同时截距____（若截距也相等则是____）", "answer": "不等；重合"}
          ]
        },
        {
          "step_label": "⏱ 第2步（3–4分钟）",
          "title": "易错点 & 正误对比（全板块）",
          "items": [
            {"type": "body", "text": "📌 【待定系数法】正误对比："},
            {"type": "fill", "text": "✅ 正确：将两点坐标分别代入 y=kx+b，列____个方程联立求解", "answer": "两"},
            {"type": "fill", "text": "❌ 易错：只代入____个点，少一个方程，k 和 b 无法唯一确定", "answer": "一"},
            {"type": "body", "text": "📌 【k、b 符号与象限】正误对比："},
            {"type": "fill", "text": "k>0，b>0 → 图像经过第____、____、____象限（不经过第____象限）", "answer": "一、二、三；四"},
            {"type": "fill", "text": "k<0，b<0 → 图像经过第____、____、____象限（不经过第____象限）", "answer": "二、三、四；一"},
            {"type": "fill", "text": "考试最常考：给出两点 → 用____法求解析式；给出 k、b 符号 → 判断图像经过____象限", "answer": "待定系数；对应象限（根据符号组合判断）"}
          ]
        },
        {
          "step_label": "⏱ 第3步（3–4分钟）",
          "title": "常考题型自测（每板块至少1题，共≥6道）",
          "items": [
            {"type": "fill", "text": "Q1（象限）：一次函数 y=kx+b，k>0，b<0，图像不经过第____象限", "answer": "三"},
            {"type": "fill", "text": "Q2（待定系数）：直线过(1,4)和(3,10)，k=____，b=____，解析式为____", "answer": "3；1；y=3x+1"},
            {"type": "fill", "text": "Q3（交点）：y=4x-8 与 x 轴交点是____，与 y 轴交点是____", "answer": "(2,0)；(0,-8)"},
            {"type": "fill", "text": "Q4（平行易错）：与 y=2x+5 平行的直线一定满足 k=____，且 b____5", "answer": "2；≠"},
            {"type": "fill", "text": "Q5（象限判断）：若一次函数经过一、二、三象限，则 k____0，b____0", "answer": ">；>"},
            {"type": "fill", "text": "Q6（压轴）：直线 y=ax+b 过 x 轴上点(4,0)，且 b=-3，求 a=____，写出解析式____", "answer": "a=¾；y=¾x-3"}
          ]
        }
      ],
      "self_test_phrase": "出发口令：「...」"
    },
    {
      "day": 14,
      "label": "课后第14天复习（A组）",
      "time": "6–8分钟",
      "type": "daily",
      "group": "A",
      "covered_categories": ["A组板块名称列表"],
      "items": [
        {"type": "body", "text": "📌 今天专项复习A组：[一次函数定义 · 图像走势与象限 · 待定系数法]"},
        {"type": "body", "text": "【A组·一次函数定义】"},
        {"type": "fill", "text": "一次函数 y=kx+b 的必要条件：k____0；当 b=0 时特称为____函数", "answer": "≠；正比例"},
        {"type": "fill", "text": "Q1：y=5x-2 中，k=____，b=____，图像与 y 轴交于____", "answer": "5；-2；(0,-2)"},
        {"type": "fill", "text": "Q2：以下哪些是一次函数：① y=x² ② y=3x ③ y=1/x ④ y=-2x+1 → 答：____", "answer": "②④"},
        {"type": "body", "text": "【A组·图像走势与象限】"},
        {"type": "fill", "text": "k>0 → 图像从左到右____；k<0 → 图像从左到右____", "answer": "上升（递增）；下降（递减）"},
        {"type": "fill", "text": "Q3：y=-2x+3，图像经过第____、____、____象限，不经过第____象限", "answer": "一、二、四；三"},
        {"type": "fill", "text": "Q4：已知一次函数图像经过二、三、四象限，则 k____0，b____0", "answer": "<；<"},
        {"type": "fill", "text": "A组综合题：直线 y=kx+1 经过点(2,5)，k=____，该直线经过第____象限", "answer": "2；一、二、三"}
      ],
      "self_test_phrase": "出发口令：「...」"
    },
    {
      "day": 30,
      "label": "课后第30天复习（B组）",
      "time": "6–8分钟",
      "type": "daily",
      "group": "B",
      "covered_categories": ["B组板块名称列表"],
      "items": [
        {"type": "body", "text": "📌 今天专项复习B组：[与坐标轴的交点 · 两直线位置关系 · 一次函数实际应用]"},
        {"type": "body", "text": "【B组·与坐标轴的交点】"},
        {"type": "fill", "text": "求与 x 轴交点：令____=0，解出 x；求与 y 轴交点：令____=0，直接得 y=____", "answer": "y；x；b"},
        {"type": "fill", "text": "Q1：y=3x-6 与 x 轴交点是____，与 y 轴交点是____", "answer": "(2,0)；(0,-6)"},
        {"type": "fill", "text": "Q2：直线过 x 轴上点(-3,0)和 y 轴上点(0,6)，k=____，解析式为____", "answer": "2；y=2x+6"},
        {"type": "body", "text": "【B组·两直线位置关系】"},
        {"type": "fill", "text": "平行条件：斜率____，截距____（k₁=k₂，b₁≠b₂）；重合条件：k₁____k₂ 且 b₁____b₂", "answer": "相等；不等；=；="},
        {"type": "fill", "text": "Q3：y=3x+1 和 y=3x-4 的位置关系是____（k 相同=3，b 不同）", "answer": "平行"},
        {"type": "fill", "text": "Q4：若 y=ax+b 与 y=2x-1 平行且过点(0,3)，则 a=____，b=____", "answer": "2；3"},
        {"type": "fill", "text": "B组综合题：出租车起步价8元（3km内），超出部分每km收2元，行驶 x km（x>3）费用 y=____；行驶10km费____元", "answer": "y=2x+2；22"}
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
    "下次做题前要额外注意：",
    "我需要老师再讲一遍的是："
  ]
}

【间隔复习安排规则】
- 第1天（day=1, type="day1"）：三步全面复盘，覆盖所有 key_categories，步骤3至少6道自测题。
- 第2天（day=2, type="day1"）：三步全面复习，覆盖所有 key_categories，侧重实战例题框架，步骤3至少6道自测题。
- 第7天（day=7, type="day1"）：三步全面复习，覆盖所有 key_categories，侧重易错点对比，步骤3至少6道自测题。
- 第14天（day=14, type="daily"）：只复习 group_a 板块，每个板块至少2道题，另有1道综合题。
- 第30天（day=30, type="daily"）：只复习 group_b 板块，每个板块至少2道题，另有1道综合题。
- days 数组严格只含5个元素（day=1,2,7,14,30），不要生成第60天。
- 每次复习结束都要有「出发口令」。
- 严格按照 day 字段的值设置（1、2、7、14、30），不要使用其他数字。

【题库规则】
- questions 要包含至少 15 道题，覆盖全部 key_categories。
- 每道题要有具体、清晰的答案。
- 难度均衡，覆盖基础、提升、易错三个层次。
"""

# ─── 复习风格附加提示词 ────────────────────────────────────────────────────────
PROMPT_STYLE_ADDONS = {
    "B": """
【三问法要求】
每个复习节点（第2/7/14/30/60天）的 items 内容必须围绕三个维度展开，三条填空分别对应：
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
    prompt_styles: list = None,
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
