# PubHAgent

面向公共卫生与医学数据分析的 Agent 系统，支持上传数据、自动规划分析、受限执行 Python 代码、结构化评估结果、沉淀分层 Skill，并通过 WebSocket 提供可恢复的人机协作流程。

## 快速启动

### 1. 安装依赖

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

Set-Location frontend
npm install
Set-Location ..
```

### 2. 配置模型与密钥

```powershell
Copy-Item backend\config\.env.example backend\config\.env
```

编辑 `backend\config\.env`，或在前端设置页中配置模型与 API Key。

### 3. 启动服务

```powershell
python run.py
```

也可以分别启动：

```powershell
python -m uvicorn backend.api.main:app --reload

Set-Location frontend
npm run dev
```

访问地址：

- 前端界面：[http://localhost:5173](http://localhost:5173)
- API 文档：[http://localhost:8000/docs](http://localhost:8000/docs)

## 当前能力

- 智能工作流：基于 LangGraph 的 `intent -> planner -> executor -> reflection` 主链路。
- 真实数据分析：读取上传文件，生成 `analysis_report.md` 与 `analysis_result.json`。
- 受限执行环境：仅允许会话级 `input/workspace/output` 目录访问，支持超时与用户中断。
- 中文绘图回退：可视化工具会在 Windows 上自动注册 `Microsoft YaHei`、`SimHei`、`SimSun`、`DengXian` 等字体，避免 matplotlib 中文标题和标签缺字。
- 持久化恢复：LangGraph checkpoint 持久化到 SQLite，支持 WebSocket 恢复执行。
- MCP 主链路接入：MCP 工具会自动刷新并并入统一 `ToolRegistry`。
- Memory 主链路接入：规划阶段可读长期记忆，任务完成后会写回方法摘要与上下文。
- 结构化评估：支持 artifact、process、report，以及 `descriptive_analysis`、`regression_analysis`、`survival_analysis` 的统计硬校验。
- 正式评估对象：`evaluation_reports` 独立持久化，可审阅、可追踪、可复跑。
- 分层 Skill：固定顶层方法家族，支持细分变体、过程签名、偏好设置与自动降级。
- 前端可交互：聊天结果卡片、历史详情面板、方法库页面、评估审阅、重跑、恢复、提升为新变体。

## 2026-04 升级概览

### 结果评估

- 新增 `evaluation_reports` 表，保存正式评估对象。
- 回归分析与生存分析已启用专用统计校验，不再只是占位或规则兜底。
- WebSocket 最终消息固定携带 `evaluation_report` 摘要、`analysis_id`、`trajectory_id`。
- History 页面可查看分项得分、硬失败原因、指标断言和审阅状态。

### 分层 Skill

- 顶层方法家族固定为：
  - `descriptive_analysis`
  - `statistical_test`
  - `regression_analysis`
  - `survival_analysis`
  - `epidemiology_analysis`
  - `visualization`
  - `general`
- 每个 family 下允许学习新的 `method_variant`。
- Skill 元数据新增 `method_family`、`method_variant`、`process_signature`、`input_schema_signature`、`lifecycle_state`、`confidence_score` 等字段。
- Planner 采用渐进式披露：先 family 摘要，再展开高置信 variant。

### 前端交互

- `/chat`：最终消息内展示评估卡片，并支持进入审阅、重新运行、学习为新变体。
- `/history`：列表加详情联动，支持查看完整评估报告与提交审阅。
- `/methods`：浏览方法家族与细分变体，设置 preferred variant，并查看关联评估。

## 核心接口

### WebSocket

- `WebSocket /ws/{session_id}`：用户消息、状态流、评估结果、恢复执行、中断控制。
- `GET /ws/{session_id}/status`：返回会话运行状态、事件与 checkpoint 可恢复状态。

### 分析与评估

- `GET /api/analysis`
- `GET /api/analysis/{analysis_id}`
- `GET /api/analysis/{analysis_id}/evaluation`
- `POST /api/analysis/{analysis_id}/evaluation/review`
- `POST /api/analysis/{analysis_id}/rerun`
- `POST /api/analysis/{analysis_id}/promote-variant`

### 方法库

- `GET /api/method-families`
- `GET /api/method-families/{family}/variants`
- `POST /api/method-families/{family}/preferred-variant`

### 学习与 Skill

- `GET /api/learning/trajectories`
- `GET /api/learning/trajectories/{trajectory_id}`
- `GET /api/learning/skills`
- `GET /api/skills`

## 项目结构

```text
PubHAgent/
├── backend/                     # 后端主代码
│   ├── agents/                  # Planner / Executor / Memory / Reflection
│   ├── api/                     # FastAPI、REST API、WebSocket
│   ├── core/                    # LangGraph 工作流、状态、checkpoint
│   ├── evaluation/              # Verifier / Evaluator 分层评估
│   ├── learning/                # 轨迹记录与 Skill 学习
│   ├── sandbox/                 # 受限执行与安全策略
│   ├── storage/                 # SQLite 持久化
│   └── tools/                   # Builtin tools、MCP、Skills
├── frontend/                    # Vue 3 + TypeScript 前端
├── docs/                        # 开发与运行文档
└── tests/                       # 单元、集成与端到端测试
```

## 验证命令

```powershell
ruff check backend tests
mypy backend
pytest -q

Set-Location frontend
npm run lint
npm run typecheck
npm run build
```

## 安全说明

当前默认执行路径为本地 `SafeCodeExecutor`，它提供静态导入检查、目录级路径守卫、超时控制和进程级中断，但不是强隔离容器。生产环境建议继续优先使用更强隔离的容器化沙箱。

## 文档

- [开发文档](docs/developer-guide.md)
- [运行时升级说明](docs/runtime-upgrade-2026-04.md)
- [Verifier / Evaluator 升级计划](docs/verifier-evaluator-upgrade-plan.md)
- [结果验证说明](docs/result-validation.md)

## 许可

MIT License
