# PubHAgent

公共卫生数据分析智能体系统

## 项目简介

PubHAgent 是一个基于 LangGraph 构建的智能数据分析系统，专注于公共卫生领域的数据分析任务。

## 项目结构

```
PubHAgent/
├── backend/               # 后端代码
│   ├── agents/            # Agent 核心
│   │   ├── base/          # Agent 基础模块
│   │   │   └── llm_client.py  # LLM 客户端封装
│   │   ├── intent/        # 意图识别模块
│   │   │   ├── keywords.py    # 公共卫生关键词库
│   │   │   └── recognizer.py  # 意图识别器
│   │   ├── memory/        # 记忆管理模块
│   │   │   └── manager.py     # 记忆管理器
│   │   ├── planner/       # 计划生成模块
│   │   │   ├── schemas.py     # 结构化输出格式
│   │   │   └── planner_agent.py  # Planner Agent
│   │   ├── executor/      # 执行模块
│   │   │   ├── schemas.py     # 结构化输出格式
│   │   │   └── executor_agent.py  # Executor Agent
│   │   └── reflection/    # 反思模块
│   │       ├── schemas.py     # 结构化输出格式
│   │       └── reflection_agent.py  # Reflection Agent
│   ├── tools/             # 工具系统
│   │   ├── base.py        # 工具基类
│   │   ├── registry.py    # 工具注册表
│   │   ├── builtin/       # 内置工具
│   │   │   └── file_ops.py    # 文件操作工具
│   │   ├── mcp/           # MCP 工具集成
│   │   │   ├── client.py      # MCP 客户端
│   │   │   └── adapter.py     # MCP 工具适配器
│   │   └── skills/        # 技能系统
│   │       ├── models.py      # 技能数据模型
│   │       ├── loader.py      # 技能加载器
│   │       └── registry.py    # 技能注册表
│   ├── sandbox/           # 沙箱环境
│   │   ├── manager.py     # 沙箱管理器
│   │   ├── security.py    # 安全策略
│   │   ├── Dockerfile     # Docker 镜像配置
│   │   └── requirements.txt   # 沙箱依赖
│   ├── api/               # API 层
│   │   ├── main.py        # FastAPI 应用
│   │   ├── deps.py        # 依赖注入
│   │   ├── websocket.py   # WebSocket 网关
│   │   ├── protocol.py    # 流式输出协议
│   │   └── routes/        # REST API 路由
│   │       ├── files.py   # 文件管理
│   │       ├── history.py # 历史记录
│   │       └── config.py  # 配置管理
│   ├── core/              # 核心模块
│   │   ├── state.py       # 状态定义
│   │   └── workflow.py    # LangGraph 工作流
│   └── config/            # 配置文件
│       └── models.json    # 模型配置
├── frontend/              # 前端代码
│   ├── src/
│   │   ├── components/    # Vue 组件
│   │   │   ├── ChatWindow.vue      # 对话窗口
│   │   │   ├── UserMessage.vue     # 用户消息
│   │   │   ├── AgentMessage.vue    # Agent 消息
│   │   │   ├── SystemMessage.vue   # 系统消息
│   │   │   ├── FileUpload.vue      # 文件上传
│   │   │   ├── ResultDisplay.vue   # 结果展示
│   │   │   └── charts/             # 图表组件
│   │   │       ├── LineChart.vue   # 折线图
│   │   │       ├── BarChart.vue    # 柱状图
│   │   │       ├── ScatterChart.vue # 散点图
│   │   │       └── HeatmapChart.vue # 热力图
│   │   ├── services/      # 服务层
│   │   │   ├── api.ts             # REST API 封装
│   │   │   └── websocket.ts       # WebSocket 客户端
│   │   ├── stores/        # Pinia 状态管理
│   │   ├── views/         # 页面视图
│   │   │   ├── HomeView.vue       # 首页
│   │   │   ├── ChatView.vue       # 对话页
│   │   │   ├── FilesView.vue      # 文件管理页
│   │   │   ├── HistoryView.vue    # 历史记录页
│   │   │   └── SettingsView.vue   # 设置页
│   │   ├── router/        # Vue Router 路由
│   │   ├── types/         # TypeScript 类型定义
│   │   ├── App.vue        # 根组件
│   │   └── main.ts        # 入口文件
│   ├── public/            # 静态资源
│   ├── package.json       # NPM 配置
│   ├── vite.config.ts     # Vite 配置
│   └── tsconfig.json      # TypeScript 配置
├── tests/                 # 测试代码
│   ├── test_llm_client.py # LLM 客户端测试
│   ├── test_tools.py      # 工具系统测试
│   ├── test_mcp.py        # MCP 集成测试
│   ├── test_skills.py     # 技能系统测试
│   ├── test_intent.py     # 意图识别测试
│   ├── test_memory.py     # 记忆管理测试
│   ├── test_planner.py    # Planner Agent 测试
│   ├── test_planner_memory_integration.py  # Planner 记忆集成测试
│   ├── test_executor.py   # Executor Agent 测试
│   ├── test_reflection.py # Reflection Agent 测试
│   ├── test_workflow.py   # 工作流测试
│   ├── test_sandbox.py    # 沙箱管理器测试
│   ├── test_sandbox_security.py  # 沙箱安全测试
│   └── test_api.py        # API 层测试
└── docs/                  # 文档
```

