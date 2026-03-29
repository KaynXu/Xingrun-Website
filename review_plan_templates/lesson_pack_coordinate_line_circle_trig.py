LESSON = {
    "title": "平面直角坐标系、直线方程、圆的方程与三角函数课后复习计划",
    "subtitle": "Spaced Review Plan for Coordinate Plane, Line Equations, Circle Equations, and Trigonometric Functions",
    "audience": "老师发给学生使用 / For Teacher Distribution",
    "duration": "每次 10-20 分钟 / 10-20 minutes each time",
    "core_points": [
        "从一维数轴扩展到二维平面直角坐标系，理解 x 轴、y 轴与四个象限。",
        "掌握两点确定一条直线，并用待定系数法求直线方程 y = kx + b。",
        "牢记平面直角坐标系中两点间距离公式，并能用于圆方程推导。",
        "理解圆的标准方程 (x - a)^2 + (y - b)^2 = r^2 的来源和意义。",
        "会根据圆心和半径直接写圆方程，也会用三个点确定一个圆。",
        "掌握点与圆的位置关系判断：在圆上、圆内、圆外。",
        "复习正弦、余弦、正切的基本定义，以及 sin^2θ + cos^2θ = 1、tanθ = sinθ/cosθ。",
        "理解单位圆上点坐标与三角函数值的对应关系。",
        "熟悉和角、差角公式，并能把它们作为后续计算工具。",
    ],
    "full_review_topics": [
        "平面直角坐标系的构建：从数轴到二维坐标系 / From number line to the Cartesian plane",
        "x 轴、y 轴、原点与四个象限的坐标特征 / Axes, origin, and quadrant sign patterns",
        "两点确定一条直线与一次函数表达式 / Two points determine a line and the form y = kx + b",
        "待定系数法求直线方程 / Solving line equations by undetermined coefficients",
        "平面两点距离公式及其推导 / Deriving the distance formula in the plane",
        "圆心、半径与圆的标准方程 / Center, radius, and the standard circle equation",
        "已知圆心半径、已知三点求圆方程 / Writing a circle equation from center-radius or three points",
        "点与圆的位置关系判断 / Checking whether a point is on, inside, or outside a circle",
        "正弦、余弦、正切的定义与基本恒等式 / Definitions of sin, cos, tan and core identities",
        "单位圆、角的坐标表示与和差角公式 / Unit circle coordinates and sum-difference formulas",
    ],
    "quotes": [
        "点动成线，我们想研究二维，肯定是线的事情了。",
        "方程是拿来化简的，拿来表示的，用来表示圆的方程。",
        "sin 个式的平方加 cos 个式的平方等于 1。",
        "确定一条直线只需要两个点。",
        "三个点可以确定一个圆。",
    ],
}


