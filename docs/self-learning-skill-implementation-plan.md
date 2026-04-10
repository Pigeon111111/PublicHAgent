# PubHAgent 自学习 Skill 闭环实施计划

## 背景

当前 PubHAgent 已有 Planner、Executor、Reflection、Memory、Tool、MCP、Skills 等模块，但主工作流仍存在模拟执行路径，Executor 默认在宿主机执行代码，Skill 管理和能力缺口识别没有形成从失败轨迹到成功复用的闭环。

本计划参考 Hermes Agent 的过程性记忆思路：Agent 在复杂任务中积累成功与失败路径，成功后将方法沉淀为 `SKILL.md` 与可选脚本，后续同类任务直接检索和复用，从而实现数据分析能力的自我进化。

## 目标

- 打通真实数据分析执行链路：用户上传或指定数据文件后，系统能完成读取、分析、验证、报告输出。
- 默认执行路径具备安全边界：代码不直接在无限制宿主机环境中执行；文件访问限制在会话输入、工作区和输出目录。
- 支持新分析方法探索：现有工具或 Skill 不覆盖时，系统可通过代码生成、失败修复和重新规划逐步尝试。
- 成功路径自动沉淀为 Skill：记录尝试轨迹，提炼成功方法，写入新的 `SKILL.md` 或更新现有 Skill，并进入后续 Planner 检索。
- Skill 复用可验证：第二次同类任务优先命中已学习 Skill，减少重复试错。

## 非目标

- 不实现完全多租户隔离。
- 不实现远程分布式沙箱。
- 不默认启用高危系统命令、网络访问或任意目录读写。
- 不将统计结论视为医学或公共卫生决策建议，系统只提供分析过程与结果解释。

## 技术方案

### 阶段 0：安全执行与可运行性基线

- 修复工作流模拟执行，改为真实调用 Planner、Executor、Reflection。
- 引入会话工作区：
  - `data/sessions/{session_id}/input`
  - `data/sessions/{session_id}/workspace`
  - `data/sessions/{session_id}/output`
- 将上传目录中的可用数据文件链接或复制到会话输入目录。
- Executor 默认使用安全执行器：
  - 优先 Docker 沙箱。
  - Docker 不可用时使用受限本地执行器，先通过静态安全策略，再以会话工作区为运行目录执行。
- 限制代码文件访问：
  - 允许读取 `input` 和 `workspace`。
  - 允许写入 `workspace` 和 `output`。
  - 阻止访问项目配置、密钥、用户主目录和任意绝对路径。
- 注册内置工具并接入 ToolGuard。

### 阶段 1：真实分析链路

- Planner 使用工具和 Skill 能力边界生成结构化计划。
- Executor 每步只接收隔离上下文：当前步骤、上一步结果、预期输出、允许文件路径、允许工具。
- Reflection 根据执行结果、输出文件和验证信息判断是否继续、修复或重新规划。
- 工作流生成最终 Markdown 报告，包含计划、执行摘要、产物路径、风险和验证结果。

### 阶段 2：分析轨迹记录

- 新增 `AnalysisTrajectory`、`AttemptRecord`、`ValidationRecord`。
- 每次任务记录：
  - 用户请求、意图、数据文件。
  - 计划步骤。
  - 每次代码、错误、修复说明。
  - 成功输出、报告和产物。
  - 是否适合沉淀为 Skill。
- 轨迹保存到 `data/trajectories`，必要摘要写入 Memory。

### 阶段 3：自主 Skill 学习

- 新增 Skill 学习器：
  - 从成功轨迹提炼适用场景、输入要求、步骤、验证规则、失败排查和代码模板。
  - 若已有相近 Skill，则更新版本；否则创建新 Skill。
  - 自动生成 `SKILL.md`，可选生成 `scripts/` 辅助脚本。
- 新增 Skill 安全与质量检查：
  - 文件名和目录名合法。
  - 禁止危险命令、任意路径访问、明文密钥。
  - 要求存在适用场景、限制条件和验证规则。
- 将学习结果写入 Skill 注册表并可立即复用。

### 阶段 4：Skill 复用策略

