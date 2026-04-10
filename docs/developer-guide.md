# PubHAgent 开发文档

## 1. 架构设计

### 1.1 系统架构

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

### 1.2 核心模块

| 模块 | 职责 | 文件位置 |
|------|------|----------|
| **Agent 核心** | 智能决策和执行 | backend/agents/ |
| **记忆系统** | 记忆管理和用户画像 | backend/agents/memory/ |
| **工具系统** | 工具注册和执行 | backend/tools/ |
| **沙箱环境** | 安全代码执行 | backend/sandbox/ |
| **API 层** | 前端交互和数据传输 | backend/api/ |
| **前端** | 用户界面和交互 | frontend/ |

## 2. 模块说明

### 2.1 Agent 核心

#### 意图识别
- **文件**：backend/agents/intent/recognizer.py
- **功能**：识别用户请求的意图，判断是否为数据分析任务
- **实现**：关键词匹配 + LLM 分类

#### Planner
- **文件**：backend/agents/planner/planner_agent.py
- **功能**：制定数据分析计划，分解为可执行步骤
- **实现**：使用 with_structured_output 确保结构化输出

#### Executor
- **文件**：backend/agents/executor/executor_agent.py
- **功能**：执行计划步骤，生成和执行代码
- **实现**：Reflection 循环，最多尝试 3 次

#### Reflection
- **文件**：backend/agents/reflection/reflection_agent.py
- **功能**：评估执行结果，生成反馈
- **实现**：多维度评估，Replan 触发条件

### 2.2 记忆系统

#### 记忆管理器
- **文件**：backend/agents/memory/manager.py
- **功能**：管理用户记忆，支持增删改查
- **实现**：集成 mem0，使用 ChromaDB 作为向量存储

#### 用户画像
- **文件**：backend/agents/memory/manager.py
- **功能**：记录用户偏好、常用分析方法、数据特征
- **实现**：基于记忆系统的用户画像构建

### 2.3 工具系统

#### 内置工具
- **文件**：backend/tools/builtin/
- **功能**：文件操作、数据分析、可视化、报告生成
- **实现**：使用 LangChain 的 StructuredTool

#### MCP 集成
- **文件**：backend/tools/mcp/
- **功能**：连接外部 MCP 服务器
- **实现**：使用 langchain-mcp-adapters

#### Skills 系统
- **文件**：backend/tools/skills/
- **功能**：动态加载和执行技能
- **实现**：基于 Markdown 的技能定义

### 2.4 沙箱环境

#### 沙箱管理器
- **文件**：backend/sandbox/manager.py
- **功能**：管理 Docker 容器生命周期
- **实现**：容器池管理，资源限制

#### 安全策略
- **文件**：backend/sandbox/security.py
- **功能**：静态代码分析，安全检查
- **实现**：AST 解析，危险操作检查

### 2.5 API 层

#### FastAPI 应用
- **文件**：backend/api/main.py
- **功能**：REST API 和 WebSocket 服务
- **实现**：FastAPI + Uvicorn

#### WebSocket 网关
- **文件**：backend/api/websocket.py
- **功能**：实时通信，流式输出
- **实现**：FastAPI WebSocket

#### REST API
- **文件**：backend/api/routes/
- **功能**：文件上传、历史记录、配置管理
- **实现**：FastAPI 路由

### 2.6 前端

#### 对话界面
- **文件**：frontend/src/components/ChatWindow.vue
- **功能**：消息显示，输入处理
- **实现**：Vue 3 + Element Plus

#### 文件上传
- **文件**：frontend/src/components/FileUpload.vue
- **功能**：文件上传和管理
- **实现**：Vue 3 + Element Plus

#### 分析结果展示
- **文件**：frontend/src/components/ResultDisplay.vue
- **功能**：图表渲染，结果展示
- **实现**：Vue 3 + ECharts

#### WebSocket 客户端
- **文件**：frontend/src/services/websocket.ts
- **功能**：实时通信，消息处理
- **实现**：WebSocket + TypeScript

## 3. API 文档

### 3.1 REST API

#### 文件管理
- **POST /api/upload**：上传文件
- **POST /api/upload/multiple**：多文件上传
- **GET /api/files**：文件列表
- **DELETE /api/files/{file_id}**：删除文件

#### 历史记录
- **GET /api/conversations**：对话列表
- **POST /api/conversations**：创建对话
- **GET /api/analysis**：分析历史

#### 配置管理
- **GET /api/config**：获取配置
- **PUT /api/config/agent**：更新 Agent 配置
- **PUT /api/config/sandbox**：更新沙箱配置

