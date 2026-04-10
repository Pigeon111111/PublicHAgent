# PubHAgent

公共卫生数据分析智能体系统，面向上传数据、自动规划分析、执行代码、校验结果、沉淀可复用 Skill 的完整闭环。

## 快速启动

### 1. 安装依赖

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

### 2. 配置 API Key

```powershell
Copy-Item backend/config/.env.example backend/config/.env
```

编辑 `backend/config/.env` 或在前端设置页配置模型 API Key。

### 3. 启动服务

```powershell
python run.py
```

也可以分开启动：

```powershell
python -m uvicorn backend.api.main:app --reload

cd frontend
npm run dev
```

访问地址：

- 前端界面：http://localhost:5173
- API 文档：http://localhost:8000/docs

## 核心能力

- **智能对话**：基于 LangGraph 的 Planner、Executor、Reflection 协作流程。
- **真实数据分析**：读取用户上传或指定的数据文件，生成 `analysis_report.md` 和 `analysis_result.json`。
- **受限代码执行**：默认使用会话级 `input`、`workspace`、`output` 目录，并通过静态策略、路径守卫、超时和中断控制执行 Python 代码。
- **可观察运行**：前端聊天页展示连接状态、任务状态、执行进度、运行日志和错误信息。
- **用户可中断**：WebSocket 中断消息会触发后端任务取消，长时间运行的分析子进程会被终止。
- **自学习 Skill**：成功轨迹会保存到 `data/trajectories`，并生成 `backend/tools/skills/learned_*/SKILL.md` 供后续相似任务复用。
- **多模型支持**：支持 OpenAI、Anthropic、DeepSeek、LongCat 和自定义 Base URL 模型。

## 项目结构

```text
PubHAgent/
├── backend/           # 后端代码
│   ├── agents/        # Agent 核心：Planner、Executor、Reflection
│   ├── api/           # FastAPI、REST API、WebSocket
│   ├── core/          # LangGraph 工作流、会话工作区
│   ├── learning/      # 轨迹记录与 Skill 学习
│   ├── sandbox/       # 沙箱与受限执行器
│   └── tools/         # 内置工具、MCP、Skills
├── frontend/          # Vue 3 + TypeScript 前端
├── tests/             # 单元、集成、端到端测试
└── docs/              # 项目文档
```

## 运行校验

```powershell
ruff check backend tests
mypy backend
pytest -q

cd frontend
npm run lint
npm run typecheck
npm run build
npm audit --audit-level=moderate
```

## 关键接口

- `WebSocket /ws/{session_id}`：用户消息、进度、状态、错误和中断控制。
- `GET /ws/{session_id}/status`：查看会话状态、运行事件和连接信息。
- `GET /api/learning/trajectories`：查看最近学习轨迹。
- `GET /api/learning/trajectories/{trajectory_id}`：查看单条轨迹。
- `GET /api/learning/skills`：查看自动学习生成的 Skill。

## 安全说明

当前本地 `SafeCodeExecutor` 是可运行的受限执行路径，不是强隔离容器。它会限制读写目录、阻止危险代码、设置超时并支持中断杀进程；生产环境仍建议优先启用容器沙箱或更强隔离的执行环境。

## 文档

- [开发者文档](docs/developer-guide.md)
- [自学习 Skill 实施计划](docs/self-learning-skill-implementation-plan.md)
- [结果验证说明](docs/result-validation.md)

## 许可证

MIT License
