# 运行时升级说明（2026-04）

本文档记录 2026-04 这一轮运行时与交互层升级后的实际状态，重点覆盖 MCP、Memory、History、持久化 checkpoint、结构化 evaluator、分层 Skill 与前端交互能力。

## 1. 本轮目标

这一轮改造不是重写 Agent，而是在既有 LangGraph 主链路上补齐生产可用能力：

- 把 MCP 工具接入 Planner 与 Executor 默认主路径。
- 把 Memory 接入规划读取与任务完成后的写回。
- 把 History 从进程内对象切换到 SQLite 持久化。
- 把 LangGraph checkpoint 升级为持久化恢复链路。
- 把代码执行升级为 reflection 写码范式。
- 把结果验证升级为正式 evaluator，并补齐回归与生存分析硬校验。
- 把 Skill 治理升级为固定 family + 可学习 variant 的分层体系。
- 把前端升级为可审阅、可恢复、可交互的方法库与评估界面。

## 2. 当前主链路

### 2.1 执行流程

1. 前端在 `frontend/src/views/ChatView.vue` 创建或恢复 `session_id`。
2. WebSocket 客户端 `frontend/src/services/websocket.ts` 发送用户消息或恢复请求。
3. 后端 `backend/api/websocket.py` 创建会话上下文、持久化聊天消息、初始化分析记录。
4. `backend/core/workflow.py` 驱动 LangGraph 主链路：
   - `intent`
   - `planner`
   - `executor`
   - `reflection`
5. `reflection` 节点先走结构化 evaluator，再折叠为兼容旧链路的验证结果。
6. 工作流完成后写回：
   - 历史记录
   - 正式评估对象
   - 轨迹
   - Skill 学习结果
   - 长期记忆
7. WebSocket 最终消息把 `evaluation_report`、`analysis_id`、`trajectory_id` 回传给前端。

### 2.2 用户中断与恢复

- 用户在前端触发中断后，`SafeCodeExecutor` 会终止运行中的子进程。
- `backend/core/checkpoint_store.py` 负责持久化 checkpoint 状态。
- `GET /ws/{session_id}/status` 会返回 `checkpoint.resumable`。
- 前端在 `ChatWindow.vue` 中暴露恢复入口。
- 用户恢复后，`backend/api/websocket.py` 会调用 `AgentWorkflow.resume()` 从最近可用 checkpoint 继续执行。

当前支持：

- 中断长任务
- 终止代码执行子进程
- 通过持久化 checkpoint 恢复工作流

当前不支持：

- 节点内部的细粒度断点续跑
- 可视化编辑中间状态后继续执行

## 3. MCP 主链路接入

### 3.1 关键文件

- `backend/tools/mcp/client.py`
- `backend/tools/mcp/runtime.py`
- `backend/tools/mcp/wrapper.py`
- `backend/tools/registry.py`

### 3.2 实现方式

- `MCPToolRuntime` 管理多个 MCP server 的连接与工具缓存。
- `MCPWrappedTool` 把 MCP 工具统一包装成项目内部 `BaseTool`。
- `ToolRegistry.refresh_mcp_tools()` 会在规划与执行前刷新 MCP 工具。
- Planner 和 Executor 都通过统一的 `ToolRegistry` 感知内置工具与 MCP 工具。

结果是：

- Planner 可以把 MCP 工具纳入选型。
- Executor 可以与 builtin tools 以同一种方式执行 MCP 工具。

## 4. Memory 主链路接入

### 4.1 关键文件

- `backend/agents/memory/manager.py`
- `backend/agents/memory/factory.py`
- `backend/core/workflow.py`

### 4.2 实现方式

- 工作流初始化时尝试创建 `MemoryManager`。
- Planner 在构建计划前读取长期记忆。
- 任务完成后，工作流写回方法摘要、数据特征、对话摘要和关联 Skill 信息。
- 用户修改模型或 Key 配置时，会清理相关 MemoryManager 缓存。

结果是：

