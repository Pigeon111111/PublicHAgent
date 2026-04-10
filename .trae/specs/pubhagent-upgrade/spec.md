# PubHAgent 项目改进计划规格说明

## 背景

PubHAgent 是一个针对公共卫生数据分析场景特化的智能 Agent 系统。经过初步开发和测试，系统已具备基本功能，但在实际使用中发现了以下需要改进的地方：

1. **Planner 能力认知不足**：Planner 无法识别工具能力边界，无法自动升级/创建 Skill
2. **Executor 上下文过多**：Executor 获取了过多的上下文信息
3. **工具能力描述不清晰**：工具说明中没有明确能力范围
4. **Skill 管理缺失**：无法创建、修改、启用/禁用 Skill
5. **配置管理不够灵活**：不支持第三方模型接入，用户 API Key 未隔离
6. **文档不够简洁**：README 缺乏快速启动指南
7. **前端交互体验不足**：导航不便，缺少配置界面
8. **项目入口分散**：需要前后端分别启动，缺乏统一入口

## 目标

### 核心目标
1. **智能 Skill 管理**：Planner 发现工具能力缺口时，能够建议创建或更新 Skill
2. **上下文隔离**：Executor 只获取必要的上下文信息
3. **工具能力明确**：在工具说明中明确能力范围
4. **灵活配置**：支持多种第三方模型，用户 API Key 隔离存储
5. **快速启动**：简化项目启动流程，提供统一入口
6. **用户友好**：改进前端交互，提供配置界面

### 非目标
- 不重构核心工作流架构
- 不改变现有数据库结构
- 不添加新的分析算法
- 不考虑多平台设备兼容

## 技术方案

### 1. Planner 能力认知与 Skill 管理

#### 1.1 工具能力描述

**方案**：在工具定义中添加能力描述字段，LLM 通过阅读描述自行判断。

```python
# 工具能力描述示例
class ToolDefinition:
    name: str
    description: str
    capability: str  # 能力范围描述
    limitations: list[str]  # 限制条件
    applicable_scenarios: list[str]  # 适用场景
```

**实现**：
- 为所有内置工具添加 `capability` 字段
- 为所有 Skill 添加能力描述
- Planner 通过 LLM 理解工具能力

#### 1.2 Skill 创建/更新机制

**流程**：
1. Planner 发现工具无法完成任务
2. Planner 判断是否有类似的 Skill 大类
3. 如果有类似 Skill：建议更新该 Skill，加入新功能
4. 如果没有：建议创建新 Skill
5. 测试通过后，将 Skill 固化到系统中

**实现**：
```python
# Planner 提示词中添加
"""
当你发现现有工具无法完成用户任务时：
1. 分析任务需求
2. 判断是否有类似的 Skill 可以扩展
3. 如果有，建议更新该 Skill 并说明需要添加的功能
4. 如果没有，建议创建新 Skill 并提供 Skill 定义
"""
```

#### 1.3 Skill 管理功能

**API 设计**：
```
GET  /api/skills              # 列出所有 Skill
POST /api/skills              # 创建新 Skill
GET  /api/skills/{skill_id}   # 获取 Skill 详情
PUT  /api/skills/{skill_id}   # 更新 Skill
DELETE /api/skills/{skill_id} # 删除 Skill
POST /api/skills/{skill_id}/enable   # 启用 Skill
POST /api/skills/{skill_id}/disable  # 禁用 Skill
```

### 2. Executor 上下文隔离

**方案**：Executor 只获取当前步骤、上一步结果、所需输出。

```python
class IsolatedExecutionContext:
    """隔离的执行上下文"""
    current_step: ExecutionStep    # 当前步骤
    previous_result: str           # 上一步结果
    required_output: str           # 所需输出
    available_tools: list[str]     # 可用工具名称列表
```

**实现**：
- 修改 Executor Agent 的上下文构建逻辑
- 只传递必要信息给 LLM

### 3. 配置管理增强

#### 3.1 第三方模型接入

**支持的模型**：
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- DeepSeek
- LongCat
- 自定义 OpenAI 兼容 API

**实现**：
```python
# models.json 扩展
{
  "providers": {
    "openai": {
      "name": "OpenAI",
      "models": ["gpt-4", "gpt-3.5-turbo"],
      "api_key_env": "OPENAI_API_KEY",
      "base_url": "https://api.openai.com/v1"
    },
    "deepseek": {
      "name": "DeepSeek",
      "models": ["deepseek-chat", "deepseek-coder"],
      "api_key_env": "DEEPSEEK_API_KEY",
      "base_url": "https://api.deepseek.com/v1"
    },
    "custom": {
      "name": "Custom",
      "models": [],
      "api_key_env": "CUSTOM_API_KEY",
      "base_url": null
    }
  }
}
```

#### 3.2 用户 API Key 隔离

**存储方案**：
- 使用 SQLite 存储（`data/user_configs.db`）
- API Key 加密存储（AES-256）
- 按用户 ID 隔离

### 4. 前端改进

#### 4.1 导航优化
- 添加顶部导航栏
- 实现面包屑导航
- 添加返回按钮

#### 4.2 配置界面
- 模型配置（选择模型、输入 API Key）
- Skill 管理（启用/禁用、创建/修改）
- MCP 配置（添加/删除 MCP 服务器）

#### 4.3 美观度提升
- 添加页面过渡动画
- 实现消息气泡动画
- 优化颜色主题

### 5. 项目统一入口

**启动脚本**：
```python
# run.py
def main():
    """统一启动入口"""
    # 1. 检查环境
    check_environment()
    # 2. 启动后端
    backend_process = start_backend()
    # 3. 启动前端
    frontend_process = start_frontend()
    # 4. 打开浏览器
    open_browser()
    # 5. 等待进程
    wait_for_processes()
```

