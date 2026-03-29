LESSON = {
    "title": "向量解题方法讲解课后复习计划",
    "subtitle": "Spaced Review Plan for Vector Methods, Dot Product, Projection, and Geometric Transfer",
    "audience": "老师发给学生使用 / For Teacher Distribution",
    "duration": "每次 10-20 分钟 / 10-20 minutes each time",
    "core_points": [
        "向量题常见有几何法和代数法两条主线。",
        "遇到夹角和数量积，要先整理向量位置，再判断能否转成投影、几何恒等式或图形关系。",
        "标准化做题流程的起点是先翻译条件，再决定方法。",
        "代数法使用前必须先检查定义域与参数范围。",
        "圆上点常可用三角换元参数化。",
        "等和线适合处理系数和、线性组合和比例关系。",
        "第 5 题、第 7 题、第 9 题分别对应角平分线、圆与投影迁移、几何优先看范围等代表方法。",
        "第 9 题里，分类讨论、符号变化、不能共线和菱形结构都很关键。",
    ],
    "full_review_topics": [
        "向量坐标表示、模长计算与最值判断 / Coordinate form, norm, and extremum judgment",
        "夹角、数量积与投影 / Angle, dot product, and projection",
        "标准化做题流程：先翻译条件再选方法 / Standard workflow: translate conditions first",
        "代数法中的定义域与参数范围检查 / Domain and parameter checks in algebraic methods",
        "圆与三角换元 / Circles and trigonometric substitution",
        "等和线、比例与系数和 / Equal-sum lines, ratios, and coefficient sums",
        "第 5 题、第 7 题、第 9 题的关键迁移思路 / Transfer ideas from Questions 5, 7, and 9",
        "分类讨论、图形约束与范围判断 / Case analysis, geometry constraints, and range judgment",
    ],
    "quotes": [
        "做向量题时，两种方法都要会，千万不能只会一个方法。",
        "使用代数方法，一定要先考虑定义域，否则可能出现错误情况。",
        "不到万不得已，都不要去用这些高级方法，避免大炮打蚊子。",
        "做题要标准化，第一步先翻译条件。",
        "看到数量积，先想投影、夹角和几何图像。",
    ],
}