## 核心模块

### LLM 客户端 (backend/agents/base/llm_client.py)

统一的 LLM 客户端封装，支持：
- OpenAI 和 Anthropic 模型
- 单例缓存机制（避免重复初始化）
- 错误处理和重试逻辑（使用 tenacity）
- 从 models.json 加载配置
- 从环境变量读取 API Key

```python
from backend.agents import get_llm_client

client = get_llm_client()
llm = client.get_llm("gpt-4o")
response = await llm.ainvoke("Hello!")
```

### 工具注册表 (backend/tools/)

工具系统的核心组件：

**BaseTool 抽象基类**：定义工具标准接口
- name: 工具名称
- description: 工具描述
- args_schema: 参数 Schema（Pydantic BaseModel）
- run: 执行方法

**ToolRegistry 注册表**：管理工具生命周期
- register/unregister: 注册/注销工具
- get/list_tools: 查询工具
- execute: 执行工具
- get_openai_tools_definition: 导出 OpenAI 格式定义

**内置工具**：
- ReadFileTool: 读取文件内容
- WriteFileTool: 写入文件内容
- EditFileTool: 编辑文件（搜索替换）

```python
from backend.tools import ToolRegistry, ReadFileTool, WriteFileTool

registry = ToolRegistry()
registry.register(ReadFileTool())
registry.register(WriteFileTool())

result = registry.execute("read_file", file_path="test.txt")
```

### MCP 工具集成 (backend/tools/mcp/)

基于 langchain-mcp-adapters 的 MCP (Model Context Protocol) 工具集成：

**MCP 客户端 (client.py)**：
- 使用 MultiServerMCPClient 连接多个 MCP 服务器
- 支持 stdio 和 SSE 两种传输方式
- 从 backend/config/mcp.json 加载配置
- 异步上下文管理器支持

**工具适配器 (adapter.py)**：
- 将 MCP 工具转换为 LangChain StructuredTool
- 支持工具发现和动态加载
- 提供批量适配功能

```python
from backend.tools.mcp import MCPClient

async with MCPClient(config_path="backend/config/mcp.json") as client:
    tools = await client.get_tools()
    # tools 可直接用于 LangChain Agent
```

**MCP 配置示例 (backend/config/mcp.json)**：
```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./data"],
      "enabled": true
    }
  ]
}
```

### 技能系统 (backend/tools/skills/)

可扩展的技能管理框架，支持动态加载和执行：

**技能数据模型 (models.py)**：
- SkillMetadata: 技能元数据（名称、版本、描述、标签等）
- SkillParameter: 参数定义（类型、是否必需、默认值等）
- Skill: 完整技能定义（元数据、参数、提示词模板、示例）

**技能加载器 (loader.py)**：
- 从 SKILL.md 文件动态加载技能
- 支持 YAML front matter 和 Markdown 格式
- 技能缓存机制，支持按需加载

**技能注册表 (registry.py)**：
- 管理所有已加载的技能
- 支持按类别、标签搜索
- 提供技能查询和加载接口

```python
from backend.tools.skills import SkillRegistry, get_skill_registry

registry = get_skill_registry()
registry.load_all()

# 获取技能
skill = registry.get("descriptive_statistics")

# 按类别搜索
stats_skills = registry.get_by_category("statistics")

# 渲染提示词
prompt = skill.render_prompt(data_source="data.csv", variables=["age", "bmi"])
```

