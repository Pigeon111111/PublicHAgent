# PubHAgent 项目构建计划

## 一、项目背景

### 1.1 项目概述

PubHAgent 是一个针对公共卫生数据分析场景特化的智能 Agent 系统，基于 LangGraph 构建后端，配备美观、高可用性的前端界面。系统采用 Planner-Executor 范式，结合 Reflection 机制，实现复杂的数据分析任务自动化执行。

### 1.2 核心目标

- **智能意图识别**：准确识别用户数据分析需求
- **自动化分析流程**：通过 Planner-Executor 范式实现复杂分析任务的自动规划与执行
- **安全可控执行**：在沙箱环境中执行代码，确保系统安全
- **记忆系统**：支持用户偏好、分析方法、数据特征的持久化记忆
- **实时交互**：基于 WebSocket 的流式输出和 Human-in-the-loop 能力
- **可扩展工具系统**：支持 Tool、MCP、Skill 三层工具体系

### 1.3 非目标

- 不支持非数据分析类的通用任务（如闲聊、翻译等）
- 不支持实时数据流处理（仅支持批量数据分析）
- 不支持多租户系统（单用户场景）

---

## 二、技术方案

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                      │
│              Vue 3 + TypeScript + WebSocket Client           │
│    ┌──────────────┬──────────────┬──────────────┬─────────┐ │
│    │  对话界面     │  文件上传     │  分析结果展示  │  打断控制 │ │
│    └──────────────┴──────────────┴──────────────┴─────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket (流式通信)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     网关层 (Gateway)                          │
│                    FastAPI + WebSocket Server                │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │ Session管理  │ Channel路由  │  流式输出    │  Human-in-loop│  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agent 核心 (Core)                         │
│                      基于 LangGraph 构建                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  LangGraph 工作流                      │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐         │   │
│  │  │ 意图识别  │→→→│  Planner │→→→│ Executor │         │   │
│  │  └──────────┘   └──────────┘   └──────────┘         │   │
│  │       ↑              ↑              ↑                │   │
│  │       └──────────────┴──────────────┘                │   │
│  │                   Reflection 循环                     │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │ 记忆系统     │ 工具注册表   │  会话管理    │  安全模块    │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐       ┌─────────┐       ┌─────────┐
   │  Tools  │       │   MCP   │       │ Skills  │
   │ 内置工具 │       │ 连接器   │       │  技能库  │
   └─────────┘       └─────────┘       └─────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                    ┌─────────────┐
                    │   沙箱环境   │
                    │ (Docker)    │
                    └─────────────┘
```

### 2.2 核心组件设计

#### 2.2.1 意图识别模块

**设计思路**：
- **两层识别机制**：关键词匹配 → LLM 判断
- **置信度阈值**：关键词完全匹配直接通过，部分匹配计算置信度
- **Few-shot 学习**：LLM 判断采用结构化输出

**实现方案**：

```python
class IntentRecognizer:
    """意图识别器"""
    
    def __init__(self, llm, keywords: List[str], threshold: float = 0.7):
        self.llm = llm
        self.keywords = keywords
        self.threshold = threshold
    
    async def recognize(self, user_input: str) -> IntentResult:
        # 第一层：关键词匹配
        keyword_result = self._keyword_match(user_input)
        if keyword_result.confidence == 1.0:
            return keyword_result
        
        # 第二层：LLM 判断
        if keyword_result.confidence >= self.threshold:
            return keyword_result
        
        return await self._llm_classify(user_input)
    
    def _keyword_match(self, text: str) -> IntentResult:
        """关键词匹配算法"""
        matched_keywords = [kw for kw in self.keywords if kw in text]
        if not matched_keywords:
            return IntentResult(intent="unknown", confidence=0.0)
        
        # 完全匹配
        if any(kw in text for kw in ["分析", "统计", "可视化", "数据"]):
            return IntentResult(intent="data_analysis", confidence=1.0)
        
        # 部分匹配，计算置信度
        confidence = len(matched_keywords) / len(self.keywords)
        return IntentResult(intent="data_analysis", confidence=confidence)
