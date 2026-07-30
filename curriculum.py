import random

# curriculum.py —— 学科知识点图谱（诊断/出题锚点）
#
# Phase 1 仅开放：数学 · 八年级（人教版）。
# 每个知识点含：
#   id     知识点唯一 id
#   name   知识点名称
#   weight 出题权重（越大越容易被选入诊断卷）
#   quiz   离线兜底选择题：{q, options[4], a(正确下标0-3), exp}
#          保证离线/MOCK 模式下诊断卷仍然正确可用。
#
# 后续扩展：在 CURRICULUM 中追加 {学科: {年级: [章节...]}} 即可，
# 后端 /diagnose、/curriculum 与前端诊断视图会自动适配。

# ===== 八年级 · 数学（人教版） =====
_MATH_G8 = [
    {
        "chapter": "三角形",
        "points": [
            {"id": "tri-1", "name": "三角形三边关系", "weight": 3,
             "quiz": {"q": "三角形任意两边之和与第三边的关系是？", "options": ["大于", "小于", "等于", "无法确定"], "a": 0,
                      "exp": "三角形任意两边之和大于第三边，任意两边之差小于第三边。"}},
            {"id": "tri-2", "name": "三角形内角和", "weight": 3,
             "quiz": {"q": "三角形三个内角的和是多少度？", "options": ["90°", "180°", "270°", "360°"], "a": 1,
                      "exp": "三角形内角和恒为 180°。"}},
            {"id": "tri-3", "name": "三角形外角性质", "weight": 2,
             "quiz": {"q": "三角形的一个外角与和它不相邻的两个内角的关系是？", "options": ["等于两内角和", "大于两内角和", "小于较大内角", "等于较大内角"], "a": 0,
                      "exp": "三角形外角等于与它不相邻的两个内角之和。"}},
            {"id": "tri-4", "name": "多边形内角和", "weight": 2,
             "quiz": {"q": "n 边形的内角和公式是？", "options": ["(n-1)×180°", "(n-2)×180°", "n×180°", "(n+2)×180°"], "a": 1,
                      "exp": "n 边形内角和为 (n-2)×180°。"}},
        ],
    },
    {
        "chapter": "全等三角形",
        "points": [
            {"id": "cong-1", "name": "全等三角形判定", "weight": 3,
             "quiz": {"q": "下列条件中，不能判定两个三角形全等的是？", "options": ["SSS", "SAS", "AAA", "ASA"], "a": 2,
                      "exp": "AAA 只能证相似，不能证全等（边长可缩放）。"}},
            {"id": "cong-2", "name": "直角三角形全等 HL", "weight": 2,
             "quiz": {"q": "直角三角形全等的 HL 判定指的是？", "options": ["斜边和一条直角边对应相等", "两直角边对应相等", "两锐角对应相等", "斜边和一锐角对应相等"], "a": 0,
                      "exp": "HL：斜边和一条直角边对应相等的两个直角三角形全等。"}},
            {"id": "cong-3", "name": "角平分线性质", "weight": 2,
             "quiz": {"q": "角平分线上的点到角两边的距离？", "options": ["相等", "不相等", "与边长有关", "无法确定"], "a": 0,
                      "exp": "角平分线上的点到角两边的距离相等。"}},
        ],
    },
    {
        "chapter": "轴对称",
        "points": [
            {"id": "axis-1", "name": "轴对称性质", "weight": 2,
             "quiz": {"q": "轴对称图形沿对称轴对折后，下列说法正确的是？", "options": ["两部分重合", "对应点关于对称轴对称", "对应点到对称轴距离相等", "以上都对"], "a": 3,
                      "exp": "轴对称图形对折后完全重合，对应点关于对称轴对称且到对称轴距离相等。"}},
            {"id": "axis-2", "name": "等腰三角形性质", "weight": 3,
             "quiz": {"q": "等腰三角形的两个底角？", "options": ["相等", "互补", "和为 90°", "不确定"], "a": 0,
                      "exp": "等腰三角形两底角相等（等边对等角）。"}},
            {"id": "axis-3", "name": "等边三角形性质", "weight": 2,
             "quiz": {"q": "等边三角形的每个内角是多少度？", "options": ["45°", "60°", "90°", "120°"], "a": 1,
                      "exp": "等边三角形三个角均为 60°。"}},
        ],
    },
    {
        "chapter": "整式乘法与因式分解",
        "points": [
            {"id": "poly-1", "name": "幂的运算", "weight": 3,
             "quiz": {"q": "计算 a³·a⁴ 的结果是？", "options": ["a⁷", "a¹²", "a⁶", "a"], "a": 0,
                      "exp": "同底数幂相乘，底数不变、指数相加：a³·a⁴ = a⁷。"}},
            {"id": "poly-2", "name": "平方差公式", "weight": 3,
             "quiz": {"q": "(a+b)(a−b) 等于？", "options": ["a²+b²", "a²−b²", "a²+2ab+b²", "a²−2ab+b²"], "a": 1,
                      "exp": "平方差公式：(a+b)(a−b) = a²−b²。"}},
            {"id": "poly-3", "name": "完全平方公式", "weight": 3,
             "quiz": {"q": "(a+b)² 等于？", "options": ["a²+b²", "a²−b²", "a²+2ab+b²", "a²−2ab+b²"], "a": 2,
                      "exp": "完全平方公式：(a+b)² = a²+2ab+b²。"}},
            {"id": "poly-4", "name": "因式分解", "weight": 2,
             "quiz": {"q": "把 x²−9 因式分解的结果是？", "options": ["(x−3)²", "(x+3)(x−3)", "x(x−9)", "(x−9)(x+1)"], "a": 1,
                      "exp": "x²−9 是平方差，分解为 (x+3)(x−3)。"}},
        ],
    },
    {
        "chapter": "分式",
        "points": [
            {"id": "frac-1", "name": "分式有意义的条件", "weight": 2,
             "quiz": {"q": "分式 1/(x−2) 有意义的条件是？", "options": ["x≠2", "x=2", "x≠0", "x 为任意实数"], "a": 0,
                      "exp": "分母不能为 0，故 x−2≠0 即 x≠2。"}},
            {"id": "frac-2", "name": "解分式方程", "weight": 3,
             "quiz": {"q": "解分式方程时必不可少的关键步骤是？", "options": ["去分母化为整式方程", "直接开平方", "两边平方", "因式分解"], "a": 0,
                      "exp": "分式方程通常先去分母化为整式方程，最后必须检验增根。"}},
            {"id": "frac-3", "name": "分式乘除法", "weight": 2,
             "quiz": {"q": "计算 (a/b)·(c/d) 的结果是？", "options": ["ac/bd", "(a+c)/(b+d)", "ad/bc", "ac/(b+d)"], "a": 0,
                      "exp": "分式乘法：分子乘分子、分母乘分母，即 ac/bd。"}},
        ],
    },
    {
        "chapter": "二次根式",
        "points": [
            {"id": "rad-1", "name": "二次根式有意义", "weight": 2,
             "quiz": {"q": "二次根式 √(x−1) 在实数范围内有意义的条件是？", "options": ["x≥1", "x>1", "x≤1", "x 为任意实数"], "a": 0,
                      "exp": "被开方数须非负：x−1≥0，即 x≥1。"}},
            {"id": "rad-2", "name": "二次根式乘除", "weight": 2,
             "quiz": {"q": "√2·√8 的结果是？", "options": ["√10", "4", "16", "√16"], "a": 1,
                      "exp": "√2·√8 = √16 = 4。"}},
            {"id": "rad-3", "name": "二次根式加减", "weight": 2,
             "quiz": {"q": "√18+√2 化简后等于？", "options": ["√20", "4√2", "2√2", "3√2"], "a": 1,
                      "exp": "√18 = 3√2，故 √18+√2 = 4√2。"}},
        ],
    },
    {
        "chapter": "勾股定理",
        "points": [
            {"id": "pyth-1", "name": "勾股定理", "weight": 3,
             "quiz": {"q": "直角三角形中两直角边分别为 3 和 4，斜边为？", "options": ["5", "6", "7", "25"], "a": 0,
                      "exp": "3²+4² = 25，斜边 = 5。"}},
            {"id": "pyth-2", "name": "勾股定理逆定理", "weight": 2,
             "quiz": {"q": "三边长分别为 3、4、5 的三角形是？", "options": ["锐角三角形", "直角三角形", "钝角三角形", "等腰三角形"], "a": 1,
                      "exp": "3²+4² = 5²，满足勾股定理逆定理，是直角三角形。"}},
            {"id": "pyth-3", "name": "勾股定理关系", "weight": 2,
             "quiz": {"q": "直角三角形中，斜边 c 与直角边 a、b 的关系是？", "options": ["c²=a²+b²", "c=a+b", "c²=a²−b²", "c=ab"], "a": 0,
                      "exp": "勾股定理：直角三角形两直角边的平方和等于斜边的平方。"}},
        ],
    },
    {
        "chapter": "平行四边形",
        "points": [
            {"id": "para-1", "name": "平行四边形性质", "weight": 3,
             "quiz": {"q": "平行四边形的对角线？", "options": ["互相垂直", "互相平分", "相等", "垂直平分"], "a": 1,
                      "exp": "平行四边形对角线互相平分。"}},
            {"id": "para-2", "name": "平行四边形判定", "weight": 2,
             "quiz": {"q": "下列条件能判定四边形是平行四边形的是？", "options": ["一组对边平行", "两组对边分别相等", "一组对角相等", "对角线互相垂直"], "a": 1,
                      "exp": "两组对边分别相等的四边形是平行四边形。"}},
            {"id": "para-3", "name": "矩形性质", "weight": 2,
             "quiz": {"q": "矩形的对角线？", "options": ["互相垂直", "相等", "不相等", "垂直平分"], "a": 1,
                      "exp": "矩形对角线互相平分且相等。"}},
            {"id": "para-4", "name": "菱形性质", "weight": 2,
             "quiz": {"q": "菱形的对角线互相垂直且？", "options": ["相等", "平分每组对角", "平行", "和为 180°"], "a": 1,
                      "exp": "菱形对角线互相垂直，并且每条对角线平分一组对角。"}},
            {"id": "para-5", "name": "正方形性质", "weight": 2,
             "quiz": {"q": "正方形同时具备下列哪两组图形的性质？", "options": ["平行四边形与梯形", "矩形与菱形", "梯形与菱形", "矩形与梯形"], "a": 1,
                      "exp": "正方形既是特殊的矩形，又是特殊的菱形。"}},
        ],
    },
    {
        "chapter": "一次函数",
        "points": [
            {"id": "func-1", "name": "函数概念", "weight": 2,
             "quiz": {"q": "下列描述中，能表示 y 是 x 的函数的是？", "options": ["一个 x 对应两个 y", "每个 x 有唯一确定的 y", "x 与 y 无关", "y 随 x 无限增大"], "a": 1,
                      "exp": "函数要求对每个自变量 x 都有唯一确定的 y 值。"}},
            {"id": "func-2", "name": "一次函数解析式", "weight": 3,
             "quiz": {"q": "一次函数 y=kx+b (k≠0) 中，k 决定？", "options": ["与 y 轴交点", "增减性（斜率）", "与 x 轴交点", "常数项"], "a": 1,
                      "exp": "k 为斜率，决定函数的增减性与图象倾斜程度。"}},
            {"id": "func-3", "name": "一次函数图象", "weight": 2,
             "quiz": {"q": "函数 y=2x+1 的图象经过？", "options": ["一、二、三象限", "一、二、四象限", "二、三、四象限", "一、三、四象限"], "a": 0,
                      "exp": "k=2>0、b=1>0，图象经过一、二、三象限。"}},
            {"id": "func-4", "name": "待定系数法", "weight": 2,
             "quiz": {"q": "已知一次函数过 (0,1) 和 (1,3)，其解析式为？", "options": ["y=2x+1", "y=x+1", "y=3x", "y=2x−1"], "a": 0,
                      "exp": "代入可得 k=2、b=1，即 y=2x+1。"}},
        ],
    },
    {
        "chapter": "数据的分析",
        "points": [
            {"id": "data-1", "name": "平均数", "weight": 2,
             "quiz": {"q": "数据 2、4、6 的平均数是？", "options": ["3", "4", "12", "2"], "a": 1,
                      "exp": "(2+4+6)/3 = 4。"}},
            {"id": "data-2", "name": "中位数", "weight": 2,
             "quiz": {"q": "数据 1、3、5、7、9 的中位数是？", "options": ["3", "5", "7", "4"], "a": 1,
                      "exp": "奇数个数据取排序后的中间值 5。"}},
            {"id": "data-3", "name": "众数", "weight": 2,
             "quiz": {"q": "数据 2、2、3、5 的众数是？", "options": ["2", "3", "5", "无"], "a": 0,
                      "exp": "出现次数最多的数是 2。"}},
            {"id": "data-4", "name": "方差", "weight": 2,
             "quiz": {"q": "方差越大，说明数据？", "options": ["越集中", "波动越大", "平均数越大", "越稳定"], "a": 1,
                      "exp": "方差衡量波动大小，方差越大波动越大、越不稳定。"}},
        ],
    },
]

