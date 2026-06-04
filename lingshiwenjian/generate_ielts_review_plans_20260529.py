from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_plan_templates.generate_review_pdfs import render_review_plan_pdf


BASE_DIR = Path(__file__).resolve().parent
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
BASE_DATE = date(2026, 5, 29)


def make_safe_name(value: str) -> str:
    banned = '<>:"/\\|?*'
    return "".join("_" if char in banned else char for char in value).strip()


def day(
    offset: int,
    name: str,
    focus: str,
    goal: str,
    tasks: list[str],
    blanks: list[tuple[str, str]],
    choices: list[dict],
    quotes: list[str],
) -> dict:
    return {
        "offset": offset,
        "day": name,
        "focus": focus,
        "goal": goal,
        "tasks": tasks,
        "blanks": blanks,
        "choices": choices,
        "quotes": quotes,
    }


def mixed_section(title: str, blanks: list[tuple[str, str]], choices: list[dict], prompts: list[str], keypoints: list[str]) -> dict:
    return {
        "title": title,
        "mixed": {"blanks": blanks, "choices": choices},
        "oral": {"prompts": prompts, "keypoints": keypoints},
    }


def write_source_markdown(output_path: Path, lesson: dict, days: list[dict], final_lines: list[str]) -> None:
    lines = [
        f"# {lesson['title']}",
        "",
        f"- 生成日期：{BASE_DATE.isoformat()}",
        f"- 使用对象：{lesson['audience']}",
        f"- 单次时长：{lesson['duration']}",
        "",
        "## 核心复习点",
        "",
    ]
    lines.extend(f"- {item}" for item in lesson["core_points"])
    lines.extend(["", "## 复习节点", ""])
    for item in days:
        lines.extend(
            [
                f"### {item['day']}",
                "",
                f"- 复习重点：{item['focus']}",
                f"- 目标：{item['goal']}",
                "",
                "填空题：",
            ]
        )
        lines.extend(f"- {blank}（答案：{answer}）" for blank, answer in item["blanks"])
        lines.extend(["", "选择题："])
        for choice in item["choices"]:
            lines.append(f"- {choice['question']}（答案：{choice['answer']}）")
        lines.extend(["", "课堂原话："])
        lines.extend(f"- {quote}" for quote in item["quotes"])
        lines.append("")
    lines.extend(["## 最后提醒", ""])
    lines.extend(f"- {item}" for item in final_lines)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def static_bar_chart_plan(student: str, title_detail: str, emphasis: str, topic: str) -> tuple[dict, list[dict], dict, list[str]]:
    lesson = {
        "title": f"{student}{title_detail}课后复习计划",
        "subtitle": "IELTS Writing Task 1 Review Plan",
        "audience": "老师发给学生使用",
        "duration": "每次 10-20 分钟",
        "core_points": [
            f"本节课围绕雅思小作文 Task 1 静态柱状图展开：{topic}。",
            "开头段先判断图表类型、是否有时间、单位是数额还是比例，再做题干改写。",
            "概述段要先找项目组，再以组为单位找最大、最小、最明显的整体规律。",
            "静态图不能写 change、increase、decrease 这类动态变化词。",
            "细节段要先决定按国家还是按产品/方法分组，分组以后不要横竖混写。",
            "细节段优先写有意义的数据：最高、最低、相等、相似、差额、倍数或范围。",
            emphasis,
        ],
        "full_review_topics": [
            "Task 1 四段结构：开头段、概述段、两个细节段",
            "静态图与动态图的时态和动词区别",
            "项目组识别：国家、产品、方法、活动",
            "横着看与竖着看的切入点",
            "amount / spending / expenditure 与 proportion / percentage 的区别",
            "概述段：it is clear/evident that + 宏观规律",
            "细节段：turning to the details / when it comes to / in terms of / regarding",
            "数据表达：at, with the figure being, ranging from",
            "逻辑连接：however 只能连接同一比较维度的一高一低",
            "常见语法：主谓宾完整、最高级加 the、国家名前一般不加 the",
        ],
        "quotes": [
            "概述段我们拿到以后是要观察项目组的。",
            "静态图千万不能够说 change。",
            "我们分好了就不要再乱晃了。",
            "不能就谁 highest 谁 lowest，这样很无聊。",
            "你要先想这个图到底表达什么。",
            "如果没有关系，就不要去凑那个逻辑词。",
        ],
    }
    days = [
        day(
            1,
            "第1天",
            "第一次整课回放，先把静态图四段结构和项目组判断重新挂起来。",
            "能口头说出这类 Task 1 从审题到分段的完整流程。",
            [
                "默写 Task 1 四段结构。",
                "用 2 分钟判断图表类型、时间、单位和项目组。",
                "完成填空题，检查是否还会把数额写成比例。",
                "读课堂原话，提醒自己静态图不要写动态变化。",
            ],
            [
                ("Task 1 静态柱状图一般写四段：开头段、____________段和两个细节段。", "概述"),
                ("审题时先看有没有时间；没有时间且题目是 spent，通常用____________时。", "过去"),
                ("amount / spending / expenditure 表示____________，不能误写成 percentage。", "数额"),
                ("概述段先找____________组，再找一组一组的最大、最小和整体规律。", "项目"),
                ("横着看和竖着看代表不同____________，不能随意混用。", "切入点"),
                ("静态图不能写 increase、decrease、____________。", "change"),
                ("细节段要写单个有意义数据，如最高、最低、相等、差额和____________。", "范围"),
                ("however 只能连接同一比较维度下的一高一低，不能乱接____________维度。", "不同"),
            ],
            [
                {"question": "静态图最需要先避免的表达是什么？", "options": ["A. change / increase / decrease", "B. amount spent", "C. among", "D. with the figure being"], "answer": "A"},
                {"question": "概述段的第一步是什么？", "options": ["A. 找项目组", "B. 写所有数据", "C. 背模板不看图", "D. 先写结论段"], "answer": "A"},
            ],
            [lesson["quotes"][0], lesson["quotes"][1]],
        ),
        day(
            2,
            "第2天",
            "第二次整课复习，重点校准单位、主语和句子主干。",
            "能把“谁在什么范围内最高/最低”写成主谓宾完整的句子。",
            [
                "把 amount、spending、expenditure、percentage、proportion 各写一个中文解释。",
                "任选一条数据，用 had the highest / was allocated to / with the figure being 写 3 句。",
                "检查每句是否有真正谓语。",
                "复盘课堂指出的错句：比例、数额、国家、产品不要互相替换。",
            ],
            [
                ("percentage / proportion 表示____________，只有图中是百分比时才优先使用。", "比例"),
                ("the highest spending among six products 表示六种产品____________的最高花销。", "之中"),
                ("国家 Britain 作主语时，可写 Britain had the highest spending on every ____________。", "product"),
                ("the highest spending was allocated to... 里的 allocated to 表示数据____________到某类。", "分配"),
                ("with the figure being 150 thousand pounds 中 with 是介词，后面 be 要写成____________。", "being"),
                ("最高级 largest / highest 前通常要加____________。", "the"),
                ("国家名 Portugal / France / Germany 前一般不加____________。", "the"),
                ("一句英文不能只有名词短语，必须有真正的____________。", "谓语"),
            ],
            [
                {"question": "题目给的是 thousand pounds，概述段最不该写什么？", "options": ["A. the highest percentage", "B. the highest spending", "C. the amount spent", "D. expenditure"], "answer": "A"},
                {"question": "which doubled the figure of... 中 doubled 的作用是？", "options": ["A. 表示倍数关系", "B. 表示下降", "C. 表示无数据", "D. 表示题目顺序"], "answer": "A"},
            ],
            [lesson["quotes"][4]],
        ),
        day(
            7,
            "第7天",
            "一周后迁移，重点练概述段的宏观选择和细节段分组。",
            "能说明为什么一段按高花销组写，另一段按低花销组写。",
            [
                "拿一张新静态图，只写项目组和概述段要点，不写全文。",
                "口头解释按国家分组和按产品/方法分组的区别。",
                "回答口述卡片，每题都要说出“为什么这样分组”。",
                "检查自己是否又开始把不同维度硬接 however。",
            ],
            [
                ("概述段看的是____________信息，不是每一个单独数据。", "宏观"),
                ("细节段才开始写____________数据。", "单个"),
                ("如果按产品分组，就比较同一产品下不同____________。", "国家"),
                ("如果按国家分组，就比较同一国家下不同____________。", "产品"),
                ("两个细节段之间最好有逻辑，例如高花销产品一段、____________产品一段。", "低花销"),
                ("相等、相似、差额、倍数都比机械重复最高最低更有____________。", "意义"),
                ("overall 常用于引出概述，不等于随便放在任何____________句前。", "细节"),
                ("静态图的核心不是变化趋势，而是不同组别之间的____________。", "对比"),
            ],
            [
                {"question": "什么时候更适合按产品/方法分组？", "options": ["A. 同一产品/方法下国家差异清楚", "B. 完全看不懂单位", "C. 想写流水账", "D. 不想比较"], "answer": "A"},
                {"question": "however 最适合连接哪种关系？", "options": ["A. 同一维度的一高一低", "B. 两个毫无关系的观察", "C. 开头段和题目", "D. 作业安排"], "answer": "A"},
            ],
            [lesson["quotes"][2], lesson["quotes"][5]],
        ),
        day(
            14,
            "第14天",
            "两周后校准，重点减少静态图高频失分点。",
            "能独立检查一篇 Task 1 是否有动态词、单位错、主语错和分组跳跃。",
            [
                "拿自己旧作文，用红笔标出所有单位词和动态词。",
                "把每个细节句缩成主谓宾，检查是否完整。",
                "回答口述卡片：为什么这句话不能这么写。",
                "重写一个细节段，必须包含最高、最低和一个额外比较点。",
            ],
            [
                ("静态图里写 change 会把图误写成____________图。", "动态"),
                ("roughly the same 只能用于数据真的很____________时。", "接近"),
                ("如果数据有 150、160、172，不能统统说成____________。", "160"),
                ("about / approximately 可用于读图估算，但不能改变数据的____________。", "大小关系"),
                ("when it comes to、in terms of、regarding 都表示____________。", "关于"),
                ("turning to the details 用于提醒考官进入____________段。", "细节"),
                ("the lowest spender 这种表达要看主语是否真的是____________。", "国家"),
                ("越想写复杂句，越要先保证____________正确。", "主干"),
            ],
            [
                {"question": "看到图中没有时间变化，最稳的处理是什么？", "options": ["A. 写静态对比", "B. 写上升下降", "C. 写未来预测", "D. 写原因分析"], "answer": "A"},
                {"question": "细节段最不推荐的写法是？", "options": ["A. 机械列每个数据", "B. 按组比较", "C. 写相等差额", "D. 写范围"], "answer": "A"},
            ],
            [lesson["quotes"][3]],
        ),
        day(
            30,
            "第30天",
            "一个月后总复盘，用一篇完整 Task 1 检验流程是否稳定。",
            "能在 20 分钟内完成静态图审题、概述段和两个细节段。",
            [
                "限时 20 分钟写一篇静态柱状图。",
                "写完后按四项检查：单位、时态、分组、数据表达。",
                "把最弱的一句改写成更清楚的主谓宾结构。",
                "总结下一篇小作文最要改的一件事。",
            ],
            [
                ("长期固定流程：审题看图表、时间、单位、____________组。", "项目"),
                ("概述段只写宏观规律，不写太多____________数据。", "具体"),
                ("细节段分组后不能____________切换维度。", "随意"),
                ("数据表达至少掌握 at、with the figure being、ranging ____________。", "from"),
                ("最高最低之外，还要找相等、相似、差额、____________。", "倍数"),
                ("写完后先查有没有动态词，再查有没有____________错误。", "单位"),
                ("长句不稳时，优先回到清楚的____________结构。", "主谓宾"),
                ("Task 1 的目标不是堆模板，而是清楚描述____________。", "数据关系"),
            ],
            [
                {"question": "一个月后最应该稳定留下的能力是什么？", "options": ["A. 审题-概述-分组-数据表达流程", "B. 背一个万能句", "C. 每题都写五段", "D. 不看单位"], "answer": "A"},
                {"question": "写完 Task 1 最先自查哪项？", "options": ["A. 单位和静动态是否写错", "B. 字体颜色", "C. 标题是否加粗", "D. 是否写了作业"], "answer": "A"},
            ],
            [lesson["quotes"][1], lesson["quotes"][2]],
        ),
    ]
    knowledge = {
        item["day"]: [
            mixed_section(
                "静态图 Task 1 写作动作",
                [("静态图先判断单位，再决定写 amount 还是____________。", "percentage"), ("细节段分组后不要____________维度。", "跳")],
                [{"question": "静态图细节段最应该写什么？", "options": ["A. 有意义的数据关系", "B. 作文感想", "C. 图表原因", "D. 未来趋势"], "answer": "A"}],
                ["为什么静态图不能写 change？", "概述段和细节段最大的区别是什么？", "如何判断 however 能不能用？"],
                ["没有时间变化就写静态对比。", "概述段写组别规律，细节段写具体数据。", "必须是同一维度下的对比。"],
            )
        ]
        for item in days
    }
    final = [
        "审题先看图表类型、时间、单位和项目组。",
        "数额用 amount / spending / expenditure；比例才用 percentage / proportion。",
        "概述段先找项目组，再写宏观最大、最小和整体规律。",
        "静态图不要写 change / increase / decrease。",
        "细节段分组后不要横竖混写。",
        "数据表达要写清最高、最低、相等、相似、差额、倍数或范围。",
    ]
    return lesson, days, knowledge, final