**初始技能库**：
- descriptive_statistics: 描述性统计分析
- regression_analysis: 回归分析
- survival_analysis: 生存分析
- data_visualization: 数据可视化

### 意图识别模块 (backend/agents/intent/)

基于关键词匹配和 LLM 分类的意图识别系统：

**关键词库 (keywords.py)**：
- 10 种公共卫生领域意图类型
- 包含描述性分析、统计检验、回归分析、生存分析、流行病学分析等
- 支持中英文关键词

**意图识别器 (recognizer.py)**：
- 关键词完全匹配：置信度 = 1.0
- 关键词部分匹配：基础置信度 0.75 + 奖励
- LLM 分类：使用 with_structured_output 确保结构化输出
- 置信度阈值：0.7

```python
from backend.agents.intent import IntentRecognizer

recognizer = IntentRecognizer()
result = await recognizer.recognize("计算均值和标准差")
# result.intent = "descriptive_analysis"
# result.confidence = 0.8
```

### 记忆管理模块 (backend/agents/memory/)

基于 mem0 的智能记忆管理系统：

**核心功能**：
- ChromaDB 向量存储：持久化记忆数据
- 用户隔离：通过 user_id + session_id 实现多用户隔离
- 记忆操作：添加、搜索、更新、删除记忆
- 用户画像：记录用户偏好、分析方法、数据特征
- 记忆注入：为 Planner 提供历史记忆参考

**数据结构**：
- MemoryConfig: 记忆系统配置
- MemoryResult: 记忆搜索结果
- UserProfile: 用户画像（偏好、分析方法、数据特征）

```python
from backend.agents.memory import MemoryManager

manager = MemoryManager()

# 添加记忆
manager.add_memory("用户偏好使用 Python 进行数据分析", user_id="user1")

# 记录用户偏好
manager.record_user_preference(user_id="user1", preference="喜欢使用 t 检验")

# 获取用户画像
profile = manager.get_user_profile("user1")

# 搜索相关记忆
results = manager.search_memory("数据分析", user_id="user1", limit=5)
```

**Planner 集成**：
```python
from backend.agents import PlannerAgent
from backend.agents.memory import MemoryManager

memory_manager = MemoryManager()
planner = PlannerAgent(memory_manager=memory_manager)

# 创建计划时自动注入用户历史记忆
plan = await planner.create_plan(
    user_query="分析两组数据差异",
    intent="statistical_test",
    user_id="user1"
)
```

### LangGraph 工作流 (backend/core/)

基于 LangGraph 的多智能体工作流系统：

**状态定义 (state.py)**：
- AgentState: 使用 TypedDict 定义工作流状态
- 包含字段：user_query, intent, plan, execution_results, reflection_feedback 等

**工作流 (workflow.py)**：
- 计划-执行-反思循环
- 节点：intent_node, planner_node, executor_node, reflection_node
- 条件路由：根据执行状态和反思结果决定下一步
- 状态持久化：使用 MemorySaver

```python
from backend.core import AgentWorkflow

workflow = AgentWorkflow()
workflow.compile()
result = await workflow.run("分析这组数据的特征")
```

### Planner Agent (backend/agents/planner/)

计划生成 Agent，负责将用户请求分解为可执行的步骤序列：

**核心功能**：
- 计划生成：使用 with_structured_output 确保结构化输出
- 工具选择：根据步骤描述选择合适的工具
- Replan 能力：根据执行反馈重新制定计划
- 依赖管理：支持步骤间的依赖关系
- 记忆注入：集成 MemoryManager，参考用户历史偏好

**结构化输出**：
- ExecutionStep: step_id, description, tool_name, tool_args, dependencies, expected_output
- ExecutionPlan: steps, reasoning, estimated_complexity

```python
from backend.agents import PlannerAgent, ExecutionPlan

planner = PlannerAgent()
plan = await planner.create_plan(
    user_query="分析数据分布",
    intent="descriptive_analysis"
)

# 带记忆注入的计划生成
planner_with_memory = PlannerAgent(memory_manager=memory_manager)
plan = await planner.create_plan(
    user_query="分析数据分布",
    intent="descriptive_analysis",
    user_id="user1"
)
```

