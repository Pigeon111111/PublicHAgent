# PubHAgent 核心系统实现 Spec

## Why

PubHAgent 需要一个针对公共卫生数据分析场景特化的智能 Agent 系统，能够自动规划、执行和反思数据分析任务，同时提供友好的用户交互界面。当前项目仅有需求文档，需要从零开始构建完整的系统架构。

## What Changes

- **架构调整**：移除 OpenClaw 的 Gateway 层，直接使用 FastAPI 作为后端服务
- **Agent 核心**：基于 LangGraph 实现 Planner-Executor-Reflection 工作流
- **记忆系统**：集成 mem0 实现三层记忆架构（工作记忆、短期记忆、长期记忆）
- **工具系统**：构建 Tool + MCP + Skill 三层工具体系
- **沙箱环境**：使用 Docker 容器隔离执行代码
- **前端界面**：Vue 3 + TypeScript 实现对话、文件上传、结果展示
- **WebSocket 通信**：实现流式输出和 Human-in-the-loop 能力
- **开发规范**：严格遵循 LangChain 官方 MCP 和 LangGraph 指导文档
- **测试流程**：每个模块构建完成后执行增量测试

## Impact

- **新增文件**：整个项目从零构建，预计新增 100+ 文件
- **核心模块**：
  - `backend/agents/` - Agent 核心实现
  - `backend/tools/` - 工具系统
  - `backend/sandbox/` - 沙箱环境
  - `backend/api/` - FastAPI 后端
  - `frontend/` - Vue 3 前端
- **依赖项**：LangChain、LangGraph、langchain-mcp-adapters、FastAPI、mem0、Docker SDK、Vue 3

## ADDED Requirements

### Requirement: LangChain 官方规范遵循

系统 SHALL 严格遵循 LangChain 官方提供的 MCP 和 LangGraph 指导文档进行实施，确保所有组件调用符合官方规范，避免错误的 API 调用方式及重复开发已有功能模块。

#### Scenario: MCP 集成规范
- **WHEN** 系统集成 MCP 工具
- **THEN** 系统使用 `langchain-mcp-adapters` 库的 `MultiServerMCPClient` 连接 MCP 服务器，使用 `client.get_tools()` 获取工具，避免自定义实现

#### Scenario: MCP 服务器创建
- **WHEN** 系统需要创建自定义 MCP 服务器
- **THEN** 系统使用 `FastMCP` 库创建服务器，使用 `@mcp.tool()` 装饰器定义工具，避免重复开发

#### Scenario: LangGraph 工作流规范
- **WHEN** 系统构建 Agent 工作流
- **THEN** 系统使用 `StateGraph` 构建图，定义 `State` 类型化字典，使用 `add_node`、`add_edge`、`add_conditional_edges` 构建图，使用 `compile()` 编译工作流

#### Scenario: 避免重复开发
- **WHEN** 系统需要实现已有功能
- **THEN** 系统优先使用 LangChain 提供的内置组件（如 `ChatAnthropic`、`ChatOpenAI`），避免重复造轮子

### Requirement: 增量测试流程

系统 SHALL 在每个功能模块构建完成后执行全面的增量测试流程，确保系统稳定性和功能正确性。

#### Scenario: 前序模块验证
- **WHEN** 新模块构建完成
- **THEN** 系统首先验证保留的前序模块功能是否保持完整可用

#### Scenario: 新增模块测试
- **WHEN** 前序模块验证通过
- **THEN** 系统测试新增模块的各项功能是否符合设计预期正常运行

#### Scenario: 模块间集成测试
- **WHEN** 新增模块测试通过
- **THEN** 系统进行模块间的集成测试，确保新增模块与已有系统能够正确协同工作

#### Scenario: 测试逻辑调整
- **WHEN** 实际需求变化
- **THEN** 测试逻辑可根据实际需求进行合理调整，但必须保证能够完全实现预定的测试功能和验证目标

### Requirement: 意图识别系统

系统 SHALL 提供智能意图识别功能，准确判断用户请求是否为数据分析任务。

#### Scenario: 关键词完全匹配
- **WHEN** 用户输入包含"分析"、"统计"、"可视化"等关键词
- **THEN** 系统直接判定为数据分析意图，置信度为 1.0

#### Scenario: 关键词部分匹配
- **WHEN** 用户输入包含部分相关关键词
- **THEN** 系统计算置信度，若超过阈值（0.7）则判定为数据分析意图

#### Scenario: LLM 判断
- **WHEN** 关键词匹配失败或置信度不足
- **THEN** 系统调用 LLM 进行意图分类，返回结构化结果