- Memory 已从“仓库里有实现但默认不参与主流程”变成默认主链路能力。

## 5. History、正式评估对象与聊天主流程打通

### 5.1 持久化对象

`backend/storage/history_storage.py` 现在维护四类核心表：

- `conversations`
- `messages`
- `analysis_records`
- `evaluation_reports`

同时新增：

- `method_preferences`

### 5.2 analysis_records 新字段

- `trajectory_id`
- `evaluation_id`
- `task_family`
- `evaluation_score`
- `evaluation_passed`
- `evaluation_summary`
- `review_status`

### 5.3 evaluation_reports 字段

- `id`
- `analysis_record_id`
- `session_id`
- `trajectory_id`
- `task_family`
- `final_score`
- `passed`
- `summary`
- `report_json`
- `review_status`
- `review_label`
- `review_comment`
- `reviewed_by`
- `created_at`
- `updated_at`

### 5.4 结果

- 聊天主流程会自动创建和更新分析记录。
- 正式评估对象独立持久化，不再只把评估摘要塞进 `analysis_records`。
- 历史页看到的结果与实时聊天输出使用同一持久化来源。

## 6. Evaluator 升级

### 6.1 关键文件

- `backend/evaluation/orchestrator.py`
- `backend/evaluation/checks/artifact_checks.py`
- `backend/evaluation/checks/process_checks.py`
- `backend/evaluation/checks/report_checks.py`
- `backend/evaluation/checks/statistical_checks.py`

### 6.2 评估分层

- `artifact`：输出文件、结构完整性、JSON 契约
- `statistical`：针对任务家族的硬性统计验证
- `process`：重试次数、失败模式、无效 replan、沙箱拒绝等过程质量
- `report`：报告结构、结论一致性与软评分

### 6.3 已启用的硬校验

- `descriptive_analysis`
- `regression_analysis`
- `survival_analysis`

#### regression_analysis 输出契约

- `model_type`
- `target`
- `features`
- `coefficients`
- `p_values`
- `fit_metrics`
- `confidence_intervals`
- `sample_size`

#### survival_analysis 输出契约

- `time_column`
- `event_column`
- `group_column`
- `km_summary`
- `median_survival`
- `log_rank`
- `cox_summary`
- `sample_size`

### 6.4 判定策略

- 参考结果统一通过重新读取输入数据本地复算得到。
- 容差使用 `rel_tol + abs_tol` 双阈值。
- 模型类型错误、方向性错误、事件编码错误直接判硬失败。
- `workflow.py` 中旧 `_validate_execution()` 仅保留为 evaluator 异常时的 fallback。

## 7. Reflection 写码范式

### 7.1 关键文件

- `backend/agents/executor/executor_agent.py`
- `backend/agents/executor/schemas.py`

### 7.2 执行闭环

1. 根据当前 step 生成代码
2. 在 `SafeCodeExecutor` 中执行
3. 分析执行结果
4. 通过 reflection 提示归纳失败原因与修复方向
5. 生成修复版代码并重试

这让 Executor 从“仅在报错后补救”升级为“生成 -> 执行 -> 反思 -> 修复”的闭环。

## 8. 分层 Skill 体系

### 8.1 固定顶层方法家族

- `descriptive_analysis`
- `statistical_test`
- `regression_analysis`
- `survival_analysis`
- `epidemiology_analysis`
- `visualization`
- `general`

### 8.2 新增元数据

`backend/tools/skills/models.py` 中的 `SkillMetadata` 已新增：

- `analysis_domain`
- `method_family`
- `method_variant`
- `process_signature`
- `input_schema_signature`
- `verifier_family`
- `provenance_trajectory_id`
- `confidence_score`
- `lifecycle_state`
- `last_used_at`
- `usage_count`
- `verifier_pass_rate`

### 8.3 生命周期策略

- `active`
- `candidate`
- `deprecated`
- `legacy`

规则：

