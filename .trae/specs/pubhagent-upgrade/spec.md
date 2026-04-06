# PubHAgent 项目改进计划规格说明

## 背景

PubHAgent 是一个针对公共卫生数据分析场景特化的智能 Agent 系统。经过初步开发和测试，系统已具备基本功能，但在实际使用中发现了以下需要改进的地方：

1. **Planner-Executor 架构优化**：Planner 缺乏工具能力边界认知，无法自动升级/创建 Skill；Executor 上下文隔离不足
2. **工具系统边界模糊**：Tools、MCP、Skill 三层工具体系能力边界不明确，导致工具选择错误
3. **配置管理不够灵活**：不支持第三方模型接入，用户 API Key 未隔离
4. **文档不够简洁**：README 缺乏快速启动指南
5. **前端交互体验不足**：导航不便，缺少配置界面，美观度有待提升
6. **项目入口分散**：需要前后端分别启动，缺乏统一入口

## 目标

### 核心目标
1. **智能工具管理**：Planner 能够识别工具能力边界，自动升级或创建 Skill
2. **上下文隔离**：Executor 只获取必要的上下文信息，提高执行效率
3. **工具能力明确**：清晰定义 Tools、MCP、Skill 的能力边界和使用场景
4. **灵活配置**：支持多种第三方模型，用户 API Key 隔离存储
5. **快速启动**：简化项目启动流程，提供统一入口
6. **用户友好**：改进前端交互，提供配置界面，提升美观度

### 非目标
- 不重构核心工作流架构
- 不改变现有数据库结构
- 不添加新的分析算法

## 技术方案

### 1. Planner-Executor 架构优化

#### 1.1 Planner 工具能力认知

**当前问题**：
- Planner 不知道工具的能力边界
- 无法识别当前工具是否能够完成任务
- 缺乏自动升级/创建 Skill 的能力

**解决方案**：
```python
# 在 Planner 中添加工具能力评估模块
class ToolCapabilityEvaluator:
    """工具能力评估器"""
    
    def evaluate_capability(self, task: str, available_tools: List[Tool]) -> CapabilityResult:
        """评估工具是否能够完成任务"""
        # 1. 解析任务需求
        requirements = self._parse_requirements(task)
        # 2. 匹配工具能力
        matched_tools = self._match_tools(requirements, available_tools)
        # 3. 评估能力缺口
        gaps = self._identify_gaps(requirements, matched_tools)
        # 4. 生成建议
        suggestions = self._generate_suggestions(gaps)
        return CapabilityResult(matched_tools, gaps, suggestions)
```

**实现步骤**：
1. 为每个工具添加能力描述（capability_description）
2. 实现任务需求解析器
3. 实现工具能力匹配算法
4. 实现 Skill 升级/创建建议生成器
5. 集成到 Planner Agent

#### 1.2 Executor 上下文隔离

**当前问题**：
- Executor 获取了过多的上下文信息
- 可能导致信息泄露或干扰
- 影响执行效率

**解决方案**：
```python
class IsolatedExecutionContext:
    """隔离的执行上下文"""
    
    def __init__(self):
        self.current_step: ExecutionStep  # 当前步骤
        self.previous_result: str  # 上一步结果
        self.required_output: str  # 所需输出
        self.available_tools: List[str]  # 可用工具列表
    
    @classmethod
    def create(cls, full_context: AgentState, step_index: int) -> 'IsolatedExecutionContext':
        """从完整上下文创建隔离上下文"""
        current_step = full_context.plan.steps[step_index]
        previous_result = full_context.step_results[step_index - 1] if step_index > 0 else ""
        
        return cls(
            current_step=current_step,
            previous_result=previous_result,
            required_output=current_step.expected_output,
            available_tools=current_step.tools
        )
```

**实现步骤**：
1. 定义隔离上下文数据结构
2. 实现上下文提取逻辑
3. 修改 Executor Agent 使用隔离上下文
4. 添加上下文验证测试

### 2. 工具系统能力边界明确化

#### 2.1 工具能力描述标准

**定义三层工具的能力边界**：

| 工具类型 | 能力范围 | 使用场景 | 示例 |
|---------|---------|---------|------|
| **Built-in Tools** | 基础文件操作、数据读取、基础统计 | 通用数据处理 | `read_csv`, `describe_data` |
| **Skills** | 特定分析方法、领域知识 | 复杂分析任务 | `linear_regression`, `survival_analysis` |
| **MCP Tools** | 外部服务集成、扩展能力 | 外部资源访问 | `database_query`, `api_call` |

**实现方案**：
```python
class ToolCapability:
    """工具能力描述"""
    
    name: str
    description: str
    input_types: List[str]  # 支持的输入类型
    output_types: List[str]  # 输出类型
    complexity: str  # simple/medium/complex
    domain: str  # general/statistical/ml/visualization
    prerequisites: List[str]  # 前置条件
    limitations: List[str]  # 限制条件
```

#### 2.2 Skill 管理系统