CURRICULUM = {
    "数学": {
        "八年级": _MATH_G8,
    }
}

SUPPORTED = {(s, g) for s, gs in CURRICULUM.items() for g in gs}


def get_curriculum(subject: str, grade: str) -> list:
    """返回该学科/年级的章节列表（每章含 points）。不支持则返回 []。"""
    return CURRICULUM.get(subject, {}).get(grade, []) or []


def get_all_points(subject: str, grade: str) -> list:
    """扁平化返回该学科/年级的全部知识点（含 quiz）。"""
    pts = []
    for ch in get_curriculum(subject, grade):
        pts.extend(ch.get("points", []))
    return pts


def sample_points(points: list, count: int, seed=None) -> list:
    """按 weight 加权无放回抽样 count 个知识点。count<=0 或大于总量时返回全部。"""
    if not points:
        return []
    if count <= 0 or count >= len(points):
        return list(points)
    rng = random.Random(seed)
    chosen = rng.choices(points, weights=[max(1, p.get("weight", 1)) for p in points], k=count)
    # 去重保序
    seen, out = set(), []
    for p in chosen:
        if p["id"] not in seen:
            seen.add(p["id"])
            out.append(p)
    # 补足（若权重抽样巧合去重后不足）
    for p in points:
        if len(out) >= count:
            break
        if p["id"] not in seen:
            seen.add(p["id"])
            out.append(p)
    return out


def list_supported() -> list:
    return [{"subject": s, "grade": g} for s, g in SUPPORTED]
