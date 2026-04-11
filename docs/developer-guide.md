# PubHAgent 开发文档

> 本文档描述当前代码结构、运行链路、评估体系、方法库接口和前端交互方式。若需了解本轮运行时升级背景，请同时阅读 [运行时升级说明](runtime-upgrade-2026-04.md)。

## 1. 核心架构

### 1.1 主链路

后端核心工作流位于 `backend/core/workflow.py`，主链路如下：

1. `intent`：识别任务是否为数据分析及其大类
2. `planner`：生成分析计划，并补充高置信 method variant
3. `executor`：在安全执行器中运行工具或 Python 代码
4. `reflection`：先做结构化 evaluator，再写回轨迹、Skill 与记忆

### 1.2 关键目录

| 目录 | 职责 |
|---|---|
| `backend/agents` | Planner、Executor、Intent、Memory、Reflection |
| `backend/core` | LangGraph 工作流、状态、checkpoint |
| `backend/evaluation` | 分层 verifier / evaluator |
| `backend/learning` | 轨迹与 Skill 学习 |
| `backend/storage` | SQLite 持久化 |
| `backend/tools` | Builtin tools、MCP、Skills |
| `frontend/src/views` | 主要页面 |
| `frontend/src/components` | 交互组件 |
| `tests` | 单元、集成、端到端测试 |

## 2. 后端实现说明

### 2.1 Workflow

关键文件：

- `backend/core/workflow.py`
- `backend/core/state.py`
- `backend/core/checkpoint_store.py`

职责：

- 初始化会话工作区
- 驱动 LangGraph 工作流
- 管理恢复与 checkpoint 状态
- 在反思阶段写回历史、评估、记忆、轨迹和 Skill

### 2.2 Planner

关键文件：

- `backend/agents/planner/planner_agent.py`
- `backend/tools/skills/registry.py`
- `backend/learning/skill_learning.py`

当前策略：

- 先根据 query、intent、memory 召回方法 family
- 再展开 family 下的高置信 variant
- 将 `skill_name`、`method_variant`、`analysis_type` 写入计划步骤 `tool_args`

### 2.3 Executor

关键文件：

- `backend/agents/executor/executor_agent.py`
- `backend/sandbox/safe_executor.py`
- `backend/sandbox/security.py`

当前策略：

- 工具步骤通过统一 `ToolRegistry` 执行
- Python 步骤采用 reflection 写码范式
- 失败后基于反思结果重试，而不是直接模板化补救
- 支持用户中断与子进程终止

### 2.4 Memory

关键文件：

- `backend/agents/memory/manager.py`
- `backend/agents/memory/factory.py`

职责：

- 规划前提供长期记忆上下文
- 任务完成后写回用户偏好、分析方法、数据摘要

### 2.5 MCP

关键文件：

- `backend/tools/mcp/client.py`
- `backend/tools/mcp/runtime.py`
- `backend/tools/mcp/wrapper.py`
- `backend/tools/registry.py`

职责：

- 动态发现 MCP 工具
- 统一包装为项目内部工具
- 在规划和执行前刷新工具集

### 2.6 可视化与中文字体

关键文件：

- `backend/tools/builtin/visualization.py`

当前策略：

- 初始化 matplotlib 时自动注册 Windows 常见中文字体。
- 全局设置 `font.sans-serif` 回退链，优先使用 `Microsoft YaHei`、`SimHei`、`SimSun`、`DengXian`。
- 设置 `axes.unicode_minus = False`，避免中文图表中的负号显示异常。

## 3. Evaluator 体系

### 3.1 关键文件

- `backend/evaluation/orchestrator.py`
- `backend/evaluation/checks/artifact_checks.py`
- `backend/evaluation/checks/process_checks.py`
- `backend/evaluation/checks/report_checks.py`
- `backend/evaluation/checks/statistical_checks.py`

### 3.2 评估分层

- `artifact`：产物结构与文件存在性
- `process`：过程质量、重试与失败模式
- `report`：报告完整性、摘要质量、结论一致性
- `statistical`：本地复算的统计硬校验

### 3.3 已启用的 statistical verifier

- `descriptive_analysis`
- `regression_analysis`
- `survival_analysis`

### 3.4 正式评估对象

持久化位置：`backend/storage/history_storage.py`

正式对象表：`evaluation_reports`

审阅字段：

- `review_status`
- `review_label`
- `review_comment`
- `reviewed_by`

审阅只管理评估结果，不阻塞 Skill 自动启用。

## 4. 分层 Skill 体系

### 4.1 顶层 family

- `descriptive_analysis`
- `statistical_test`
- `regression_analysis`
- `survival_analysis`
- `epidemiology_analysis`
- `visualization`
- `general`

### 4.2 关键元数据

