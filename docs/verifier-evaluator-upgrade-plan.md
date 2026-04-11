# Verifier / Evaluator 升级计划

本文档记录 verifier / evaluator 的目标方案。当前仓库已经落地 Phase 1 基础设施：`backend/evaluation/`、工作流接入、history/trajectory 持久化，以及描述统计任务的硬性统计校验；以下内容描述的是后续完整升级路径。

## 1. 为什么要升级

当前系统的验证逻辑主要集中在：

- `backend/core/workflow.py::_validate_execution()`

它的优势是简单、稳定、可快速闭环，但局限也很明显：

- 更像“任务完成检查”，不是“结果正确性验证”。
- 主要检查文件是否存在、执行是否成功、报告是否非空。
- 无法判断统计结果是否正确。
- 无法区分“代码成功运行但分析结论错误”和“代码本身失败”。
- 无法为后续 AgenticRL、离线评测或 A/B 对比提供可分解评分。

如果项目要跟进主流做法，这一层必须升级为“硬验证 + 多维评估 + 结构化评分”的组合系统。

## 2. 设计原则

### 2.1 参考方法

本方案主要参考三类公开方法：

- DeepAnalyze：强调真实数据环境中的 agentic 训练与 data-grounded trajectory synthesis，更适合我们把验证建立在真实数据、真实产物和真实流程之上，而不是只做格式检查。
- DSAEval：强调多维评估，覆盖 reasoning、code、results，适合本项目把“过程”“代码”“结果”拆开评分。
- LangGraph 官方 durable execution / interrupts 文档：要求恢复链路中的副作用可重放、可幂等，因此 verifier 设计必须尽量纯函数化，或至少具备幂等写入能力。

### 2.2 核心原则

1. 先硬验证，后软评估。
2. 先可验证奖励，后 LLM judge。
3. 先结果正确性，后文本质量。
4. 评分必须结构化、可追溯、可落盘。
5. 任何 LLM evaluator 都不能覆盖硬性失败。

## 3. 目标架构

建议新增一个独立评估层：

```text
workflow reflection node
  -> EvaluationOrchestrator
       -> ArtifactVerifier
       -> StatisticalVerifier
       -> ProcessEvaluator
       -> ReportEvaluator
       -> ScoreAggregator
  -> EvaluationReport
  -> history / trajectory / memory / frontend
```

### 3.1 建议新增目录

```text
backend/evaluation/
├── __init__.py
├── schemas.py
├── orchestrator.py
├── aggregator.py
├── artifact_collector.py
├── task_registry.py
├── checks/
│   ├── __init__.py
│   ├── artifact_checks.py
│   ├── schema_checks.py
│   ├── statistical_checks.py
│   ├── reproducibility_checks.py
│   └── process_checks.py
├── judges/
│   ├── __init__.py
│   └── report_judge.py
└── fixtures/
    └── task_specs/
```

## 4. 分层评估模型

### 4.1 第一层：Artifact Verifier

职责：

- 检查产物是否完整、命名是否正确、是否可解析。

检查项：

- `analysis_report.md` 是否存在、是否非空。
- `analysis_result.json` 是否存在、是否符合 schema。
- 图表文件是否存在且路径合法。
- 输出文件是否位于会话 `output` 目录下。
- 报告是否包含最基本章节：
  - 数据概览
  - 方法说明
  - 结果结论
  - 局限性或风险提示

建议实现文件：

- `backend/evaluation/checks/artifact_checks.py`
- `backend/evaluation/checks/schema_checks.py`

输出：

- `artifact_pass: bool`
- `artifact_score: float`
- `artifact_findings: list[...]`

### 4.2 第二层：Statistical Verifier

职责：

- 检查统计结果与参考答案或参考计算逻辑是否一致。

这是升级的核心层，优先级最高。

#### 任务族拆分

建议按当前项目已有能力分三个第一批任务族：

1. 描述统计
2. 回归分析
3. 生存分析

后续再扩展：

4. 假设检验
5. 时间序列
6. 文本/多模态数据分析

