---
name: data_visualization
version: 1.0.0
description: 数据可视化技能，支持多种统计图表的创建和定制
author: PubHAgent Team
tags:
  - visualization
  - plotting
  - charts
  - graphics
category: visualization
min_python_version: "3.10"
dependencies:
  - pandas
  - numpy
  - matplotlib
  - seaborn
---

# 数据可视化

## 参数

- `data_source`: (string) 数据源路径
- `chart_type`: (string) 图表类型，可选值: histogram, boxplot, scatter, line, bar, heatmap, pairplot, survival_curve
- `variables`: (array) 变量列表
- `group_variable`: (string) 分组变量名 [可选]
- `title`: (string) 图表标题 [可选]
- `x_label`: (string) X轴标签 [可选]
- `y_label`: (string) Y轴标签 [可选]
- `color_palette`: (string) 配色方案 [可选] 默认: default
- `figure_size`: (array) 图表尺寸 [宽, 高] [可选] 默认: [10, 6]
- `save_path`: (string) 保存路径 [可选]
- `style`: (string) 样式主题 [可选] 默认: whitegrid

## 提示词模板

请基于数据集 `{data_source}` 创建 {chart_type} 图表：

**图表配置**
- 变量: {variables}
{group_section}

**样式设置**
- 标题: {title}
- X轴标签: {x_label}
- Y轴标签: {y_label}
- 配色方案: {color_palette}
- 图表尺寸: {figure_size}
- 样式主题: {style}

请生成符合学术出版标准的图表，包括：
1. 清晰的轴标签和标题
2. 适当的图例
3. 统计标注（如适用）
4. 高分辨率输出

## 使用示例

### 示例 1：直方图

**输入**
- data_source: "health_data.csv"
- chart_type: "histogram"
- variables: ["bmi"]
- group_variable: "gender"
- title: "BMI 分布按性别分组"
- x_label: "BMI (kg/m²)"
- y_label: "频数"

**输出**
生成带有性别分组的 BMI 直方图，包含：
- 两组数据的分布曲线
- 均值和中位数标注
- 正态分布拟合曲线

### 示例 2：箱线图

**输入**
- data_source: "clinical_trial.csv"
- chart_type: "boxplot"
- variables: ["treatment_effect"]
- group_variable: "treatment_group"
- title: "各治疗组疗效分布"
- style: "whitegrid"

**输出**
生成箱线图，显示：
- 各组的中位数和四分位数
- 异常值标记
- 显著性差异标注

### 示例 3：相关性热图

**输入**
- data_source: "biomarkers.csv"
- chart_type: "heatmap"
- variables: ["marker1", "marker2", "marker3", "marker4", "marker5"]
- title: "生物标志物相关性矩阵"
- color_palette: "coolwarm"

**输出**
生成相关性热图，包括：
- 相关系数数值标注
- 颜色条图例
- 显著性标记

### 示例 4：生存曲线

**输入**
- data_source: "survival_data.csv"
- chart_type: "survival_curve"
- variables: ["time", "event"]
- group_variable: "treatment"
- title: "Kaplan-Meier 生存曲线"

**输出**
生成生存曲线图，包括：
- 各组生存曲线及 95% CI
- 风险表
- Log-rank p值

## 注意事项

- 自动根据变量类型推荐合适的图表
- 支持中文字体显示
- 图表默认 DPI 为 300，适合出版
- 支持多种输出格式（PNG, PDF, SVG）
- 提供色盲友好的配色方案选项