- Planner 在生成计划前加载启用 Skill 的索引。
- 对新请求优先匹配已学习 Skill。
- 若 Skill 命中，计划中明确引用 Skill，并把 Skill 内容注入 Executor 上下文。
- 若执行失败，轨迹记录为该 Skill 的失败样本，后续成功后更新 Skill。

### 阶段 5：API、测试和文档

- 修复 Skill CRUD API 的注册表方法名。
- 暴露轨迹和已学习 Skill 状态查询接口。
- 增加单元测试和集成测试：
  - 安全执行器可读取用户数据。
  - 危险代码被拒绝。
  - 完整数据分析可执行。
  - 新分析方法成功后生成 Skill。
  - 同类任务复用已学习 Skill。
- 更新 README、开发文档和结果验证文档。

## 验收标准

- `pytest` 中新增后端测试通过。
- `ruff check backend tests` 不因新增代码引入错误。
- `mypy backend` 不因新增模块引入类型错误。
- 用户上传或指定 CSV 后，系统能完成至少一种真实分析并生成报告。
- 新分析方法在成功执行后会生成或更新 Skill。
- 后续同类请求可检索并复用该 Skill。

## 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 自动学习错误方法 | 高 | 仅从成功且通过验证的轨迹生成 Skill，并记录限制条件 |
| Docker 不可用 | 中 | 提供受限本地执行器，但保留明确安全提示和路径限制 |
| LLM 输出不稳定 | 高 | 增加启发式回退计划和报告生成，测试不依赖真实 LLM |
| 路径越权 | 高 | 所有文件路径归一化后校验 allowed roots |
| Skill 污染 | 中 | Skill 生成前做安全扫描，写入版本与来源轨迹 |

## 实施结果

- 已新增会话工作区与受限代码执行器，代码可读取会话输入数据并把产物写入会话输出目录。
- 已修复工作流主链路，`AgentWorkflow.run()` 会真实执行 Planner、Executor、Reflection，并生成最终报告。
- 已新增分析轨迹记录和 Skill 学习服务，成功分析会写入 `data/trajectories`，并生成 `backend/tools/skills/learned_*/SKILL.md`。
- 已接入已学习 Skill 检索，后续相似请求可在 Planner 回退计划中引用历史学习结果。
- 已补齐学习轨迹与已学习 Skill 查询 API：`/api/learning/trajectories`、`/api/learning/trajectories/{trajectory_id}`、`/api/learning/skills`。
- 已新增 `tests/test_self_learning_workflow.py`，覆盖安全执行器路径边界和完整自学习闭环。

## 实施顺序

1. 写入计划文档。
2. 实现会话工作区与安全执行器。
3. 修改 Executor，接入安全执行与轨迹记录。
4. 修改 AgentWorkflow，使用真实 Agent。
5. 实现 Skill 学习器和注册表落盘刷新。
6. 修复 API 与工具注册。
7. 增加测试和文档。
8. 运行 lint、type check、pytest。

## 追加实施结果：可观察与可中断执行

- 后端 WebSocket 已改为后台任务执行用户请求，接收循环可继续处理 `interrupt` 和 `ping`。
- `SessionContext` 记录运行状态、最近错误、事件时间线和当前任务，`GET /ws/{session_id}/status` 可查询会话快照。
- `AgentWorkflow` 支持外部 `cancellation_checker`，在工作流节点和执行循环边界响应用户中断。
- `ExecutorAgent` 通过 `asyncio.to_thread()` 调用受限执行器，避免长时间 Python 分析脚本阻塞 WebSocket 事件循环。
- `SafeCodeExecutor` 使用 `subprocess.Popen()` 轮询子进程，支持超时和用户中断时杀进程。
- 前端聊天页新增任务观察区，展示连接状态、任务状态、进度、运行日志、错误信息和中断请求状态。
- 前端 WebSocket 客户端补齐显式断开、重连控制、心跳和发送失败返回值。
- 前端补齐 ESLint 配置并升级 Vite、Vue 插件、TypeScript、vue-tsc，`npm audit --audit-level=moderate` 已无漏洞。
