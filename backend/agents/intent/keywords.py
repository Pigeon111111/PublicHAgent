"""公共卫生领域关键词库

定义各类分析意图的关键词，用于意图识别。
"""

from typing import Any

INTENT_KEYWORDS: dict[str, dict[str, Any]] = {
    "descriptive_analysis": {
        "name": "描述性分析",
        "keywords": [
            "描述性分析",
            "描述统计",
            "描述性统计",
            "基本统计",
            "汇总统计",
            "频数",
            "频率",
            "百分比",
            "均值",
            "平均数",
            "中位数",
            "标准差",
            "方差",
            "最大值",
            "最小值",
            "范围",
            "四分位数",
            "分布",
            "数据概况",
            "数据概览",
            "数据摘要",
            "统计摘要",
            "基本描述",
            "数据分布",
        ],
        "description": "对数据进行基本统计描述，包括均值、中位数、标准差、频数等",
    },
    "statistical_test": {
        "name": "统计检验",
        "keywords": [
            "统计检验",
            "假设检验",
            "t检验",
            "t-test",
            "卡方检验",
            "chi-square",
            "方差分析",
            "anova",
            "显著性检验",
            "p值",
            "p-value",
            "差异检验",
            "比较检验",
            "正态性检验",
            "非参数检验",
            "秩和检验",
            "mann-whitney",
            "wilcoxon",
            "kruskal-wallis",
            "显著性差异",
            "统计显著性",
        ],
        "description": "进行各类统计假设检验，如t检验、卡方检验、方差分析等",
    },
    "regression_analysis": {
        "name": "回归分析",
        "keywords": [
            "回归分析",
            "回归",
            "线性回归",
            "logistic回归",
            "逻辑回归",
            "多元回归",
            "多重回归",
            "回归模型",
            "预测模型",
            "风险因素",
            "影响因素",
            "关联因素",
            "预测因子",
            "回归系数",
            "odds ratio",
            "比值比",
            "相对风险",
            "cox回归",
            "泊松回归",
            "广义线性模型",
            "glm",
        ],
        "description": "建立回归模型分析变量间的关系，包括线性回归、Logistic回归等",
    },
    "survival_analysis": {
        "name": "生存分析",
        "keywords": [
            "生存分析",
            "生存曲线",
            "kaplan-meier",
            "km曲线",
            "cox模型",
            "cox比例风险",
            "生存率",
            "生存时间",
            "生存期",
            "预后分析",
            "随访",
            "随访时间",
            "风险函数",
            "累积风险",
            "中位生存时间",
            "log-rank",
            "时序检验",
            "删失数据",
            "截尾数据",
            "生存函数",
            "死亡风险",
        ],
        "description": "分析生存时间和生存率，包括Kaplan-Meier曲线和Cox回归",
    },
    "epidemiology_analysis": {
        "name": "流行病学分析",
        "keywords": [
            "流行病学",
            "发病率",
            "患病率",
            "死亡率",
            "病死率",
            "感染率",
            "罹患率",
            "续发率",
            "相对危险度",
            "rr",
            "归因风险",
            "ar",
            "人群归因风险",
            "par",
            "标准化率",
            "标化率",
            "年龄标化",
            "性别标化",
            "疾病负担",
            "daly",
            "qaly",
            "寿命损失年",
            "yll",
            "伤残损失年",
            "yld",
            "暴发调查",
            "疫情分析",
            "传播动力学",
            "基本再生数",
            "r0",
            "有效再生数",
            "re",
        ],
        "description": "计算流行病学指标，如发病率、患病率、相对危险度等",
    },
    "visualization": {
        "name": "数据可视化",
        "keywords": [
            "可视化",
            "图表",
            "绘图",
            "画图",
            "作图",
            "柱状图",
            "条形图",
            "折线图",
            "饼图",
            "散点图",
            "箱线图",
            "直方图",
            "热力图",
            "地图",
            "趋势图",
            "森林图",
            "forest plot",
            "漏斗图",
            "funnel plot",
            "气泡图",
            "雷达图",
            "小提琴图",
            "误差棒图",
            "置信区间图",
            "生存曲线图",
            "展示",
            "呈现",
            "图形",
            "图像",
        ],
        "description": "创建各类统计图表进行数据可视化展示",
    },
    "data_cleaning": {
        "name": "数据清洗",
        "keywords": [
            "数据清洗",
            "数据预处理",
            "缺失值",
            "缺失数据",
            "异常值",
            "离群值",
            "重复值",
            "数据转换",
            "变量编码",
            "标准化",
            "归一化",
            "数据类型转换",
            "格式转换",
            "变量重命名",
            "变量标签",
            "数据校验",
            "数据质量",
            "数据整理",
            "数据合并",
            "数据筛选",
            "数据过滤",
        ],
        "description": "进行数据清洗和预处理，处理缺失值、异常值等",
    },
    "sample_size": {
        "name": "样本量计算",
        "keywords": [
            "样本量",
            "样本大小",
            "样本量计算",
            "样本量估计",
            "样本量确定",
            "power",
            "功效",
            "检验效能",
            "效应量",
            "alpha",
            "显著性水平",
            "置信水平",
            "抽样方法",
            "随机抽样",
            "分层抽样",
            "整群抽样",
            "样本设计",
        ],
        "description": "计算研究所需的样本量和检验效能",
    },
    "meta_analysis": {
        "name": "Meta分析",
        "keywords": [
            "meta分析",
            "荟萃分析",
            "系统综述",
            "系统评价",
            "文献综合",
            "定量综合",
            "合并效应",
            "异质性检验",
            "i2",
            "q检验",
            "发表偏倚",
            "敏感性分析",
            "亚组分析",
            "meta回归",
            "固定效应",
            "随机效应",
        ],
        "description": "进行Meta分析和系统综述",
    },
    "general_query": {
        "name": "一般查询",
        "keywords": [
            "查询",
            "查找",
            "搜索",
            "显示",
            "列出",
            "查看",
            "获取",
            "读取",
            "导出",
            "保存",
            "帮助",
            "说明",
            "介绍",
            "什么是",
            "如何",
            "怎么",
            "为什么",
        ],
        "description": "一般性数据查询和操作请求",
    },
}


def get_intent_keywords(intent: str) -> list[str]:
    """获取指定意图的关键词列表

    Args:
        intent: 意图名称

    Returns:
        关键词列表
    """
    if intent in INTENT_KEYWORDS:
        return list(INTENT_KEYWORDS[intent]["keywords"])
    return []


def get_all_keywords() -> list[str]:
    """获取所有关键词

    Returns:
        所有关键词列表
    """
    all_keywords = []
    for intent_data in INTENT_KEYWORDS.values():
        all_keywords.extend(intent_data["keywords"])
    return all_keywords


def get_intent_by_keyword(keyword: str) -> str | None:
    """根据关键词获取意图

    Args:
        keyword: 关键词

    Returns:
        意图名称，如果未找到则返回 None
    """
    keyword_lower = keyword.lower()
    for intent, data in INTENT_KEYWORDS.items():
        for kw in data["keywords"]:
            if kw.lower() == keyword_lower:
                return intent
    return None


def get_intent_description(intent: str) -> str:
    """获取意图描述

    Args:
        intent: 意图名称

    Returns:
        意图描述
    """
    if intent in INTENT_KEYWORDS:
        return str(INTENT_KEYWORDS[intent]["description"])
    return ""