**新增功能**：
1. **查询 Skill**：列出所有可用 Skill 及其能力
2. **创建 Skill**：用户可以通过界面创建新 Skill
3. **修改 Skill**：更新现有 Skill 的定义
4. **启用/禁用 Skill**：用户可以选择启用哪些 Skill

**API 设计**：
```python
# Skill 管理 API
GET  /api/skills              # 列出所有 Skill
POST /api/skills              # 创建新 Skill
GET  /api/skills/{skill_id}   # 获取 Skill 详情
PUT  /api/skills/{skill_id}   # 更新 Skill
DELETE /api/skills/{skill_id} # 删除 Skill
POST /api/skills/{skill_id}/enable   # 启用 Skill
POST /api/skills/{skill_id}/disable  # 禁用 Skill
```

#### 2.3 MCP 插口明确化

**实现方案**：
1. 创建 MCP 配置向导界面
2. 提供标准 MCP 配置模板
3. 自动生成 MCP 连接代码

```json
// mcp_config_template.json
{
  "mcp_servers": {
    "example_server": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "env": {
        "API_KEY": "your_api_key"
      },
      "capabilities": ["data_access", "external_api"]
    }
  }
}
```

### 3. 配置管理增强

#### 3.1 第三方模型接入

**支持的模型**：
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- DeepSeek
- LongCat
- 自定义 OpenAI 兼容 API

**实现方案**：
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
      "base_url": null  # 用户自定义
    }
  }
}
```

#### 3.2 用户 API Key 隔离

**数据结构**：
```python
class UserConfig:
    """用户配置"""
    
    user_id: str
    api_keys: Dict[str, str]  # provider -> api_key
    enabled_skills: List[str]
    preferences: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
```

**存储方案**：
- 使用 SQLite 存储（`data/user_configs.db`）
- API Key 加密存储（使用 AES-256）
- 按用户 ID 隔离

### 4. 文档优化

#### 4.1 README 简化

**新结构**：
```markdown
# PubHAgent

一句话介绍

## 快速启动（3 步）

1. 安装依赖
2. 配置 API Key
3. 启动服务

## 功能特性

## 详细文档

## 贡献指南

## 许可证
```

### 5. 前端改进

#### 5.1 导航优化

**改进方案**：
- 添加顶部导航栏
- 实现面包屑导航
- 添加侧边栏快捷入口
- 支持快捷键导航

#### 5.2 配置界面

**新增页面**：
- SettingsView 扩展：
  - 模型配置（选择模型、输入 API Key）
  - Skill 管理（启用/禁用、创建/修改）
  - MCP 配置（添加/删除 MCP 服务器）
  - 用户偏好设置

#### 5.3 美观度提升

**改进方向**：
- 添加页面过渡动画
- 实现消息气泡动画
- 添加加载状态动画
- 优化颜色主题
- 响应式布局优化

### 6. 项目统一入口

#### 6.1 启动脚本

**实现方案**：
```python
# run.py
import subprocess
import sys
from pathlib import Path

def main():
    """统一启动入口"""
    print("🚀 启动 PubHAgent...")
    
    # 1. 检查环境
    check_environment()
    
    # 2. 启动后端
    backend_process = start_backend()
    
    # 3. 启动前端
    frontend_process = start_frontend()
    
    # 4. 打开浏览器
    open_browser()
    
    # 5. 等待进程
    wait_for_processes([backend_process, frontend_process])

if __name__ == "__main__":
    main()
```

**启动方式**：
```bash
# 开发模式
python run.py --dev

# 生产模式
python run.py --prod

# 仅后端
python run.py --backend-only

