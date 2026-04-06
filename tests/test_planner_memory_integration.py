"""PlannerAgent 与 MemoryManager 集成测试

测试记忆注入到 Planner 的功能。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.memory.manager import MemoryManager, UserProfile
from backend.agents.planner.planner_agent import PlannerAgent
from backend.agents.planner.schemas import ExecutionPlan, ExecutionStep


@pytest.fixture
def mock_memory_manager():
    """创建 mock MemoryManager"""
    mock = MagicMock(spec=MemoryManager)
    mock.get_relevant_memories_for_planning.return_value = """用户偏好:
- 喜欢使用 Python 进行数据分析
- 偏好可视化图表

常用分析方法:
- t检验
- 卡方检验"""
    return mock


@pytest.fixture
def mock_llm():
    """创建 mock LLM"""
    mock = MagicMock()
    mock_plan = ExecutionPlan(
        steps=[
            ExecutionStep(
                step_id="step_1",
                description="读取数据文件",
                tool_name="read_file",
                tool_args={"file_path": "data.csv"},
                dependencies=[],
                expected_output="数据内容",
            ),
            ExecutionStep(
                step_id="step_2",
                description="执行 t 检验分析",
                tool_name="python_code",
                tool_args={},
                dependencies=["step_1"],
                expected_output="检验结果",
            ),
        ],
        reasoning="根据用户偏好使用 t 检验",
        estimated_complexity="medium",
    )

    structured_mock = MagicMock()
    structured_mock.ainvoke = AsyncMock(return_value=mock_plan)
    mock.with_structured_output.return_value = structured_mock
    return mock


class TestPlannerMemoryIntegration:
    """测试 Planner 与 Memory 集成"""

    def test_planner_init_with_memory_manager(self, mock_memory_manager):
        """测试 Planner 初始化时接收 MemoryManager"""
        planner = PlannerAgent(memory_manager=mock_memory_manager)

        assert planner._memory_manager is mock_memory_manager
        assert planner._token_budget == 500

    def test_planner_init_with_custom_token_budget(self, mock_memory_manager):
        """测试自定义 Token 预算"""
        planner = PlannerAgent(
            memory_manager=mock_memory_manager,
            token_budget=1000,
        )

        assert planner._token_budget == 1000

    def test_planner_init_without_memory_manager(self):
        """测试不带 MemoryManager 初始化"""
        planner = PlannerAgent()

        assert planner._memory_manager is None

    @pytest.mark.asyncio
    async def test_create_plan_with_memory_injection(
        self, mock_memory_manager, mock_llm
    ):
        """测试创建计划时注入记忆"""
        planner = PlannerAgent(
            llm=mock_llm,
            memory_manager=mock_memory_manager,
        )

        plan = await planner.create_plan(
            user_query="分析两组数据的差异",
            intent="statistical_analysis",
            user_id="test_user",
        )

        assert isinstance(plan, ExecutionPlan)
        mock_memory_manager.get_relevant_memories_for_planning.assert_called_once_with(
            user_id="test_user",
            query="分析两组数据的差异",
            token_budget=500,
        )

    @pytest.mark.asyncio
    async def test_create_plan_without_user_id(self, mock_memory_manager, mock_llm):
        """测试不带 user_id 时不注入记忆"""
        planner = PlannerAgent(
            llm=mock_llm,
            memory_manager=mock_memory_manager,
        )

        plan = await planner.create_plan(
            user_query="分析数据",
            intent="analysis",
        )

        assert isinstance(plan, ExecutionPlan)
        mock_memory_manager.get_relevant_memories_for_planning.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_plan_without_memory_manager(self, mock_llm):
        """测试不带 MemoryManager 时正常工作"""
        planner = PlannerAgent(llm=mock_llm)

        plan = await planner.create_plan(
            user_query="分析数据",
            intent="analysis",
            user_id="test_user",
        )

        assert isinstance(plan, ExecutionPlan)

    def test_load_memory_context_success(self, mock_memory_manager):
        """测试成功加载记忆上下文"""
        planner = PlannerAgent(memory_manager=mock_memory_manager)

        context = planner._load_memory_context(
            user_id="test_user",
            query="数据分析",
        )

        assert "历史记忆参考" in context
        assert "用户偏好" in context

    def test_load_memory_context_no_memory(self):
        """测试无记忆时返回空字符串"""
        mock_manager = MagicMock(spec=MemoryManager)
        mock_manager.get_relevant_memories_for_planning.return_value = "暂无相关历史记忆"

        planner = PlannerAgent(memory_manager=mock_manager)

        context = planner._load_memory_context(
            user_id="test_user",
            query="数据分析",
        )

        assert context == ""

    def test_load_memory_context_exception(self):
        """测试记忆加载异常时返回空字符串"""
        mock_manager = MagicMock(spec=MemoryManager)
        mock_manager.get_relevant_memories_for_planning.side_effect = Exception("Error")

        planner = PlannerAgent(memory_manager=mock_manager)

        context = planner._load_memory_context(
            user_id="test_user",
            query="数据分析",
        )

        assert context == ""

    def test_load_memory_context_no_manager(self):
        """测试无 MemoryManager 时返回空字符串"""
        planner = PlannerAgent()

        context = planner._load_memory_context(
            user_id="test_user",
            query="数据分析",
        )

        assert context == ""


class TestMemoryManagerWithPlannerWorkflow:
    """测试完整的记忆管理工作流"""

    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_llm):
        """测试完整工作流：记录偏好 -> 获取画像 -> 注入 Planner"""
        with patch("backend.agents.memory.manager.Memory") as mock_memory_class:
            mock_memory = MagicMock()
            mock_memory_class.from_config.return_value = mock_memory

            mock_memory.add.return_value = {
                "results": [{"id": "mem-1", "memory": "用户偏好: 喜欢使用 t 检验"}]
            }
            mock_memory.get_all.return_value = {
                "results": [
                    {
                        "id": "mem-1",
                        "memory": "用户偏好: 喜欢使用 t 检验",
                        "metadata": {"type": "preference"},
                        "user_id": "test_user",
                        "created_at": "2024-01-01",
                        "updated_at": "2024-01-01",
                    }
                ]
            }
            mock_memory.search.return_value = {
                "results": [
                    {
                        "id": "mem-1",
                        "memory": "用户偏好: 喜欢使用 t 检验",
                        "score": 0.95,
                        "metadata": {"type": "preference"},
                        "user_id": "test_user",
                        "created_at": "2024-01-01",
                        "updated_at": "2024-01-01",
                    }
                ]
            }

            from backend.agents.memory.manager import MemoryConfig
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                config = MemoryConfig(
                    collection_name="test_workflow",
                    persist_directory=tmpdir,
                )
                memory_manager = MemoryManager(config=config)

                memory_manager.record_user_preference(
                    user_id="test_user",
                    preference="喜欢使用 t 检验",
                    category="statistics",
                )

                profile = memory_manager.get_user_profile("test_user")
                assert profile.user_id == "test_user"

                planner = PlannerAgent(
                    llm=mock_llm,
                    memory_manager=memory_manager,
                )

                plan = await planner.create_plan(
                    user_query="比较两组数据",
                    intent="statistical_analysis",
                    user_id="test_user",
                )

                assert isinstance(plan, ExecutionPlan)