#### 校验方式

每类任务提供一套隐藏参考校验器：

- 输入：原始数据文件 + agent 产物
- 输出：结构化断言结果

示例：

- 描述统计：
  - 样本数
  - 均值
  - 中位数
  - 标准差
  - 缺失值统计
- 回归分析：
  - 系数方向
  - 关键系数数值误差
  - `p-value` 阈值判断
  - `R^2` 或拟合优度范围
- 生存分析：
  - 中位生存期
  - hazard ratio
  - log-rank 检验结果

误差建议：

- 采用 `abs_tol + rel_tol` 双阈值。
- 允许轻微浮点波动，不允许方向性错误和结论级错误。

建议实现文件：

- `backend/evaluation/checks/statistical_checks.py`
- `backend/evaluation/task_registry.py`
- `backend/evaluation/fixtures/task_specs/*.yaml`

输出：

- `stat_pass: bool`
- `stat_score: float`
- `metric_assertions: list[...]`

### 4.3 第三层：Process Evaluator

职责：

- 评估完成任务的过程质量，而不仅是最终产物。

这部分参考 DSAEval 的多维评估思路，但初版尽量避免纯主观判断。

指标建议：

- 计划长度是否过度冗长。
- 是否出现无效 replan。
- 修复次数是否过多。
- 是否多次调用错误工具。
- 是否反复生成被沙箱拒绝的代码。
- 是否重复读写同一输出。
- 总耗时是否异常。

建议实现文件：

- `backend/evaluation/checks/process_checks.py`

输入来源：

- `AgentState`
- `execution_results`
- `trajectory`
- `ExecutorAgent` 的 reflection 信息
- WebSocket 事件或运行日志摘要

输出：

- `process_score: float`
- `efficiency_penalty: float`
- `process_findings: list[...]`

### 4.4 第四层：Report Evaluator

职责：

- 评估报告是否表达清晰、是否解释了方法与结论、是否包含风险提示。

这层允许使用 LLM judge，但必须遵守两个限制：

1. 只能做软评分，不得覆盖硬验证失败。
2. 只评估文本质量与解释充分性，不评估数值真伪。

推荐 rubric：

- 方法说明是否自洽
- 结论是否与结果一致
- 是否指出样本/缺失值/偏差风险
- 是否避免过度归因

建议实现文件：

- `backend/evaluation/judges/report_judge.py`

输出：

- `report_score: float`
- `report_findings: list[...]`

## 5. 结构化评分模型

建议评分拆成“硬门槛 + 加权分”。

### 5.1 硬门槛

以下任意失败都直接 `passed = false`：

- 安全执行失败
- 关键产物缺失
- JSON schema 不合法
- 关键统计断言失败
- 可复现性检查失败

### 5.2 加权分

建议初版权重：

- Artifact Completeness：0.15
- Statistical Correctness：0.45
- Process Quality：0.20
- Report Quality：0.20

原因：

- 当前项目核心是公共卫生数据分析，结果正确性比语言质量更重要。

### 5.3 最终输出结构

建议在 `backend/evaluation/schemas.py` 定义：

- `EvaluationFinding`
- `MetricAssertion`
- `EvaluationScoreBreakdown`
- `EvaluationReport`

其中 `EvaluationReport` 至少包含：

- `passed`
- `final_score`
- `artifact_score`
- `stat_score`
- `process_score`
- `report_score`
- `hard_failures`
- `findings`
- `task_family`
- `evaluator_version`

## 6. 与当前工作流的对接方式

### 6.1 现状

当前 `reflection` 节点仍以 `_validate_execution()` 为主。

### 6.2 目标接法

建议在 `backend/core/workflow.py` 中逐步替换：

1. 保留 `_validate_execution()` 作为 fallback。
2. 新增 `_evaluate_execution()`，调用 `EvaluationOrchestrator`。
3. `reflection` 节点优先执行 `_evaluate_execution()`。
4. 如果 evaluator 初始化失败，再退回旧规则验证。

### 6.3 状态扩展