### Requirement: LangGraph 工作流

系统 SHALL 基于 LangGraph 构建 Agent 工作流，支持 Planner-Executor-Reflection 循环，严格遵循官方最佳实践。

#### Scenario: 正常执行流程
- **WHEN** 用户提交数据分析请求
- **THEN** 系统依次执行：意图识别 → Planner 制定计划 → Executor 执行步骤 → Reflection 评估结果

#### Scenario: Replan 触发
- **WHEN** Reflection 发现执行结果不符合预期
- **THEN** 系统返回 Planner 重新制定计划

#### Scenario: 任务完成
- **WHEN** 所有计划步骤执行完成且 Reflection 通过
- **THEN** 系统返回最终结果给用户

#### Scenario: 工作流持久化
- **WHEN** Agent 执行长时任务
- **THEN** 系统使用 LangGraph 的 checkpointer 机制实现状态持久化，支持任务中断和恢复

#### Scenario: 流式输出
- **WHEN** Agent 执行任务
- **THEN** 系统使用 LangGraph 的 streaming 能力实时输出中间结果

### Requirement: Planner Agent

系统 SHALL 提供智能规划能力，将用户请求分解为可执行的步骤序列。

#### Scenario: 计划生成
- **WHEN** Planner 接收到用户请求和上下文
- **THEN** 系统生成结构化的执行计划（JSON 格式），包含步骤、工具、依赖关系

#### Scenario: 记忆注入
- **WHEN** Planner 初始化
- **THEN** 系统自动加载用户画像（偏好、常用方法、历史数据特征）

#### Scenario: Replan 支持
- **WHEN** Executor 反馈执行失败
- **THEN** Planner 根据历史执行结果重新制定计划

#### Scenario: 结构化输出
- **WHEN** Planner 生成计划
- **THEN** 系统使用 LangChain 的 `with_structured_output` 方法确保输出格式正确

### Requirement: Executor Agent

系统 SHALL 在沙箱环境中安全执行代码，支持 Reflection 自我修正。

#### Scenario: 代码生成与执行
- **WHEN** Executor 接收到执行步骤
- **THEN** 系统生成 Python 代码并在 Docker 沙箱中执行

#### Scenario: Reflection 循环
- **WHEN** 执行结果验证失败
- **THEN** 系统进行反思，生成修正建议，最多尝试 3 次

#### Scenario: 错误处理
- **WHEN** 多次 Reflection 后仍失败
- **THEN** 系统保留错误信息供 Planner 使用

### Requirement: 记忆系统

系统 SHALL 提供三层记忆架构，支持用户偏好和数据分析历史的持久化。

#### Scenario: 工作记忆
- **WHEN** Agent 执行任务
- **THEN** 系统在 LangGraph State 中维护当前对话上下文

#### Scenario: 短期记忆
- **WHEN** 对话结束或 Token 超限
- **THEN** 系统将对话历史压缩并存储到 SQLite

#### Scenario: 长期记忆
- **WHEN** 用户提出新的分析请求
- **THEN** 系统从向量数据库检索相关历史信息

#### Scenario: 用户隔离
- **WHEN** 不同用户使用系统
- **THEN** 记忆按 user_id 和 session_id 隔离，避免污染

### Requirement: 工具系统

系统 SHALL 提供三层工具体系（Tool、MCP、Skill），支持动态扩展，严格遵循 LangChain MCP 官方规范。

#### Scenario: 内置工具
- **WHEN** Agent 需要基础功能
- **THEN** 系统提供文件操作、代码执行、数据读取等内置工具

#### Scenario: MCP 连接器
- **WHEN** Agent 需要外部 API
- **THEN** 系统使用 `langchain-mcp-adapters` 的 `MultiServerMCPClient` 连接 MCP 服务器，通过 `client.get_tools()` 获取工具

#### Scenario: MCP 传输方式
- **WHEN** 系统连接 MCP 服务器
- **THEN** 系统支持 HTTP 和 stdio 两种传输方式，根据服务器类型选择合适的传输方式

#### Scenario: MCP 拦截器
- **WHEN** MCP 工具需要访问运行时上下文
- **THEN** 系统使用拦截器（interceptors）注入用户上下文信息

#### Scenario: Skills 技能库
- **WHEN** Agent 需要领域知识
- **THEN** 系统动态加载 Skills（描述性统计、回归分析、生存分析等）

#### Scenario: Skill 自动生成
- **WHEN** 用户协同完成新的分析方法
- **THEN** 系统自动创建新的 Skill 并确保可被触发

