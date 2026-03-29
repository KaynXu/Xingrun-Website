LESSON = {
    "title": "光学与波动综合题解析课后复习计划",
    "subtitle": "Spaced Review Plan for Refraction, Total Internal Reflection, Interference, and Mechanical Waves",
    "audience": "老师发给学生使用 / For Teacher Distribution",
    "duration": "每次 10-20 分钟 / 10-20 minutes each time",
    "core_points": [
        "折射率公式要和波速、波长变化一起理解，进入介质后频率不变、波长变短。",
        "全反射必须同时满足两个条件：从光密介质射向光疏介质，且入射角大于等于临界角。",
        "薄膜干涉要抓光程差与半波损失，劈尖干涉条纹间距与夹角成反比。",
        "牛顿环中心通常为暗斑，条纹呈内疏外密的同心圆分布。",
        "双缝干涉要熟悉明暗条纹条件和条纹间距公式，并能判断介质变化带来的影响。",
        "机械波部分要明确：质点只在平衡位置附近振动，不随波迁移。",
        "波形图和振动图要结合传播方向、位移、加速度和时间分段一起判断。",
        "综合题优先用极值分析、分段讨论和图像辅助法，不要只背公式。",
    ],
    "full_review_topics": [
        "折射率、波速、波长之间的关系 / Relation among refractive index, speed, and wavelength",
        "折射定律与全反射条件 / Refraction law and total internal reflection",
        "临界角、边界光线与极值分析 / Critical angle, boundary rays, and extremum analysis",
        "薄膜干涉中的光程差、半波损失与等厚干涉 / Optical path difference, half-wave loss, and equal-thickness interference",
        "劈尖干涉与条纹间距变化 / Wedge interference and fringe spacing",
        "牛顿环的结构、中心暗斑与条纹特点 / Newton's rings, central dark spot, and ring pattern",
        "双缝干涉的明暗条件与条纹间距公式 / Bright-dark conditions and fringe spacing in double-slit interference",
        "机械波传播中波速、频率、波长和质点振动 / Wave speed, frequency, wavelength, and particle motion",
        "波的叠加、加强减弱点与分段讨论 / Superposition, constructive-destructive points, and piecewise analysis",
        "波形图、振动图和传播方向判断 / Waveform, vibration graph, and propagation direction judgment",
    ],
    "quotes": [
        "不是背诵公式，而是掌握如何从物理情境中抽象出数学关系。",
        "先把物理过程分开：折射、反射、干涉，再逐层建模。",
        "薄膜干涉一定别漏掉半波损失。",
        "质点只是在各自平衡位置附近振动，不会跟着波往前跑。",
        "复杂题先画图，边界光线和临界情况往往就是突破口。",
    ],
}


