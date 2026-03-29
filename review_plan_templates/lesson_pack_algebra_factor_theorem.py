LESSON = {
    "title": "代数公式与因式定理课后复习计划",
    "subtitle": "Spaced Review Plan for Binomial Expansion, Higher-Power Identities, Symmetry, and Factor Theorem",
    "audience": "老师发给学生使用 / For Teacher Distribution",
    "duration": "每次 10-20 分钟 / 10-20 minutes each time",
    "core_points": [
        "完全平方与二项式展开要抓住降幂排列、总次数恒定和组合数系数来源。",
        "二项式系数不是背出来的，而是由从若干括号中选取项的方式数得到。",
        "高次幂差公式可用错位相减法推导，本质上和等比求和结构相关。",
        "x^n+y^n 何时可分解要看 n 的奇偶性以及是否能进一步换元拆成奇数次。",
        "纯 2 的幂次在这类和式分解中通常不能继续分解，是重要边界结论。",
        "多元展开要识别轮换对称、其次性和交叉项个数的组合来源。",
        "因式定理的核心是 f(c)=0 等价于 x-c 是因式，也是余数为零定理。",
        "有理根判定和试根是高次整系数多项式分解的重要入口。",
    ],
    "full_review_topics": [
        "完全平方与二项式定理的结构特征 / Structure of perfect squares and binomial expansion",
        "二项式系数的组合来源 / Combinatorial source of binomial coefficients",
        "高次幂差公式与错位相减法 / Power-difference formulas and shifted subtraction",
        "高次幂和式的可分解条件 / When power sums can be factorized",
        "换元、其次性与边界情况 / Substitution, homogeneous structure, and boundary cases",
        "两种等价分解路径的选择 / Choosing between equivalent factorization paths",
        "轮换对称与多元展开 / Cyclic symmetry and multivariable expansion",
        "因式定理与余数定理 / Factor theorem and remainder theorem",
        "有理根判定法与试根范围缩小 / Rational root theorem and narrowing candidates",
        "四次整式因式分解综合实践 / Full factorization practice for quartic polynomials",
    ],
    "quotes": [
        "理解比记忆更重要，公式要会推，不要只会背。",
        "系数为什么是这个数，一定要从组合意义上说得出来。",
        "高次幂差公式先想错位相减，不要硬记模板。",
        "因式定理不是单独一个点，而是和试根、整式除法连成一套工具。",
        "轮换对称和其次性是这节课的隐藏主线。",
    ],
}