### Requirement: 沙箱环境

系统 SHALL 在 Docker 容器中隔离执行代码，确保系统安全。

#### Scenario: 容器管理
- **WHEN** Executor 需要执行代码
- **THEN** 系统启动 Docker 容器，执行代码，返回结果

#### Scenario: 资源限制
- **WHEN** 容器执行代码
- **THEN** 系统限制 CPU、内存、网络资源

#### Scenario: 安全检查
- **WHEN** 代码包含危险操作（文件系统访问、网络请求等）
- **THEN** 系统拦截并返回错误

### Requirement: FastAPI 后端

系统 SHALL 提供 FastAPI 后端服务，支持 REST API 和 WebSocket。

#### Scenario: REST API
- **WHEN** 前端请求文件上传、历史记录等
- **THEN** 系统通过 REST API 返回数据

#### Scenario: WebSocket 连接
- **WHEN** 前端建立 WebSocket 连接
- **THEN** 系统维护会话，支持流式输出

#### Scenario: 流式输出
- **WHEN** Agent 执行任务
- **THEN** 系统实时推送思考内容、执行进度、结果

### Requirement: Human-in-the-loop

系统 SHALL 支持用户中途打断和纠正分析过程，利用 LangGraph 的 Human-in-the-loop 能力。

#### Scenario: 打断执行
- **WHEN** 用户点击打断按钮
- **THEN** 系统暂停当前执行，等待用户指令

#### Scenario: 修正计划
- **WHEN** 用户修改计划
- **THEN** 系统根据用户输入重新规划

#### Scenario: 恢复执行
- **WHEN** 用户确认修改
- **THEN** 系统从断点继续执行

#### Scenario: 状态检查
- **WHEN** 用户查看执行状态
- **THEN** 系统使用 LangGraph 的状态检查能力显示当前执行进度

### Requirement: 前端界面

系统 SHALL 提供美观、响应式的前端界面。

#### Scenario: 对话界面
- **WHEN** 用户打开应用
- **THEN** 系统显示对话界面，支持 Markdown 渲染、代码高亮

#### Scenario: 文件上传
- **WHEN** 用户拖拽或选择文件
- **THEN** 系统上传文件并显示预览

#### Scenario: 结果展示
- **WHEN** Agent 返回分析结果
- **THEN** 系统渲染图表、表格，支持导出

### Requirement: 数据格式支持

系统 SHALL 支持公共卫生专业常用数据格式。

#### Scenario: CSV 文件
- **WHEN** 用户上传 CSV 文件
- **THEN** 系统自动解析并提供数据预览

#### Scenario: XLSX 文件
- **WHEN** 用户上传 Excel 文件
- **THEN** 系统支持多 Sheet 读取和分析

#### Scenario: Word 文档
- **WHEN** 用户上传 Word 文档
- **THEN** 系统提取文本内容供分析

## MODIFIED Requirements

无修改的需求（首次构建）。

## REMOVED Requirements

### Requirement: OpenClaw Gateway 架构

**Reason**：用户明确不需要 OpenClaw 的 Gateway 层，直接使用 FastAPI 作为后端服务即可。

**Migration**：使用 FastAPI 原生的 WebSocket 支持，无需额外的 Gateway 层。

## 开发规范

### LangChain MCP 规范

1. **使用官方库**：必须使用 `langchain-mcp-adapters` 库连接 MCP 服务器
2. **工具获取**：使用 `client.get_tools()` 获取工具，不要自定义实现
3. **服务器创建**：使用 `FastMCP` 库创建自定义 MCP 服务器
4. **传输方式**：支持 HTTP 和 stdio 两种传输方式
5. **拦截器**：使用拦截器访问运行时上下文

### LangGraph 规范

1. **工作流构建**：使用 `StateGraph` 构建工作流
2. **状态定义**：使用 `TypedDict` 定义状态结构
3. **节点连接**：使用 `add_node`、`add_edge`、`add_conditional_edges` 构建图
4. **工作流编译**：使用 `compile()` 编译工作流
5. **持久化**：使用 checkpointer 实现状态持久化
6. **流式输出**：使用 streaming 能力实时输出

### 增量测试规范

1. **测试顺序**：前序模块验证 → 新增模块测试 → 模块间集成测试
2. **测试覆盖**：每个模块必须有对应的单元测试
3. **集成测试**：模块间集成必须有集成测试
4. **测试调整**：测试逻辑可根据实际需求调整，但必须保证测试目标
