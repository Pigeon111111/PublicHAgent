"""意图识别端到端测试

测试意图识别模块的完整功能。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.intent.recognizer import IntentRecognizer, IntentResult
from backend.agents.intent.keywords import INTENT_KEYWORDS


class TestIntentRecognitionE2E:
    """意图识别端到端测试"""

    @pytest.fixture
    def recognizer(self) -> IntentRecognizer:
        """创建意图识别器"""
        return IntentRecognizer()

    def test_recognizer_initialization(self, recognizer: IntentRecognizer) -> None:
        """测试识别器初始化"""
        assert recognizer is not None
        assert recognizer.CONFIDENCE_THRESHOLD == 0.7

    def test_get_supported_intents(self, recognizer: IntentRecognizer) -> None:
        """测试获取支持的意图列表"""
        intents = recognizer.get_supported_intents()
        assert isinstance(intents, list)
        assert len(intents) > 0
        assert "descriptive_analysis" in intents
        assert "visualization" in intents

    def test_get_intent_info(self, recognizer: IntentRecognizer) -> None:
        """测试获取意图详细信息"""
        info = recognizer.get_intent_info("descriptive_analysis")
        assert info is not None
        assert "name" in info
        assert "description" in info
        assert "keywords" in info

    def test_get_intent_info_invalid(self, recognizer: IntentRecognizer) -> None:
        """测试获取无效意图信息"""
        info = recognizer.get_intent_info("invalid_intent")
        assert info is None

    @pytest.mark.asyncio
    async def test_keyword_exact_match(self, recognizer: IntentRecognizer) -> None:
        """测试关键词完全匹配"""
        intent, confidence = recognizer._keyword_match("描述性分析")
        assert intent is not None
        assert confidence == 1.0

    @pytest.mark.asyncio
    async def test_keyword_partial_match(self, recognizer: IntentRecognizer) -> None:
        """测试关键词部分匹配"""
        intent, confidence = recognizer._keyword_match("请帮我做一个描述性分析")
        assert intent is not None
        assert confidence >= 0.7

    @pytest.mark.asyncio
    async def test_keyword_no_match(self, recognizer: IntentRecognizer) -> None:
        """测试关键词不匹配"""
        intent, confidence = recognizer._keyword_match("今天天气很好")
        assert intent is None
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_recognize_with_keyword_match(self, recognizer: IntentRecognizer) -> None:
        """测试关键词匹配识别"""
        result = await recognizer.recognize("请进行描述性分析")
        assert isinstance(result, IntentResult)
        assert result.intent in INTENT_KEYWORDS
        assert 0 <= result.confidence <= 1
        assert result.reason != ""

    @pytest.mark.asyncio
    async def test_recognize_visualization_intent(self, recognizer: IntentRecognizer) -> None:
        """测试可视化意图识别"""
        result = await recognizer.recognize("画一个柱状图")
        assert result.intent == "visualization"

    @pytest.mark.asyncio
    async def test_recognize_data_cleaning_intent(self, recognizer: IntentRecognizer) -> None:
        """测试数据清洗意图识别"""
        result = await recognizer.recognize("帮我进行数据清洗")
        assert result.intent == "data_cleaning"

    @pytest.mark.asyncio
    async def test_recognize_statistical_test_intent(self, recognizer: IntentRecognizer) -> None:
        """测试统计检验意图识别"""
        result = await recognizer.recognize("进行t检验")
        assert result.intent == "statistical_test"

    @pytest.mark.asyncio
    async def test_recognize_correlation_intent(self, recognizer: IntentRecognizer) -> None:
        """测试回归分析意图识别"""
        result = await recognizer.recognize("进行回归分析")
        assert result.intent == "regression_analysis"

    @pytest.mark.asyncio
    async def test_recognize_visualization_intent_2(self, recognizer: IntentRecognizer) -> None:
        """测试可视化意图识别"""
        result = await recognizer.recognize("生成图表")
        assert result.intent == "visualization"

    def test_sync_recognize(self, recognizer: IntentRecognizer) -> None:
        """测试同步识别"""
        result = recognizer.recognize_sync("描述性分析")
        assert isinstance(result, IntentResult)
        assert result.intent in INTENT_KEYWORDS


class TestIntentRecognitionWithMockedLLM:
    """使用模拟 LLM 的意图识别测试"""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """创建模拟 LLM"""
        llm = MagicMock()
        mock_result = IntentResult(
            intent="descriptive_analysis",
            confidence=0.85,
            reason="LLM 分类结果",
        )
        llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=mock_result)
        return llm

    @pytest.fixture
    def recognizer_with_mock(self, mock_llm: MagicMock) -> IntentRecognizer:
        """创建带模拟 LLM 的识别器"""
        return IntentRecognizer(llm=mock_llm)

    @pytest.mark.asyncio
    async def test_llm_classification(
        self,
        recognizer_with_mock: IntentRecognizer,
    ) -> None:
        """测试 LLM 分类"""
        result = await recognizer_with_mock.recognize("这是一个复杂的分析请求")
        assert isinstance(result, IntentResult)
        assert result.intent == "descriptive_analysis"

    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self, mock_llm: MagicMock) -> None:
        """测试 LLM 错误时的回退"""
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
            side_effect=Exception("LLM 错误")
        )
        recognizer = IntentRecognizer(llm=mock_llm)

        result = await recognizer.recognize("描述性分析")
        assert result.intent == "descriptive_analysis"


class TestIntentKeywords:
    """意图关键词测试"""

    def test_all_intents_have_keywords(self) -> None:
        """测试所有意图都有关键词"""
        for intent, data in INTENT_KEYWORDS.items():
            assert "name" in data, f"意图 {intent} 缺少 name"
            assert "description" in data, f"意图 {intent} 缺少 description"
            assert "keywords" in data, f"意图 {intent} 缺少 keywords"
            assert len(data["keywords"]) > 0, f"意图 {intent} 关键词为空"

    def test_keywords_are_strings(self) -> None:
        """测试关键词都是字符串"""
        for intent, data in INTENT_KEYWORDS.items():
            for keyword in data["keywords"]:
                assert isinstance(keyword, str), f"意图 {intent} 的关键词 {keyword} 不是字符串"

    def test_no_duplicate_intents(self) -> None:
        """测试没有重复的意图"""
        intents = list(INTENT_KEYWORDS.keys())
        assert len(intents) == len(set(intents))


class TestIntentConfidence:
    """意图置信度测试"""

    @pytest.fixture
    def recognizer(self) -> IntentRecognizer:
        """创建意图识别器"""
        return IntentRecognizer()

    def test_confidence_calculation(self, recognizer: IntentRecognizer) -> None:
        """测试置信度计算"""
        confidence = recognizer._calculate_confidence(
            query="描述性分析",
            matched_keywords=["描述性分析"],
            total_keywords=5,
        )
        assert 0 <= confidence <= 1

    def test_confidence_with_no_matches(self, recognizer: IntentRecognizer) -> None:
        """测试无匹配时的置信度"""
        confidence = recognizer._calculate_confidence(
            query="测试查询",
            matched_keywords=[],
            total_keywords=5,
        )
        assert confidence == 0.0

    def test_confidence_bounds(self, recognizer: IntentRecognizer) -> None:
        """测试置信度边界"""
        confidence = recognizer._calculate_confidence(
            query="a",
            matched_keywords=["a"],
            total_keywords=1,
        )
        assert confidence <= 1.0