def listening_matching_plan() -> tuple[dict, list[dict], dict, list[str]]:
    lesson = {
        "title": "刘同学雅思听力匹配题课后复习计划",
        "subtitle": "IELTS Listening Matching Review Plan",
        "audience": "老师发给学生使用",
        "duration": "每次 10-20 分钟",
        "core_points": [
            "本节课重点训练雅思听力匹配题，尤其是普通匹配和特殊匹配的预读策略。",
            "普通匹配通常选项比题目多，重点读容易被同义替换的选项。",
            "特殊匹配题目比选项多时，要反过来重点读题目。",
            "预读不能只看一遍，要画关键词，并展开合理想象。",
            "同义替换常通过近义词、解释、举例和具体化出现。",
            "相似选项要特别警惕：单复数、包含关系、动作对象都可能成为陷阱。",
            "听力过程要按顺序定位，把预判和录音内容结合，不要听到熟词就立刻选。",
        ],
        "full_review_topics": [
            "普通匹配与特殊匹配的区别",
            "选项和题目谁更容易被替换",
            "关键词与 content words",
            "上下游合理想象",
            "具体例子替换抽象表达",
            "相似选项、相反选项和包含关系",
            "转折、推脱和人名分工",
            "听力长前摇中的心态稳定",
            "地图式定位：period / style / topic 先抓住",
            "错题复盘：没预判、没定位、误选熟词",
        ],
        "quotes": [
            "匹配题难不是难在生难词，而是逻辑的转换。",
            "哪个内容容易被同义替换掉，我们就认真看哪一个内容。",
            "画完关键词以后要展开合理想象。",
            "不要看完了题目就看完了，脑子里什么都不留。",
            "听到原词很可能是陷阱。",
            "前面很长没有出题，不要慌。",
        ],
    }
    days = [
        day(1, "第1天", "第一次整课回放，先区分普通匹配和特殊匹配。", "能判断每道匹配题应该重点读选项还是题目。", ["默写普通匹配和特殊匹配的区别。", "拿一组匹配题，标出最容易被同义替换的部分。", "完成填空题和选择题。", "读课堂原话，提醒自己不能只扫一遍。"], [("普通匹配通常选项比题目____________，重点读选项。", "多"), ("特殊匹配通常题目比选项____________，重点读题目。", "多"), ("预读先画能够提示内容的____________词。", "关键词"), ("匹配题常考抽象表达变成具体____________。", "例子"), ("produce water and soil 更接近 produce materials，不一定等于 produce ____________。", "fertilizer"), ("听到熟悉单词不能马上选，要看单复数和____________关系。", "包含"), ("人名分工题要听转折、推脱和最后____________。", "归属"), ("听力题一般按____________出现，但替换方式会绕。", "顺序")], [{"question": "普通匹配题最应该重点预读什么？", "options": ["A. 容易被替换的选项", "B. 页码", "C. 标题颜色", "D. 所有虚词"], "answer": "A"}, {"question": "听到 fertilizer 时为什么不能马上选 fertilizer 选项？", "options": ["A. 可能只是施肥动作或材料关系", "B. 一定没听到", "C. 题目不按顺序", "D. fertilizer 不重要"], "answer": "A"}], [lesson["quotes"][0], lesson["quotes"][1]]),
        day(2, "第2天", "第二次整课复习，重点训练合理想象和同义替换。", "能把抽象选项提前转成可能听到的具体词。", ["给每个选项写 2 个可能替换词。", "把 visual work 联想到 photos / videos / PowerPoint。", "把 food and drink 联想到具体食物饮料。", "复盘 selfish / independent / attention-seeking 等性格词。"], [("visual work 可能被替换成 photos、pictures、videos 或____________。", "PowerPoint"), ("provide food and drink 可能通过具体____________来替换。", "例子"), ("outgoing 可联想到 extroverted、active、like to ____________ friends。", "make"), ("selfish 可解释为 only care about ____________。", "oneself"), ("independent 可解释为 do things by ____________。", "oneself"), ("attention-seeking 可解释为 wanting others to ____________ him。", "notice"), ("cooperative 可解释为 work with ____________。", "others"), ("相似相反选项要连起来看，因为它们常是____________。", "陷阱")], [{"question": "合理想象的目的是什么？", "options": ["A. 让听到替换时能主动连接", "B. 背文章", "C. 猜题号", "D. 忽略录音"], "answer": "A"}, {"question": "content words 指什么？", "options": ["A. 有具体意义、能定位的词", "B. of / the / and", "C. 标点符号", "D. 页眉"], "answer": "A"}], [lesson["quotes"][2], lesson["quotes"][3]]),
        day(7, "第7天", "一周后迁移，集中训练相似选项和特殊匹配。", "能解释为什么某些选项看起来像但不能选。", ["做一组特殊匹配，只读题目中的可替换内容。", "标出每组相似选项的区别。", "回答口述卡片。", "复盘 refrigerated goods / health impact / food producers 这些题干如何预判。"], [("refrigerated goods 可预判为 cake、food、drink 或放进____________。", "fridge"), ("positive health impact 可替换为 good for health 或 health ____________。", "benefit"), ("negative impact 可替换为 harmful 或____________。", "dangerous"), ("food producers 可联想到 farmers 或____________。", "suppliers"), ("特殊匹配里难点可能不是选项，而是题干____________。", "定位"), ("人名/时期/风格先抓住，后面再听具体____________。", "特征"), ("长前摇没有答案时，先稳住____________。", "心态"), ("同一篇中难点会转移：有时难在替换，有时难在____________。", "定位")], [{"question": "特殊匹配题中“谁做什么研究”最该先读什么？", "options": ["A. 每个 topic", "B. 页码", "C. 例句长度", "D. 听力标题颜色"], "answer": "A"}, {"question": "相似选项最需要比较什么？", "options": ["A. 具体对象和动作", "B. 字母顺序", "C. 是否好看", "D. 是否最长"], "answer": "A"}], [lesson["quotes"][4]]),
        day(14, "第14天", "两周后校准，重点处理长前摇和定位崩掉的问题。", "听到很久没出题时，仍能根据 period / style / topic 等信号重新定位。", ["复听一段含长前摇的匹配题。", "只记录出题点前的定位信号。", "总结自己是没听懂替换，还是没抓到题号位置。", "做口述卡片。"], [("长前摇里没有答案时，不要把所有信息都当____________。", "答案"), ("modern style 对应 X-ray、internal skeleton，这属于____________替换。", "解释"), ("yam style 的 curvy figures 可对应 rounded ____________。", "figures"), ("without hands 可对应 parts ____________。", "missing"), ("miniature 可对应 small 或____________。", "tiny"), ("vegetables / yam 可提示 food source 从 animals 转向____________。", "plants"), ("没定位到题号时，要回到 period / style / topic 这类____________信号。", "锚点"), ("复盘时分清：替换没听出，还是____________没抓住。", "定位")], [{"question": "听到很长背景介绍时最稳的做法是？", "options": ["A. 继续等题号锚点", "B. 随便选", "C. 放弃后面", "D. 把背景全写下来"], "answer": "A"}, {"question": "internal skeleton 最可能对应哪个选项？", "options": ["A. revealing bones", "B. rounded figures", "C. food source", "D. miniature"], "answer": "A"}], [lesson["quotes"][5]]),
        day(30, "第30天", "一个月后总复盘，用完整听力匹配检验预读流程。", "能在真实限时中完成预读、定位、替换判断和错题归因。", ["限时完成一组听力匹配题。", "做题前写下每个选项的 1 个替换或例子。", "做完后按三类归因：没预判、没定位、误选熟词。", "选一个最弱动作，下次听力前固定执行。"], [("长期流程：先判断题型，再读容易被____________的部分。", "替换"), ("预读后要留下关键词和合理____________。", "想象"), ("听题时按顺序定位，同时警惕____________词陷阱。", "原"), ("错选熟词往往是没有核对单复数、对象或____________关系。", "包含"), ("人名分工题尤其要听转折和最终____________。", "决定"), ("长前摇时先听锚点，不要被背景扰乱____________。", "节奏"), ("错题归因可分为没预判、没定位、____________熟词。", "误选"), ("下次训练前只固定改一个最关键的____________动作。", "预读")], [{"question": "一个月后最该留下的听力匹配能力是什么？", "options": ["A. 主动预判同义替换", "B. 听到熟词就选", "C. 不看题干", "D. 只背答案"], "answer": "A"}, {"question": "复盘听力匹配错题最有效的方式是？", "options": ["A. 判断错在预判、定位还是误选", "B. 只看分数", "C. 只背录音", "D. 不听第二遍"], "answer": "A"}], [lesson["quotes"][2], lesson["quotes"][3]]),
    ]
    knowledge = {
        item["day"]: [
            mixed_section(
                "听力匹配预读动作",
                [("普通匹配重点读容易被替换的____________。", "选项"), ("预读后要展开合理____________。", "想象")],
                [{"question": "听到原词时应该怎样？", "options": ["A. 核对对象和逻辑再选", "B. 立刻选", "C. 放弃", "D. 跳题"], "answer": "A"}],
                ["普通匹配和特殊匹配怎么区分？", "为什么要联想上下游？", "相似选项怎么防陷阱？"],
                ["看题目和选项数量。", "抽象表达常被具体例子替换。", "比较对象、动作、单复数和包含关系。"],
            )
        ]
        for item in days
    }
    final = [
        "普通匹配重点读选项，特殊匹配反过来看题目。",
        "哪个内容容易被同义替换，就认真预读哪个。",
        "画关键词后要做上下游合理想象。",
        "相似选项要核对单复数、对象、动作和包含关系。",
        "长前摇不要慌，等题号锚点和核心特征。",
        "错题按没预判、没定位、误选熟词三类复盘。",
    ]
    return lesson, days, knowledge, final


