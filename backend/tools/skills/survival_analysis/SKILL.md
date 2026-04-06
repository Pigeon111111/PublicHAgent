---
name: survival_analysis
version: 1.0.0
description: 生存分析技能，支持生存曲线估计和风险模型分析
author: PubHAgent Team
tags:
  - survival
  - kaplan-meier
  - cox-model
  - time-to-event
category: statistics
min_python_version: "3.10"
dependencies:
  - pandas
  - numpy
  - lifelines
  - scipy
---

# 生存分析

## 参数

- `data_source`: (string) 数据源路径
- `time_variable`: (string) 生存时间变量名
- `event_variable`: (string) 事件发生变量名（0=删失，1=事件）
- `analysis_type`: (string) 分析类型，可选值: kaplan-meier, cox, both [可选] 默认: both
- `group_variable`: (string) 分组变量名 [可选]
- `covariates`: (array) Cox 模型协变量列表 [可选]
- `strata`: (array) 分层变量列表 [可选]
- `confidence_level`: (number) 置信水平 [可选] 默认: 0.95

## 提示词模板

请对数据集 `{data_source}` 进行生存分析：

**数据信息**
- 生存时间变量: {time_variable}
- 事件变量: {event_variable}

{group_section}

{covariates_section}

请执行以下分析：
1. 描述性统计（事件数、删失数、中位随访时间）
2. Kaplan-Meier 生存曲线估计
3. 生存率比较（Log-rank 检验）
4. Cox 比例风险模型（如适用）
5. 比例风险假设检验
6. 风险比（HR）计算与解释

置信水平: {confidence_level}

## 使用示例

### 示例 1：Kaplan-Meier 分析

**输入**
- data_source: "cancer_survival.csv"
- time_variable: "survival_months"
- event_variable: "death"
- analysis_type: "kaplan-meier"
- group_variable: "treatment_group"

**输出**
```
生存分析结果：

描述性统计：
| 组别 | 样本量 | 事件数 | 删失数 | 中位生存时间(月) |
|------|--------|--------|--------|------------------|
| 对照组 | 100 | 65 | 35 | 24.5 |
| 治疗组 | 100 | 45 | 55 | 36.2 |

Log-rank 检验: χ² = 8.5, p = 0.003

1年生存率: 对照组 72%, 治疗组 85%
3年生存率: 对照组 38%, 治疗组 58%
```

### 示例 2：Cox 回归模型

**输入**
- data_source: "cardiovascular_study.csv"
- time_variable: "follow_up_years"
- event_variable: "cv_event"
- analysis_type: "cox"
- covariates: ["age", "sex", "smoking", "hypertension", "diabetes"]

**输出**
```
Cox 比例风险模型结果：

模型拟合: Likelihood ratio test = 45.3, p < 0.001

风险比（HR）：
| 变量 | HR | 95% CI | p值 |
|------|-----|--------|-----|
| age | 1.05 | [1.02, 1.08] | <0.001 |
| sex (male) | 1.45 | [1.10, 1.92] | 0.008 |
| smoking | 1.78 | [1.35, 2.35] | <0.001 |
| hypertension | 1.56 | [1.18, 2.06] | 0.002 |
| diabetes | 2.12 | [1.58, 2.84] | <0.001 |

比例风险假设检验: p = 0.42 (满足假设)
```

## 注意事项

- 自动检测和处理删失数据
- 支持左删失和区间删失数据
- 比例风险假设不满足时提供替代方案建议
- 自动生成生存曲线图
- 竞争风险模型可作为高级选项