# 仅前端
python run.py --frontend-only
```

## 实施步骤

### 阶段一：核心架构优化（第 1-2 周）

#### 任务清单

- [ ] **1.1 Planner 工具能力认知** (复杂度：高)
  - 设计工具能力描述标准
  - 实现 ToolCapability 数据结构
  - 实现任务需求解析器
  - 实现工具能力匹配算法
  - 实现 Skill 升级/创建建议生成器
  - 集成到 Planner Agent
  - 编写单元测试

- [ ] **1.2 Executor 上下文隔离** (复杂度：中)
  - 设计隔离上下文数据结构
  - 实现上下文提取逻辑
  - 修改 Executor Agent
  - 添加上下文验证测试
  - 性能基准测试

#### 验收标准

- [ ] Planner 能够识别工具能力缺口
- [ ] Planner 能够生成 Skill 创建建议
- [ ] Executor 只获取必要的上下文信息
- [ ] 所有测试通过

---

### 阶段二：工具系统完善（第 3-4 周）

#### 任务清单

- [ ] **2.1 工具能力边界明确化** (复杂度：中)
  - 为所有内置工具添加能力描述
  - 为所有 Skill 添加能力描述
  - 创建工具选择决策树
  - 更新工具注册逻辑
  - 编写文档

- [ ] **2.2 Skill 管理系统** (复杂度：高)
  - 设计 Skill 管理数据结构
  - 实现 Skill CRUD API
  - 实现 Skill 启用/禁用逻辑
  - 创建 Skill 管理界面
  - 编写测试

- [ ] **2.3 MCP 插口明确化** (复杂度：中)
  - 创建 MCP 配置模板
  - 实现 MCP 配置向导
  - 生成 MCP 连接代码
  - 编写文档

#### 验收标准

- [ ] 所有工具都有明确的能力描述
- [ ] 用户可以创建、修改、查询、删除 Skill
- [ ] 用户可以启用/禁用 Skill
- [ ] MCP 配置流程清晰

---

### 阶段三：配置管理增强（第 5 周）

#### 任务清单

- [ ] **3.1 第三方模型接入** (复杂度：中)
  - 扩展 models.json 配置
  - 实现 DeepSeek 适配器
  - 实现 LongCat 适配器
  - 实现自定义模型适配器
  - 更新 LLM 客户端
  - 编写测试

- [ ] **3.2 用户 API Key 隔离** (复杂度：中)
  - 设计用户配置数据结构
  - 实现 API Key 加密存储
  - 实现用户配置 API
  - 集成到记忆系统
  - 编写测试

#### 验收标准

- [ ] 支持 DeepSeek、LongCat 等第三方模型
- [ ] 用户 API Key 按用户 ID 隔离存储
- [ ] API Key 加密存储

---

### 阶段四：前端改进（第 6-7 周）

#### 任务清单

- [ ] **4.1 导航优化** (复杂度：中)
  - 实现顶部导航栏
  - 实现面包屑导航
  - 添加侧边栏快捷入口
  - 实现快捷键导航
  - 测试导航流程

- [ ] **4.2 配置界面** (复杂度：高)
  - 扩展 SettingsView
  - 实现模型配置界面
  - 实现 Skill 管理界面
  - 实现 MCP 配置界面
  - 实现用户偏好设置
  - 集成后端 API

- [ ] **4.3 美观度提升** (复杂度：中)
  - 添加页面过渡动画
  - 实现消息气泡动画
  - 添加加载状态动画
  - 优化颜色主题
  - 响应式布局优化

#### 验收标准

- [ ] 导航流畅，可以点击返回
- [ ] 用户可以在前端配置 API Key
- [ ] 前端美观度提升

---

### 阶段五：项目统一入口（第 8 周）

#### 任务清单

- [ ] **5.1 统一启动脚本** (复杂度：中)
  - 实现 run.py 启动脚本
  - 实现环境检查
  - 实现进程管理
  - 实现浏览器自动打开
  - 测试启动流程

- [ ] **5.2 文档优化** (复杂度：低)
  - 简化 README
  - 添加快速启动指南
  - 更新用户手册
  - 更新开发者文档

- [ ] **5.3 结果验证说明** (复杂度：低)
  - 编写结果验证指南
  - 添加验证示例
  - 创建验证工具

#### 验收标准

- [ ] 可以通过 `python run.py` 一键启动
- [ ] README 简洁明了
- [ ] 用户知道如何验证分析结果

## 依赖关系

```
阶段一（核心架构优化）
    ↓
阶段二（工具系统完善）← 依赖阶段一的 Planner 改进
    ↓
阶段三（配置管理增强）← 依赖阶段二的 Skill 管理
    ↓
阶段四（前端改进）← 依赖阶段三的配置 API
    ↓
阶段五（项目统一入口）← 依赖所有前序阶段
```

## 风险与缓解

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|----------|
| Planner 能力评估算法复杂 | 高 | 中 | 参考成熟项目实现，先实现简单版本 |
| Executor 上下文隔离影响功能 | 高 | 低 | 充分测试，保留回退机制 |
| 前端改动影响用户体验 | 中 | 中 | 渐进式改进，保留旧版入口 |
| 第三方模型 API 变更 | 中 | 低 | 使用适配器模式，隔离 API 差异 |
| 用户数据安全 | 高 | 低 | API Key 加密存储，定期安全审计 |

## 测试策略

### 单元测试
- 每个新模块必须有对应的单元测试
- 测试覆盖率 > 80%

### 集成测试
- Planner-Executor 集成测试
- 工具系统端到端测试
- 前后端集成测试

### 用户验收测试
- 快速启动流程测试
- 配置界面可用性测试
- 分析结果验证测试

## 成功标准

- [ ] Planner 能够识别工具能力缺口并建议创建 Skill
- [ ] Executor 只获取必要的上下文信息
- [ ] 工具能力边界明确，用户不会选择错误工具
- [ ] 用户可以创建、修改、启用/禁用 Skill
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
- 阶段二：2 周
- 阶段三：1 周
- 阶段四：2 周
- 阶段五：1 周
- **总计：8 周**

## 开放问题

1. Skill 创建是否需要 LLM 辅助？
2. 用户 API Key 是否需要定期轮换？
3. 前端动画是否影响性能？
4. 是否需要支持多语言？