### Executor Agent (backend/agents/executor/)

执行 Agent，负责代码生成和执行：

**核心功能**：
- 代码生成：根据步骤生成 Python 代码
- 本地执行：在安全环境中执行代码
- Reflection 循环：最多尝试 3 次修复错误
- 工具集成：支持注册的工具执行

**结构化输出**：
- GeneratedCode: code, explanation, imports
- ExecutionResult: success, output, error, code, execution_time

```python
from backend.agents import ExecutorAgent, ExecutionStep

executor = ExecutorAgent()
step = ExecutionStep(step_id="step_1", description="计算均值")
result = await executor.execute_step(step)
```

### Reflection Agent (backend/agents/reflection/)

反思 Agent，负责评估执行结果：

**核心功能**：
- 结果评估：判断执行是否成功
- 反馈生成：生成修正建议
- Replan 触发：根据评估结果决定是否需要 replan
- 质量评分：给执行结果打分（0-1）

**结构化输出**：
- ReflectionResult: should_replan, feedback, quality_score, quality_level, suggestions
- EvaluationCriteria: correctness, completeness, efficiency, clarity

```python
from backend.agents import ReflectionAgent

reflection = ReflectionAgent()
result = await reflection.evaluate(
    user_query="分析数据",
    plan=plan,
    execution_results=results
)
```

### 沙箱环境 (backend/sandbox/)

基于 Docker 的安全代码执行环境：

**沙箱管理器 (manager.py)**：
- 容器生命周期管理：创建、启动、停止、销毁
- 容器池复用：提高执行效率
- 健康检查：自动清理不健康容器
- 执行控制：超时、内存限制、CPU 限制

**安全策略 (security.py)**：
- 静态代码分析：AST 解析检查危险操作
- 禁止模块：os, subprocess, socket, pickle 等
- 禁止函数：exec, eval, open, input 等
- 敏感信息过滤：隐藏路径、API Key、密码等

**Docker 配置**：
- 基于 Python 3.11-slim 镜像
- 非 root 用户运行
- 网络完全隔离
- 内存限制 512MB

```python
from backend.sandbox import SandboxManager, SandboxConfig

# 创建沙箱管理器
config = SandboxConfig(
    image_name="pubhagent-sandbox:latest",
    memory_limit="512m",
    timeout=60,
)
manager = SandboxManager(config)

# 执行代码
result = manager.execute_code("""
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3]})
print(df.mean())
""")

print(result.output)  # a    2.0
print(result.success)  # True

# 清理容器
manager.cleanup()
```

**安全检查**：
```python
from backend.sandbox.security import analyze_code, is_code_safe

# 检查代码安全性
result = analyze_code("import os")
print(result.is_safe)  # False
print(result.blocked_imports)  # ['os']

# 快速检查
print(is_code_safe("x = 1 + 1"))  # True
print(is_code_safe("import subprocess"))  # False
```

**构建 Docker 镜像**：
```powershell
docker build -t pubhagent-sandbox:latest backend/sandbox/
```

### API 层 (backend/api/)

基于 FastAPI 的 RESTful API 和 WebSocket 网关：

**FastAPI 应用 (main.py)**：
- CORS 配置：支持跨域请求
- 中间件：日志记录、错误处理
- 生命周期管理：启动和关闭钩子
- 静态文件服务：上传文件访问

**依赖注入 (deps.py)**：
- LLM 客户端依赖：单例模式
- 记忆管理器依赖：自动初始化
- 工具注册表依赖：全局共享
- 文件验证：类型和大小检查

**WebSocket 网关 (websocket.py)**：
- 连接管理：多用户会话隔离
- 流式输出：实时推送执行进度
- 打断机制：支持用户中断执行
- 会话上下文：状态持久化

**REST API 路由 (routes/)**：
- `/api/upload`: 文件上传（支持多文件）
- `/api/files`: 文件列表和删除
- `/api/conversations`: 对话管理
- `/api/analysis`: 分析历史
- `/api/config`: 配置管理

**流式输出协议 (protocol.py)**：
- 消息类型：user, agent, status, progress, error
- 消息工厂：统一创建消息对象
- 进度追踪器：阶段进度管理
- 序列化/反序列化：JSON 格式转换