DAYS = [
    {
        "offset": 1,
        "day": "第1天 / Day 1",
        "focus": "第一次整课回放，重点先把光学与机械波的主框架重新挂起来。 / First whole-lesson replay focused on rebuilding the full framework of optics and waves.",
        "goal": "能说出本节课的主要模块，并知道每个模块最先想到的物理量或判断入口。 / Name the main modules and the first physical quantity or entry point for each.",
        "tasks": [
            "先默写整节课的知识框架，再核对课堂笔记。Write down the lesson framework before checking notes.",
            "完成填空题，把折射、全反射、干涉、机械波四大块先重新连起来。Complete the blanks to reconnect refraction, total internal reflection, interference, and mechanical waves.",
            "完成选择题，检查基础概念是否真的区分清楚。Finish the choices to verify the core distinctions.",
            "读一次上课金句回顾，再口头复述整节课主线。Read the class quotes once, then retell the lesson flow.",
        ],
        "blanks": [
            ("折射率公式可写成 n = c/v，也可理解为真空波长与介质中____________之比。", "波长"),
            ("光进入折射率更大的介质后，频率通常____________，波长会变____________。", "不变；短"),
            ("全反射发生的第一个前提是光必须从____________介质射向____________介质。", "光密；光疏"),
            ("全反射发生的第二个前提是入射角要____________临界角。", "大于等于"),
            ("薄膜干涉分析条纹明暗时，除了光程差，还要特别考虑____________。", "半波损失"),
            ("机械波传播时，质点只在平衡位置附近____________，不会随波整体迁移。", "振动"),
            ("复杂光路题的起手式通常是先____________，把几何关系标出来。", "画图"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合本节课对全反射的判断 / Which best matches the lesson's criterion for total internal reflection?",
                "options": [
                    "A. 只要入射角够大就一定全反射 / A large incident angle alone guarantees total internal reflection",
                    "B. 只要从空气射入玻璃就一定全反射 / Any air-to-glass transition causes total internal reflection",
                    "C. 必须从光密到光疏，且入射角大于等于临界角 / From optically denser to rarer medium, with incident angle at least the critical angle",
                    "D. 只和波长有关 / It depends only on wavelength",
                ],
                "answer": "C",
            },
            {
                "question": "关于机械波传播，下列说法正确的是 / Which statement about mechanical waves is correct?",
                "options": [
                    "A. 质点会跟着波整体向前移动 / Particles move forward with the wave",
                    "B. 波速由波源决定，频率由介质决定 / Wave speed is set by the source, frequency by the medium",
                    "C. 质点只在平衡位置附近振动，波速由介质决定 / Particles vibrate near equilibrium, and wave speed is determined by the medium",
                    "D. 波长与介质无关 / Wavelength is unrelated to the medium",
                ],
                "answer": "C",
            },
        ],
        "quotes": [LESSON["quotes"][1], LESSON["quotes"][3]],
    },
    {
        "offset": 2,
        "day": "第2天 / Day 2",
        "focus": "第二次整课复习，重点区分各类干涉模型和条纹条件。 / Second full review focused on distinguishing interference models and fringe conditions.",
        "goal": "能快速判断一道题属于薄膜干涉、牛顿环还是双缝干涉，并写出关键条件。 / Quickly identify whether a problem is thin-film interference, Newton's rings, or double-slit interference, and state the key condition.",
        "tasks": [
            "快速过一遍全课覆盖清单。Run through the full lesson coverage list once.",
            "完成填空题，重点复盘光程差、半波损失、明暗条纹和条纹间距。Complete the blanks with focus on optical path difference, half-wave loss, bright-dark conditions, and fringe spacing.",
            "完成选择题，纠正干涉类型混淆。Finish the choices to correct model confusion.",
            "口头说明为什么牛顿环中心常是暗斑。Explain orally why the center of Newton's rings is usually dark.",
        ],
        "blanks": [
            ("薄膜干涉中，明暗条纹最终由____________决定。", "光程差"),
            ("若下表面反射存在半波损失，分析时常要额外加上____________。", "λ/2"),
            ("劈尖干涉条纹间距公式中，夹角越小，条纹会越____________。", "疏"),
            ("牛顿环实验中，中心通常呈____________斑。", "暗"),
            ("双缝干涉的明纹条件可写成 Δs = ____________。", "kλ"),
            ("双缝干涉的暗纹条件可写成 Δs = ____________。", "(2k+1)λ/2"),
            ("双缝干涉条纹间距与波长成____________比，与缝距成____________比。", "正；反"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合牛顿环的条纹特点 / Which best matches Newton's rings?",
                "options": [
                    "A. 平行直条纹 / Parallel straight fringes",
                    "B. 内疏外密的同心圆环 / Concentric rings that are sparse inside and dense outside",
                    "C. 只有一条亮纹 / Only one bright fringe",
                    "D. 与半波损失无关 / Unrelated to half-wave loss",
                ],
                "answer": "B",
            },
            {
                "question": "双缝干涉条纹间距公式最能说明哪组关系 / What relationship is shown by the double-slit fringe-spacing formula?",
                "options": [
                    "A. 与波长成正比、与缝距成反比 / Proportional to wavelength and inversely proportional to slit distance",
                    "B. 与波长成反比、与缝距成正比 / Inversely proportional to wavelength and proportional to slit distance",
                    "C. 与屏距无关 / Independent of screen distance",
                    "D. 只与颜色有关 / Only depends on color",
                ],
                "answer": "A",
            },
        ],
        "quotes": [LESSON["quotes"][2]],
    },
    {
        "offset": 7,
        "day": "第7天 / Day 7",
        "focus": "一周后迁移，重点把综合题中的建模顺序和边界思维说清楚。 / One-week transfer review focused on modeling order and boundary thinking in integrated problems.",
        "goal": "看到综合题时，能先分离物理过程，再判断应该用极值分析、分段讨论还是图像辅助。 / For integrated problems, separate the physical processes first, then choose extremum analysis, piecewise discussion, or graphical support.",
        "tasks": [
            "先口头复述整节课的方法地图。Orally restate the lesson's method map.",
            "回答老师提问卡片，每题都要补一句为什么先这样建模。Answer oral prompt cards and add why that modeling order comes first.",
            "重点复盘采光球与导光管、多次折射反射、边界光线三类综合思路。Review integrated ideas for daylight sphere and light pipe, multiple refraction-reflection, and boundary rays.",
            "最后复述至少 3 句课堂原话。Retell at least 3 class quotes at the end.",
        ],
        "blanks": [
            ("处理光照区域长度、最大可见范围等问题时，常优先使用____________法。", "极值分析"),
            ("多波源或多阶段传播问题，如果一个公式覆盖不了全程，常改用____________法。", "分段讨论"),
            ("综合光路题里，边界突破口常常是____________光线或临界全反射光线。", "切线"),
            ("老师强调复杂题要先把物理过程____________，再逐层建模。", "分开"),
            ("采光球与导光管题里，传播时间通常要按不同____________分段计算。", "介质"),
            ("即使发生多次反射，只要几何结构固定，路径总长度也可能保持____________。", "恒定"),
            ("图像辅助法最核心的作用，是把抽象条件变得更____________。", "直观"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合本节课处理复杂光路题的顺序 / Which best matches the class order for complex ray-path problems?",
                "options": [
                    "A. 先套最终公式 / Apply the final formula first",
                    "B. 先分离折射、反射、干涉等过程，再逐层建模 / Separate refraction, reflection, interference, then model step by step",
                    "C. 先猜答案再补图 / Guess the answer before drawing",
                    "D. 只靠计算不画图 / Compute without any diagram",
                ],
                "answer": "B",
            },
            {
                "question": "哪一类问题最适合先抓边界光线 / Which type of problem most strongly suggests starting with boundary rays?",
                "options": [
                    "A. 光照范围极值题 / Extremum problems about illumination range",
                    "B. 简单定义题 / Simple definition questions",
                    "C. 纯记忆题 / Pure memorization questions",
                    "D. 只有单位换算的题 / Problems with only unit conversion",
                ],
                "answer": "A",
            },
        ],
        "quotes": [LESSON["quotes"][0], LESSON["quotes"][4]],
    },
    {
        "offset": 14,
        "day": "第14天 / Day 14",
        "focus": "两周后校准，重点检查机械波图像判断和易错概念。 / Two-week calibration focused on mechanical-wave graph interpretation and common pitfalls.",
        "goal": "能结合波形图、振动图、传播方向和时间先后，判断质点状态与加强减弱。 / Combine waveform, vibration graph, propagation direction, and time sequence to judge particle states and constructive-destructive effects.",
        "tasks": [
            "先口头总结这节课最容易错的 5 个点。First summarize the 5 easiest mistakes orally.",
            "回答老师提问卡片，重点说明为什么质点不迁移、为什么要分段。Answer oral prompt cards and explain why particles do not migrate and why piecewise reasoning is needed.",
            "复盘波的叠加、加强减弱点、波速周期波长之间的联系。Review superposition, constructive-destructive points, and the links among wave speed, period, and wavelength.",
            "最后再说一遍图像判断不能脱离传播方向。Close by restating that graph interpretation depends on propagation direction.",
        ],
        "blanks": [
            ("波速由____________决定，而频率由____________决定。", "介质；波源"),
            ("若介质不变，则波速固定，波长与____________成正比。", "周期"),
            ("加强点满足波程差为____________，减弱点满足波程差为____________。", "kλ；(2k+1)λ/2"),
            ("判断质点下一时刻如何运动时，除了位移，还要看传播____________。", "方向"),
            ("课堂里判断质点振动方向时，提到可以借助____________法。", "坡"),
            ("两列波先后到达某点时，若要判断是否持续振动，常要比较____________差和时间差。", "路程"),
        ],
        "choices": [
            {
                "question": "下列哪一项是课堂反复强调的机械波易错点 / Which was repeatedly emphasized as a pitfall in mechanical waves?",
                "options": [
                    "A. 质点跟着波形整体平移 / Particles translate together with the waveform",
                    "B. 质点只在平衡位置附近振动 / Particles only vibrate near equilibrium",
                    "C. 频率由介质决定 / Frequency is determined by the medium",
                    "D. 波长与波速完全无关 / Wavelength is unrelated to wave speed",
                ],
                "answer": "B",
            },
            {
                "question": "当两列波不是同时到达同一点时，更稳妥的思路是 / When two waves do not reach the same point simultaneously, the safer approach is:",
                "options": [
                    "A. 直接套同时干涉结论 / Apply simultaneous interference conclusions directly",
                    "B. 按时间或空间做分段讨论 / Do a piecewise discussion in time or space",
                    "C. 忽略到达先后 / Ignore arrival order",
                    "D. 只看最大位移 / Only inspect maximum displacement",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][3]],
    },
    {
        "offset": 30,
        "day": "第30天 / Day 30",
        "focus": "一个月后的总复盘，要求脱离课堂语境也能稳定调用这一整套光学与波动工具。 / One-month final review for stable independent recall of the optics-and-waves toolkit.",
        "goal": "看到新题时能先识别属于几何光学、干涉还是机械波，再决定建模顺序和得分点。 / Identify whether a new problem belongs to geometrical optics, interference, or mechanical waves, then choose the modeling order and scoring points.",
        "tasks": [
            "先默写整节课的题型-方法对照表。Write the topic-to-method map from memory.",
            "完成总复盘填空和选择，检查长期记忆是否稳定。Complete the final blanks and choices to test retention.",
            "任选一个专题，口头说出入口物理量、核心关系、易错点和突破口。Pick one topic and retell the entry quantity, core relation, pitfall, and breakthrough.",
            "最后读一遍上课金句回顾。Finish by reviewing the class quotes once more.",
        ],
        "blanks": [
            ("几何光学部分最基础的两个入口是____________和____________。", "折射定律；全反射条件"),
            ("薄膜干涉和牛顿环共同离不开的两个关键词是光程差与____________。", "半波损失"),
            ("双缝干涉长期最该记住的是明暗条件和____________公式。", "条纹间距"),
            ("机械波部分最容易错的一句话是：质点____________随波迁移。", "不"),
            ("综合题如果出现最值、边界或最大范围，常先找____________光线。", "边界"),
            ("遇到传播过程较多的题，先把物理过程分开，再做____________建模。", "逐层"),
            ("这节课长期最该留下的，不是零散公式，而是现象、原理、模型与____________之间的对应关系。", "应用"),
        ],
        "choices": [
            {
                "question": "一个月后的理想状态是 / What is the ideal state after one month?",
                "options": [
                    "A. 只记住几个公式的字母形式 / Remember only the symbolic formulas",
                    "B. 看到新题能先识别模块，再判断物理过程和建模顺序 / Identify the module first, then judge the physical process and modeling order",
                    "C. 只会做课堂原题 / Only solve the original class examples",
                    "D. 所有题都先做大量代数变形 / Start every problem with heavy algebraic manipulation",
                ],
                "answer": "B",
            },
            {
                "question": "本节课长期复习最该留下的是什么 / What should remain most clearly after long-term review?",
                "options": [
                    "A. 作业题号 / Homework question numbers",
                    "B. 零散答案 / Isolated answers",
                    "C. 物理情境、数学关系和解题策略之间的对应关系 / The mapping among physical scenarios, mathematical relations, and problem-solving strategy",
                    "D. 每道题的具体数字 / The specific numbers in each problem",
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
            "title": "折射与全反射 / Refraction and Total Internal Reflection",
            "mixed": {
                "blanks": [
                    ("若入射角为 45° 的题目要求发生全反射，常要先比较折射率与____________的大小。", "根号2"),
                ],
                "choices": [
                    {
                        "question": "判断全反射时，哪一个量最值得先写出来 / Which quantity is most useful to write down first when judging total internal reflection?",
                        "options": [
                            "A. 临界角关系 / The critical-angle relation",
                            "B. 万有引力公式 / The gravitational formula",
                            "C. 电场强度定义 / The electric-field definition",
                            "D. 动量守恒 / Momentum conservation",
                        ],
                        "answer": "A",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么全反射一定要同时满足两个条件？",
                    "为什么进入高折射率介质后波长会变短？",
                    "复杂折射反射题里为什么一定要先画光路图？",
                ],
                "keypoints": [
                    "因为只有从光密到光疏且入射角足够大时，折射光才会消失。",
                    "因为频率由波源决定不变，而波速减小，所以波长变短。",
                    "因为角度和边界关系不画出来很容易漏条件。",
                ],
            },
        },
        {
            "title": "机械波基础 / Mechanical Wave Basics",
            "mixed": {
                "blanks": [
                    ("机械波中，波速由____________决定，频率由____________决定。", "介质；波源"),
                ],
                "choices": [
                    {
                        "question": "哪一句最能纠正机械波的典型误解 / Which sentence best corrects the typical misconception about mechanical waves?",
                        "options": [
                            "A. 质点会被波带着整体跑 / Particles are carried forward by the wave",
                            "B. 质点只是在平衡位置附近振动 / Particles only vibrate near equilibrium",
                            "C. 波长永远不变 / Wavelength never changes",
                            "D. 频率会被介质改变 / Frequency is changed by the medium",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么说质点不迁移是机械波题的底线概念？",
                    "波速、频率、波长三者分别由什么决定？",
                    "为什么图像题不能只看某一个瞬间的形状？",
                ],
                "keypoints": [
                    "因为很多判断错误都来自把波形传播误认为质点运动。",
                    "波速看介质，频率看波源，波长由二者共同联系。",
                    "因为传播方向和时序信息也会改变结论。",
                ],
            },
        },
    ],
    "第2天 / Day 2": [
        {
            "title": "薄膜干涉与牛顿环 / Thin-Film Interference and Newton's Rings",
            "mixed": {
                "blanks": [
                    ("牛顿环中心常为暗斑，核心原因是存在____________。", "半波损失"),
                ],
                "choices": [
                    {
                        "question": "条纹向接触边弯曲，课堂上用来判断什么 / If fringes bend toward the contact edge, what is it used to judge?",
                        "options": [
                            "A. 表面凹凸情况 / Surface concavity or convexity",
                            "B. 波源频率大小 / Source frequency",
                            "C. 波速方向 / Wave-speed direction",
                            "D. 临界角大小 / Critical angle magnitude",
                        ],
                        "answer": "A",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么薄膜干涉不能只看几何厚度，还要看半波损失？",
                    "牛顿环为什么会形成同心圆条纹？",
                    "如何利用条纹弯曲判断表面凹凸？",
                ],
                "keypoints": [
                    "因为反射附加相位会直接改变明暗条件。",
                    "因为空气膜厚度关于圆心呈对称变化。",
                    "要结合等厚干涉和条纹对应同厚度区域来判断。",
                ],
            },
        },
        {
            "title": "双缝干涉 / Double-Slit Interference",
            "mixed": {
                "blanks": [
                    ("双缝干涉里，相干光源通常来自同一____________分出的两束光。", "光源"),
                ],
                "choices": [
                    {
                        "question": "若介质改变使波长变短，条纹间距通常会怎样变化 / If the wavelength becomes shorter in a medium, what happens to fringe spacing?",
                        "options": [
                            "A. 变大 / It increases",
                            "B. 变小 / It decreases",
                            "C. 不变 / It stays unchanged",
                            "D. 先变大后变小 / It first increases then decreases",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么双缝干涉必须先获得相干光源？",
                    "明纹和暗纹条件各自体现了什么物理含义？",
                    "条纹间距公式能帮助判断哪些物理变化？",
                ],
                "keypoints": [
                    "因为只有相位关系稳定，条纹才稳定。",
                    "明纹对应相长干涉，暗纹对应相消干涉。",
                    "能判断波长、缝距、屏距和介质变化的影响。",
                ],
            },
        },
    ],
    "第7天 / Day 7": [
        {
            "title": "综合光路建模 / Integrated Ray-Path Modeling",
            "mixed": {
                "blanks": [
                    ("处理多次折射与反射时，第一步不是硬算，而是先把物理过程____________。", "拆开"),
                ],
                "choices": [
                    {
                        "question": "采光球与导光管题里，时间计算更稳妥的方法是 / In the daylight sphere and light-pipe problem, the safer way to compute time is:",
                        "options": [
                            "A. 把所有介质当成同一种 / Treat all media as identical",
                            "B. 按不同介质分段求传播时间 / Compute travel time piecewise by medium",
                            "C. 只算第一次折射 / Only compute the first refraction",
                            "D. 不看路径长度 / Ignore path length",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么综合题必须先把折射、反射、干涉过程拆开？",
                    "什么时候边界光线会成为解题突破口？",
                    "为什么路径长度恒定这一点在时间题里很关键？",
                ],
                "keypoints": [
                    "因为不同过程对应的关系式和限制条件不同。",
                    "当题目问最大范围、最短最长或临界情况时。",
                    "因为时间等于路程除以速度，先锁定路程能大幅简化。",
                ],
            },
        },
        {
            "title": "图像辅助法 / Graphical Support",
            "mixed": {
                "blanks": [
                    ("图像辅助法最典型的三个图是光路图、____________图和振动曲线。", "波形"),
                ],
                "choices": [
                    {
                        "question": "图像辅助法最直接的价值是 / The most direct value of a graphical method is:",
                        "options": [
                            "A. 替代所有公式 / Replace all formulas",
                            "B. 让边界、方向和几何关系更直观 / Make boundaries, directions, and geometry more visible",
                            "C. 只用于作图题 / Only for drawing tasks",
                            "D. 只能帮助记忆术语 / Only helps memorize terms",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "光路图、波形图、振动图各自最适合解决什么问题？",
                    "为什么复杂题不画图容易把条件混在一起？",
                    "图像法和代数计算之间应该怎样配合？",
                ],
                "keypoints": [
                    "光路图看角度路径，波形图看空间分布，振动图看单点随时间变化。",
                    "因为空间关系、时间关系和方向关系会互相干扰。",
                    "先用图像定结构，再用公式定量。",
                ],
            },
        },
    ],
    "第14天 / Day 14": [
        {
            "title": "波的叠加与分段讨论 / Superposition and Piecewise Discussion",
            "mixed": {
                "blanks": [
                    ("两列波先后到达同一点时，若想判断是否持续振动，要比较时间差与____________差。", "路程"),
                ],
                "choices": [
                    {
                        "question": "哪种情况最需要分段讨论 / Which situation most strongly requires a piecewise discussion?",
                        "options": [
                            "A. 只有一个固定波源且全过程同一关系 / One fixed source with one relation throughout",
                            "B. 多阶段传播或两列波到达先后不同 / Multi-stage propagation or different arrival times of waves",
                            "C. 只问一个定义 / A simple definition question",
                            "D. 只做单位换算 / Only unit conversion",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么两列波不是同时到达时，不能直接套普通干涉结论？",
                    "加强点和减弱点条件在什么时候成立得最稳？",
                    "时间先后信息是如何改变结论的？",
                ],
                "keypoints": [
                    "因为叠加关系是否成立取决于同一时刻是否同时存在扰动。",
                    "在相干、同频且满足相应波程差条件时最稳。",
                    "它会改变某一点是否已经开始振动以及振动相位。",
                ],
            },
        },
        {
            "title": "传播方向与图像判断 / Propagation Direction and Graph Interpretation",
            "mixed": {
                "blanks": [
                    ("根据波形平移方向判断质点振动方向时，课堂提到了____________法。", "坡"),
                ],
                "choices": [
                    {
                        "question": "若只看波形图形状而不看传播方向，最容易出什么问题 / If you look only at waveform shape and ignore propagation direction, what is the main risk?",
                        "options": [
                            "A. 把质点下一时刻运动方向判断错 / Misjudge the particle's next motion direction",
                            "B. 算不出折射率 / Fail to calculate refractive index",
                            "C. 不会写条纹间距公式 / Fail to write fringe-spacing formula",
                            "D. 忘记单位换算 / Forget unit conversion",
                        ],
                        "answer": "A",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么传播方向是图像判断的关键补充信息？",
                    "位移、加速度和振动趋势之间该怎样联动判断？",
                    "波形图和振动图最容易混淆在哪里？",
                ],
                "keypoints": [
                    "因为同一形状在不同传播方向下对应的质点运动趋势不同。",
                    "要结合当前位置、回复趋势和传播引起的相位变化一起看。",
                    "一个看空间同一时刻，一个看单点随时间变化。",
                ],
            },
        },
    ],
    "第30天 / Day 30": [
        {
            "title": "模块入口总复盘 / Entry-Point Synthesis",
            "mixed": {
                "blanks": [
                    ("看到临界条件先想____________，看到条纹间距先想____________，看到波形图先想传播方向。", "全反射；干涉"),
                ],
                "choices": [
                    {
                        "question": "哪一项最能体现这节课的长期方法迁移 / Which best shows long-term method transfer from this lesson?",
                        "options": [
                            "A. 只记原题数字 / Remember only the original numbers",
                            "B. 看到新题能先判断它属于折射、干涉还是机械波 / Identify whether a new problem belongs to refraction, interference, or mechanical waves",
                            "C. 只会复述老师原话 / Only repeat the teacher's words",
                            "D. 先做代数再想物理 / Do algebra before thinking physics",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "一个月后你最该保留下来的三个入口关键词是什么？",
                    "看到新题时你的判断顺序应该是什么？",
                    "这节课哪些内容最能体现先物理后数学？",
                ],
                "keypoints": [
                    "全反射条件、光程差与半波损失、传播方向与分段。",
                    "先识别模块，再分离过程，再选公式和策略。",
                    "综合光路题、干涉题和机械波图像题都很典型。",
                ],
            },
        },
        {
            "title": "长期记忆校验 / Long-Term Memory Check",
            "mixed": {
                "blanks": [
                    ("长期复习时，最该记住的不是零散公式，而是物理情境与____________、____________之间的对应关系。", "数学关系；解题策略"),
                ],
                "choices": [
                    {
                        "question": "哪一项最符合这节课的长期目标 / Which best matches the long-term goal of the lesson?",
                        "options": [
                            "A. 看见题目先背模板 / Start by recalling a template",
                            "B. 看见题目先认物理过程，再决定建模方式 / Identify the physical process first, then choose the model",
                            "C. 只记住老师布置的作业 / Remember only the homework assigned",
                            "D. 只保留条纹公式 / Keep only the fringe formula",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么这节课最不该留下的是孤立公式表？",
                    "如果只剩 1 分钟复盘，你会先回想哪几个高频易错点？",
                    "请口头总结这节课最核心的 3 个方法提醒。",
                ],
                "keypoints": [
                    "因为公式只有放回物理情境里才知道何时能用。",
                    "半波损失、全反射双条件、质点不迁移。",
                    "先分过程、先画图、遇到边界就想极值或临界。",
                ],
            },
        },
    ],
}


FINAL_REMINDER_LINES = [
    "看到折射与边界，先写清介质关系、角度关系和临界条件。",
    "看到薄膜干涉、牛顿环，先想光程差和半波损失。",
    "看到双缝干涉，优先回忆明暗条件和条纹间距公式。",
    "看到机械波图像，先分清空间图还是时间图，再看传播方向。",
    "每个复习日都要扫完整节课，不要只盯一个公式或一道题。",
]