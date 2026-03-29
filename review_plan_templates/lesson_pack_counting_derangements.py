LESSON = {
    "title": "排列组合、错排与综合题型课后复习计划",
    "subtitle": "Spaced Review Plan for Counting, Derangements, and Transfer Across Problem Types",
    "audience": "老师发给学生使用 / For Teacher Distribution",
    "duration": "每次 10-20 分钟 / 10-20 minutes each time",
    "core_points": [
        "分类与分步的区别。",
        "多面手问题的分类标准。",
        "先选后排。",
        "错排定义、递推与公式。",
        "部分错排 C(n,m)×D(m)。",
        "路灯不相邻与间隔限制。",
        "路径题中的正难则反。",
        "楼梯题中的递推与组合模型。",
        "数字组合题中的枚举判断。",
        "人员排列中的插空与间隔。",
    ],
    "full_review_topics": [
        "分类与分步的区别 / Distinguish case analysis from step-by-step counting",
        "多面手问题的分类标准 / Classification standards for all-rounder problems",
        "先选后排 / Choose first, then arrange",
        "错排定义、递推与公式 / Derangements: definition, recurrence, and formula",
        "部分错排 C(n,m)×D(m) / Partial derangements: choose then derange",
        "路灯不相邻与间隔限制 / Lamp problems with non-adjacency and spacing constraints",
        "路径题中的正难则反 / Complement counting in path problems",
        "楼梯题中的递推与组合模型 / Stair problems: recurrence versus combinations",
        "数字组合题中的枚举判断 / When enumeration is better than formulas",
        "人员排列中的插空与间隔 / Insertion method for people-arrangement constraints",
    ],
    "quotes": [
        "遭不住了就分类。",
        "先选人，再排列。",
        "不要把分布和分类搞混了。",
        "错排不是背个公式就完了，关键是你得会推。",
        "排列组合要先读懂题，再决定方法。",
        "先把别的排好，再插空。",
    ],
}