- `descriptive_analysis`、`regression_analysis`、`survival_analysis` 在通过 family 专用 verifier 后可自动进入 `active`。
- 其他 family 先进入 `candidate`。
- 如果评估结果被人工标记为 `disputed`，关联 Skill 会自动降级为 `candidate`。

### 8.4 family / variant 检索

`backend/tools/skills/registry.py` 和 `backend/learning/skill_learning.py` 已支持：

- family 摘要
- variant 列表
- family 排序
- variant 选择
- legacy Skill 迁移

## 9. Planner 的渐进式披露

### 9.1 核心思路

Planner 不再把所有 Skill 文本平铺进 prompt，而是按以下顺序注入：

1. 根据 query、intent、memory 召回 top-N family
2. 先只展示 family 摘要
3. 对高置信 family 再展开 top-K variant
4. 若 family 命中但 variant 置信度低，则提示可以学习新细分方法

### 9.2 当前实现

- `backend/learning/skill_learning.py` 提供 family/variant 上下文构建能力。
- `backend/agents/planner/planner_agent.py` 会把高置信 variant 补充到计划步骤的 `tool_args` 中，包括：
  - `skill_name`
  - `method_variant`
  - `analysis_type`

这让后续评估、历史落盘和方法库展示可以知道本次实际使用了哪个细分方法。

## 10. 前端交互升级

### 10.1 Chat

- 关键文件：
  - `frontend/src/views/ChatView.vue`
  - `frontend/src/components/AgentMessage.vue`
  - `frontend/src/components/ChatWindow.vue`

能力：

- 显示评估卡片
- 展示方法家族、得分、通过状态、关键硬失败原因
- 支持进入审阅
- 支持重新运行
- 支持从本次分析学习为新变体
- 支持恢复上次任务

### 10.2 History

- 关键文件：`frontend/src/views/HistoryView.vue`

能力：

- 分析列表与详情联动
- 查看完整评估对象
- 查看分项得分、指标断言、hard failures、findings
- 提交评估审阅
- 重新运行
- 提升为新变体
- 跳转关联方法

### 10.3 Methods

- 关键文件：`frontend/src/views/MethodsView.vue`

能力：

- 浏览 family 列表
- 浏览 family 下的 variant
- 查看状态、通过率、最近使用、是否 preferred
- 设为优先或取消优先
- 查看关联评估并跳转到历史详情

## 11. 中文绘图字体修复

关键文件：

- `backend/tools/builtin/visualization.py`

修复内容：

- 初始化 matplotlib 时自动扫描并注册 Windows 常见中文字体文件。
- 默认优先使用 `Microsoft YaHei`、`SimHei`、`SimSun`、`DengXian` 等字体。
- 统一设置 `axes.unicode_minus = False`，避免负号在中文图表中显示异常。

结果：

- `matplotlib` / `seaborn` 生成中文标题、中文坐标轴和中文注释时，不再依赖 Arial 回退。
- 针对 `Glyph xxxx missing from font(s) Arial` 的告警已加入回归测试。

## 12. API 增量

### 11.1 分析与评估

- `GET /api/analysis/{analysis_id}`
- `GET /api/analysis/{analysis_id}/evaluation`
- `POST /api/analysis/{analysis_id}/evaluation/review`
- `POST /api/analysis/{analysis_id}/rerun`
- `POST /api/analysis/{analysis_id}/promote-variant`

### 11.2 方法库

- `GET /api/method-families`
- `GET /api/method-families/{family}/variants`
- `POST /api/method-families/{family}/preferred-variant`

## 13. 当前状态总结

已经落地：

- MCP 主链路接入
- Memory 主链路接入
- History 持久化
- 持久化 checkpoint / 恢复链路
- reflection 写码范式
- regression / survival 专用统计校验
- 正式评估对象与审阅流
- 分层 Skill 与方法库
- 前端评估与方法交互

仍保留的保护性设计：

- 旧 `_validate_execution()` 作为 fallback，不是主路径
- 旧扁平 Skill 不删除，而是迁移为 `legacy`

这保证了新能力已经成为默认路径，但不会因为单点故障让整条分析链路失效。