```

#### 2.2.2 Planner-Executor 架构

**基于 LangGraph 的实现**：

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any

class AgentState(TypedDict):
    """Agent 状态定义"""
    user_query: str
    intent: str
    plan: List[Dict[str, Any]]
    current_step: int
    execution_results: List[Dict[str, Any]]
    reflection_feedback: str
    should_replan: bool
    final_result: str

# 定义节点
def planner_node(state: AgentState) -> AgentState:
    """规划节点：制定执行计划"""
    planner = PlannerAgent(llm, tools, memory)
    plan = planner.create_plan(
        state["user_query"],
        state["execution_results"]
    )
    return {**state, "plan": plan}

def executor_node(state: AgentState) -> AgentState:
    """执行节点：执行当前步骤"""
    executor = ExecutorAgent(llm, tools, sandbox)
    current_step_info = state["plan"][state["current_step"]]
    
    result = executor.execute(
        step=current_step_info,
        context=state["execution_results"]
    )
    
    return {
        **state,
        "execution_results": state["execution_results"] + [result]
    }

def reflection_node(state: AgentState) -> AgentState:
    """反思节点：评估执行结果"""
    reflector = ReflectionAgent(llm)
    feedback = reflector.evaluate(
        state["plan"][state["current_step"]],
        state["execution_results"][-1]
    )
    
    should_replan = feedback.needs_replan
    return {
        **state,
        "reflection_feedback": feedback.content,
        "should_replan": should_replan
    }

# 构建工作流
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)
workflow.add_node("reflection", reflection_node)

# 定义边
workflow.add_edge("planner", "executor")
workflow.add_edge("executor", "reflection")

# 条件路由
def should_continue(state: AgentState) -> str:
    if state["should_replan"]:
        return "replan"
    elif state["current_step"] < len(state["plan"]) - 1:
        return "next_step"
    else:
        return "finish"

workflow.add_conditional_edges(
    "reflection",
    should_continue,
    {
        "replan": "planner",
        "next_step": "executor",
        "finish": END
    }
)

# 编译工作流
app = workflow.compile()
```

#### 2.2.3 Executor 反思机制

**设计要点**：
- **上下文隔离**：每次执行只传递上一步结果、当前步骤、下一步需求
- **错误处理**：多次反思后仍失败，保留错误供 replan 使用
- **沙箱执行**：代码在 Docker 容器中执行

```python
class ExecutorAgent:
    """执行 Agent，采用 Reflection 范式"""
    
    def __init__(self, llm, tools, sandbox, max_reflections: int = 3):
        self.llm = llm
        self.tools = tools
        self.sandbox = sandbox
        self.max_reflections = max_reflections
    
    async def execute(self, step: Dict, context: List[Dict]) -> Dict:
        """执行单个步骤"""
        for attempt in range(self.max_reflections):
            try:
                # 生成执行代码
                code = await self._generate_code(step, context)
                
                # 在沙箱中执行
                result = await self.sandbox.execute(code)
                
                # 验证结果
                if self._is_valid_result(result):
                    return {"success": True, "output": result, "code": code}
                
                # 反思并修正
                reflection = await self._reflect(step, code, result)
                context.append({"reflection": reflection})
                
            except Exception as e:
                # 记录错误，继续尝试
                context.append({"error": str(e)})
        
        # 多次尝试后仍失败，返回错误
        return {
            "success": False,
            "error": context[-1].get("error", "Unknown error"),
            "attempts": self.max_reflections
        }
```

#### 2.2.4 记忆系统

**三层记忆架构**：

| 层级 | 存储 | 用途 | 实现 |
|------|------|------|------|
| **工作记忆** | InMemory | 当前对话上下文 | LangGraph State |
| **短期记忆** | SQLite | 最近对话历史 | mem0 短期记忆 |
| **长期记忆** | Vector Store | 持久化事实 | mem0 + ChromaDB |

**集成 mem0**：

```python
from mem0 import Memory

class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, config):
        self.memory = Memory.from_config(config)
    
    async def add_memory(self, messages: List[Dict], user_id: str, session_id: str):
        """添加记忆"""
        await self.memory.add(
            messages,
            user_id=user_id,
            metadata={"session_id": session_id}
        )
    
    async def search_memory(self, query: str, user_id: str, limit: int = 5):
        """搜索记忆"""
        return await self.memory.search(
            query,
            user_id=user_id,
            limit=limit
        )
    
    async def get_user_profile(self, user_id: str):
        """获取用户画像"""
        # 搜索用户偏好、常用分析方法等
        preferences = await self.search_memory(
            "用户偏好 分析方法",
            user_id=user_id
        )
        return preferences
```