DAYS = [
    {
        "offset": 1,
        "day": "第1天 / Day 1",
        "focus": "第一次整课回放，先把题型和方法一一对上。 / First whole-lesson replay focused on matching problem types to methods.",
        "goal": "能口头说出这节课的主要题型，并知道各自首选方法。 / Name the main problem types and their preferred methods.",
        "tasks": [
            "先默写整节课的方法清单，再核对。Write down the method list before checking notes.",
            "完成填空题，按“方法-概念-例题-提醒”的顺序回顾。Complete the blanks in the order: methods, concepts, examples, warnings.",
            "完成选择题，检查基础记忆和易混概念。Finish the multiple choice items to test recall and distinction.",
            "朗读一次上课金句回顾，再口头复述整节课主线。Read the class quotes, then retell the lesson flow.",
        ],
        "blanks": [
            ("排列组合题做不下去时，一个常见通法是先做____________。", "分类"),
            ("分类时最重要的要求是既要____________，又要____________。", "不重；不漏"),
            ("篮球队选人安排题中，常见顺序是先____________，再____________。", "选人；排列"),
            ("多面手问题更高效的分类方式之一，是按多面手参与某岗位的____________来分。", "人数"),
            ("错排指的是每个元素都不能回到自己的____________。", "原位"),
            ("部分错排的一般结构是先____________，再____________。", "选出错位对象；对错位对象做错排"),
            ("看到“不相邻”这类限制，常优先考虑____________法。", "插空"),
        ],
        "choices": [
            {
                "question": "哪一项最体现“分类”而不是“分步” / Which best shows case analysis rather than step-by-step counting?",
                "options": [
                    "A. 先选 3 人再排座位 / Choose 3 people, then assign seats",
                    "B. 按多面手去唱歌的人数分成 0、1、2、3 类 / Split by how many all-rounders go to sing",
                    "C. 先算总数再减去坏情况 / Count all, then subtract bad cases",
                    "D. 先排男生再插空排女生 / Arrange boys first, then insert girls",
                ],
                "answer": "B",
            },
            {
                "question": "下列哪类题最适合优先考虑插空法 / Which type most strongly suggests insertion method?",
                "options": [
                    "A. 全错排 / Full derangements",
                    "B. 普通选人题 / Simple selection problems",
                    "C. 元素不能相邻 / Elements cannot be adjacent",
                    "D. 纯路径总数 / Total path count only",
                ],
                "answer": "C",
            },
        ],
        "quotes": [LESSON["quotes"][0], LESSON["quotes"][1]],
    },
    {
        "offset": 2,
        "day": "第2天 / Day 2",
        "focus": "第二次整课复习，重点区分错排、部分错排和普通排列组合。 / Second full review focused on distinguishing derangements, partial derangements, and ordinary counting.",
        "goal": "看到“恰有几个不同”或“全部不在原位”时，能快速判断模型。 / Quickly recognize partial versus full derangement structures.",
        "tasks": [
            "快速过一遍全课覆盖清单。Run through the full-lesson coverage list.",
            "完成填空题，重点复盘错排、部分错排和路灯题。Complete the blanks with emphasis on derangements and lamp problems.",
            "完成选择题，纠正“看到位置不同就一律当错排”的误判。Use choices to correct common overgeneralization.",
            "口头说明错排递推为什么会出现前两项。Explain orally why the recurrence uses the previous two terms.",
        ],
        "blanks": [
            ("错排题中，最重要的不是死记公式，而是理解公式的____________过程。", "推导"),
            ("错排递推里，第一个元素放错后，后续通常分成____________类情况。", "两"),
            ("若题目说“恰有 3 个位置不一致”，本质上通常是在做____________错排。", "部分"),
            ("部分错排的公式结构可写为____________。", "C(n,m)×D(m)"),
            ("路灯题如果首尾受限、间隔受限，常先设____________再转成组合问题。", "变量"),
            ("路径题“不经过某点”时，常用策略是____________。", "总数减去经过该点的情况"),
            ("楼梯题中，如果已知几个 1、几个 2，再问排法，通常转成____________问题。", "排列组合"),
        ],
        "choices": [
            {
                "question": "哪一项最可能是“部分错排” / Which is most likely a partial derangement?",
                "options": [
                    "A. 5 个元素全部不在原位 / All 5 elements are displaced",
                    "B. 8 个信封中恰有 3 个装错 / Exactly 3 of 8 envelopes are mismatched",
                    "C. 4 个人站成一排 / 4 people stand in a line",
                    "D. 从 6 人中选 2 人 / Choose 2 from 6 people",
                ],
                "answer": "B",
            },
            {
                "question": "下列哪一项是课堂反复强调的错误 / Which mistake was repeatedly warned against?",
                "options": [
                    "A. 分类标准选得太随意 / Choosing a classification standard too casually",
                    "B. 先读题 / Reading the problem first",
                    "C. 先看限制条件 / Looking at constraints first",
                    "D. 检查是否重不漏 / Checking completeness and non-overlap",
                ],
                "answer": "A",
            },
        ],
        "quotes": [LESSON["quotes"][3]],
    },
    {
        "offset": 7,
        "day": "第7天 / Day 7",
        "focus": "一周后整课迁移，要求看到题目特征就能说出方法。 / One-week transfer review: identify methods directly from problem features.",
        "goal": "不用落笔也能口头讲清各类题的首选思路。 / Explain the preferred method for each problem type orally.",
        "tasks": [
            "先口头复述整课方法地图。Orally restate the lesson method map.",
            "回答老师提问卡片，每题必须补一句“为什么”。Answer oral prompt cards and add one reason each time.",
            "再回看一遍路灯题、路径题和楼梯题的共通逻辑。Review the shared logic of lamp, path, and stair problems.",
            "最后复述至少 3 句课堂金句。Retell at least 3 class quotes at the end.",
        ],
        "blanks": [
            ("看到“不能经过某点”的路径题，常用____________法。", "正难则反"),
            ("看到“相邻两盏关灯之间至少隔若干盏亮灯”时，常结合____________与组合转化。", "设变量"),
            ("楼梯题如果问“到第 n 级有多少种走法”，更偏向____________思想。", "递推"),
            ("如果一道题既有人员角色又有位置安排，首先要区分是____________还是____________。", "分类；分步"),
            ("数字组合题规模较小、结构直观时，直接____________往往更快。", "枚举"),
            ("人员排列题里，“两名女生之间至少有一个男生”常优先考虑____________法。", "插空"),
            ("多面手题分类太乱，往往说明____________没有选好。", "分类标准"),
        ],
        "choices": [
            {
                "question": "哪一项最符合“正难则反” / Which best matches complement counting?",
                "options": [
                    "A. 先分类再分步 / Cases first, then steps",
                    "B. 先算总情况，再减去必须经过限制点的情况 / Count all then subtract paths through the restricted point",
                    "C. 先选人再排列 / Choose first, then arrange",
                    "D. 先设坐标再求方程 / Set coordinates first",
                ],
                "answer": "B",
            },
            {
                "question": "楼梯题何时更适合递推 / When is recurrence the right model for stair problems?",
                "options": [
                    "A. 已经给定 2 的个数 / The number of 2-steps is fixed",
                    "B. 问到第 n 级共有多少种走法 / It asks the total number of ways to reach step n",
                    "C. 只问选哪两步走 2 / It only asks which two steps are double-steps",
                    "D. 没有任何限制 / There are no constraints",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][4]],
    },
    {
        "offset": 14,
        "day": "第14天 / Day 14",
        "focus": "两周后校准，重点检查方法本质而不是题面外形。 / Two-week calibration focused on method essence rather than surface wording.",
        "goal": "看到变式题时，仍能认出和课堂例题同类的方法结构。 / Recognize the same method structure in new variants.",
        "tasks": [
            "先口头总结本节课最容易错的 5 个点。First summarize the 5 easiest mistakes orally.",
            "回答老师提问卡片，重点说清“为什么不用别的方法”。Answer oral prompts and explain why other methods are less suitable.",
            "回想多面手题、错排题和路径题的共同点：都要先抓限制条件。Recall that all these types start from constraints.",
            "最后再说一遍“先读题，再选方法”的总原则。Close by restating the lesson’s overall principle.",
        ],
        "blanks": [
            ("如果一道题分类以后情况太多，通常说明____________不够好。", "分类标准"),
            ("错排递推中会出现前两项，是因为第一步放错后会分成____________大类。", "两"),
            ("部分错排里，先选出需要错位的对象，再对这部分做____________。", "错排"),
            ("路灯题中“不相邻”和“至少隔一盏”这两类限制的共同高频方法是____________。", "插空"),
            ("路径题中，正面做很麻烦时，常改用____________。", "总数减坏情况"),
            ("本节课老师最反对的做题习惯是：不先读题就直接____________。", "套公式"),
        ],
        "choices": [
            {
                "question": "下列哪一项最可能导致整题思路崩掉 / Which issue most likely breaks the whole solution?",
                "options": [
                    "A. 分类和分步混淆 / Mixing up case analysis and step-by-step counting",
                    "B. 书写速度慢 / Writing slowly",
                    "C. 题号看错 / Reading the wrong question number",
                    "D. 页边距不整齐 / Uneven margins",
                ],
                "answer": "A",
            },
            {
                "question": "下列哪一项最符合本节课的做题观 / Which best matches the lesson's problem-solving view?",
                "options": [
                    "A. 哪个公式熟就先套哪个 / Apply whichever formula feels familiar",
                    "B. 先判断题目限制，再选方法 / Inspect constraints first, then choose the method",
                    "C. 所有题都必须分类 / Every problem must use case analysis",
                    "D. 所有题都必须列公式 / Every problem must start from a formula",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][2], LESSON["quotes"][4]],
    },
    {
        "offset": 30,
        "day": "第30天 / Day 30",
        "focus": "一个月后的总复盘，要求脱离课堂语境也能独立调用方法。 / One-month final review for independent method recall.",
        "goal": "形成长期记忆：看到新题时能先识别结构，再稳定下手。 / Reach long-term memory: recognize the structure first, then solve steadily.",
        "tasks": [
            "先默写整节课的题型-方法对照表。Write the type-to-method map from memory.",
            "完成总复盘填空和选择，检查长期记忆是否稳定。Complete the final blanks and choices to test long-term retention.",
            "复述一个你最熟悉的例题变成“方法模板”。Retell one familiar example as a reusable method template.",
            "最后读一遍上课金句回顾。Finish by reviewing the class quotes once more.",
        ],
        "blanks": [
            ("本节课最重要的总原则是：先____________题目，再____________方法。", "读懂；决定"),
            ("排列组合中，分类要求做到____________且____________。", "不重；不漏"),
            ("“每个元素都不能回原位”对应的模型叫____________。", "全错排"),
            ("“只有部分对象需要错位”对应的模型叫____________。", "部分错排"),
            ("看到“不能相邻”时，最典型的方法是____________。", "插空法"),
            ("看到“不经过指定点”的路径题时，最典型的方法是____________。", "正难则反"),
            ("这节课里，最容易混淆的两个概念是____________和____________。", "分类；分步"),
        ],
        "choices": [
            {
                "question": "一个月后的理想状态是 / What is the ideal state after one month?",
                "options": [
                    "A. 只背住课堂原话 / Only memorize the teacher's quotes",
                    "B. 看到新题能先判断方法，再稳定下手 / Identify the method first, then solve steadily",
                    "C. 只会做原题 / Only solve the original examples",
                    "D. 每题都从最复杂的方法开始 / Start every problem with the most complex method",
                ],
                "answer": "B",
            },
            {
                "question": "本节课长期复习最该留下的是什么 / What should remain most clearly after long-term review?",
                "options": [
                    "A. 零散答案 / Isolated answers",
                    "B. 题号顺序 / The order of question numbers",
                    "C. 题型与方法之间的对应关系 / The mapping between problem types and methods",
                    "D. 每道题的运算细节 / Every calculation detail",
                ],
                "answer": "C",
            },
        ],
        "quotes": [LESSON["quotes"][5]],
    },
]


KNOWLEDGE_SECTIONS = {
    "第1天 / Day 1": [
        {
            "title": "分类与分步 / Case Analysis vs Step-by-Step Counting",
            "mixed": {
                "blanks": [
                    ("“先选人再安排位置”更符合____________；“按多面手人数分 0、1、2 类”更符合____________。", "分步；分类"),
                ],
                "choices": [
                    {
                        "question": "下列哪项最能体现“先选后排” / Which best reflects choose first, then arrange?",
                        "options": [
                            "A. 按情况分成若干类 / Divide into several cases",
                            "B. 先从候选人中选，再安排角色或位置 / Select people first, then assign roles or positions",
                            "C. 先总后减 / Count all then subtract",
                            "D. 直接枚举 / Enumerate directly",
                        ],
                        "answer": "B",
                    }
                ],
            },
        },
        {
            "title": "多面手问题 / All-Rounder Problems",
            "mixed": {
                "blanks": [
                    ("多面手题分类过乱时，往往不是不会算，而是____________没选好。", "分类标准"),
                ],
                "choices": [
                    {
                        "question": "多面手题中更优的分类方式通常是 / The better classification in all-rounder problems usually is:",
                        "options": [
                            "A. 按题目里出现的顺序乱分 / Split randomly by appearance order",
                            "B. 按某岗位中多面手被选中的人数分类 / Split by how many all-rounders enter a chosen role",
                            "C. 按名字首字母分类 / Split by initials",
                            "D. 只按总人数分类 / Split only by total count",
                        ],
                        "answer": "B",
                    }
                ],
            },
        },
    ],
    "第2天 / Day 2": [
        {
            "title": "错排与部分错排 / Derangements and Partial Derangements",
            "mixed": {
                "blanks": [
                    ("部分错排的一般做法是先从总对象中选出____________，再做____________。", "需要错位的对象；错排"),
                ],
                "choices": [
                    {
                        "question": "哪一项最符合部分错排的逻辑 / Which best describes a partial derangement?",
                        "options": [
                            "A. 全部对象都必须错位 / All objects must move",
                            "B. 先挑出错位对象，其余默认在原位 / Choose the displaced objects first, the others stay fixed",
                            "C. 只要排列就算错排 / Any arrangement counts as a derangement",
                            "D. 与组合无关 / It is unrelated to combinations",
                        ],
                        "answer": "B",
                    }
                ],
            },
        },
        {
            "title": "路灯题 / Lamp Problems",
            "mixed": {
                "blanks": [
                    ("基础路灯题中，“关掉的不相邻”通常先把亮灯排好，再从____________中选位置。", "空位"),
                ],
                "choices": [
                    {
                        "question": "复杂路灯题常怎样处理 / How are more complex lamp problems often handled?",
                        "options": [
                            "A. 一律错排 / Always use derangements",
                            "B. 设变量并转化为组合问题 / Set variables and convert to a combination problem",
                            "C. 一律枚举 / Always enumerate",
                            "D. 只背结论 / Memorize conclusions only",
                        ],
                        "answer": "B",
                    }
                ],
            },
        },
    ],
    "第7天 / Day 7": [
        {
            "title": "路径题 / Path Problems",
            "oral": {
                "prompts": [
                    "为什么“不经过某点”正面做往往更麻烦？",
                    "正难则反的结构为什么更稳？",
                    "路径题里什么时候还能想到插空法？",
                ],
                "keypoints": [
                    "因为直接枚举合法路径通常结构复杂。",
                    "总数和坏情况都更容易被标准化计算。",
                    "当题目限制某类动作不能连续出现时。",
                ],
            },
        },
        {
            "title": "楼梯与数字组合 / Stair and Number Selection Problems",
            "oral": {
                "prompts": [
                    "楼梯题什么时候该用递推，什么时候该用组合？",
                    "为什么有些数字组合题没必要硬套排列组合？",
                    "课堂里“看题目本质”在这两类题上怎么体现？",
                ],
                "keypoints": [
                    "问总走法数时偏递推，固定 1 和 2 的个数时偏组合。",
                    "因为直接枚举更快、更清楚，没必要复杂化。",
                    "先看题目到底在问过程总数还是固定构成下的安排数。",
                ],
            },
        },
    ],
    "第14天 / Day 14": [
        {
            "title": "方法选择 / Method Selection",
            "oral": {
                "prompts": [
                    "为什么老师反复强调“先读题再决定方法”？",
                    "什么情况下你会优先考虑分类？",
                    "什么情况下你会优先考虑插空或正难则反？",
                ],
                "keypoints": [
                    "因为方法来自题目限制，而不是来自习惯。",
                    "当题目存在多类互斥情形且需要覆盖全部情况时。",
                    "出现不相邻、至少间隔、不能经过、不能连续等条件时。",
                ],
            },
        },
        {
            "title": "易错点校准 / Pitfall Calibration",
            "oral": {
                "prompts": [
                    "为什么分类标准选错会让整题变得混乱？",
                    "为什么部分错排容易被误判成全错排？",
                    "这节课最值得长期警惕的错误有哪些？",
                ],
                "keypoints": [
                    "因为标准不好会导致情况过多、重复或遗漏。",
                    "因为“位置不同”不等于“所有位置都不同”。",
                    "混淆分类与分步、乱选分类标准、不读题直接套公式。",
                ],
            },
        },
    ],
    "第30天 / Day 30": [
        {
            "title": "题型与方法对照 / Problem Type to Method Map",
            "mixed": {
                "blanks": [
                    ("“多面手问题”优先检查____________；“不经过某点”优先检查____________。", "分类标准；正难则反"),
                ],
                "choices": [
                    {
                        "question": "哪一项最能体现“方法迁移” / Which best shows method transfer?",
                        "options": [
                            "A. 只记住原题答案 / Only remember the original answer",
                            "B. 看到新题还能认出它和旧题同类 / Recognize a new problem as the same type as an old one",
                            "C. 只会照抄板书 / Only copy the board work",
                            "D. 只记住题号 / Only remember question numbers",
                        ],
                        "answer": "B",
                    }
                ],
            },
        },
        {
            "title": "长期记忆校验 / Long-Term Memory Check",
            "mixed": {
                "blanks": [
                    ("长期复习时，最该记住的不是零散答案，而是题型与____________之间的对应关系。", "方法"),
                ],
                "choices": [
                    {
                        "question": "哪一项最符合本节课的长期目标 / Which best matches the long-term goal of the lesson?",
                        "options": [
                            "A. 只背结论 / Memorize conclusions only",
                            "B. 只记课堂原话 / Remember quotes only",
                            "C. 看到题目能先识别结构，再稳定下手 / Recognize the structure first, then solve steadily",
                            "D. 只会一道代表题 / Only master one representative example",
                        ],
                        "answer": "C",
                    }
                ],
            },
        },
    ],
}


FINAL_REMINDER_LINES = [
    "先几何、后代数；先翻译条件、后计算。 / Geometry first, algebra if needed.",
    "看到数量积，先想投影、几何恒等式和数形结合。 / Link dot product to projection and geometry.",
    "看到圆，判断标准式和三角换元哪个更顺。 / Choose between standard circle form and trig substitution.",
    "看到系数和与线性组合，优先回想等和线。 / Use equal-sum lines for coefficient sums.",
    "每个复习日都要扫完整节课。 / Review the full lesson every time.",
]