建议扩展 `backend/core/state.py::AgentState`：

- `evaluation_report`
- `evaluation_score`
- `evaluation_findings`
- `task_family`

### 6.4 下游同步

评估结果要同步写到：

- history analysis record
- trajectory
- learned skill metadata
- frontend 最终结果展示

## 7. 先补观测，再补强验证

在真正替换规则验证之前，建议先补观测字段。这一步是升级的前置条件。

### 7.1 需要新增的运行时观测

建议扩展以下结构：

- `backend/agents/executor/schemas.py::ExecutionResult`
- `backend/learning/trajectory.py::AnalysisTrajectory`

新增字段：

- 生成代码摘要
- 实际执行代码路径
- stderr / stdout 摘要
- 运行时长
- 重试次数
- reflection 决策
- 最终产物清单
- task_family

### 7.2 原因

没有这些字段，就很难做过程评估，也很难做后续训练或离线对比。

## 8. 可复现性检查

为了避免“偶然正确”，建议加入轻量可复现性检查。

做法：

- 对成功任务，在同一会话工作区内做一次只读复核，或对产物重新跑参考校验脚本。
- 不要求重新完整跑一遍 agent，只要求关键数值能复算。

建议实现文件：

- `backend/evaluation/checks/reproducibility_checks.py`

## 9. 任务规格注册机制

为了让 verifier 不写成一堆 if/else，建议引入任务规格注册表。

每个任务族配置：

- `task_family`
- 输入文件模式
- 期望产物
- 参考指标
- 容差
- 报告要求

推荐存储方式：

- YAML 或 JSON 规格文件
- Python 注册器负责加载并返回对应校验器

这样后续新增任务族时，只需新增规格和校验器，不必重写 workflow。

## 10. 渐进式落地顺序

### Phase 0：只补结构化观测

- 不改验证结论
- 仅补 evaluator 所需的 trace / artifact / runtime 字段

### Phase 1：影子模式运行 evaluator

- `_validate_execution()` 仍决定 pass/fail
- evaluator 只生成报告，不阻塞主链路
- 前端和 history 可查看 evaluator 结果

### Phase 2：对描述统计/回归分析启用硬验证

- 先覆盖最确定、最易程序化验证的任务
- 失败时直接标记验证失败

### Phase 3：加入 LLM report judge

- 只做软评分
- 不影响统计正确性硬判定

### Phase 4：输出训练/评测样本

- evaluator 结果进入 trajectory
- 为后续 AgenticRL、SFT 或离线 benchmark 做数据基础

## 11. 测试计划

建议新增：

```text
tests/evaluation/
├── test_artifact_checks.py
├── test_schema_checks.py
├── test_statistical_checks.py
├── test_process_checks.py
├── test_report_judge.py
└── test_evaluation_orchestrator.py
```

测试原则：

- 对每个任务族提供成功样本和失败样本。
- 失败样本要覆盖：
  - 文件缺失
  - JSON 格式错误
  - 数值偏差
  - 结论反向
  - 报告缺章节

## 12. 和 AgenticRL 的关系

这一层升级完成后，系统才具备真正的“可学习信号”：

- `hard_failures` 可作为离散惩罚
- `final_score` 可作为终局奖励
- `process_score` 可作为过程奖励
- `metric_assertions` 可作为细粒度信用分配信号

也就是说，verifier/evaluator 是后续 AgenticRL 的前置基础设施，不是可有可无的附属模块。

## 13. 本项目建议的最小实施包

如果只做第一轮最有价值的升级，我建议按下面顺序：

1. 新增 `backend/evaluation/schemas.py`
2. 新增 `artifact_checks.py`
3. 新增 `statistical_checks.py`
4. 为描述统计、回归分析、生存分析建立 `task_specs`
5. 在 `workflow.py` 中引入 `EvaluationOrchestrator`
6. 将 evaluator 报告写入 history / trajectory
7. 前端展示分项评分与失败原因

这套最小实施包能显著提升系统正确性控制，但不会把工程复杂度一下拉得过高。