#### 2.2.5 工具系统

**三层工具体系**：

```
┌─────────────────────────────────────────────────┐
│              Skills（技能层）                    │
│  - 领域知识、工作流、最佳实践                    │
│  - SKILL.md + references/ + scripts/           │
│  - 示例：描述性统计、回归分析、生存分析          │
├─────────────────────────────────────────────────┤
│           MCP Servers（连接器层）               │
│  - 外部 API 集成、工具调用                       │
│  - mcp.json + tools/*.json                     │
│  - 示例：数据库连接、文件系统、图表库            │
├─────────────────────────────────────────────────┤
│              Tools（基础工具层）                 │
│  - Python 内置工具                              │
│  - 文件操作、代码执行、数据读取                  │
│  - 示例：pandas、numpy、matplotlib              │
└─────────────────────────────────────────────────┘
```

**Skill 标准格式**：

```markdown
---
name: descriptive_statistics
description: 描述性统计分析
allowed-tools: pandas, numpy, matplotlib
tags: statistics, data-analysis
---

# 描述性统计分析

## 功能
计算数据集的基本统计指标，包括：
- 集中趋势：均值、中位数、众数
- 离散程度：方差、标准差、极差
- 分布形态：偏度、峰度

## 使用场景
- 数据探索性分析
- 数据质量检查
- 报告生成

## 示例代码
```python
import pandas as pd
import numpy as np

def descriptive_stats(df):
    return df.describe()
```

## references/
- 统计学基础.pdf
- pandas 官方文档
```

#### 2.2.6 前端设计

**技术栈**：
- **框架**：Vue 3 + TypeScript + Vite
- **UI 库**：Element Plus / Ant Design Vue
- **图表库**：ECharts / Plotly.js
- **通信**：WebSocket Client

**核心功能**：

1. **对话界面**：
   - 流式输出（实时显示 Planner 思考、Executor 执行）
   - Markdown 渲染（支持代码高亮、表格、图表）
   - 打断控制（Human-in-the-loop）

2. **文件上传**：
   - 拖拽上传
   - 支持格式：CSV、XLSX、Word
   - 文件预览

3. **分析结果展示**：
   - 图表渲染（ECharts）
   - 表格展示
   - 导出功能（PDF、Word）

**WebSocket 通信协议**：

```typescript
// 客户端发送
interface ClientMessage {
  type: 'query' | 'upload' | 'interrupt' | 'approve';
  payload: any;
}

// 服务端推送
interface ServerMessage {
  type: 'plan' | 'thinking' | 'executing' | 'result' | 'error';
  content: string;
  metadata?: {
    step?: number;
    tool?: string;
    progress?: number;
  };
}
```

### 2.3 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| **Agent 框架** | LangGraph | 提供图结构工作流、状态管理、可视化监控 |
| **记忆系统** | mem0 | 成熟的记忆层，支持向量检索、图存储 |
| **沙箱环境** | Docker | 隔离执行环境，确保安全 |
| **前端框架** | Vue 3 | 生态成熟，TypeScript 支持好 |
| **WebSocket** | FastAPI WebSocket | 原生支持异步、流式输出 |
| **工具协议** | MCP | 标准化工具协议，易于扩展 |

---

## 三、实施步骤

### 阶段一：基础架构搭建（第 1-2 周）

#### 任务清单

- [ ] **1.1 项目初始化** (复杂度：低)
  - 创建项目目录结构
  - 配置 Python 虚拟环境
  - 安装核心依赖（LangChain、LangGraph、FastAPI、mem0）
  - 配置代码质量工具（black、ruff、mypy）

- [ ] **1.2 核心配置系统** (复杂度：低)
  - 实现 `config/` 配置管理
  - 创建 `models.json`（LLM 模型配置）
  - 创建 `mcp.json`（MCP 服务器配置）
  - 创建 `.env` 环境变量模板

- [ ] **1.3 LLM 客户端封装** (复杂度：中)
  - 实现 `agents/base/llm_client.py`
  - 支持多 LLM Provider（OpenAI、DeepSeek、本地模型）
  - 实现单例缓存机制
  - 添加错误处理和重试逻辑

- [ ] **1.4 基础工具注册表** (复杂度：中)
  - 实现 `tools/registry.py`
  - 定义工具标准接口
  - 实现文件操作工具（读取、写入、编辑）
  - 实现代码执行工具（沙箱调用）

