---
name: descriptive_statistics
version: 1.0.0
description: 描述性统计分析技能，提供数据的基本统计特征计算
author: PubHAgent Team
tags:
  - statistics
  - descriptive
  - data-analysis
category: statistics
min_python_version: "3.10"
dependencies:
  - pandas
  - numpy
  - scipy
---

# 描述性统计分析

## 能力描述

**能力范围**：计算数据的基本统计特征，包括集中趋势、离散程度、分布形态等描述性统计量。

**限制条件**：
- 不支持推断性统计分析（如假设检验、置信区间估计）
- 不支持复杂的多变量分析
- 分组分析仅支持单一分组变量
- 不自动处理时间序列数据的特殊性质

**适用场景**：
- 数据探索性分析的第一步
- 数据质量评估（缺失值、异常值识别）
- 研究报告中的基线特征描述
- 变量分布特征初步了解

## 参数

- `data_source`: (string) 数据源路径或数据框变量名
- `variables`: (array) 需要分析的变量列表
- `statistics`: (array) 统计量类型，可选值: mean, median, std, var, min, max, quartiles, skewness, kurtosis [可选]
- `group_by`: (string) 分组变量名 [可选]
- `output_format`: (string) 输出格式，可选值: table, dict, markdown [可选] 默认: table

## 提示词模板

请对数据集 `{data_source}` 中的以下变量进行描述性统计分析：
变量列表：{variables}

{group_by_instruction}

请计算以下统计量：
{statistics_list}

请以 {output_format} 格式输出结果，包括：
1. 各变量的基本统计量
2. 数据分布特征描述
3. 异常值检测结果（如有）
4. 缺失值统计

## 使用示例

### 示例 1：基本描述性统计

**输入**
- data_source: "patient_data.csv"
- variables: ["age", "bmi", "blood_pressure"]
- statistics: ["mean", "std", "min", "max"]

**输出**
```
变量统计摘要：
| 变量 | 均值 | 标准差 | 最小值 | 最大值 |
|------|------|--------|--------|--------|
| age  | 45.3 | 12.5   | 18     | 85     |
| bmi  | 25.6 | 4.2    | 16.5   | 42.1   |
| blood_pressure | 120.5 | 15.3 | 90 | 180 |
```

### 示例 2：分组描述性统计

**输入**
- data_source: "clinical_trial.csv"
- variables: ["treatment_effect", "side_effects"]
- statistics: ["mean", "median", "quartiles"]
- group_by: "treatment_group"

**输出**
按治疗组别分组的统计结果...

## 注意事项

- 对于分类变量，自动计算频数和百分比
- 缺失值默认排除，在结果中单独报告
- 正态性检验结果将作为分布描述的参考
- 大数据集会自动进行采样以提高效率