def reading_heading_plan() -> tuple[dict, list[dict], dict, list[str]]:
    lesson = {
        "title": "刘同学雅思阅读Heading题课后复习计划",
        "subtitle": "IELTS Reading Heading Review Plan",
        "audience": "老师发给学生使用",
        "duration": "每次 10-20 分钟",
        "core_points": [
            "本节课训练雅思阅读 heading 题，也就是为段落找标题。",
            "heading 题找的是段落中心，不是信息匹配里的微观细节。",
            "观点可能来自个人言论、事实陈述、转折后内容、总结句或下一段开头的承上启下。",
            "for example、for instance、because、according to、数据、具体例子多数只是论据。",
            "不能机械只看首尾句；现在的 heading 更要求真正识别观点。",
            "一个段落可能有不止一个观点，选项通常只对应其中一个可匹配观点。",
            "嗅觉与记忆文章中，unreliable evidence、bring back memories、escape the past 等选项要看是否在观点位置出现。",
        ],
        "full_review_topics": [
            "heading 与信息匹配的区别",
            "观点句识别：states / claims / argues / 引号",
            "事实类陈述也可能是中心",
            "例子、解释、数据和 according to 的处理",
            "but / however / even so 后的观点",
            "下一段 this / these 指代上一段中心",
            "一个段落多个观点时的选项匹配",
            "unreliable evidence 出现在例子还是观点",
            "scent / image / sense / aroma 等词汇",
            "题后复盘：别把提及当中心",
        ],
        "quotes": [
            "heading 要找的永远都是最重要的那个观点。",
            "不要说全文瞄完了，然后感觉第一句更重要。",
            "不是没有提到，而是它并非观点。",
            "例子里面再怎么样都不重要。",
            "一个段里面也不一定只有一个观点。",
            "没有在观点里面找到内容，不要回去把例子当成观点。",
        ],
    }
    days = [
        day(1, "第1天", "第一次整课回放，先分清 heading 和信息匹配。", "能说出 heading 找中心，信息匹配找细节。", ["默写 heading 题的目标。", "列出观点信号和细节信号。", "完成填空与选择。", "读课堂原话，提醒自己不要把提及当中心。"], [("Heading 题找的是段落____________，不是一句细节。", "中心"), ("信息匹配常找微观内容，heading 更看重____________。", "观点"), ("states、claims、argues、引号常提示个人____________。", "言论"), ("事实类陈述也可能是段落____________。", "观点"), ("for example / for instance 常提示后面是____________。", "例子"), ("because / due to 后面常是解释，不一定是____________。", "中心"), ("according to 和大量数据通常优先当作____________处理。", "细节"), ("每段 heading 都会考，没有信息匹配那种____________。", "NB")], [{"question": "heading 题最核心的任务是什么？", "options": ["A. 找段落中心", "B. 找所有数字", "C. 翻译全文", "D. 背选项"], "answer": "A"}, {"question": "argues 在阅读观点句里常等于什么？", "options": ["A. says", "B. fights", "C. calculates", "D. copies"], "answer": "A"}], [lesson["quotes"][0], lesson["quotes"][2]]),
        day(2, "第2天", "第二次整课复习，重点练观点与例子的边界。", "看到例子、解释、数据时能判断是否需要跳过。", ["拿 3 个段落标出观点句和例子句。", "把 because / for example / say 后面的内容标成细节。", "完成填空与选择。", "复盘 unreliable evidence 为什么有时不是答案。"], [("论据只是 supporting topic sentence，通常不是____________。", "答案"), ("say 有时等于 for example，提示后面是____________。", "举例"), ("如果 evidence 只在例子中出现，不一定能选 checking unreliable ____________。", "evidence"), ("conclude 后面通常更可能是____________。", "观点"), ("but 后内容即使看起来微观，也可能是____________转折。", "核心"), ("比较两个具体类目时，通常已经进入____________层面。", "细节"), ("不能因为一个词被提到，就认为它是段落____________。", "中心"), ("读 heading 时要坚定找观点，不要回头把____________当观点。", "例子")], [{"question": "为什么某段提到 unreliable evidence 却不一定选 F？", "options": ["A. 它可能只在例子里，不在观点里", "B. 这个词一定错", "C. heading 不看英文", "D. 因为字母太后"], "answer": "A"}, {"question": "看到 conclude 时通常应该怎样？", "options": ["A. 认真看后面的总结", "B. 直接跳过", "C. 当成数字", "D. 当作例子"], "answer": "A"}], [lesson["quotes"][2], lesson["quotes"][3]]),
        day(7, "第7天", "一周后迁移，集中训练复杂段落里的多观点识别。", "能接受一个段落不止一个观点，并从选项里找能对应的那个。", ["读一段较长 heading 段落，只标观点，不翻译全部细节。", "用下一段 this / these 指代反推上一段中心。", "回答口述卡片。", "复盘 language paradox、tourism impact、course title 这些例子。"], [("如果下一段开头 this problem 指代上一段，上一段中心可能与____________有关。", "problem"), ("一个段落可能有多个____________，不能主观只认一个。", "观点"), ("选项通常只给一个能与段落观点____________的标题。", "对应"), ("travel 段落可能考 history，也可能考 importance，要看选项____________。", "匹配"), ("apparently incompatible characteristics 表示看似____________的特点。", "不兼容"), ("but 后面的 surprising course title 即使具体，也可能是____________。", "答案"), ("观点很散时，先把每个可能观点____________列出来。", "独立"), ("heading 不是要求把所有细节读懂，而是抓住可匹配的____________。", "中心")], [{"question": "下一段开头 this / these 有什么价值？", "options": ["A. 可能指回上一段中心", "B. 一定没用", "C. 只表示语法", "D. 只能做填空"], "answer": "A"}, {"question": "一个段落多个观点时该怎么选？", "options": ["A. 看选项哪个能对应段内观点", "B. 自己选最喜欢的观点", "C. 只选第一句", "D. 只选最长选项"], "answer": "A"}], [lesson["quotes"][4]]),
        day(14, "第14天", "两周后校准，重点辨析嗅觉文章中的相似选项。", "能区分视觉与嗅觉的伴随、对比、不可靠证据和逃离过去。", ["复盘 scent / aroma / image / sense 的含义。", "把 A、D、F 等相似选项写成中文区别。", "回答口述卡片。", "检查自己是否看到 scent 就选相关选项。"], [("sense 可表示感官，不只是____________。", "意识"), ("scent / aroma 表示____________。", "气味"), ("image 属于视觉，scent 属于____________。", "嗅觉"), ("reinforcing one sense with another 强调两种感官____________。", "伴随"), ("scent versus image 强调两种感官____________。", "对比"), ("escaping from reliving the past 表示逃离____________。", "过去"), ("checking unreliable evidence 里的 checking 强调____________动作。", "验证"), ("同一篇文章都在讲嗅觉，不能看到气味就____________。", "乱选")], [{"question": "A 与 D 都可能出现两种感官，区别是什么？", "options": ["A. A 是伴随增强，D 是对比", "B. A 是数字，D 是地点", "C. A 是例子，D 是题号", "D. 没区别"], "answer": "A"}, {"question": "checking unreliable evidence 的核心动词是什么？", "options": ["A. checking", "B. smelling", "C. image", "D. past"], "answer": "A"}], [lesson["quotes"][5]]),
        day(30, "第30天", "一个月后总复盘，用一篇完整 heading 题检验观点识别。", "能在限时中完成读选项、找观点、排除例子和错题归因。", ["限时做一篇 heading 题。", "读选项时标出区别：伴随、对比、证据、过去、警告等。", "每段只标观点句，不标所有细节。", "错题按三类归因：没找观点、把例子当观点、选项区别没分清。"], [("长期流程：先读 heading 选项，再回段落找____________。", "观点"), ("观点信号包括个人言论、事实陈述、转折、总结和____________指代。", "下段"), ("例子和数据只在其他题型需要时才可能细看，heading 中先____________。", "跳过"), ("看到关键词被提及，要问它是不是在____________位置。", "观点"), ("选项区别要提前拆开，例如伴随、对比、验证、____________过去。", "逃离"), ("错题常见原因之一是把____________当中心。", "例子"), ("第二类错因是只看首尾，没有看转折或____________句。", "总结"), ("最终目标是用观点对应标题，而不是把全文逐句____________。", "翻译")], [{"question": "heading 错题最常见的复盘角度是什么？", "options": ["A. 是否把例子当观点", "B. 字体是否整齐", "C. 是否背了全文", "D. 是否写了作文"], "answer": "A"}, {"question": "一个月后最该留下的阅读动作是什么？", "options": ["A. 观点位置优先", "B. 看到原词就选", "C. 全文逐字翻译", "D. 只看第一句"], "answer": "A"}], [lesson["quotes"][0], lesson["quotes"][5]]),
    ]
    knowledge = {
        item["day"]: [
            mixed_section(
                "Heading 观点识别",
                [("Heading 找段落____________。", "中心"), ("例子被提到不等于它是____________。", "观点")],
                [{"question": "看到 for example 后通常怎样？", "options": ["A. 先当细节处理", "B. 一定选它", "C. 只看数字", "D. 结束答题"], "answer": "A"}],
                ["heading 和信息匹配的区别是什么？", "哪些句子更可能是观点？", "为什么提到不等于答案？"],
                ["heading 找中心，信息匹配找细节。", "个人言论、事实陈述、转折总结更重要。", "必须看它是否处在观点位置。"],
            )
        ]
        for item in days
    }
    final = [
        "Heading 题找段落中心，不找零散细节。",
        "观点可能在个人言论、事实陈述、转折、总结或下一段指代里。",
        "for example、because、according to、数据通常先当细节。",
        "一个段落可能有多个观点，选项能对应哪个就选哪个。",
        "提到不等于答案，必须看是否在观点位置。",
        "错题按没找观点、把例子当观点、选项区别没分清来复盘。",
    ]
    return lesson, days, knowledge, final


