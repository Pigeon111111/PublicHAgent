---
name: regression_analysis
version: 1.0.0
description: 回归分析技能，支持多种回归模型的建立和诊断
author: PubHAgent Team
tags:
  - regression
  - linear-models
  - prediction
category: statistics
min_python_version: "3.10"
dependencies:
  - pandas
  - numpy
  - scipy
  - statsmodels
  - sklearn
---

# 回归分析

## 能力描述

**能力范围**：建立和诊断多种回归模型，包括线性回归、Logistic回归、Poisson回归、Cox比例风险模型，提供回归系数估计、模型拟合优度评估、残差诊断等功能。

**限制条件**：
- 不支持非线性回归模型的自动拟合
- 不支持混合效应模型
- 不支持分位数回归
- 不自动处理高维数据的变量选择
- Cox模型不支持时变协变量

**适用场景**：
- 因果关系探索性分析
- 风险因素识别
- 预测模型构建
- 协变量调整分析

## 参数

- `data_source`: (string) 数据源路径
- `dependent_variable`: (string) 因变量名称
- `independent_variables`: (array) 自变量列表
- `model_type`: (string) 模型类型，可选值: linear, logistic, poisson, cox [可选] 默认: linear
- `covariates`: (array) 协变量列表 [可选]
- `interaction_terms`: (array) 交互项定义 [可选]
- `diagnostics`: (boolean) 是否进行模型诊断 [可选] 默认: true

## 提示词模板

请对数据集 `{data_source}` 进行回归分析：

**模型设定**
- 因变量: {dependent_variable}
- 自变量: {independent_variables}
- 模型类型: {model_type}

{covariates_section}

{interaction_section}

请执行以下分析：
1. 模型拟合与参数估计
2. 回归系数解释（包括效应量和置信区间）
3. 模型拟合优度评估
4. 残差诊断和假设检验
5. 多重共线性检测
6. 影响点分析

## 使用示例

### 示例 1：简单线性回归

**输入**
- data_source: "health_survey.csv"
- dependent_variable: "bmi"
- independent_variables: ["age", "exercise_hours"]
- model_type: "linear"

**输出**
```
线性回归模型结果：
R² = 0.35, 调整R² = 0.34
F(2, 997) = 268.5, p < 0.001

回归系数：
| 变量 | 系数 | 标准误 | t值 | p值 | 95% CI |
|------|------|--------|-----|-----|--------|
| Intercept | 28.5 | 1.2 | 23.8 | <0.001 | [26.1, 30.9] |
| age | 0.05 | 0.01 | 5.0 | <0.001 | [0.03, 0.07] |
| exercise_hours | -0.8 | 0.1 | -8.0 | <0.001 | [-1.0, -0.6] |
```

### 示例 2：Logistic 回归

**输入**
- data_source: "disease_outcome.csv"
- dependent_variable: "disease_status"
- independent_variables: ["age", "smoking", "bmi"]
- model_type: "logistic"
- covariates: ["gender", "education"]

**输出**
Logistic 回归模型结果，包括 OR 值和 95% CI...

## 注意事项

- 自动检测因变量类型并建议合适的模型
- 分类自变量自动进行哑变量编码
- 提供多重共线性诊断（VIF）
- 残差分析包括正态性、同方差性检验
- 对于 Logistic 回归，报告 OR 值而非原始系数
