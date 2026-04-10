# 分析结果验证指南

本文档说明如何验证 PubHAgent 生成的分析结果是否正确。

## 验证原则

1. **交叉验证**：使用不同方法验证同一结果
2. **边界检查**：检查结果的合理范围
3. **逻辑一致性**：确保结果之间不矛盾
4. **可视化验证**：通过图表直观检查

## 常见分析结果验证

### 1. 描述性统计

**验证方法**：

```python
import pandas as pd

# 读取数据
df = pd.read_csv('your_data.csv')

# 验证均值
print(f"均值: {df['column'].mean()}")
print(f"中位数: {df['column'].median()}")
print(f"标准差: {df['column'].std()}")

# 验证范围
print(f"最小值: {df['column'].min()}")
print(f"最大值: {df['column'].max()}")
```

**检查清单**：
- [ ] 均值是否在中位数附近（偏态分布除外）
- [ ] 标准差是否合理（不为负数，不为异常大）
- [ ] 最小值和最大值是否在合理范围内
- [ ] 缺失值数量是否正确

### 2. 回归分析

**验证方法**：

```python
import statsmodels.api as sm

# 拟合模型
X = sm.add_constant(df[['x1', 'x2']])
model = sm.OLS(df['y'], X).fit()

# 检查结果
print(model.summary())

# 检查 R²
print(f"R²: {model.rsquared}")

# 检查系数显著性
print(f"P值: {model.pvalues}")
```

**检查清单**：
- [ ] R² 是否在合理范围（0-1）
- [ ] 系数符号是否符合预期
- [ ] 显著性 P 值是否正确解释
- [ ] 残差是否满足假设（正态性、同方差性）

### 3. 生存分析

**验证方法**：

```python
from lifelines import KaplanMeierFitter

# 拟合 Kaplan-Meier 曲线
kmf = KaplanMeierFitter()
kmf.fit(df['time'], df['event'])

# 检查生存率
print(f"中位生存时间: {kmf.median_survival_time_}")
print(f"生存率: {kmf.survival_function_}")
```

**检查清单**：
- [ ] 生存曲线是否单调递减
- [ ] 中位生存时间是否合理
- [ ] 风险比（HR）解释是否正确
- [ ] 比例风险假设是否检验

### 4. 统计检验

**验证方法**：

```python
from scipy import stats

# t 检验
t_stat, p_value = stats.ttest_ind(group1, group2)
print(f"t 统计量: {t_stat}")
print(f"P 值: {p_value}")

# 卡方检验
chi2, p, dof, expected = stats.chi2_contingency(contingency_table)
print(f"卡方值: {chi2}")
print(f"P 值: {p}")
```

**检查清单**：
- [ ] 检验方法选择是否正确
- [ ] P 值解释是否正确（< 0.05 为显著）
- [ ] 效应量是否报告
- [ ] 假设前提是否满足

## 可视化验证

### 1. 分布检查

```python
import matplotlib.pyplot as plt

# 直方图
plt.hist(df['column'], bins=30)
plt.show()

# Q-Q 图
stats.probplot(df['column'], plot=plt)
plt.show()
```

### 2. 关系检查

```python
# 散点图
plt.scatter(df['x'], df['y'])
plt.xlabel('X')
plt.ylabel('Y')
plt.show()

# 相关性热力图
import seaborn as sns
sns.heatmap(df.corr(), annot=True)
plt.show()
```

## 常见错误案例

### 案例 1：P 值解释错误

❌ **错误**：P 值 = 0.03 表示结果有 3% 的概率是错误的

✅ **正确**：P 值 = 0.03 表示在零假设为真的情况下，观察到当前或更极端结果的概率是 3%

### 案例 2：相关性因果混淆

❌ **错误**：A 和 B 相关，所以 A 导致 B

✅ **正确**：相关性不等于因果性，可能存在混杂因素

### 案例 3：多重比较问题

❌ **错误**：进行 20 次检验，发现 1 个 P < 0.05，认为有显著发现

✅ **正确**：需要进行多重比较校正（如 Bonferroni 校正）

## 验证工具

### 内置验证

PubHAgent 在执行分析时会自动进行以下验证：

1. **数据质量检查**：缺失值、异常值、数据类型
2. **假设检验**：正态性检验、方差齐性检验
3. **模型诊断**：残差分析、多重共线性检查

### 外部验证

建议使用以下工具进行交叉验证：

- **R 语言**：使用相同数据在 R 中重复分析
- **SPSS/SAS**：商业统计软件验证
- **Excel**：简单统计量验证

## 验证报告模板

```markdown
# 分析结果验证报告

## 1. 数据概况
- 样本量：N = ?
- 变量数：p = ?
- 缺失值：?

## 2. 分析方法
- 使用方法：?
- 假设前提：?
- 检验统计量：?

## 3. 结果验证
- [ ] 结果 1：验证通过/失败
- [ ] 结果 2：验证通过/失败
- [ ] 结果 3：验证通过/失败

## 4. 可视化检查
- [ ] 图表 1：合理/异常
- [ ] 图表 2：合理/异常

## 5. 结论
- 结果可信度：高/中/低
- 建议：?
```

## 联系支持

如果在验证过程中发现问题，请：

1. 保存原始数据和分析结果
2. 记录验证步骤和发现的问题
3. 在 GitHub Issues 中提交问题报告