#### 验收标准

- [x] 项目结构清晰，符合 Python 最佳实践
- [x] LLM 客户端可以成功调用至少一个模型
- [x] 基础工具可以正常注册和调用
- [x] 代码通过 lint 和 typecheck 检查

---

### 阶段二：Agent 核心实现（第 3-5 周）

#### 任务清单

- [ ] **2.1 意图识别模块** (复杂度：中)
  - 实现 `agents/intent/recognizer.py`
  - 构建关键词库（公共卫生领域）
  - 实现 LLM 分类器（Few-shot 提示词）
  - 添加单元测试

- [ ] **2.2 LangGraph 工作流** (复杂度：高)
  - 定义 `AgentState` 状态结构
  - 实现 Planner 节点
  - 实现 Executor 节点
  - 实现 Reflection 节点
  - 构建工作流图（节点、边、条件路由）
  - 添加状态持久化（checkpointer）

- [ ] **2.3 Planner Agent** (复杂度：高)
  - 实现计划生成逻辑
  - 设计结构化输出格式（JSON Schema）
  - 实现工具选择逻辑
  - 添加 replan 能力
  - 集成记忆系统（获取用户画像）

- [ ] **2.4 Executor Agent** (复杂度：高)
  - 实现代码生成逻辑
  - 集成沙箱环境（Docker SDK）
  - 实现 Reflection 循环
  - 添加错误处理和重试机制
  - 实现结果验证逻辑

- [ ] **2.5 Reflection Agent** (复杂度：中)
  - 实现执行结果评估
  - 设计反馈生成逻辑
  - 实现 replan 触发条件
  - 添加质量评分机制

#### 验收标准

- [x] 意图识别准确率 > 85%
- [x] LangGraph 工作流可以正常运行
- [x] Planner 可以生成合理的执行计划
- [x] Executor 可以在沙箱中执行代码
- [x] Reflection 可以识别错误并触发 replan
- [x] 核心模块单元测试覆盖率 > 80%

---

### 阶段三：记忆系统集成（第 6 周）

#### 任务清单

- [ ] **3.1 mem0 集成** (复杂度：中)
  - 安装 mem0 库
  - 配置向量存储（ChromaDB）
  - 实现 `agents/memory/manager.py`
  - 添加用户隔离机制（user_id + session_id）

- [ ] **3.2 记忆操作接口** (复杂度：中)
  - 实现添加记忆接口
  - 实现搜索记忆接口
  - 实现更新记忆接口
  - 实现删除记忆接口

- [ ] **3.3 用户画像管理** (复杂度：中)
  - 实现用户偏好记录
  - 实现常用分析方法记录
  - 实现数据特征记录
  - 实现画像检索接口

- [ ] **3.4 记忆注入 Planner** (复杂度：低)
  - 在 Planner 初始化时加载用户画像
  - 在生成计划时参考历史分析方法
  - 实现记忆摘要机制（Token 预算）

#### 验收标准

- [x] 记忆可以成功存储和检索
- [x] 用户隔离机制正常工作
- [x] Planner 可以获取用户画像
- [x] 记忆系统不影响核心性能

---

### 阶段四：工具系统完善（第 7-8 周）

#### 任务清单

- [x] **4.1 MCP 集成** (复杂度：中)
  - 实现 `tools/mcp/client.py`
  - 配置 MCP 服务器（文件系统、数据库）
  - 实现工具发现机制
  - 实现工具调用接口

- [x] **4.2 Skills 系统** (复杂度：中)
  - 设计 Skill 标准格式
  - 实现 `tools/skills/loader.py`
  - 创建初始技能库：
    - 描述性统计
    - 回归分析
    - 生存分析
    - 数据可视化
  - 实现技能动态加载

- [x] **4.3 数据分析工具** (复杂度：高)
  - 实现 CSV/XLSX/JSON 读取工具
  - 实现数据清洗工具（缺失值、异常值、重复值）
  - 实现统计分析工具（描述性统计、相关性分析、假设检验）
  - 实现数据转换工具（标准化、归一化、编码）
  - 实现可视化工具（matplotlib、seaborn）
  - 实现报告生成工具（Markdown、HTML）

- [x] **4.4 工具安全守卫** (复杂度：中)
  - 实现 `tools/security/guard.py`
  - 实现工具权限检查
  - 实现参数验证
  - 实现执行日志记录
  - 实现异常捕获
  - 实现安全策略（黑名单、路径限制、敏感数据检测）