## 实施步骤

### 阶段一：核心架构优化（第 1-2 周）

#### 任务清单

- [ ] **1.1 工具能力描述完善** (复杂度：低)
  - 为所有内置工具添加能力描述字段
  - 为所有 Skill 添加能力描述
  - 更新工具注册逻辑
  - 编写文档

- [ ] **1.2 Planner Skill 管理提示词** (复杂度：中)
  - 修改 Planner 提示词
  - 添加能力缺口识别逻辑
  - 添加 Skill 创建/更新建议逻辑
  - 编写测试

- [ ] **1.3 Skill 管理 API** (复杂度：中)
  - 实现 Skill CRUD API
  - 实现 Skill 启用/禁用逻辑
  - 编写测试

- [ ] **1.4 Executor 上下文隔离** (复杂度：中)
  - 设计隔离上下文数据结构
  - 实现上下文提取逻辑
  - 修改 Executor Agent
  - 编写测试

#### 验收标准
- [ ] 所有工具有能力描述
- [ ] Planner 能发现能力缺口并建议创建/更新 Skill
- [ ] Skill CRUD API 可用
- [ ] Executor 只获取必要上下文
- [ ] 所有测试通过

---

### 阶段二：配置管理增强（第 3 周）

#### 任务清单

- [ ] **2.1 第三方模型接入** (复杂度：中)
  - 扩展 models.json 配置
  - 实现 DeepSeek 适配器
  - 实现 LongCat 适配器
  - 实现自定义模型适配器
  - 更新 LLM 客户端
  - 编写测试

- [ ] **2.2 用户 API Key 隔离** (复杂度：中)
  - 设计用户配置数据结构
  - 实现 API Key 加密存储
  - 实现用户配置 API
  - 集成到记忆系统
  - 编写测试

#### 验收标准
- [ ] 支持 DeepSeek、LongCat 等第三方模型
- [ ] 用户 API Key 按用户 ID 隔离存储
- [ ] API Key 加密存储
- [ ] 所有测试通过

---

### 阶段三：前端改进（第 4-5 周）

#### 任务清单

- [ ] **3.1 导航优化** (复杂度：中)
  - 实现顶部导航栏
  - 实现面包屑导航
  - 添加返回按钮
  - 测试导航流程

- [ ] **3.2 配置界面** (复杂度：高)
  - 扩展 SettingsView
  - 实现模型配置界面
  - 实现 Skill 管理界面
  - 实现 MCP 配置界面
  - 集成后端 API

- [ ] **3.3 美观度提升** (复杂度：中)
  - 添加页面过渡动画
  - 实现消息气泡动画
  - 优化颜色主题

#### 验收标准
- [ ] 导航流畅，可以点击返回
- [ ] 用户可以在前端配置 API Key
- [ ] 用户可以管理 Skill
- [ ] 前端美观度提升

---

### 阶段四：项目统一入口与文档（第 6 周）

#### 任务清单

- [ ] **4.1 统一启动脚本** (复杂度：中)
  - 实现 run.py 启动脚本
  - 实现环境检查
  - 实现进程管理
  - 测试启动流程

- [ ] **4.2 文档优化** (复杂度：低)
  - 简化 README
  - 添加快速启动指南
  - 更新用户手册
  - 更新开发者文档

- [ ] **4.3 结果验证说明** (复杂度：低)
  - 编写结果验证指南
  - 添加验证示例

#### 验收标准
- [ ] 可以通过 `python run.py` 一键启动
- [ ] README 简洁明了
- [ ] 文档更新完整

## 依赖关系

```
阶段一（核心架构优化）
    ↓
阶段二（配置管理增强）
    ↓
阶段三（前端改进）← 依赖阶段二的配置 API
    ↓
阶段四（项目统一入口与文档）
```

## 风险与缓解

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|----------|
| Planner 提示词效果不佳 | 中 | 中 | 参考 LangChain 成熟项目，迭代优化 |
| Executor 上下文隔离影响功能 | 高 | 低 | 充分测试，保留回退机制 |
| 第三方模型 API 变更 | 中 | 低 | 使用适配器模式，隔离 API 差异 |
| 用户数据安全 | 高 | 低 | API Key 加密存储，定期安全审计 |

## 测试策略

### 增量测试原则
1. **测试顺序**：前序模块验证 → 新增模块测试 → 模块间集成测试
2. **测试覆盖**：每个模块必须有对应的单元测试
3. **集成测试**：模块间集成必须有集成测试
4. **自动化**：所有测试应可自动化执行

### 测试类型
- 单元测试：每个新模块必须有对应的单元测试，覆盖率 > 80%
- 集成测试：Planner-Executor 集成测试，工具系统端到端测试
- 用户验收测试：快速启动流程测试，配置界面可用性测试

## 成功标准

- [ ] 所有工具有明确的能力描述
- [ ] Planner 能发现能力缺口并建议创建/更新 Skill
- [ ] 用户可以创建、修改、启用/禁用 Skill
- [ ] Executor 只获取必要的上下文信息
- [ ] 支持 DeepSeek、LongCat 等第三方模型
- [ ] 用户 API Key 按用户 ID 隔离存储
- [ ] 前端导航流畅，可以点击返回
- [ ] 用户可以在前端配置 API Key
- [ ] 可以通过 `python run.py` 一键启动项目
- [ ] README 简洁，包含快速启动指南
- [ ] 所有测试通过
- [ ] 文档更新完整

## 时间估算

- 阶段一：2 周
- 阶段二：1 周
- 阶段三：2 周
- 阶段四：1 周
- **总计：6 周**