```python
from backend.api import app, MessageFactory

# 创建消息
message = MessageFactory.create_user_message(
    session_id="session-1",
    content="分析这组数据",
)

# 序列化
json_str = message.model_dump_json()
```

**WebSocket 使用示例**：
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/session-1');

// 发送消息
ws.send(JSON.stringify({
    type: 'user',
    content: '分析数据分布',
    user_id: 'user1'
}));

// 接收消息
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    console.log(message.type, message.content);
};
```

## 快速开始

### 环境配置

1. 创建虚拟环境：
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. 安装后端依赖：
```powershell
pip install -r requirements.txt
```

3. 安装前端依赖：
```powershell
Set-Location frontend
npm install
Set-Location ..
```

4. 配置环境变量：
```powershell
Copy-Item backend/config/.env.example backend/config/.env
# 编辑 .env 文件，填入实际配置
```

### 运行项目

```powershell
# 启动后端服务
python -m uvicorn backend.api.main:app --reload

# 启动前端开发服务器（新终端）
Set-Location frontend
npm run dev
```

前端访问地址：http://localhost:3000
后端 API 文档：http://localhost:8000/docs

## 开发指南

### 代码规范

- 使用 black 格式化代码
- 使用 ruff 进行 lint 检查
- 使用 mypy 进行类型检查

```powershell
# 格式化
black .

# Lint 检查
ruff check .

# 类型检查
mypy backend/
```

### 运行测试

```powershell
pytest
```

## 技术栈

- **后端框架**: FastAPI + LangGraph
- **LLM**: LangChain (OpenAI, Anthropic)
- **记忆系统**: mem0ai
- **数据分析**: pandas, numpy, scipy
- **沙箱环境**: Docker
- **前端框架**: Vue 3 + TypeScript + Vite
- **UI 组件库**: Element Plus
- **状态管理**: Pinia
- **图表库**: ECharts
- **Markdown 渲染**: marked + highlight.js

## 前端模块

### 对话界面 (frontend/src/components/)

**ChatWindow.vue**：主对话窗口组件
- 消息列表展示
- Markdown 渲染和代码高亮
- 流式输出显示
- 输入框和发送按钮
- 打断执行按钮

**消息组件**：
- UserMessage.vue：用户消息气泡
- AgentMessage.vue：Agent 响应消息（支持 Markdown）
- SystemMessage.vue：系统提示消息

### 文件上传 (frontend/src/components/FileUpload.vue)

- 拖拽上传支持
- 文件类型验证（CSV, XLSX, JSON, PDF, Word）
- 文件大小限制（50MB）
- 上传进度显示
- 文件预览列表

### 分析结果展示 (frontend/src/components/)

**ResultDisplay.vue**：结果展示容器
- 图表渲染
- 表格展示
- 导出功能（PDF、Word）

**图表组件**（基于 ECharts）：
- LineChart.vue：折线图
- BarChart.vue：柱状图
- ScatterChart.vue：散点图
- HeatmapChart.vue：热力图

### WebSocket 客户端 (frontend/src/services/websocket.ts)

- 连接管理：自动连接和断线重连
- 消息解析：JSON 格式解析
- 心跳机制：30 秒心跳保活
- 打断支持：中断执行功能

```typescript
import { connectWebSocket, sendMessage, interruptExecution } from '@/services/websocket'

// 连接 WebSocket
await connectWebSocket('session-1', (message) => {
  console.log('收到消息:', message)
})

// 发送消息
sendMessage({
  type: 'user',
  content: '分析数据分布',
  user_id: 'user1',
})

// 打断执行
interruptExecution()
```

### REST API 服务 (frontend/src/services/api.ts)

封装所有后端 REST API 调用：

```typescript
import { uploadFile, getFiles, getConfig } from '@/services/api'

// 上传文件
const fileInfo = await uploadFile(file)

// 获取文件列表
const { files, total } = await getFiles(1, 20)

// 获取配置
const config = await getConfig()
```

### 状态管理 (frontend/src/stores/)

使用 Pinia 进行状态管理：

- **useChatStore**：对话状态（消息列表、连接状态、处理进度）
- **useFileStore**：文件状态（文件列表、上传进度）
- **useAnalysisStore**：分析结果状态（图表、表格）

## 许可证

MIT License