#### 验收标准

- [x] MCP 工具可以正常调用
- [x] Skills 可以动态加载和执行
- [x] 数据分析工具覆盖常用场景
- [x] 工具安全机制有效

---

### 阶段五：沙箱环境搭建（第 9 周）

#### 任务清单

- [ ] **5.1 Docker 环境配置** (复杂度：中)
  - 创建 Dockerfile（Python 数据分析环境）
  - 配置资源限制（CPU、内存）
  - 配置网络隔离
  - 配置文件系统隔离

- [ ] **5.2 沙箱管理器** (复杂度：中)
  - 实现 `sandbox/manager.py`
  - 实现容器生命周期管理
  - 实现代码执行接口
  - 实现结果获取接口

- [ ] **5.3 安全策略** (复杂度：高)
  - 实现代码静态检查（禁止危险操作）
  - 实现执行超时控制
  - 实现资源监控
  - 实现异常隔离

#### 验收标准

- [x] Docker 容器可以正常启动和销毁
- [x] 代码可以在沙箱中安全执行
- [x] 危险操作被有效拦截
- [x] 资源限制正常工作

---

### 阶段六：后端 API 开发（第 10-11 周）

#### 任务清单

- [ ] **6.1 FastAPI 应用搭建** (复杂度：中)
  - 创建 FastAPI 应用实例
  - 配置 CORS
  - 配置中间件（日志、错误处理）
  - 配置依赖注入

- [ ] **6.2 WebSocket 网关** (复杂度：高)
  - 实现 WebSocket 连接管理
  - 实现会话管理（session_id）
  - 实现流式输出
  - 实现打断机制（Human-in-the-loop）

- [ ] **6.3 REST API** (复杂度：中)
  - 实现文件上传接口
  - 实现文件列表接口
  - 实现历史记录接口
  - 实现配置管理接口

- [ ] **6.4 流式输出协议** (复杂度：中)
  - 定义消息格式（JSON Schema）
  - 实现消息序列化
  - 实现进度推送
  - 实现错误推送

#### 验收标准

- [x] WebSocket 连接稳定
- [x] 流式输出正常工作
- [x] 打断机制有效
- [x] API 文档完整（Swagger）

---

### 阶段七：前端开发（第 12-14 周）

#### 任务清单

- [ ] **7.1 项目初始化** (复杂度：低)
  - 创建 Vue 3 项目（Vite）
  - 配置 TypeScript
  - 安装 UI 库（Element Plus）
  - 配置路由和状态管理

- [ ] **7.2 对话界面** (复杂度：高)
  - 实现消息列表组件
  - 实现 Markdown 渲染（代码高亮）
  - 实现流式输出显示
  - 实现输入框组件
  - 实现打断按钮

- [ ] **7.3 文件上传** (复杂度：中)
  - 实现拖拽上传组件
  - 实现文件预览组件
  - 实现上传进度显示
  - 实现文件管理界面

- [ ] **7.4 分析结果展示** (复杂度：高)
  - 实现图表渲染组件（ECharts）
  - 实现表格展示组件
  - 实现结果导出功能
  - 实现历史记录查看

- [ ] **7.5 WebSocket 客户端** (复杂度：中)
  - 实现 WebSocket 连接管理
  - 实现消息解析
  - 实现断线重连
  - 实现心跳机制

#### 验收标准

- [x] 界面美观、响应式
- [x] 流式输出实时显示
- [x] 文件上传功能正常
- [x] 图表渲染正确
- [x] 打断机制有效

---

### 阶段八：集成测试与优化（第 15-16 周）

#### 任务清单

- [ ] **8.1 端到端测试** (复杂度：高)
  - 编写 E2E 测试用例
  - 测试完整分析流程
  - 测试异常场景
  - 测试并发场景

- [ ] **8.2 性能优化** (复杂度：中)
  - 优化 LLM 调用延迟
  - 优化沙箱启动时间
  - 优化前端渲染性能
  - 添加缓存机制

- [ ] **8.3 安全审计** (复杂度：中)
  - 代码安全审查
  - 依赖安全检查
  - 渗透测试
  - 修复安全漏洞

- [ ] **8.4 文档编写** (复杂度：中)
  - 编写用户手册
  - 编写开发文档
  - 编写 API 文档
  - 编写部署文档

