"""意图识别模块单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.intent.keywords import (
    INTENT_KEYWORDS,
    get_all_keywords,
    get_intent_by_keyword,
    get_intent_description,
    get_intent_keywords,
)
from backend.agents.intent.recognizer import IntentRecognizer, IntentResult


class TestKeywords:
    """测试关键词库"""

    def test_intent_keywords_structure(self) -> None:
        """测试关键词库结构"""
        assert "descriptive_analysis" in INTENT_KEYWORDS
        assert "statistical_test" in INTENT_KEYWORDS
        assert "regression_analysis" in INTENT_KEYWORDS
        assert "survival_analysis" in INTENT_KEYWORDS
        assert "epidemiology_analysis" in INTENT_KEYWORDS
        assert "visualization" in INTENT_KEYWORDS

    def test_get_intent_keywords(self) -> None:
        """测试获取意图关键词"""
        keywords = get_intent_keywords("descriptive_analysis")
        assert "均值" in keywords
        assert "中位数" in keywords
        assert "标准差" in keywords

    def test_get_intent_keywords_not_found(self) -> None:
        """测试获取不存在的意图关键词"""
        keywords = get_intent_keywords("nonexistent_intent")
        assert keywords == []

    def test_get_all_keywords(self) -> None:
        """测试获取所有关键词"""
        all_keywords = get_all_keywords()
        assert len(all_keywords) > 0
        assert "均值" in all_keywords
        assert "t检验" in all_keywords

    def test_get_intent_by_keyword(self) -> None:
        """测试根据关键词获取意图"""
        intent = get_intent_by_keyword("均值")
        assert intent == "descriptive_analysis"

        intent = get_intent_by_keyword("t检验")
        assert intent == "statistical_test"

    def test_get_intent_by_keyword_case_insensitive(self) -> None:
        """测试关键词匹配不区分大小写"""
        intent = get_intent_by_keyword("T检验")
        assert intent == "statistical_test"

    def test_get_intent_by_keyword_not_found(self) -> None:
        """测试关键词不存在"""
        intent = get_intent_by_keyword("不存在的关键词xyz")
        assert intent is None

    def test_get_intent_description(self) -> None:
        """测试获取意图描述"""
        desc = get_intent_description("descriptive_analysis")
        assert "基本统计描述" in desc

    def test_get_intent_description_not_found(self) -> None:
        """测试获取不存在的意图描述"""
        desc = get_intent_description("nonexistent_intent")
        assert desc == ""


class TestIntentResult:
    """测试意图识别结果"""

    def test_intent_result_creation(self) -> None:
        """测试创建意图识别结果"""
        result = IntentResult(
            intent="descriptive_analysis",
            confidence=0.95,
            reason="关键词匹配成功",
        )
        assert result.intent == "descriptive_analysis"
        assert result.confidence == 0.95
        assert result.reason == "关键词匹配成功"


class TestIntentRecognizer:
    """测试意图识别器"""

    def test_init_without_llm(self) -> None:
        """测试不带 LLM 初始化"""
        recognizer = IntentRecognizer()
        assert recognizer._llm is None
        assert recognizer._llm_client is None

    def test_init_with_llm(self) -> None:
        """测试带 LLM 初始化"""
        mock_llm = MagicMock()
        recognizer = IntentRecognizer(llm=mock_llm)
        assert recognizer._llm == mock_llm

    def test_keyword_match_exact(self) -> None:
        """测试关键词完全匹配"""
        recognizer = IntentRecognizer()
        intent, confidence = recognizer._keyword_match("均值")
        assert intent == "descriptive_analysis"
        assert confidence == 1.0

    def test_keyword_match_partial(self) -> None:
        """测试关键词部分匹配"""
        recognizer = IntentRecognizer()
        intent, confidence = recognizer._keyword_match("请计算均值和中位数")
        assert intent == "descriptive_analysis"
        assert confidence > 0

    def test_keyword_match_no_match(self) -> None:
        """测试关键词无匹配"""
        recognizer = IntentRecognizer()
        intent, confidence = recognizer._keyword_match("这是一段没有任何关键词的文本")
        assert intent is None
        assert confidence == 0.0

    def test_keyword_match_multiple_intents(self) -> None:
        """测试多个意图关键词匹配"""
        recognizer = IntentRecognizer()
        intent, confidence = recognizer._keyword_match("进行t检验和回归分析")
        assert intent is not None
        assert confidence > 0

    def test_get_supported_intents(self) -> None:
        """测试获取支持的意图列表"""
        recognizer = IntentRecognizer()
        intents = recognizer.get_supported_intents()
        assert "descriptive_analysis" in intents
        assert "statistical_test" in intents
        assert "regression_analysis" in intents

    def test_get_intent_info(self) -> None:
        """测试获取意图信息"""
        recognizer = IntentRecognizer()
        info = recognizer.get_intent_info("descriptive_analysis")
        assert info is not None
        assert info["id"] == "descriptive_analysis"
        assert "name" in info
        assert "description" in info
        assert "keywords" in info

    def test_get_intent_info_not_found(self) -> None:
        """测试获取不存在的意图信息"""
        recognizer = IntentRecognizer()
        info = recognizer.get_intent_info("nonexistent_intent")
        assert info is None

    @pytest.mark.asyncio
    async def test_recognize_keyword_match_high_confidence(self) -> None:
        """测试高置信度关键词匹配"""
        recognizer = IntentRecognizer()
        result = await recognizer.recognize("请计算数据的均值和标准差")
        assert result.intent == "descriptive_analysis"
        assert result.confidence >= 0.7
        assert "关键词匹配" in result.reason

    @pytest.mark.asyncio
    async def test_recognize_keyword_match_statistical_test(self) -> None:
        """测试统计检验意图识别"""
        recognizer = IntentRecognizer()
        result = await recognizer.recognize("进行t检验比较两组差异")
        assert result.intent == "statistical_test"
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_recognize_keyword_match_regression(self) -> None:
        """测试回归分析意图识别"""
        recognizer = IntentRecognizer()
        result = await recognizer.recognize("建立logistic回归模型")
        assert result.intent == "regression_analysis"
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_recognize_keyword_match_survival(self) -> None:
        """测试生存分析意图识别"""
        recognizer = IntentRecognizer()
        result = await recognizer.recognize("绘制kaplan-meier生存曲线")
        assert result.intent == "survival_analysis"
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_recognize_keyword_match_visualization(self) -> None:
        """测试可视化意图识别"""
        recognizer = IntentRecognizer()
        result = await recognizer.recognize("绘制柱状图展示数据")
        assert result.intent == "visualization"
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_recognize_llm_fallback(self) -> None:
        """测试 LLM 回退分类"""
        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=IntentResult(
            intent="descriptive_analysis",
            confidence=0.85,
            reason="LLM 分类结果",
        ))
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        recognizer = IntentRecognizer(llm=mock_llm)
        result = await recognizer.recognize("分析这组数据的特征")

        assert result.intent == "descriptive_analysis"
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_recognize_llm_error_fallback(self) -> None:
        """测试 LLM 错误时的回退"""
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(side_effect=Exception("LLM Error"))

        recognizer = IntentRecognizer(llm=mock_llm)
        result = await recognizer.recognize("这是一段完全没有任何匹配关键词的文本xyzabc")

        assert result.intent == "general_query"
        assert result.confidence == 0.5
        assert "无法识别" in result.reason

    def test_recognize_sync(self) -> None:
        """测试同步识别"""
        recognizer = IntentRecognizer()
        result = recognizer.recognize_sync("计算均值")
        assert result.intent == "descriptive_analysis"
        assert result.confidence >= 0.7


class TestIntentRecognitionAccuracy:
    """测试意图识别准确率"""

    @pytest.fixture
    def recognizer(self) -> IntentRecognizer:
        """创建识别器实例"""
        return IntentRecognizer()

    @pytest.mark.asyncio
    async def test_descriptive_analysis_accuracy(self, recognizer: IntentRecognizer) -> None:
        """测试描述性分析识别准确率"""
        test_cases = [
            ("计算均值和标准差", "descriptive_analysis"),
            ("数据的基本统计描述", "descriptive_analysis"),
            ("频数分布分析", "descriptive_analysis"),
            ("中位数和四分位数", "descriptive_analysis"),
        ]

        correct = 0
        for query, expected_intent in test_cases:
            result = await recognizer.recognize(query)
            if result.intent == expected_intent:
                correct += 1

        accuracy = correct / len(test_cases)
        assert accuracy >= 0.85

    @pytest.mark.asyncio
    async def test_statistical_test_accuracy(self, recognizer: IntentRecognizer) -> None:
        """测试统计检验识别准确率"""
        test_cases = [
            ("进行t检验", "statistical_test"),
            ("卡方检验分析", "statistical_test"),
            ("方差分析ANOVA", "statistical_test"),
            ("显著性差异检验", "statistical_test"),
        ]

        correct = 0
        for query, expected_intent in test_cases:
            result = await recognizer.recognize(query)
            if result.intent == expected_intent:
                correct += 1

        accuracy = correct / len(test_cases)
        assert accuracy >= 0.85

    @pytest.mark.asyncio
    async def test_regression_analysis_accuracy(self, recognizer: IntentRecognizer) -> None:
        """测试回归分析识别准确率"""
        test_cases = [
            ("建立线性回归模型", "regression_analysis"),
            ("logistic回归分析", "regression_analysis"),
            ("分析风险因素", "regression_analysis"),
            ("多元回归", "regression_analysis"),
        ]

        correct = 0
        for query, expected_intent in test_cases:
            result = await recognizer.recognize(query)
            if result.intent == expected_intent:
                correct += 1

        accuracy = correct / len(test_cases)
        assert accuracy >= 0.85

    @pytest.mark.asyncio
    async def test_survival_analysis_accuracy(self, recognizer: IntentRecognizer) -> None:
        """测试生存分析识别准确率"""
        test_cases = [
            ("生存分析", "survival_analysis"),
            ("kaplan-meier曲线", "survival_analysis"),
            ("绘制生存曲线", "survival_analysis"),
            ("计算生存率", "survival_analysis"),
        ]

        correct = 0
        for query, expected_intent in test_cases:
            result = await recognizer.recognize(query)
            if result.intent == expected_intent:
                correct += 1

        accuracy = correct / len(test_cases)
        assert accuracy >= 0.85

    @pytest.mark.asyncio
    async def test_visualization_accuracy(self, recognizer: IntentRecognizer) -> None:
        """测试可视化识别准确率"""
        test_cases = [
            ("绘制柱状图", "visualization"),
            ("数据可视化", "visualization"),
            ("画一个散点图", "visualization"),
            ("生成箱线图", "visualization"),
        ]

        correct = 0
        for query, expected_intent in test_cases:
            result = await recognizer.recognize(query)
            if result.intent == expected_intent:
                correct += 1

        accuracy = correct / len(test_cases)
        assert accuracy >= 0.85