DAYS = [
    {
        "offset": 1,
        "day": "第1天 / Day 1",
        "focus": "第一次整课回放，重点把整节课的知识地图重新搭起来。 / First whole-lesson replay focused on rebuilding the full knowledge map.",
        "goal": "能口头说出这节课从坐标系到直线、圆、三角函数的主线。 / Retell the main line from coordinates to lines, circles, and trigonometry.",
        "tasks": [
            "先默写整节课的四大模块，再核对课堂笔记。Write down the four major modules before checking notes.",
            "完成填空题，先回忆概念与公式，再回到例题。Complete the blanks by recalling concepts and formulas first.",
            "完成选择题，检查基础概念是否混淆。Finish the multiple-choice items to test basic distinctions.",
            "读一次上课金句回顾，再口头复述本节课主线。Read the class quotes once, then retell the lesson flow.",
        ],
        "blanks": [
            ("平面直角坐标系是在一维____________的基础上，再增加一条与它垂直的数轴得到的。", "数轴"),
            ("平面直角坐标系由____________轴和____________轴组成。", "x；y"),
            ("确定一条直线只需要____________个点。", "两"),
            ("直线方程常写成 y = kx + b，其中 k 和 b 是待定____________。", "系数"),
            ("通过把两个点的坐标代入 y = kx + b 求 k、b 的方法叫____________法。", "待定系数"),
            ("圆的标准方程是 (x - a)^2 + (y - b)^2 = ____________。", "r^2"),
            ("在直角三角形中，正弦是____________比斜边。", "对边"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合本节课关于直线方程的起手方式 / Which best matches the lesson's starting point for a line equation?",
                "options": [
                    "A. 先猜图像再补公式 / Guess the graph first and patch the formula later",
                    "B. 先设 y = kx + b，再代入已知点求 k 和 b / Set y = kx + b first, then substitute known points",
                    "C. 先把圆方程写出来 / Write a circle equation first",
                    "D. 直接背答案 / Memorize the final answer directly",
                ],
                "answer": "B",
            },
            {
                "question": "下列哪一项最符合本节课对坐标系的理解 / Which best matches the lesson's view of the coordinate plane?",
                "options": [
                    "A. 只有一条数轴 / It has only one axis",
                    "B. 是从一维数轴扩展出来的二维坐标系统 / It extends the number line into a 2D system",
                    "C. 只用来画圆 / It is only for drawing circles",
                    "D. 与三角函数无关 / It is unrelated to trigonometry",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][0], LESSON["quotes"][3]],
    },
    {
        "offset": 2,
        "day": "第2天 / Day 2",
        "focus": "第二次整课复习，重点区分公式的来源和使用场景。 / Second full review focused on where formulas come from and when to use them.",
        "goal": "能判断什么时候用待定系数法、什么时候用距离公式、什么时候直接写标准方程。 / Decide when to use undetermined coefficients, the distance formula, or a standard form directly.",
        "tasks": [
            "快速过一遍全课覆盖清单。Run through the full-lesson coverage list once.",
            "完成填空题，重点回忆距离公式、圆方程和点圆关系。Complete the blanks with focus on distance, circle equations, and point-circle relations.",
            "完成选择题，纠正“会写公式但不知道为什么”的问题。Use the choices to correct formula-only memorization.",
            "口头说明圆方程为什么本质上来自两点距离公式。Explain orally why the circle equation comes from the distance formula.",
        ],
        "blanks": [
            ("平面上两点 (x1, y1)、(x2, y2) 之间的距离公式里，要先算横向差和____________差。", "纵向"),
            ("圆上任一点到圆心的距离恒等于____________。", "半径"),
            ("已知圆心 (a, b) 和半径 r，可以直接写出圆的____________方程。", "标准"),
            ("若已知圆上的三个点，可通过____________法求出圆心和半径。", "待定系数"),
            ("把点坐标代入圆方程后，若左边大于右边，则点在圆____________。", "外"),
            ("把点坐标代入圆方程后，若左边小于右边，则点在圆____________。", "内"),
            ("老师强调圆的方程首先是拿来____________和化简的。", "表示"),
        ],
        "choices": [
            {
                "question": "哪一项最符合圆的标准方程的来源 / Which best describes the source of the standard circle equation?",
                "options": [
                    "A. 直接规定出来的 / It is simply declared",
                    "B. 由圆上点到圆心距离等于半径推导得到 / It comes from equating point-center distance to the radius",
                    "C. 由一次函数变形得到 / It is transformed from a linear function",
                    "D. 只靠作图猜出来 / It is guessed from a sketch only",
                ],
                "answer": "B",
            },
            {
                "question": "已知圆心和半径时，最直接的做法是 / When the center and radius are known, the most direct move is:",
                "options": [
                    "A. 重新推导距离公式 / Re-derive the distance formula",
                    "B. 直接写标准方程 / Write the standard form directly",
                    "C. 先求斜率 / Find a slope first",
                    "D. 先用和角公式 / Use a sum-angle formula first",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][1], LESSON["quotes"][4]],
    },
    {
        "offset": 7,
        "day": "第7天 / Day 7",
        "focus": "一周后迁移，重点把几何图形和代数表达之间的联系说清楚。 / One-week transfer review focused on linking geometric objects to algebraic expressions.",
        "goal": "不用落笔也能说明直线、圆、三角函数为什么都能放进同一坐标系里理解。 / Explain orally why lines, circles, and trigonometric ideas can all be understood in one coordinate system.",
        "tasks": [
            "先口头复述整节课的方法地图。Orally restate the lesson method map first.",
            "回答老师提问口述卡片，每题补一句“为什么这样建模”。Answer oral prompts and add why that model is chosen.",
            "再复盘直线方程、圆方程、单位圆三块内容的联系。Review the links among line equations, circle equations, and the unit circle.",
            "最后复述至少 3 句课堂原话。Retell at least 3 classroom quotes at the end.",
        ],
        "blanks": [
            ("研究二维图形时，先要把点放进____________系里。", "平面直角坐标"),
            ("单位圆是以____________为圆心、以 1 为半径的圆。", "原点"),
            ("单位圆上一点的坐标可以写成 (____________, ____________)。", "cosθ；sinθ"),
            ("三角函数从直角三角形推广到坐标系后，角度通常与 x 轴____________半轴的夹角有关。", "正"),
            ("sin^2θ + cos^2θ = 1 说明单位圆上对应点的横纵坐标满足____________关系。", "平方和为 1"),
            ("tanθ = sinθ/cosθ 说明正切可以看作____________与余弦的比。", "正弦"),
            ("本节课里，圆和三角函数之间的桥梁是____________圆。", "单位"),
        ],
        "choices": [
            {
                "question": "哪一项最符合单位圆中的坐标含义 / Which best matches coordinate meaning on the unit circle?",
                "options": [
                    "A. 点坐标写成 (sinθ, cosθ) 且顺序固定不能变 / Coordinates are always (sinθ, cosθ)",
                    "B. 点坐标写成 (cosθ, sinθ) / Coordinates are (cosθ, sinθ)",
                    "C. 点坐标只和半径有关 / Coordinates depend only on radius",
                    "D. 单位圆与三角函数无关 / The unit circle is unrelated to trigonometry",
                ],
                "answer": "B",
            },
            {
                "question": "本节课把三角函数放进坐标系里复习，主要是为了 / Why does the lesson revisit trigonometric functions inside the coordinate plane?",
                "options": [
                    "A. 只为了多背一个定义 / Only to memorize one more definition",
                    "B. 让图形关系和代数关系能互相对应 / Let geometric and algebraic relationships correspond to each other",
                    "C. 只为了画图好看 / Only to make sketches look better",
                    "D. 避免使用公式 / Avoid formulas entirely",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][2]],
    },
    {
        "offset": 14,
        "day": "第14天 / Day 14",
        "focus": "两周后校准，重点检查推导逻辑和易错符号。 / Two-week calibration focused on derivation logic and sign-sensitive details.",
        "goal": "看到变式题时，仍能抓住“定义-推导-表达式”这条主线。 / Keep the chain of definition, derivation, and expression clear even in variants.",
        "tasks": [
            "先口头总结这节课最容易错的 5 个点。First summarize the 5 easiest mistakes orally.",
            "回答老师提问卡片，重点说明为什么不能只背结果。Answer oral prompts and explain why memorizing results alone is not enough.",
            "复盘距离公式、圆方程和和差角公式的推导入口。Review the entry points for distance, circle equations, and sum-difference formulas.",
            "最后再说一遍“方程是拿来表示和化简的”的提醒。Close by restating the role of equations.",
        ],
        "blanks": [
            ("两点距离公式里，横向和纵向差都要先做____________，再平方相加。", "相减"),
            ("判断点与圆的位置关系时，本质上是在比较代入后左右两边的____________大小。", "数值"),
            ("cos(α + β) = cosαcosβ - sinαsinβ，其中最容易记错的是中间的____________号。", "符"),
            ("cos(α - β) = cosαcosβ + sinαsinβ，和角与差角在 cos 公式中的主要差别是____________。", "符号"),
            ("sin(α + β) 与 sin(α - β) 的区别也主要体现在中间项的____________上。", "符号"),
            ("老师强调公式可以先背，但更重要的是知道公式从哪里____________出来。", "推"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合本节课对公式学习的要求 / Which best matches the lesson's requirement for learning formulas?",
                "options": [
                    "A. 只要会背，不用理解 / Memorization alone is enough",
                    "B. 既要会背，也要知道公式从哪一步推出来 / Memorize them and understand the derivation route",
                    "C. 只要会计算，不用建模 / Calculation alone matters",
                    "D. 所有题都只画图 / Solve everything by sketching only",
                ],
                "answer": "B",
            },
            {
                "question": "下列哪一项最可能是这节课的常见错误 / Which is the most likely common mistake in this lesson?",
                "options": [
                    "A. 把符号、坐标顺序或内外判断记混 / Mixing up signs, coordinate order, or inside-outside judgments",
                    "B. 不知道什么是圆 / Not knowing what a circle is",
                    "C. 不会写 x 和 y / Not knowing how to write x and y",
                    "D. 不会画坐标轴 / Not being able to draw axes",
                ],
                "answer": "A",
            },
        ],
        "quotes": [LESSON["quotes"][1], LESSON["quotes"][2]],
    },
    {
        "offset": 30,
        "day": "第30天 / Day 30",
        "focus": "一个月后的总复盘，要求脱离课堂语境也能稳定调用这些工具。 / One-month final review for stable independent recall of the full toolset.",
        "goal": "形成长期记忆：看到题目先识别模块，再判断该用坐标、方程还是三角函数工具。 / Reach long-term memory by recognizing the module first, then choosing the right tool.",
        "tasks": [
            "先默写整节课的题型-方法对照表。Write the topic-to-method map from memory.",
            "完成总复盘填空和选择，检查长期记忆是否稳定。Complete the final blanks and choices to test retention.",
            "任选一个专题，口头说出“概念-公式-用法-易错点”。Pick one topic and retell concept, formula, use, and pitfalls.",
            "最后读一遍上课金句回顾。Finish by reviewing the class quotes once more.",
        ],
        "blanks": [
            ("本节课最基础的几何表示工具是____________坐标系。", "平面直角"),
            ("已知两个点求直线方程，最典型的方法是设 y = kx + b，再用____________法求参数。", "待定系数"),
            ("圆的标准方程中，(a, b) 表示____________坐标，r 表示半径。", "圆心"),
            ("判断点在圆上、圆内还是圆外，核心是把点代入方程后做____________。", "比较"),
            ("单位圆上一点的坐标是 (cosθ, sinθ)，所以 x 对应____________，y 对应____________。", "cosθ；sinθ"),
            ("和角、差角公式长期最该记住的，不只是结果，还有中间____________的变化。", "符号"),
            ("这节课长期最该留下的，是图形、方程和____________之间的对应关系。", "三角函数"),
        ],
        "choices": [
            {
                "question": "一个月后的理想状态是 / What is the ideal state after one month?",
                "options": [
                    "A. 只记住老师原话 / Remember only the teacher's quotes",
                    "B. 看到题目能先判断属于直线、圆还是三角函数，再选方法 / Identify whether a problem is about lines, circles, or trig first, then choose a method",
                    "C. 只会做课堂原题 / Only solve the original class examples",
                    "D. 所有题都从最复杂的方法开始 / Start every problem with the most complex method",
                ],
                "answer": "B",
            },
            {
                "question": "本节课长期复习最该留下的是什么 / What should remain most clearly after long-term review?",
                "options": [
                    "A. 零散答案 / Isolated answers",
                    "B. 作业题号 / Homework question numbers",
                    "C. 坐标表示、方程表达和三角函数之间的联系 / The links among coordinates, equations, and trigonometric functions",
                    "D. 每一步板书顺序 / The exact order of every board step",
                ],
                "answer": "C",
            },
        ],
        "quotes": [LESSON["quotes"][0], LESSON["quotes"][1]],
    },
]


KNOWLEDGE_SECTIONS = {
    "第1天 / Day 1": [
        {
            "title": "坐标系与直线方程 / Coordinate Plane and Line Equations",
            "mixed": {
                "blanks": [
                    ("从一维到二维，关键是增加一条与原数轴____________的数轴。", "垂直"),
                ],
                "choices": [
                    {
                        "question": "哪一项最能体现待定系数法 / Which best reflects undetermined coefficients?",
                        "options": [
                            "A. 直接猜 k 和 b / Guess k and b directly",
                            "B. 设出含参数的式子，再代入已知条件求参数 / Set a form with parameters and solve them using conditions",
                            "C. 只画图不列式 / Draw only and never write equations",
                            "D. 先用三角函数 / Use trigonometry first",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么研究二维图形要先引入平面直角坐标系？",
                    "为什么两个点就能确定一条直线？",
                    "待定系数法在直线方程里具体体现在哪一步？",
                ],
                "keypoints": [
                    "因为要把图形位置转成可计算的坐标信息。",
                    "因为两点唯一确定一条直线。",
                    "先设 y = kx + b，再代入已知点求 k 和 b。",
                ],
            },
        },
        {
            "title": "四象限与坐标意义 / Quadrants and Coordinate Meaning",
            "mixed": {
                "blanks": [
                    ("四个象限的划分依据是横纵坐标的____________情况。", "正负"),
                ],
                "choices": [
                    {
                        "question": "复习四象限最重要的目的是什么 / What is the main purpose of reviewing quadrants?",
                        "options": [
                            "A. 只为了背名字 / Only to memorize the names",
                            "B. 为后续判断点的位置和符号特征打基础 / To support later position and sign judgments",
                            "C. 只为了画坐标轴 / Only to draw axes",
                            "D. 与圆方程无关 / It is unrelated to circle equations",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么四象限的正负特征要先弄清？",
                    "坐标表示为什么是后面所有方程表达的基础？",
                    "这部分内容和直线、圆、三角函数分别有什么连接？",
                ],
                "keypoints": [
                    "因为后续所有点的位置判断都依赖它。",
                    "因为坐标是图形代数化的起点。",
                    "直线靠点定式，圆靠点到圆心距离，三角函数靠单位圆坐标。",
                ],
            },
        },
    ],
    "第2天 / Day 2": [
        {
            "title": "距离公式与圆方程 / Distance Formula and Circle Equation",
            "mixed": {
                "blanks": [
                    ("圆方程的推导核心是：圆上任一点到圆心的距离恒等于____________。", "半径"),
                ],
                "choices": [
                    {
                        "question": "哪一项最符合“用距离公式推圆方程” / Which best matches deriving a circle equation from distance?",
                        "options": [
                            "A. 把半径写成斜率 / Turn radius into a slope",
                            "B. 把点到圆心的距离平方后等于 r^2 / Set the squared point-center distance equal to r^2",
                            "C. 直接设 y = kx + b / Set y = kx + b directly",
                            "D. 只记结论不管来源 / Memorize the result without source",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么圆方程本质上是一个距离关系？",
                    "为什么已知圆心和半径时能直接写标准方程？",
                    "两点距离公式里最容易错的是哪一步？",
                ],
                "keypoints": [
                    "因为圆上所有点到圆心距离相等。",
                    "因为标准方程已经把圆心和半径直接编码进表达式里。",
                    "横纵坐标相减的顺序和代数符号。",
                ],
            },
        },
        {
            "title": "点与圆的位置关系 / Point-Circle Position",
            "mixed": {
                "blanks": [
                    ("判断点与圆的位置关系时，关键是比较代入后左边与右边的____________。", "大小"),
                ],
                "choices": [
                    {
                        "question": "点在圆内时，代入圆方程后通常表现为 / If a point is inside the circle, substitution usually gives:",
                        "options": [
                            "A. 左边等于右边 / Left side equals right side",
                            "B. 左边大于右边 / Left side is greater than right side",
                            "C. 左边小于右边 / Left side is smaller than right side",
                            "D. 无法比较 / It cannot be compared",
                        ],
                        "answer": "C",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么把点代入圆方程就能判断位置关系？",
                    "圆上、圆内、圆外三种情况分别对应什么比较结果？",
                    "这类题为什么看似简单却容易错？",
                ],
                "keypoints": [
                    "因为代入后本质上是在比较点到圆心距离的平方和半径平方。",
                    "相等在圆上，小于在圆内，大于在圆外。",
                    "因为容易把不等号方向或内外关系记反。",
                ],
            },
        },
    ],
    "第7天 / Day 7": [
        {
            "title": "三角函数基本概念 / Trigonometric Basics",
            "oral": {
                "prompts": [
                    "正弦、余弦、正切分别是什么比值？",
                    "为什么 tanθ = sinθ/cosθ？",
                    "sin^2θ + cos^2θ = 1 最适合联系哪一个图形来理解？",
                ],
                "keypoints": [
                    "正弦是对边比斜边，余弦是邻边比斜边，正切是对边比邻边。",
                    "因为正切等于对边比邻边，而正弦和余弦正好可以相除得到这个比值。",
                    "最适合联系单位圆或直角三角形的勾股关系。",
                ],
            },
        },
        {
            "title": "单位圆与坐标对应 / Unit Circle and Coordinate Mapping",
            "oral": {
                "prompts": [
                    "为什么单位圆上一点可以写成 (cosθ, sinθ)？",
                    "为什么高中里的角要和 x 轴正半轴联系起来？",
                    "把三角函数放到坐标系里理解，有什么好处？",
                ],
                "keypoints": [
                    "因为单位圆半径为 1，横坐标对应余弦，纵坐标对应正弦。",
                    "因为角需要有统一的起始方向和旋转定义。",
                    "能把图形位置、函数值和恒等式统一到一个框架中。",
                ],
            },
        },
    ],
    "第14天 / Day 14": [
        {
            "title": "和差角公式 / Sum and Difference Formulas",
            "oral": {
                "prompts": [
                    "为什么老师说这些公式可以先背，但不能只背？",
                    "cos(α + β) 和 cos(α - β) 最容易混淆的地方是什么？",
                    "sin 的和差角公式和 cos 的和差角公式在记忆上有什么不同？",
                ],
                "keypoints": [
                    "因为考试时需要快速调用，但长期还是要理解结构和符号变化。",
                    "最容易混淆的是中间项的符号。",
                    "sin 的结构更顺，cos 的符号变化更需要刻意记忆。",
                ],
            },
        },
        {
            "title": "公式推导意识 / Derivation Awareness",
            "oral": {
                "prompts": [
                    "为什么这节课反复从定义和推导出发？",
                    "圆方程和三角函数恒等式在学习方式上有什么共同点？",
                    "如果只记结果不记来源，最容易在哪些题里失误？",
                ],
                "keypoints": [
                    "因为定义决定表达式，推导帮助避免机械记忆。",
                    "都需要把图形关系翻成代数关系。",
                    "在符号判断、公式变形和综合应用题里最容易失误。",
                ],
            },
        },
    ],
    "第30天 / Day 30": [
        {
            "title": "整课工具总复盘 / Full Toolset Synthesis",
            "mixed": {
                "blanks": [
                    ("已知两点先想____________；已知圆心半径先想____________；看到单位圆先想 (cosθ, sinθ)。", "待定系数法；标准方程"),
                ],
                "choices": [
                    {
                        "question": "哪一项最能体现“方法迁移” / Which best shows method transfer?",
                        "options": [
                            "A. 只会做老师讲过的原题 / Only solve the original examples",
                            "B. 看到新题也能认出它在用哪类表示工具 / Recognize which representation tool a new problem is using",
                            "C. 只记板书顺序 / Only remember the board order",
                            "D. 只记住作业 / Only remember the homework",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "一个月后你最该保留下来的四个关键词是什么？",
                    "直线、圆、三角函数这三块内容是如何串起来的？",
                    "看到新题时你的判断顺序应该是什么？",
                ],
                "keypoints": [
                    "坐标、方程、距离、单位圆。",
                    "都建立在坐标表示上，再转成方程或函数关系。",
                    "先认模块，再找已知条件，再选公式和表达方式。",
                ],
            },
        },
        {
            "title": "长期记忆校验 / Long-Term Memory Check",
            "mixed": {
                "blanks": [
                    ("长期复习时，最该记住的不是零散答案，而是图形、方程与____________之间的联系。", "三角函数"),
                ],
                "choices": [
                    {
                        "question": "哪一项最符合本节课的长期目标 / Which best matches the long-term goal of the lesson?",
                        "options": [
                            "A. 只背定义 / Memorize definitions only",
                            "B. 只记公式 / Memorize formulas only",
                            "C. 能把坐标、方程、圆和三角函数放到同一个理解框架里 / Place coordinates, equations, circles, and trig into one understanding framework",
                            "D. 只会做课堂例题 / Only solve class examples",
                        ],
                        "answer": "C",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么这节课最该留下的是框架而不是零散结论？",
                    "如果只剩 1 分钟复盘，你会先回想哪几个公式或图形？",
                    "本节课最容易长期遗忘的细节是什么？",
                ],
                "keypoints": [
                    "因为框架能迁移到新题，零散结论不能。",
                    "坐标系、两点直线、圆标准方程、单位圆、和差角公式。",
                    "符号、坐标顺序、内外判断和公式中间项。",
                ],
            },
        },
    ],
}


FINAL_REMINDER_LINES = [
    "先认这是坐标、直线、圆还是三角函数问题，再选工具。 / Identify the module before choosing the tool.",
    "看到两点先想直线方程和待定系数法。 / Two points suggest a line equation with undetermined coefficients.",
    "看到圆心和半径，优先回忆标准方程；看到圆上点，优先回忆距离关系。 / Center-radius suggests standard form; circle points suggest distance.",
    "看到单位圆，马上联想到 (cosθ, sinθ) 和 sin^2θ + cos^2θ = 1。 / The unit circle should trigger coordinates and the core identity.",
    "每个复习日都要扫完整节课，而不是只看某一块。 / Review the full lesson every time.",
]