#### 验收标准

- [x] E2E 测试覆盖率 > 90%
- [x] 性能指标达标（响应时间 < 5s）
- [x] 无高危安全漏洞
- [x] 文档完整清晰

---

## 四、依赖关系

### 4.1 技术依赖

| 依赖项 | 版本 | 用途 |
|--------|------|------|
| Python | 3.10+ | 后端运行环境 |
| LangChain | 0.3+ | LLM 应用框架 |
| LangGraph | 0.2+ | Agent 工作流编排 |
| FastAPI | 0.110+ | 后端 API 框架 |
| mem0 | 0.1+ | 记忆系统 |
| ChromaDB | 0.4+ | 向量存储 |
| Docker | 24+ | 沙箱环境 |
| Vue 3 | 3.4+ | 前端框架 |
| Node.js | 18+ | 前端构建工具 |

### 4.2 模块依赖

```
前端 → WebSocket → Gateway → Agent Core → Tools/Memory/Sandbox
                                    ↓
                                LLM Provider
```

---

## 五、风险与应对

| 风险 | 影响 | 可能性 | 应对策略 |
|------|------|--------|----------|
| **LLM 调用延迟高** | 高 | 中 | 1. 使用流式输出<br>2. 添加缓存<br>3. 优化提示词 |
| **沙箱逃逸风险** | 高 | 低 | 1. 严格资源限制<br>2. 代码静态检查<br>3. 网络隔离 |
| **记忆系统性能瓶颈** | 中 | 中 | 1. 使用高效向量库<br>2. 分层记忆策略<br>3. 异步写入 |
| **前端渲染卡顿** | 中 | 低 | 1. 虚拟滚动<br>2. 懒加载<br>3. Web Worker |
| **并发冲突** | 中 | 中 | 1. 会话级锁<br>2. 消息队列<br>3. 状态同步机制 |
| **工具兼容性问题** | 低 | 中 | 1. 版本锁定<br>2. 兼容性测试<br>3. 降级方案 |

---

## 六、测试策略

### 6.1 单元测试

- **覆盖范围**：所有核心模块
- **工具**：pytest + pytest-asyncio
- **目标覆盖率**：> 80%

### 6.2 集成测试

- **覆盖范围**：Agent 工作流、记忆系统、工具系统
- **工具**：pytest + testcontainers（Docker）
- **测试场景**：
  - 完整分析流程
  - 错误恢复
  - 并发执行

### 6.3 端到端测试

- **覆盖范围**：前后端集成
- **工具**：Playwright
- **测试场景**：
  - 用户上传文件 → 分析 → 查看结果
  - 打断执行 → 修改 → 重新执行
  - 历史记录查看

### 6.4 性能测试

- **工具**：Locust
- **指标**：
  - 并发用户数：10
  - 平均响应时间：< 5s
  - 错误率：< 1%

---

## 七、成功标准

### 7.1 功能标准

- [x] 意图识别准确率 > 85%
- [x] 支持至少 5 种数据分析场景
- [x] 记忆系统正常工作（存储、检索、更新）
- [x] 沙箱环境安全可靠
- [x] 流式输出实时显示
- [x] Human-in-the-loop 功能正常

### 7.2 性能标准

- [x] 单次分析响应时间 < 30s（简单场景）
- [x] 并发支持 10 用户
- [x] 内存占用 < 2GB（单会话）
- [x] 前端首屏加载 < 3s

### 7.3 质量标准

- [x] 单元测试覆盖率 > 80%
- [x] E2E 测试覆盖率 > 90%
- [x] 无高危安全漏洞
- [x] 代码通过 lint 和 typecheck

### 7.4 用户体验标准

- [x] 界面美观、响应式
- [x] 操作流程直观
- [x] 错误提示清晰
- [x] 文档完整

---

## 八、时间估算

| 阶段 | 预计时间 | 关键里程碑 |
|------|----------|------------|
| 阶段一：基础架构 | 2 周 | LLM 客户端可用 |
| 阶段二：Agent 核心 | 3 周 | LangGraph 工作流运行 |
| 阶段三：记忆系统 | 1 周 | 记忆存储检索正常 |
| 阶段四：工具系统 | 2 周 | 基础工具集完成 |
| 阶段五：沙箱环境 | 1 周 | 沙箱安全执行 |
| 阶段六：后端 API | 2 周 | WebSocket 网关可用 |
| 阶段七：前端开发 | 3 周 | 界面完整可用 |
| 阶段八：测试优化 | 2 周 | 所有测试通过 |
| **总计** | **16 周** | **系统上线** |

