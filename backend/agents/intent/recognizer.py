"""意图识别器模块

实现基于关键词匹配和 LLM 分类的意图识别功能。
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from backend.agents.base.llm_client import LLMClient, invoke_structured_output
from backend.agents.intent.keywords import INTENT_KEYWORDS


class IntentResult(BaseModel):
    """意图识别结果"""

    intent: str = Field(description="识别出的意图类型")
    confidence: float = Field(description="置信度，范围 0-1")
    reason: str = Field(description="识别理由说明")


class IntentRecognizer:
    """意图识别器

    支持关键词匹配和 LLM 分类两种识别方式。
    关键词完全匹配时置信度为 1.0，部分匹配时计算置信度。
    当关键词匹配置信度低于阈值时，使用 LLM 进行分类。
    """

    CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, llm: BaseChatModel | None = None) -> None:
        """初始化意图识别器

        Args:
            llm: LLM 实例，如果为 None 则使用默认 LLM
        """
        self._llm = llm
        self._llm_client: LLMClient | None = None

    def _get_llm(self) -> BaseChatModel:
        """获取 LLM 实例"""
        if self._llm is not None:
            return self._llm
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client.get_default_llm()

    def _keyword_match(self, query: str) -> tuple[str | None, float]:
        """关键词匹配

        Args:
            query: 用户查询

        Returns:
            (意图, 置信度) 元组
        """
        query_lower = query.lower()
        matched_intents: dict[str, float] = {}

        for intent, data in INTENT_KEYWORDS.items():
            keywords = data["keywords"]
            matched_keywords: list[str] = []
            exact_match = False

            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in query_lower:
                    matched_keywords.append(keyword)
                    if keyword_lower == query_lower.strip():
                        exact_match = True

            if matched_keywords:
                if exact_match:
                    return intent, 1.0
                base_confidence = 0.75
                bonus = min(len(matched_keywords) * 0.05, 0.2)
                confidence = min(base_confidence + bonus, 1.0)
                matched_intents[intent] = confidence

        if matched_intents:
            best_intent = max(matched_intents, key=lambda k: matched_intents[k])
            return best_intent, matched_intents[best_intent]

        return None, 0.0

    def _calculate_confidence(
        self, query: str, matched_keywords: list[str], total_keywords: int
    ) -> float:
        """计算置信度

        Args:
            query: 用户查询
            matched_keywords: 匹配的关键词列表
            total_keywords: 该意图的总关键词数

        Returns:
            置信度
        """
        if not matched_keywords:
            return 0.0

        matched_count = len(matched_keywords)
        base_confidence = matched_count / total_keywords

        query_length = len(query)
        keyword_coverage = sum(len(kw) for kw in matched_keywords) / query_length
        keyword_coverage = min(keyword_coverage, 1.0)

        confidence = base_confidence * 0.6 + keyword_coverage * 0.4
        return min(confidence, 1.0)

    async def _classify_with_llm(self, query: str) -> IntentResult:
        """使用 LLM 进行意图分类

        Args:
            query: 用户查询

        Returns:
            意图识别结果
        """
        llm = self._get_llm()

        intent_descriptions = "\n".join(
            [f"- {intent}: {data['name']} - {data['description']}"
             for intent, data in INTENT_KEYWORDS.items()]
        )

        prompt = f"""你是一个公共卫生数据分析意图识别专家。请分析用户的查询，识别其意图类型。

可用的意图类型：
{intent_descriptions}

用户查询：{query}

请返回最匹配的意图类型、置信度和识别理由。"""

        from langchain_core.messages import HumanMessage
        result = await invoke_structured_output(
            llm,
            [HumanMessage(content=prompt)],
            IntentResult,
        )

        if isinstance(result, IntentResult):
            return result
        return IntentResult(
            intent="general_query",
            confidence=0.5,
            reason="LLM 返回格式异常",
        )

    async def recognize(self, query: str) -> IntentResult:
        """识别用户查询的意图

        Args:
            query: 用户查询

        Returns:
            意图识别结果
        """
        intent, confidence = self._keyword_match(query)

        if intent is not None and confidence >= self.CONFIDENCE_THRESHOLD:
            reason = f"关键词匹配成功，匹配意图: {INTENT_KEYWORDS[intent]['name']}"
            return IntentResult(
                intent=intent,
                confidence=confidence,
                reason=reason,
            )

        try:
            llm_result = await self._classify_with_llm(query)
            return llm_result
        except Exception:
            if intent is not None:
                reason = f"关键词部分匹配（LLM 分类失败），匹配意图: {INTENT_KEYWORDS[intent]['name']}"
                return IntentResult(
                    intent=intent,
                    confidence=confidence,
                    reason=reason,
                )
            return IntentResult(
                intent="general_query",
                confidence=0.5,
                reason="无法识别具体意图，默认为一般查询",
            )

    def recognize_sync(self, query: str) -> IntentResult:
        """同步识别用户查询的意图

        Args:
            query: 用户查询

        Returns:
            意图识别结果
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.recognize(query))
                return future.result()
        else:
            return asyncio.run(self.recognize(query))

    def get_supported_intents(self) -> list[str]:
        """获取支持的意图类型列表

        Returns:
            意图类型列表
        """
        return list(INTENT_KEYWORDS.keys())

    def get_intent_info(self, intent: str) -> dict[str, Any] | None:
        """获取意图详细信息

        Args:
            intent: 意图类型

        Returns:
            意图信息字典
        """
        if intent in INTENT_KEYWORDS:
            return {
                "id": intent,
                "name": INTENT_KEYWORDS[intent]["name"],
                "description": INTENT_KEYWORDS[intent]["description"],
                "keywords": INTENT_KEYWORDS[intent]["keywords"],
            }
        return None