DAYS = [
    {
        "offset": 1,
        "day": "第1天",
        "focus": "第一次整课回放，先把整节课的模块和方法主线搭起来。 / First full replay focused on rebuilding the full method map.",
        "goal": "能完整列出本节课的主要模块，而不是只记住个别题目。 / Name the main modules of the lesson instead of isolated examples.",
        "tasks": [
            "先默写整节课的核心模块，再核对课堂笔记。Write down the core modules before checking notes.",
            "完成填空题，按“方法-概念-题目-提醒”的顺序回顾整节课。Complete the blanks in the order of method, concept, example, and warning.",
            "完成选择题，检查基础记忆和方法优先级。Finish the choices to test recall and method priority.",
            "读一次上课金句回顾，再口头复述课堂主线。Read the class quotes once, then retell the lesson flow.",
        ],
        "blanks": [
            ("向量题最重要的两种方法是____________法和____________法。", "几何；代数"),
            ("处理向量夹角时，要先摆成____________或____________。", "头碰头；尾碰尾"),
            ("看到数量积时，要想到几何恒等式、____________、____________。", "投影；夹角"),
            ("标准化做题的第一步是先____________条件。", "翻译"),
            ("代数法开始前必须先检查____________。", "定义域"),
            ("圆上点也可以用含____________和____________的三角形式表示。", "sinθ；cosθ"),
            ("看到数量积题时，如果能画出投影，常可转化为看某个向量在____________上的____________。", "另一向量；投影"),
        ],
        "choices": [
            {
                "question": "本节课最符合的总策略是 / Which best summarizes the lesson strategy?",
                "options": [
                    "A. 先硬算，再看图 / Compute first and think later",
                    "B. 优先几何法，几何不顺再转代数 / Geometry first, algebra if needed",
                    "C. 所有题都先设坐标 / Always start with coordinates",
                    "D. 看到圆就只用三角换元 / Always use trig substitution for circles",
                ],
                "answer": "B",
            },
            {
                "question": "关于向量夹角的判断，下列说法正确的是 / Which statement about vector angles is correct?",
                "options": [
                    "A. 只要在同一平面内就能直接判断 / Any same-plane drawing works directly",
                    "B. 默认只看锐角 / Always take the acute angle",
                    "C. 必须先摆成头碰头或尾碰尾 / Put them head-to-head or tail-to-tail first",
                    "D. 夹角与方向无关 / Direction does not matter",
                ],
                "answer": "C",
            },
        ],
        "quotes": [LESSON["quotes"][0], LESSON["quotes"][3]],
    },
    {
        "offset": 2,
        "day": "第2天",
        "focus": "第二次整课复习，重点把概念、陷阱和工具重新连起来。 / Second full review focused on reconnecting tools, concepts, and pitfalls.",
        "goal": "看到任一关键词，都能连回整节课的完整解题网络。 / Reconnect any keyword to the lesson's full solution network.",
        "tasks": [
            "快速过一遍全课覆盖清单。Run through the full-lesson checklist.",
            "完成填空题，覆盖模长、投影、定义域、圆、等和线和代表题。Complete the blanks across all major topics.",
            "完成选择题，区分“会做”和“能做对”。Use the choices to separate partial understanding from correct execution.",
            "口头说明为什么“先翻译条件”是这节课的起点。Explain why translating conditions comes first.",
        ],
        "blanks": [
            ("若若干向量共线，相关模长问题常对应____________值。", "最值"),
            ("往底向量上做垂线得到的量叫____________。", "投影"),
            ("处理 b-a 一类问题时，要先让相关向量____________。", "同起点化"),
            ("忽略参数范围，最容易在____________或最值上出错。", "取值范围"),
            ("圆上的点既可写标准式，也可通过____________完成参数化。", "三角换元"),
            ("等和线最常用来找____________和____________。", "系数和；比例关系"),
            ("第 9 题更推荐先用____________法。", "几何"),
        ],
        "choices": [
            {
                "question": "哪一步最容易让代数法做错 / Which step most often breaks an algebraic solution?",
                "options": [
                    "A. 先翻译条件 / Translate conditions first",
                    "B. 先确定定义域 / Check the domain first",
                    "C. 漏掉参数范围直接运算 / Ignore parameter ranges and compute directly",
                    "D. 先画投影 / Draw the projection first",
                ],
                "answer": "C",
            },
            {
                "question": "关于第 7 题和第 9 题，下列说法正确的是 / Which statement about Questions 7 and 9 is correct?",
                "options": [
                    "A. 第 7 题只能代数，第 9 题只能背结论 / Q7 is algebra only, Q9 is memorization only",
                    "B. 第 7 题可代数也可几何，第 9 题优先几何 / Q7 works both ways, Q9 prefers geometry first",
                    "C. 两题都不需要图形 / Neither needs geometry",
                    "D. 两题都只看函数式 / Both are purely formulaic",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][1]],
    },
    {
        "offset": 7,
        "day": "第7天",
        "focus": "一周后整课迁移，要求把工具和典型题绑在一起。 / One-week transfer review focused on binding tools to typical problems.",
        "goal": "能从整节课中抽出“题型对应工具”。 / Match problem types with the right tools.",
        "tasks": [
            "先过整课清单，再做题。Review the full checklist before answering.",
            "完成填空题，把第 5 题、第 7 题、等和线、三角换元连起来。Use the blanks to connect Questions 5 and 7, equal-sum lines, and trig substitution.",
            "完成选择题，检查错误迁移。Use the choices to test mistaken transfer.",
            "任选一题口述解法框架。Retell the framework of one sample problem.",
        ],
        "blanks": [
            ("第 5 题中，BA 与 BC 的方向向量相加得到____________方向。", "角平分线"),
            ("第 7 题中，P 点轨迹是以____________为圆心、半径为____________的圆。", "某定点；定长"),
            ("分析 BP·BC 时，本质是在看 BP 在____________上的____________。", "BC；投影"),
            ("圆上点常写成含____________和____________的形式。", "sinθ；cosθ"),
            ("等和线的典型动作是作____________线找比例。", "等和"),
            ("几何过程不清楚时，代数法常回到____________问题。", "坐标与范围"),
            ("第 7 题中，除了代数法，还可以借助____________与投影完成几何分析。", "三角换元"),
        ],
        "choices": [
            {
                "question": "第 5 题的关键结论是 / What is the key conclusion of Question 5?",
                "options": [
                    "A. 方向向量相加得到角平分线 / The sum of direction vectors gives the angle bisector",
                    "B. 一定得到中线 / It always gives a median",
                    "C. 一定得到高线 / It always gives an altitude",
                    "D. 只能坐标算 / It must be solved by coordinates only",
                ],
                "answer": "A",
            },
            {
                "question": "第 7 题最符合课堂分析的是 / Which best matches the class analysis of Question 7?",
                "options": [
                    "A. 只可能用坐标硬算 / Coordinates only",
                    "B. 三角换元和投影都可进入解题 / Both trig substitution and projection can enter the solution",
                    "C. 圆出现时不能用几何 / Once a circle appears, geometry cannot be used",
                    "D. 与等和线完全无关 / It is unrelated to equal-sum lines",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][4]],
    },
    {
        "offset": 14,
        "day": "第14天",
        "focus": "两周后整课校准，重点检查第 9 题、分类讨论与图形约束。 / Two-week calibration focused on Question 9, case analysis, and geometry constraints.",
        "goal": "能把函数条件、向量关系和图形限制一起考虑。 / Combine function conditions, vector relations, and geometry constraints.",
        "tasks": [
            "先回想整节课的高频陷阱，再做题。Recall the common traps first.",
            "完成填空题，覆盖符号分类、菱形结构、不能共线和范围判断。Finish blanks across signs, rhombus structure, non-collinearity, and range judgment.",
            "完成选择题，纠正常见误判。Use choices to correct common misjudgments.",
            "口头说明为什么第 9 题优先几何法。Explain why Question 9 is better with geometry first.",
        ],
        "blanks": [
            ("当 a·b = 0 时，f = ____________；当 a·b > 0 时，f = ____________；当 a·b < 0 时，f = ____________。", "0；1；-1"),
            ("第 9 题更推荐用____________法，通过____________向量看范围。", "几何；平移"),
            ("分析 a、b、c 三个单位向量时，不能忽略“____________”。", "不能共线"),
            ("若 a-b 垂直 c 且 a+b 与 c 共线，图形上常出现____________结构。", "菱形"),
            ("第 9 题里，a·b 的____________变化会直接影响函数值。", "符号"),
            ("两周后复盘这节课时，最该警惕的错误之一是：看见式子就直接____________。", "硬算"),
        ],
        "choices": [
            {
                "question": "若 a·b < 0，则函数值为 / If a·b < 0, then f equals:",
                "options": [
                    "A. 1",
                    "B. 0",
                    "C. -1",
                    "D. 无法确定 / Cannot tell",
                ],
                "answer": "C",
            },
            {
                "question": "第 9 题优先几何法的主要原因是 / Why does Question 9 favor geometry first?",
                "options": [
                    "A. 可通过平移直接看整体范围 / Translation reveals the range directly",
                    "B. 代数法完全不能做 / Algebra is impossible",
                    "C. 题目没有数量积 / There is no dot product",
                    "D. 三角换元一定更慢 / Trig substitution is always slower",
                ],
                "answer": "A",
            },
        ],
        "quotes": [LESSON["quotes"][1], LESSON["quotes"][2]],
    },
    {
        "offset": 30,
        "day": "第30天",
        "focus": "一个月后的整课总复盘，要求脱离课堂语境也能独立调用方法。 / One-month final full-lesson review for independent recall.",
        "goal": "看到同类向量题时，能主动调用整节课的方法清单。 / Actively call the full method list when seeing similar vector problems.",
        "tasks": [
            "先写出整节课知识清单。Write the full lesson checklist from memory.",
            "完成总复盘填空题，确保整节课都能被提取。Complete the final blanks to recall the whole lesson.",
            "完成选择题，验证基础记忆、易混概念和常见错误都已内化。Confirm that recall, distinction, and error correction are internalized.",
            "任选一道课堂例题，口述“条件翻译-方法选择-关键结论”。Retell one class example using condition translation, method choice, and key conclusion.",
        ],
        "blanks": [
            ("向量题最重要的两种解题方法是____________法与____________法。", "几何；代数"),
            ("看到数量积，至少问自己：能否用几何恒等式、能否用____________、能否画____________。", "投影；图形"),
            ("若题目出现圆、最值、数量积，常见工具组合是____________与____________。", "几何；三角换元"),
            ("标准化做题时，先____________条件，再决定如何下手。", "翻译"),
            ("求 λ+μ 一类问题时，优先回想____________。", "等和线"),
            ("第 5 题关键图形结论是____________；第 9 题更优先的方法是____________。", "角平分线；几何法"),
            ("老师强调，使用代数方法时一定先考虑____________，否则容易出错。", "定义域"),
        ],
        "choices": [
            {
                "question": "一个月后的理想状态是 / What is the ideal state after one month?",
                "options": [
                    "A. 只记住课堂原话 / Remember only the teacher's quotes",
                    "B. 看到同类向量题能先判断方法，再稳定下手 / Identify the method first, then solve steadily",
                    "C. 只会做课堂原题 / Only solve the original class examples",
                    "D. 所有题都从最复杂的方法开始 / Start every problem with the most complex method",
                ],
                "answer": "B",
            },
            {
                "question": "本节课长期复习最该留下的是什么 / What should remain most clearly after long-term review?",
                "options": [
                    "A. 零散答案 / Isolated answers",
                    "B. 题号顺序 / Question order",
                    "C. 条件翻译、方法选择和图形判断之间的对应关系 / The mapping among condition translation, method choice, and geometric judgment",
                    "D. 每一步运算细节 / Every computational detail",
                ],
                "answer": "C",
            },
        ],
        "quotes": [LESSON["quotes"][0], LESSON["quotes"][1]],
    },
]


KNOWLEDGE_SECTIONS = {
    "第1天": [
        {
            "title": "向量夹角与数量积 / Vector Angles and Dot Product",
            "mixed": {
                "blanks": [
                    ("判断向量夹角前，必须先把两个向量放到____________或____________的位置。", "头碰头；尾碰尾"),
                ],
                "choices": [
                    {
                        "question": "看到数量积时，最符合课堂要求的第一反应是 / Best first reaction to a dot product?",
                        "options": [
                            "A. 直接代数展开 / Expand immediately",
                            "B. 先想投影、夹角和几何图像 / Think of projection, angle, and geometry first",
                            "C. 先背答案 / Memorize the answer",
                            "D. 只看坐标 / Only inspect coordinates",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么判断夹角前要先统一向量位置？",
                    "数量积为什么天然适合联系投影和夹角？",
                    "什么时候几何图像比代数展开更快？",
                ],
                "keypoints": [
                    "因为夹角是方向关系，必须先摆成标准位置。",
                    "因为数量积既有代数表达，也有几何意义。",
                    "当题目能直观看出投影、长度或夹角关系时。",
                ],
            },
        },
        {
            "title": "等和线 / Equal-Sum Line",
            "mixed": {
                "blanks": [
                    ("等和线方法常用来寻找____________和____________。", "系数和；比例关系"),
                ],
                "choices": [
                    {
                        "question": "当题目目标是求 λ+μ 时，优先联想哪种工具 / Which tool best matches λ+μ problems?",
                        "options": [
                            "A. 等和线 / Equal-sum line",
                            "B. 外心性质 / Circumcenter properties",
                            "C. 导数 / Derivative",
                            "D. 排列组合 / Combinatorics",
                        ],
                        "answer": "A",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么等和线特别适合处理线性组合问题？",
                    "等和线在图形上通常怎样作出来？",
                    "这类题为什么不建议一上来就硬算？",
                ],
                "keypoints": [
                    "因为它能直接把系数和转成图形位置关系。",
                    "通常通过作一族平行线观察和不变。",
                    "因为图形法往往先给出结构和范围。",
                ],
            },
        },
    ],
    "第2天": [
        {
            "title": "标准化做题流程 / Standard Solving Workflow",
            "mixed": {
                "blanks": [
                    ("标准化做题的第一步是先____________条件。", "翻译"),
                ],
                "choices": [
                    {
                        "question": "下列哪一步最体现“先翻译条件” / Which action best represents translating conditions first?",
                        "options": [
                            "A. 先代数展开 / Expand first",
                            "B. 先画草图并整理向量关系 / Sketch first and organize vector relations",
                            "C. 先猜答案 / Guess first",
                            "D. 先列三角函数表 / Write trig tables first",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么这节课把“先翻译条件”放在第一步？",
                    "条件翻译不到位，后面最容易出什么错？",
                    "草图和向量关系整理分别起什么作用？",
                ],
                "keypoints": [
                    "因为方法选择依赖对条件结构的理解。",
                    "会导致方法选错或漏掉图形约束。",
                    "草图负责看结构，整理关系负责可计算。",
                ],
            },
        },
        {
            "title": "定义域检查 / Domain Check",
            "mixed": {
                "blanks": [
                    ("代数法如果不先检查____________，范围和最值就容易出错。", "定义域"),
                ],
                "choices": [
                    {
                        "question": "为什么课堂反复强调定义域 / Why was the domain emphasized repeatedly?",
                        "options": [
                            "A. 因为定义域决定字体大小 / It changes font size",
                            "B. 因为忽略后可能得到错误范围 / Ignoring it may produce a wrong range",
                            "C. 因为它只在函数题里出现 / It only appears in function problems",
                            "D. 因为它能代替画图 / It replaces drawing",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么定义域问题在向量代数法里也很重要？",
                    "忽略参数范围最容易影响哪些结论？",
                    "什么情况下应该先几何、后代数？",
                ],
                "keypoints": [
                    "因为参数化后同样存在可取范围限制。",
                    "最值、范围和分类判断。",
                    "当图形关系清楚、代数表达会引入额外约束时。",
                ],
            },
        },
    ],
    "第7天": [
        {
            "title": "三角换元 / Trigonometric Substitution",
            "oral": {
                "prompts": [
                    "三角换元通常在什么图形背景下出现？",
                    "为什么圆上的点适合写成含 sinθ、cosθ 的形式？",
                    "请结合第 7 题口头说明三角换元是怎么进入解题的。",
                ],
                "keypoints": [
                    "常出现在圆、定长或平方和固定的背景下。",
                    "因为圆上点满足长度固定，适合用三角函数参数化。",
                    "先把点写成三角形式，再结合投影或数量积分析。",
                ],
            },
        },
        {
            "title": "第7题迁移 / Question 7 Transfer",
            "oral": {
                "prompts": [
                    "第 7 题为什么能同时用代数法和几何法？",
                    "如果你优先走几何法，你最先看的量是什么？",
                    "请口头说出第 7 题的一个迁移结论：下次见到类似结构该想到什么。",
                ],
                "keypoints": [
                    "因为它既能参数化，也能从圆与投影关系切入。",
                    "最先看轨迹、定长和投影关系。",
                    "见到圆和数量积并存时，要想到几何图像与三角换元都可能可用。",
                ],
            },
        },
    ],
    "第14天": [
        {
            "title": "第9题分类讨论 / Question 9 Case Analysis",
            "oral": {
                "prompts": [
                    "第 9 题为什么更适合优先几何法？",
                    "平移向量在这道题里起什么作用？",
                    "请口头说明 a·b 的符号变化如何影响函数值。",
                ],
                "keypoints": [
                    "因为几何图像更容易直接看到整体范围。",
                    "平移帮助把分散关系放到同一图形里统一观察。",
                    "符号变化对应不同情形，因此函数值需要分类讨论。",
                ],
            },
        },
        {
            "title": "菱形与共线限制 / Rhombus Structure and Non-Collinearity",
            "oral": {
                "prompts": [
                    "为什么“不能共线”会影响第 9 题结论？",
                    "a-b 与 a+b 的方向关系会带来什么图形结构？",
                    "请口头说明菱形结构在判断范围时有什么帮助。",
                ],
                "keypoints": [
                    "因为共线会导致图形退化，范围判断随之改变。",
                    "会诱导出对角线垂直或共线的菱形结构。",
                    "菱形结构能把长度、角和范围统一起来观察。",
                ],
            },
        },
    ],
    "第30天": [
        {
            "title": "整课工具总复盘 / Full Toolset Synthesis",
            "mixed": {
                "blanks": [
                    ("看到数量积先想____________，看到 λ+μ 先想____________，看到圆上点先想三角换元。", "投影；等和线"),
                ],
                "choices": [
                    {
                        "question": "哪一项最能体现“方法迁移” / Which best shows method transfer?",
                        "options": [
                            "A. 只会做课堂原题 / Only solve the original examples",
                            "B. 看到新题还能认出它该用哪类工具 / Recognize which tool family a new problem needs",
                            "C. 只记住题号 / Only remember the question number",
                            "D. 只背原话 / Only memorize the quotes",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "一个月后你最该保留下来的方法清单有哪些？",
                    "这节课里几何法和代数法如何分工？",
                    "看到同类题时你的判断顺序应该是什么？",
                ],
                "keypoints": [
                    "投影、数量积、等和线、三角换元、定义域检查。",
                    "几何法负责先看结构，代数法负责补充计算和验证。",
                    "先翻译条件，再认图形结构，再决定方法。",
                ],
            },
        },
        {
            "title": "长期记忆校验 / Long-Term Memory Check",
            "mixed": {
                "blanks": [
                    ("长期复习时，最该记住的不是零散答案，而是____________、____________和图形判断之间的联系。", "条件翻译；方法选择"),
                ],
                "choices": [
                    {
                        "question": "哪一项最符合本节课的长期目标 / Which best matches the long-term goal of the lesson?",
                        "options": [
                            "A. 只背定义 / Memorize definitions only",
                            "B. 只记课堂原话 / Remember quotes only",
                            "C. 看到同类向量题能先判断结构，再稳定选方法 / Identify structure first, then choose the method steadily",
                            "D. 只会一道代表题 / Only master one representative example",
                        ],
                        "answer": "C",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么这节课最该留下的是方法框架，而不是零散结论？",
                    "如果只剩 1 分钟复盘，你会先回想哪几个关键词？",
                    "这节课最容易长期遗忘的细节是什么？",
                ],
                "keypoints": [
                    "因为方法框架能迁移到新题。",
                    "投影、定义域、等和线、三角换元、平移看范围。",
                    "夹角摆放、定义域限制和分类讨论的边界条件。",
                ],
            },
        },
    ],
}


FINAL_REMINDER_LINES = [
    "先翻译条件，再决定走几何法还是代数法。 / Translate conditions before choosing geometry or algebra.",
    "看到数量积，先想投影、夹角和几何恒等式。 / A dot product should trigger projection, angles, and geometry.",
    "看到圆上点和定长关系，优先回忆三角换元。 / Circle points and fixed lengths suggest trig substitution.",
    "看到系数和与线性组合，优先回想等和线。 / Coefficient sums and linear combinations suggest equal-sum lines.",
    "每个复习日都要扫完整节课，而不是只记某一道题。 / Review the full lesson every time.",
]