#### 意图识别
- **POST /api/intent**：识别意图

### 3.2 WebSocket 协议

#### 消息类型
- **query**：用户查询
- **upload**：文件上传
- **interrupt**：打断执行
- **plan**：计划信息
- **thinking**：思考过程
- **executing**：执行状态
- **result**：分析结果
- **error**：错误信息

#### 消息格式
```json
{
  "type": "query",
  "payload": {
    "query": "分析数据",
    "file_id": "file-123"
  }
}
```

## 4. 开发指南

### 4.1 环境设置

1. **克隆代码库**
   ```bash
   git clone <repository-url>
   cd PubHAgent
   ```

2. **配置后端环境**
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   copy backend\config\.env.example backend\config\.env
   # 编辑 .env 文件
   ```

3. **配置前端环境**
   ```bash
   cd frontend
   npm install
   ```

### 4.2 开发流程

1. **启动开发服务**
   - 后端：`python -m uvicorn backend.api.main:app --reload`
   - 前端：`npm run dev`

2. **代码规范**
   - Python：使用 black、ruff、mypy
   - TypeScript：使用 eslint、prettier

3. **测试**
   - 单元测试：`pytest tests/unit/`
   - 集成测试：`pytest tests/integration/`
   - E2E 测试：`pytest tests/e2e/`

4. **构建**
   - 后端：`pip install -e .`
   - 前端：`npm run build`

### 4.3 扩展开发

#### 添加新工具
1. 在 backend/tools/builtin/ 中创建新工具
2. 继承 BaseTool 类
3. 使用 @tool 装饰器或 StructuredTool
4. 在 registry.py 中注册工具

#### 添加新技能
1. 在 backend/tools/skills/ 中创建新技能目录
2. 创建 SKILL.md 文件
3. 遵循技能标准格式
4. 技能会被自动加载

#### 添加新 MCP 服务器
1. 在 backend/config/mcp.json 中添加配置
2. 实现对应的 MCP 服务器
3. 使用 langchain-mcp-adapters 连接

### 4.4 部署指南

#### 本地部署
1. 启动 Docker 服务
2. 构建沙箱镜像：`docker build -t pubhagent-sandbox:latest backend/sandbox/`
3. 启动后端服务
4. 启动前端服务

#### 生产部署
1. 构建前端：`npm run build`
2. 配置生产环境变量
3. 使用 Gunicorn + Uvicorn 部署后端
4. 使用 Nginx 反向代理

## 5. 故障排查

### 5.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| LLM 调用失败 | API Key 错误 | 检查环境变量 |
| 沙箱启动失败 | Docker 服务未启动 | 启动 Docker 服务 |
| 文件上传失败 | 文件格式不支持 | 检查文件格式 |
| 分析结果错误 | 数据质量问题 | 检查数据质量 |
| 系统响应缓慢 | LLM 延迟 | 优化提示词 |

### 5.2 日志查看
- 后端日志：控制台输出
- 前端日志：浏览器开发者工具
- 沙箱日志：Docker 容器日志

### 5.3 调试技巧
- 使用 LangSmith 跟踪 LangGraph 工作流
- 使用 Docker 命令查看沙箱状态
- 使用 FastAPI Swagger 测试 API

## 6. 贡献指南

### 6.1 代码风格
- Python：PEP 8 规范
- TypeScript：ESLint 规范
- 注释：使用中文

### 6.2 提交规范
- 提交消息：使用语义化提交
- 分支命名：feature/xxx 或 fix/xxx
- Pull Request：包含详细描述

### 6.3 测试要求
- 新增功能必须添加测试
- 测试覆盖率 > 80%
- 所有测试必须通过

## 7. 技术栈

### 7.1 后端
- **语言**：Python 3.10+
- **框架**：FastAPI、LangChain、LangGraph
- **数据库**：SQLite、ChromaDB
- **容器**：Docker
- **依赖管理**：pip

### 7.2 前端
- **语言**：TypeScript
- **框架**：Vue 3、Vite
- **状态管理**：Pinia
- **路由**：Vue Router
- **UI 库**：Element Plus
- **图表**：ECharts
- **构建工具**：Vite

### 7.3 工具
- **代码质量**：black、ruff、mypy、eslint
- **测试**：pytest、Playwright
- **容器**：Docker
- **监控**：Prometheus、Grafana

## 8. 版本管理

### 8.1 版本号格式
- 主版本.次版本.修订号
- 示例：1.0.0

### 8.2 版本发布流程
1. 更新版本号
2. 运行所有测试
3. 构建前端
4. 生成发布说明
5. 标签发布

## 9. 联系方式

- **技术支持**：dev@pubhagent.com
- **GitHub**：https://github.com/pubhagent/pubhagent
- **文档**：https://docs.pubhagent.com
## 10. 自学习数据分析闭环

### 10.1 执行路径
- 工作流入口为 `backend.core.workflow.AgentWorkflow.run()`。
- 每次会话会创建 `data/sessions/{session_id}/input`、`workspace`、`output` 三个目录。
- `SessionWorkspaceManager` 只接收 `data/uploads` 或项目 `data` 目录内的表格数据文件，并复制到会话 `input`。
- `ExecutorAgent` 默认通过 `SafeCodeExecutor` 执行 Python 代码，脚本运行目录固定为会话 `workspace`，输出固定写入 `output`。
- LLM 不可用或超时时，Planner 会生成本地回退计划，Executor 会执行通用 pandas/numpy/scipy 分析模板。

### 10.2 安全边界
- 受限执行器先执行静态安全检查，再运行脚本。
- 运行时代码只允许读取会话 `input`、`workspace`、`output`，只允许写入 `workspace`、`output`。
- 工具注册表默认注册内置工具，并通过 `ToolGuard` 限制路径、网络、子进程和敏感内容。
- 当前本地受限执行器不是强隔离容器；Docker 不可用时它提供可运行的安全边界，生产环境仍应优先启用容器沙箱。

### 10.3 自学习 Skill
- 每次分析结束后，Reflection 会验证 `analysis_report.md` 和 `analysis_result.json` 是否存在且非空。
- 通过验证后，系统会把用户请求、计划、执行代码、输出、错误和验证结果保存到 `data/trajectories/{trajectory_id}.json`。
- 成功轨迹会生成 `backend/tools/skills/learned_*/SKILL.md`，并立即注册到 SkillRegistry。
- 后续相似请求会优先检索 `learned-analysis` 分类 Skill，作为 Planner 回退计划的复用提示。

### 10.4 查询接口
- `GET /api/learning/trajectories`：查看最近学习轨迹。
- `GET /api/learning/trajectories/{trajectory_id}`：查看单条轨迹。
- `GET /api/learning/skills`：查看自动学习生成的 Skill。

### 10.5 验证命令
```powershell
pytest tests\test_self_learning_workflow.py -q
pytest tests\test_executor.py tests\test_workflow.py tests\test_sandbox.py tests\test_sandbox_security.py tests\test_skills.py tests\test_tools.py tests\test_self_learning_workflow.py -q
ruff check backend tests
mypy backend
```

## 11. 可观察与可中断执行

### 11.1 后端运行控制

- WebSocket 入口：`backend/api/websocket.py`。
- 每个 `SessionContext` 维护当前后台任务、运行状态、最近错误和最近 200 条事件。
- 用户消息不会再阻塞 WebSocket 接收循环；后端会创建后台任务执行 `process_user_message()`，接收循环可以继续处理 `interrupt`、`ping` 和后续控制消息。
- `GET /ws/{session_id}/status` 返回会话快照，包含 `running`、`interrupted`、`last_error`、`events` 和连接信息。

### 11.2 中断链路

- 前端停止按钮发送 `{ "type": "interrupt" }`。
- `SessionContext.interrupt()` 设置中断标记并取消当前后台任务。
- `AgentWorkflow` 接收 `cancellation_checker`，在 intent、planner、executor、reflection 和执行循环边界检查中断。
- `ExecutorAgent` 使用 `asyncio.to_thread()` 调用同步代码执行器，避免分析脚本阻塞 WebSocket 事件循环。
- `SafeCodeExecutor` 使用 `subprocess.Popen()` 轮询执行状态；发现中断或超时会杀掉子进程并返回失败结果。

### 11.3 前端观察能力

- 页面入口：`frontend/src/views/ChatView.vue`。
- 展示组件：`frontend/src/components/ChatWindow.vue`。
- WebSocket 客户端：`frontend/src/services/websocket.ts`。
- Pinia 状态：`frontend/src/stores/index.ts`。
- 聊天页右侧展示连接状态、任务状态、进度条、运行日志和错误信息，便于用户观察任务是否卡住、是否已中断、最终是否生成结果。

### 11.4 前端工具链

前端已补齐 ESLint 工具链并升级到无已知中高危审计项的构建依赖：

```powershell
cd frontend
npm run lint
npm run typecheck
npm run build
npm audit --audit-level=moderate
```

Vite 8 使用 Rolldown，`manualChunks` 需要函数形式；项目同时维护 `vite.config.ts` 和 `vite.config.js`，两者的分包配置需保持一致。