DAYS = [
    {
        "offset": 1,
        "day": "第1天 / Day 1",
        "focus": "第一次整课回放，重点先把整节课的代数地图搭起来。 / First whole-lesson replay focused on rebuilding the full algebra map.",
        "goal": "能说出这节课从二项式展开到因式定理的主线，而不是只记住个别公式。 / Retell the main line from binomial expansion to the factor theorem instead of isolated formulas.",
        "tasks": [
            "先默写整节课的核心模块，再核对课堂笔记。Write down the core modules before checking notes.",
            "完成填空题，把展开、分解、轮换对称、试根四条线先重新连起来。Complete the blanks to reconnect expansion, factorization, cyclic symmetry, and root testing.",
            "完成选择题，检查基础概念和结构判断。Finish the choices to verify the core structural ideas.",
            "读一次上课金句回顾，再口头复述整节课主线。Read the class quotes once, then retell the lesson flow.",
        ],
        "blanks": [
            ("二项式展开式通常呈____________排列，从高次到低次展开。", "降幂"),
            ("在 (x+y)^m 的每一项中，总次数始终等于____________。", "m"),
            ("二项式系数的来源不是死记，而是来自____________数。", "组合"),
            ("x^n-y^n 的通用分解公式常通过____________法推导。", "错位相减"),
            ("因式定理的核心判断是：若 f(c)=0，则 x-c 是它的____________。", "因式"),
            ("如果多项式除以 x-c 的余数为 0，就说明 x-c 可以____________原多项式。", "整除"),
            ("老师反复强调：公式首先要会____________，不能只会背。", "推导"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合本节课对二项式系数的理解 / Which best matches the lesson's view of binomial coefficients?",
                "options": [
                    "A. 只需要死记杨辉三角 / Only memorize Pascal's triangle",
                    "B. 来自从若干括号中选项的组合方式数 / They come from counting selection patterns across factors",
                    "C. 完全靠经验猜 / They are guessed by pattern only",
                    "D. 只对平方有效 / They only work for squares",
                ],
                "answer": "B",
            },
            {
                "question": "哪一句最符合因式定理 / Which statement best matches the factor theorem?",
                "options": [
                    "A. 只要代入过一个数就能得到因式 / Any substitution gives a factor",
                    "B. 若 f(c)=0，则 x-c 是因式 / If f(c)=0, then x-c is a factor",
                    "C. 任何整式都能被 x-c 整除 / Every polynomial is divisible by x-c",
                    "D. 因式定理只适用于二次式 / It only applies to quadratics",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][0], LESSON["quotes"][1]],
    },
    {
        "offset": 2,
        "day": "第2天 / Day 2",
        "focus": "第二次整课复习，重点区分高次幂差、和式与换元条件。 / Second full review focused on distinguishing power differences, sums, and substitution conditions.",
        "goal": "能判断 x^n-y^n 和 x^n+y^n 何时能分解、为什么能分解。 / Judge when x^n-y^n and x^n+y^n can be factorized and explain why.",
        "tasks": [
            "快速过一遍全课覆盖清单。Run through the full lesson coverage list once.",
            "完成填空题，重点复盘奇偶性、换元与边界情况。Complete the blanks with focus on parity, substitution, and boundary cases.",
            "完成选择题，纠正“看到和差式就机械套公式”的问题。Finish the choices to correct mechanical formula matching.",
            "口头说明为什么纯 2 的幂次是重要边界。Explain orally why pure powers of 2 are an important boundary case.",
        ],
        "blanks": [
            ("当 n 为奇数时，x^n+y^n 通常可以____________。", "分解"),
            ("当 n 为偶数时，x^n+y^n 一般不能直接分解，但若指数可拆成奇数倍，可以通过____________转化。", "换元"),
            ("像 6=2×3 这样的指数，可先把原式看成某个新元的____________次和式。", "三"),
            ("纯 2 的幂次如 2、4、8、16 在这一类和式分解里通常____________继续分解。", "不能"),
            ("同一个式子有时既能按高次幂差去拆，也能先看成____________再继续分解。", "平方差"),
            ("老师强调选哪条分解路径，要看题目是想求____________还是想做整体因式分解。", "特定项系数"),
            ("高次幂差与高次幂和的判断入口，最先要看指数的____________。", "奇偶性"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合 x^n+y^n 的分解规律 / Which best matches the factorization rule for x^n+y^n?",
                "options": [
                    "A. 任意 n 都能直接分解 / It can always be factorized directly",
                    "B. 只要 n 是偶数就一定能分解 / Any even n works directly",
                    "C. n 为奇数时可直接分解，偶数时要看能否换元转成奇次 / It factorizes directly for odd n; even n needs substitution into an odd power when possible",
                    "D. 和差式规律完全一样 / It behaves exactly like the difference formula",
                ],
                "answer": "C",
            },
            {
                "question": "如果题目更关心某一项系数，通常更适合 / If a problem cares more about a specific coefficient, which path is usually better?",
                "options": [
                    "A. 选更直接的高次幂公式路径 / Use the direct higher-power formula path",
                    "B. 只做数值代入 / Only do numerical substitution",
                    "C. 永远先平方差 / Always use difference of squares first",
                    "D. 只用整式除法 / Only use polynomial division",
                ],
                "answer": "A",
            },
        ],
        "quotes": [LESSON["quotes"][2]],
    },
    {
        "offset": 7,
        "day": "第7天 / Day 7",
        "focus": "一周后迁移，重点把轮换对称、其次性和多元展开说清楚。 / One-week transfer review focused on cyclic symmetry, homogeneous structure, and multivariable expansion.",
        "goal": "看到多元代数式时，能先识别结构，再决定用展开、配凑还是对称变形。 / For multivariable expressions, identify the structure first and then choose expansion, regrouping, or symmetry transforms.",
        "tasks": [
            "先口头复述整节课的方法地图。Orally restate the lesson's method map.",
            "回答老师提问卡片，每题都补一句为什么这是轮换对称或其次结构。Answer oral prompt cards and add why the structure is cyclic or homogeneous.",
            "重点复盘三元、四元展开和交叉项个数的组合来源。Review three-variable and four-variable expansions and the combinatorial source of cross terms.",
            "最后复述至少 3 句课堂原话。Retell at least 3 class quotes at the end.",
        ],
        "blanks": [
            ("像 x^2+y^2+z^2+xy+yz+zx 这类式子，常要先观察有没有____________对称。", "轮换"),
            ("多元完全平方展开中，交叉项的数量来源于____________数。", "组合"),
            ("老师提到“其次”时，强调的是每一项的总次数保持____________。", "一致"),
            ("(x+y+z)^2 展开后，除了三个平方项，还会出现____________个交叉项。", "三类"),
            ("更高维度的展开如果公式太长，课堂建议通过____________计算，避免死记。", "分步"),
            ("轮换对称真正有用的地方，是变量位置交换后式子的____________不变。", "结构"),
            ("看到三正一负等变体时，先不要慌，先回到____________平方式的主结构。", "完全"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合“轮换对称” / Which best matches cyclic symmetry?",
                "options": [
                    "A. 任意换字母后都完全一样 / Any permutation leaves the expression unchanged in every way",
                    "B. 按顺序轮换变量位置后，表达式结构保持不变 / The structure stays unchanged under cyclic relabeling",
                    "C. 只在二元式里出现 / It appears only in two-variable expressions",
                    "D. 只和系数大小有关 / It only depends on coefficient magnitude",
                ],
                "answer": "B",
            },
            {
                "question": "关于多元展开，下列哪项最符合课堂思路 / Which best matches the class idea for multivariable expansion?",
                "options": [
                    "A. 公式太长就完全跳过 / Skip long formulas entirely",
                    "B. 先抓结构和交叉项来源，再决定是否分步展开 / Identify the structure and cross-term source first, then expand step by step if needed",
                    "C. 只用死记公式 / Memorize formulas only",
                    "D. 一律代数字代入 / Always substitute numbers",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][4]],
    },
    {
        "offset": 14,
        "day": "第14天 / Day 14",
        "focus": "两周后校准，重点检查因式定理、有理根判定和整式分解流程。 / Two-week calibration focused on the factor theorem, rational root test, and full factorization workflow.",
        "goal": "能从一个高次整系数多项式出发，先缩小试根范围，再逐步提取因式。 / Start from a high-degree integer-coefficient polynomial, narrow the root candidates, and extract factors step by step.",
        "tasks": [
            "先口头总结这节课最容易错的 5 个点。First summarize the 5 easiest mistakes orally.",
            "回答老师提问卡片，重点说明为什么先缩小试根范围，再做代入验证。Answer oral prompts and explain why candidate narrowing comes before substitution checking.",
            "复盘四次整式因式分解题的完整流程。Review the full workflow of quartic factorization.",
            "最后再说一遍因式定理、试根和整式除法之间的关系。Close by restating the link among factor theorem, root testing, and polynomial division.",
        ],
        "blanks": [
            ("若整系数多项式存在有理根 p/q，则 p 一定整除____________项，q 一定整除____________项。", "常数；首项"),
            ("有理根判定法最主要的作用是____________试根范围。", "缩小"),
            ("代入某个候选值后若结果为 0，就说明对应的一次式是原式的____________。", "因式"),
            ("提取出一个一次因式后，通常要继续做____________除法，得到低次商式。", "整式"),
            ("剩下的二次商式如果还能分解，可再用公式法或____________完成。", "十字相乘"),
            ("老师提醒：因式定理不是孤立技巧，而是和试根、整式除法连成一套____________。", "工具"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合有理根判定法的作用 / Which best matches the role of the rational root theorem?",
                "options": [
                    "A. 直接给出所有根 / It directly gives all roots",
                    "B. 直接给出因式分解结果 / It directly gives the factorization",
                    "C. 缩小可能的有理根候选范围 / It narrows the possible rational-root candidates",
                    "D. 只适用于一次式 / It applies only to linear polynomials",
                ],
                "answer": "C",
            },
            {
                "question": "高次整式分解中，哪一步最符合课堂流程 / Which step order best matches the class workflow for high-degree factorization?",
                "options": [
                    "A. 先整式除法，再找候选根 / Divide first, then search candidate roots",
                    "B. 先找候选根并代入验证，得到因式后再做整式除法 / Find candidates and verify them first, then divide after extracting a factor",
                    "C. 只做十字相乘 / Only use cross factoring",
                    "D. 只看常数项 / Only inspect the constant term",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][3]],
    },
    {
        "offset": 30,
        "day": "第30天 / Day 30",
        "focus": "一个月后的总复盘，要求脱离课堂语境也能独立调用这整套代数工具。 / One-month final review for independently recalling the full algebra toolkit.",
        "goal": "看到新题时能先识别是展开、分解、对称结构还是试根问题，再决定方法。 / Identify whether a new problem is about expansion, factorization, symmetry, or root testing, then choose the method.",
        "tasks": [
            "先默写整节课的题型-方法对照表。Write the topic-to-method map from memory.",
            "完成总复盘填空和选择，检查长期记忆是否稳定。Complete the final blanks and choices to test retention.",
            "任选一个专题，口头说出入口结构、关键工具、易错点和突破口。Pick one topic and retell the entry structure, key tool, pitfall, and breakthrough.",
            "最后读一遍上课金句回顾。Finish by reviewing the class quotes once more.",
        ],
        "blanks": [
            ("二项式展开长期最该记住的三个词是：降幂排列、总次数恒定、____________来源。", "组合系数"),
            ("看到 x^n-y^n，优先回想____________法推导出来的通式。", "错位相减"),
            ("看到 x^n+y^n，先看指数____________，再判断能否换元。", "奇偶性"),
            ("看到多元式，先看有没有____________对称和其次结构。", "轮换"),
            ("看到高次整系数多项式，若想找一次因式，先想到因式定理和____________。", "有理根判定"),
            ("这节课长期最该留下的，不是零散公式，而是结构识别与____________之间的对应关系。", "方法选择"),
            ("老师整节课反复强调：真正要掌握的是推导与理解，而不是机械____________。", "记忆"),
        ],
        "choices": [
            {
                "question": "一个月后的理想状态是 / What is the ideal state after one month?",
                "options": [
                    "A. 只记住几条公式 / Remember only a few formulas",
                    "B. 看到新题能先识别结构，再决定展开、分解还是试根 / Identify the structure first, then decide whether to expand, factorize, or test roots",
                    "C. 只会做课堂原题 / Only solve the original class examples",
                    "D. 所有题都先套模板 / Start every problem with a template",
                ],
                "answer": "B",
            },
            {
                "question": "本节课长期复习最该留下的是什么 / What should remain most clearly after long-term review?",
                "options": [
                    "A. 小册子页码 / The booklet page numbers",
                    "B. 作业安排 / Homework arrangements",
                    "C. 代数结构、推导逻辑和工具链之间的联系 / The links among algebraic structure, derivation logic, and the tool chain",
                    "D. 所有例题的数字 / The numbers in all examples",
                ],
                "answer": "C",
            },
        ],
        "quotes": [LESSON["quotes"][0], LESSON["quotes"][4]],
    },
]


KNOWLEDGE_SECTIONS = {
    "第1天 / Day 1": [
        {
            "title": "二项式展开 / Binomial Expansion",
            "mixed": {
                "blanks": [
                    ("在 (x+y)^m 中，第 k 项的系数通常用____________表示。", "组合数"),
                ],
                "choices": [
                    {
                        "question": "为什么某一项的系数会是组合数 / Why is a term coefficient a binomial coefficient?",
                        "options": [
                            "A. 因为老师规定的 / Because it is declared",
                            "B. 因为从多个括号中选出若干个 x 或 y 的方式数恰好对应组合数 / Because choosing x and y from multiple factors matches a counting problem",
                            "C. 因为总次数不变 / Because the total degree stays fixed",
                            "D. 因为降幂排列 / Because terms are in descending powers",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么二项式系数必须从组合意义上理解？",
                    "总次数恒定这个结构对展开有什么提示？",
                    "为什么老师强调“会推”比“会背”更重要？",
                ],
                "keypoints": [
                    "因为理解来源后，忘了具体数值也能自己重新构造出来。",
                    "说明每一项都属于同一次齐次结构。",
                    "因为推导能力能迁移到新题，死记不能。",
                ],
            },
        },
        {
            "title": "因式定理 / Factor Theorem",
            "mixed": {
                "blanks": [
                    ("若代入 c 后多项式值为 0，则对应一次因式是____________。", "x-c"),
                ],
                "choices": [
                    {
                        "question": "因式定理和余数定理的关系最准确的是 / Which best describes the relation between the factor theorem and the remainder theorem?",
                        "options": [
                            "A. 两者无关 / They are unrelated",
                            "B. 因式定理就是余数为零的特殊情形 / The factor theorem is the zero-remainder case of the remainder theorem",
                            "C. 余数定理只对常数有效 / The remainder theorem only works for constants",
                            "D. 因式定理不需要代入 / The factor theorem needs no substitution",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么说 f(c)=0 和 x-c 是因式是等价关系？",
                    "因式定理在高次整式分解里扮演什么角色？",
                    "为什么它不能脱离试根和整式除法单独理解？",
                ],
                "keypoints": [
                    "因为代入值就是除以 x-c 时的余数。",
                    "它负责确认一次因式是否存在。",
                    "因为确认因式后还要继续缩降次数。",
                ],
            },
        },
    ],
    "第2天 / Day 2": [
        {
            "title": "高次和差公式 / Higher-Power Sum and Difference",
            "mixed": {
                "blanks": [
                    ("x^n-y^n 总能分解，而 x^n+y^n 是否能分解首先看 n 的____________。", "奇偶性"),
                ],
                "choices": [
                    {
                        "question": "为什么纯 2 的幂次是课堂特别提醒的边界情况 / Why were pure powers of 2 emphasized as a boundary case?",
                        "options": [
                            "A. 因为它们都能直接分解 / Because they all factor directly",
                            "B. 因为它们通常不能继续拆成奇数倍结构去分解 / Because they usually cannot be rewritten into an odd-multiple structure for further factorization",
                            "C. 因为它们只和平方差有关 / Because they only relate to difference of squares",
                            "D. 因为它们没有次数 / Because they have no degree",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么 x^n+y^n 的分解判断要先看奇偶？",
                    "什么时候换元能把偶数次问题转成奇次问题？",
                    "为什么老师不建议机械套用和差公式？",
                ],
                "keypoints": [
                    "因为奇偶性直接决定符号结构是否允许出现一次因子。",
                    "当指数能拆成偶数乘奇数时。",
                    "因为题目常常更关心结构而不是固定公式样子。",
                ],
            },
        },
        {
            "title": "路径选择 / Choosing a Factorization Path",
            "mixed": {
                "blanks": [
                    ("同一个式子若有两种拆法，课堂强调要根据题目需求选择更合适的____________。", "路径"),
                ],
                "choices": [
                    {
                        "question": "若题目要整体因式分解，通常更偏向 / If the problem wants a complete factorization, which path is usually more helpful?",
                        "options": [
                            "A. 更有利于继续整体拆开的路径 / The path that helps continue the overall factorization",
                            "B. 只关心某项系数的路径 / The path that only highlights one coefficient",
                            "C. 只做数值检验 / Numerical testing only",
                            "D. 随机选择 / Choose randomly",
                        ],
                        "answer": "A",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么同一个式子可以有多条等价分解路径？",
                    "求系数和做整体分解时，路径选择为什么不同？",
                    "怎样判断哪条路径更省力？",
                ],
                "keypoints": [
                    "因为不同公式本质上描述的是同一代数结构。",
                    "因为题目目标不同，暴露出的结构也不同。",
                    "看哪条路更快暴露目标信息。",
                ],
            },
        },
    ],
    "第7天 / Day 7": [
        {
            "title": "轮换对称 / Cyclic Symmetry",
            "mixed": {
                "blanks": [
                    ("轮换对称的核心不是字母名字，而是变量位置轮换后式子的____________保持。", "结构"),
                ],
                "choices": [
                    {
                        "question": "看到 x^2+y^2+z^2+xy+yz+zx 这类式子，先该想什么 / What should you think of first for expressions like x^2+y^2+z^2+xy+yz+zx?",
                        "options": [
                            "A. 只做代值 / Only plug in values",
                            "B. 先看轮换对称与完全平方式的联系 / First look for cyclic symmetry and its link to complete-square structures",
                            "C. 先用因式定理 / Use the factor theorem first",
                            "D. 先做整式除法 / Do polynomial division first",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "轮换对称为什么是这节课的隐藏主线？",
                    "三元式里怎样快速看出它和完全平方式有关？",
                    "为什么变量轮换不变会帮助我们做变形？",
                ],
                "keypoints": [
                    "因为很多看似不同的式子底层结构是同类的。",
                    "看平方项与交叉项是否成组出现。",
                    "因为说明结构有稳定性，可以大胆重组和配凑。",
                ],
            },
        },
        {
            "title": "高维展开 / Higher-Dimensional Expansion",
            "mixed": {
                "blanks": [
                    ("四元平方展开里，交叉项个数可由____________数得到。", "组合"),
                ],
                "choices": [
                    {
                        "question": "更高维展开时，课堂更推荐哪种策略 / Which strategy did the class prefer for higher-dimensional expansion?",
                        "options": [
                            "A. 一次性死记完整公式 / Memorize the full formula at once",
                            "B. 先分组，再分步展开 / Group first, then expand step by step",
                            "C. 直接放弃 / Give up directly",
                            "D. 只代数字 / Only plug in numbers",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么高维展开更适合分步而不是死记？",
                    "交叉项个数为什么和组合数直接相关？",
                    "其次性在高维展开里提供了什么检查标准？",
                ],
                "keypoints": [
                    "因为公式太长但结构重复，分步更稳。",
                    "因为交叉项本质上是在若干变量中选出配对。",
                    "它能检查是否漏项或次数不一致。",
                ],
            },
        },
    ],
    "第14天 / Day 14": [
        {
            "title": "有理根判定 / Rational Root Test",
            "mixed": {
                "blanks": [
                    ("若有理根写成最简分数 p/q，则 p 整除常数项，q 整除____________项。", "首"),
                ],
                "choices": [
                    {
                        "question": "为什么有理根判定法能显著提速 / Why does the rational root theorem speed things up so much?",
                        "options": [
                            "A. 因为它直接给出答案 / It directly gives the answer",
                            "B. 因为它把无限试根缩到有限候选集合 / It shrinks infinite trial values to a finite candidate set",
                            "C. 因为它不需要代入 / It needs no substitution",
                            "D. 因为它能替代因式定理 / It replaces the factor theorem",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么高次整式不可能靠盲目试根高效解决？",
                    "p 整除常数项、q 整除首项这个结论实际帮了什么忙？",
                    "有理根判定和因式定理分别负责什么步骤？",
                ],
                "keypoints": [
                    "因为候选值太多，必须先压缩范围。",
                    "它把候选值限制在有限个整除关系上。",
                    "一个负责缩小范围，一个负责验证是否为因式。",
                ],
            },
        },
        {
            "title": "整式分解流程 / Polynomial Factorization Workflow",
            "mixed": {
                "blanks": [
                    ("找到一次因式以后，下一步通常是做____________除法把次数降下来。", "整式"),
                ],
                "choices": [
                    {
                        "question": "若四次式先提取出一个一次因式，后面常见的处理是 / After extracting one linear factor from a quartic, what usually comes next?",
                        "options": [
                            "A. 停止计算 / Stop immediately",
                            "B. 继续求商式并看能否二次分解 / Compute the quotient and see whether the remaining polynomial can factor further",
                            "C. 改回展开 / Go back to expansion",
                            "D. 只看常数项 / Only inspect constants",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么因式分解是一个降次数的连续过程？",
                    "整式除法在这个流程里承担什么作用？",
                    "什么时候二次商式可以交给十字相乘或公式法？",
                ],
                "keypoints": [
                    "因为每提取一个因子都在把问题变简单。",
                    "它把已确认的因子从原式里准确剥离出来。",
                    "当剩余式子已经降到标准二次结构时。",
                ],
            },
        },
    ],
    "第30天 / Day 30": [
        {
            "title": "结构识别总复盘 / Structure Recognition Synthesis",
            "mixed": {
                "blanks": [
                    ("看到二项式先想展开结构，看到高次和差式先想____________，看到整系数多项式先想试根。", "奇偶性"),
                ],
                "choices": [
                    {
                        "question": "哪一项最能体现这节课的方法迁移 / Which best shows method transfer from this lesson?",
                        "options": [
                            "A. 只记住具体公式写法 / Remember only specific formula shapes",
                            "B. 看到式子先识别结构，再选展开、分解、轮换对称或试根 / Identify structure first, then choose expansion, factorization, cyclic symmetry, or root testing",
                            "C. 先背小册子页码 / Memorize booklet page numbers first",
                            "D. 先做数值代入 / Plug in numbers first",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "一个月后你最该保留下来的三个入口词是什么？",
                    "看到新题时你的判断顺序应该是什么？",
                    "这节课哪些地方最能体现“理解优于记忆”？",
                ],
                "keypoints": [
                    "展开结构、奇偶性判断、试根与因式。",
                    "先识别结构，再选工具，再做推导。",
                    "二项式系数来源、高次和差分解、因式定理工具链都很典型。",
                ],
            },
        },
        {
            "title": "长期记忆校验 / Long-Term Memory Check",
            "mixed": {
                "blanks": [
                    ("长期复习时，最该记住的不是孤立公式，而是结构判断与____________之间的对应关系。", "工具选择"),
                ],
                "choices": [
                    {
                        "question": "哪一项最符合这节课的长期目标 / Which best matches the long-term goal of the lesson?",
                        "options": [
                            "A. 只把公式背熟 / Memorize formulas only",
                            "B. 看到新式子能先判断属于哪类结构，再决定推导和工具 / Recognize the structural type first, then choose derivation and tools",
                            "C. 只会做课堂例题 / Only solve class examples",
                            "D. 每题都先整式除法 / Start every problem with polynomial division",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么这节课最不该留下的是零散公式表？",
                    "如果只剩 1 分钟复盘，你会先回想哪几个关键词？",
                    "请口头总结这节课最核心的 3 个方法提醒。",
                ],
                "keypoints": [
                    "因为离开结构判断，公式很难真正会用。",
                    "组合系数、奇偶性、轮换对称、因式定理。",
                    "先看结构、先会推导、先缩小候选范围。",
                ],
            },
        },
    ],
}


FINAL_REMINDER_LINES = [
    "看到二项式，不只背结果，要能解释系数为什么是这个数。",
    "看到高次和差式，先看奇偶性，再决定能不能换元或继续分解。",
    "看到多元代数式，先看轮换对称、其次性和交叉项结构。",
    "看到高次整系数多项式，先用有理根判定缩小范围，再用因式定理验证。",
    "每个复习日都要扫完整节课，不要只盯一个公式或一道题。",
]