COURSES = [
    ("20260527100038-瑶瑶 写作2", static_bar_chart_plan("瑶瑶", "雅思写作Task 1静态柱状图", "本节课特别强调：bar chart 发音、money spent 的过去时、amount 不能写成 proportion、横着看和竖着看不能乱接 however。", "不同国家在六种消费品上的花销")),
    ("20260527161519-包同学 写作 6", static_bar_chart_plan("包同学", "雅思写作Task 1环保方法静态图", "本节课特别强调：greenhouse gases 主题中，Portugal 是最积极国家，Estonia 较低，government regulations 和 advanced technology 相对更受欢迎。", "四个国家采用不同方法减少 greenhouse gases 的比例")),
    ("20260527190914-Dellen 写作", static_bar_chart_plan("Dellen", "雅思写作Task 1静态柱状图", "本节课特别强调：开头段不要为了替换写 money cost；概述段要加 it is evident/clear that；细节段要用 when it comes to / in terms of 引入。", "四个国家在六种消费品上的花销")),
    ("20260528101620-Celine 写作 6", static_bar_chart_plan("Celine", "雅思写作Task 1静态柱状图", "本节课特别强调：consumer goods 可替换为 products/items，细节段高花销组三个产品和低花销组三个产品要分开写。", "四个国家在六种消费品上的花销")),
    ("20260527135620-刘同学 听力4", listening_matching_plan()),
    ("20260528125416-刘同学 阅读4", reading_heading_plan()),
]


def main() -> None:
    outputs: list[Path] = []
    for prefix, payload in COURSES:
        lesson, days, knowledge, final_lines = payload
        safe_title = make_safe_name(lesson["title"].replace("课后复习计划", ""))
        pdf_path = BASE_DIR / f"{prefix}-{safe_title}-课后复习计划-{STAMP}.pdf"
        md_path = BASE_DIR / f"{prefix}-{safe_title}-复习计划源文件-{STAMP}.md"
        render_review_plan_pdf(
            lesson=lesson,
            days=days,
            final_reminder_lines=final_lines,
            output_path=str(pdf_path),
            variant_key="cn",
            knowledge_sections=knowledge,
        )
        write_source_markdown(md_path, lesson, days, final_lines)
        outputs.extend([pdf_path, md_path])
    print("Created review plan files:")
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