位于 `backend/tools/skills/models.py`：

- `method_family`
- `method_variant`
- `process_signature`
- `input_schema_signature`
- `verifier_family`
- `confidence_score`
- `lifecycle_state`
- `verifier_pass_rate`

### 4.3 lifecycle_state

- `active`
- `candidate`
- `deprecated`
- `legacy`

规则：

- family verifier 通过的 `descriptive/regression/survival` Skill 可自动 `active`
- 被人工审阅标记为 `disputed` 的关联 Skill 自动降为 `candidate`
- 旧 `learned_*` Skill 迁移后保留为 `legacy`

## 5. 存储层

关键文件：`backend/storage/history_storage.py`

当前 SQLite 维护：

- `conversations`
- `messages`
- `analysis_records`
- `evaluation_reports`
- `method_preferences`

`analysis_records` 已补充：

- `trajectory_id`
- `evaluation_id`
- `task_family`
- `evaluation_score`
- `evaluation_passed`
- `evaluation_summary`
- `review_status`

## 6. API 说明

### 6.1 历史与分析

- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/analysis`
- `GET /api/analysis/{analysis_id}`
- `GET /api/analysis/{analysis_id}/evaluation`
- `POST /api/analysis/{analysis_id}/evaluation/review`
- `POST /api/analysis/{analysis_id}/rerun`
- `POST /api/analysis/{analysis_id}/promote-variant`

### 6.2 方法库

- `GET /api/method-families`
- `GET /api/method-families/{family}/variants`
- `POST /api/method-families/{family}/preferred-variant`

### 6.3 学习与 Skill

- `GET /api/learning/trajectories`
- `GET /api/learning/trajectories/{trajectory_id}`
- `GET /api/learning/skills`
- `GET /api/skills`
- `POST /api/skills`
- `PUT /api/skills/{name}`

### 6.4 WebSocket

- `WebSocket /ws/{session_id}`
- `GET /ws/{session_id}/status`

WebSocket 最终消息字段包含：

- `analysis_id`
- `trajectory_id`
- `task_family`
- `evaluation_score`
- `evaluation_report`

## 7. 前端说明

### 7.1 Chat 页面

关键文件：

- `frontend/src/views/ChatView.vue`
- `frontend/src/components/AgentMessage.vue`
- `frontend/src/components/ChatWindow.vue`

能力：

- 会话恢复
- 评估卡片展示
- 重新运行
- 提升为新变体
- 跳转审阅

### 7.2 History 页面

关键文件：`frontend/src/views/HistoryView.vue`

能力：

- 列表与详情联动
- 查看完整评估对象
- 查看分项得分、硬失败、指标断言
- 提交评估审阅
- 重新运行
- 提升为新变体

### 7.3 Methods 页面

关键文件：`frontend/src/views/MethodsView.vue`

能力：

- 查看 family 与 variant
- 查看状态、通过率、最近使用
- 设置 preferred variant
- 查看关联评估

## 8. 开发流程

### 8.1 安装与启动

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

Set-Location frontend
npm install
Set-Location ..

python -m uvicorn backend.api.main:app --reload
```

前端：

```powershell
Set-Location frontend
npm run dev
```

### 8.2 校验命令

```powershell
ruff check backend tests
mypy backend
pytest -q

Set-Location frontend
npm run lint
npm run typecheck
```

### 8.3 修改建议

- 改工作流前先确认 `backend/core/workflow.py` 与 `backend/core/state.py` 的状态字段是否同步。
- 改评估器前先补测试，再改 `backend/evaluation/checks/`。
- 改方法库前同步检查：
  - `backend/tools/skills/models.py`
  - `backend/tools/skills/registry.py`
  - `backend/learning/skill_learning.py`
  - `frontend/src/services/api.ts`
  - `frontend/src/views/MethodsView.vue`
- 新增接口后同步更新：
  - `backend/api/main.py`
  - `frontend/src/services/api.ts`
  - `frontend/src/types/index.ts`

## 9. 测试覆盖重点

当前重点测试文件：

- `tests/test_evaluation.py`
- `tests/test_api.py`
- `tests/test_skills.py`
- `tests/test_planner_skill_disclosure.py`
- `tests/test_websocket_completion.py`
- `tests/test_workflow.py`

建议继续保持：

- 回归与生存分析正反样本测试
- 方法 family / variant 检索测试
- WebSocket 完成消息字段测试
- History / Methods 路由测试

## 10. 注意事项

- 不要删除旧 `learned_*` Skill，先迁移为 `legacy`。
- 不要把 `_validate_execution()` 当成主路径，它现在只做 fallback。
- 如果评估审阅标记为 `disputed`，需要同步检查关联 Skill 是否降级。
- 所有新功能都应同步更新文档与前端类型定义。