---

## 九、待解决问题

1. **LLM 成本控制**：如何优化 Token 使用，降低成本？
   - 方案：使用本地模型（Ollama）作为备选，添加 Token 预算机制

2. **多语言支持**：是否需要支持英文界面？
   - 方案：优先中文，预留国际化接口

3. **部署方案**：单机部署还是分布式部署？
   - 方案：优先单机部署（Docker Compose），预留分布式扩展能力

4. **数据分析场景扩展**：如何快速添加新的分析方法？
   - 方案：通过 Skill 系统动态扩展，用户可自定义 Skill

5. **用户反馈学习**：如何让系统从用户反馈中学习？
   - 方案：记录用户修正，定期更新记忆系统

---

## 十、参考资源

### 10.1 参考项目

| 项目 | GitHub | 关键借鉴点 |
|------|--------|------------|
| OpenClaw | https://github.com/openclaw/openclaw | Gateway 架构、多渠道支持 |
| Nanobot | https://github.com/HKUDS/nanobot | Agent 循环、工具注册表 |
| CoPaw | https://github.com/agentscope-ai/CoPaw | ReAct Agent、工具守卫 |
| mem0 | https://github.com/mem0ai/mem0 | 记忆系统设计 |

### 10.2 技术文档

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [LangChain 官方文档](https://python.langchain.com/)
- [mem0 官方文档](https://docs.mem0.ai/)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Vue 3 官方文档](https://vuejs.org/)

### 10.3 本地参考

- WorkBuddy: `C:\Users\Admin\.workbuddy`
- Trae: `C:\Users\Admin\.trae-cn`

---

## 附录：项目目录结构

```
PubHAgent/
├── backend/                    # 后端代码
│   ├── agents/                # Agent 核心
│   │   ├── base/              # 基础组件
│   │   │   ├── llm_client.py
│   │   │   └── agent_factory.py
│   │   ├── intent/            # 意图识别
│   │   │   └── recognizer.py
│   │   ├── planner/           # 规划 Agent
│   │   │   └── planner_agent.py
│   │   ├── executor/          # 执行 Agent
│   │   │   └── executor_agent.py
│   │   ├── reflection/        # 反思 Agent
│   │   │   └── reflection_agent.py
│   │   └── memory/            # 记忆系统
│   │       └── manager.py
│   ├── tools/                 # 工具系统
│   │   ├── registry.py        # 工具注册表
│   │   ├── mcp/               # MCP 连接器
│   │   │   ├── client.py
│   │   │   └── servers/
│   │   ├── skills/            # 技能库
│   │   │   ├── loader.py
│   │   │   └── skills/
│   │   └── builtin/           # 内置工具
│   │       ├── file_ops.py
│   │       ├── code_exec.py
│   │       └── data_analysis.py
│   ├── sandbox/               # 沙箱环境
│   │   ├── manager.py
│   │   └── Dockerfile
│   ├── api/                   # API 层
│   │   ├── main.py            # FastAPI 应用
│   │   ├── websocket.py       # WebSocket 网关
│   │   └── routes/            # REST API
│   ├── core/                  # 核心模块
│   │   ├── workflow.py        # LangGraph 工作流
│   │   └── state.py           # 状态定义
│   └── config/                # 配置
│       ├── models.json
│       ├── mcp.json
│       ├── settings.json
│       └── .env.example
├── frontend/                  # 前端代码
│   ├── src/
│   │   ├── components/        # 组件
│   │   │   ├── ChatWindow.vue
│   │   │   ├── FileUpload.vue
│   │   │   ├── ResultDisplay.vue
│   │   │   └── InterruptButton.vue
│   │   ├── views/             # 页面
│   │   │   └── Home.vue
│   │   ├── services/          # 服务
│   │   │   └── websocket.ts
│   │   ├── stores/            # 状态管理
│   │   │   └── chat.ts
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   └── vite.config.ts
├── tests/                     # 测试
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/                      # 文档
│   ├── user-guide.md
│   ├── developer-guide.md
│   └── api-reference.md
├── docker-compose.yml         # Docker 编排
├── requirements.txt           # Python 依赖
├── README.md                  # 项目说明
└── .gitignore
```
