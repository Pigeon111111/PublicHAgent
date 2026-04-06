# Tasks

## 阶段一：基础架构搭建（第 1-2 周）

- [x] Task 1.1: 项目初始化
  - [x] SubTask 1.1.1: 创建项目目录结构（backend、frontend、tests、docs）
  - [x] SubTask 1.1.2: 配置 Python 虚拟环境（venv）
  - [x] SubTask 1.1.3: 创建 requirements.txt（LangChain、LangGraph、langchain-mcp-adapters、FastAPI、mem0 等）
  - [x] SubTask 1.1.4: 配置代码质量工具（black、ruff、mypy）
  - [x] SubTask 1.1.5: 创建 .gitignore 和 README.md
  - [x] SubTask 1.1.6: 增量测试 - 验证项目结构完整性

- [x] Task 1.2: 核心配置系统
  - [x] SubTask 1.2.1: 创建 backend/config/ 目录
  - [x] SubTask 1.2.2: 实现 models.json（LLM 模型配置）
  - [x] SubTask 1.2.3: 实现 mcp.json（MCP 服务器配置）
  - [x] SubTask 1.2.4: 实现 settings.json（全局设置）
  - [x] SubTask 1.2.5: 创建 .env.example（环境变量模板）
  - [x] SubTask 1.2.6: 增量测试 - 验证配置文件格式正确性

- [x] Task 1.3: LLM 客户端封装
  - [x] SubTask 1.3.1: 创建 backend/agents/base/ 目录
  - [x] SubTask 1.3.2: 实现 llm_client.py（使用 LangChain 官方 ChatOpenAI/ChatAnthropic）
  - [x] SubTask 1.3.3: 实现单例缓存机制
  - [x] SubTask 1.3.4: 添加错误处理和重试逻辑
  - [x] SubTask 1.3.5: 编写单元测试
  - [x] SubTask 1.3.6: 增量测试 - 验证 LLM 客户端可正常调用模型
  - [x] SubTask 1.3.7: 增量测试 - 验证前序模块（项目结构、配置系统）仍正常工作

- [x] Task 1.4: 基础工具注册表
  - [x] SubTask 1.4.1: 创建 backend/tools/ 目录
  - [x] SubTask 1.4.2: 实现 registry.py（工具注册表）
  - [x] SubTask 1.4.3: 定义工具标准接口（BaseTool）
  - [x] SubTask 1.4.4: 实现文件操作工具（读取、写入、编辑）
  - [x] SubTask 1.4.5: 编写单元测试
  - [x] SubTask 1.4.6: 增量测试 - 验证工具注册表可正常注册和调用工具
  - [x] SubTask 1.4.7: 增量测试 - 验证前序模块（LLM 客户端）仍正常工作
  - [x] SubTask 1.4.8: 增量测试 - 集成测试（LLM 客户端 + 工具注册表）

## 阶段二：Agent 核心实现（第 3-5 周）

- [x] Task 2.1: 意图识别模块
  - [x] SubTask 2.1.1: 创建 backend/agents/intent/ 目录
  - [x] SubTask 2.1.2: 构建公共卫生领域关键词库
  - [x] SubTask 2.1.3: 实现 recognizer.py（关键词匹配 + LLM 分类）
  - [x] SubTask 2.1.4: 设计结构化输出格式（使用 with_structured_output）
  - [x] SubTask 2.1.5: 编写单元测试
  - [x] SubTask 2.1.6: 增量测试 - 验证意图识别准确率 > 85%
  - [x] SubTask 2.1.7: 增量测试 - 验证前序模块（基础架构）仍正常工作
  - [x] SubTask 2.1.8: 增量测试 - 集成测试（意图识别 + LLM 客户端）

- [x] Task 2.2: LangGraph 工作流基础
  - [x] SubTask 2.2.1: 创建 backend/core/ 目录
  - [x] SubTask 2.2.2: 实现 state.py（使用 TypedDict 定义 AgentState）
  - [x] SubTask 2.2.3: 实现 workflow.py（使用 StateGraph 构建工作流图）
  - [x] SubTask 2.2.4: 添加状态持久化（checkpointer）
  - [x] SubTask 2.2.5: 编写集成测试
  - [x] SubTask 2.2.6: 增量测试 - 验证 LangGraph 工作流可正常运行
  - [x] SubTask 2.2.7: 增量测试 - 验证前序模块（意图识别）仍正常工作
  - [x] SubTask 2.2.8: 增量测试 - 集成测试（意图识别 + LangGraph 工作流）

- [x] Task 2.3: Planner Agent
  - [x] SubTask 2.3.1: 创建 backend/agents/planner/ 目录
  - [x] SubTask 2.3.2: 实现 planner_agent.py（计划生成逻辑）
  - [x] SubTask 2.3.3: 设计结构化输出格式（使用 with_structured_output）
  - [x] SubTask 2.3.4: 实现工具选择逻辑
  - [x] SubTask 2.3.5: 集成记忆系统（获取用户画像）
  - [x] SubTask 2.3.6: 实现 replan 能力
  - [x] SubTask 2.3.7: 编写单元测试
  - [x] SubTask 2.3.8: 增量测试 - 验证 Planner 可生成结构化执行计划
  - [x] SubTask 2.3.9: 增量测试 - 验证前序模块（LangGraph 工作流）仍正常工作
  - [x] SubTask 2.3.10: 增量测试 - 集成测试（Planner + LangGraph 工作流）

- [x] Task 2.4: Executor Agent
  - [x] SubTask 2.4.1: 创建 backend/agents/executor/ 目录
  - [x] SubTask 2.4.2: 实现 executor_agent.py（代码生成逻辑）
  - [x] SubTask 2.4.3: 集成沙箱环境（Docker SDK）
  - [x] SubTask 2.4.4: 实现 Reflection 循环（最多 3 次）
  - [x] SubTask 2.4.5: 添加错误处理和重试机制
  - [x] SubTask 2.4.6: 实现结果验证逻辑
  - [x] SubTask 2.4.7: 编写单元测试
  - [x] SubTask 2.4.8: 增量测试 - 验证 Executor 可在沙箱中执行代码
  - [x] SubTask 2.4.9: 增量测试 - 验证前序模块（Planner）仍正常工作
  - [x] SubTask 2.4.10: 增量测试 - 集成测试（Planner + Executor + LangGraph 工作流）

- [x] Task 2.5: Reflection Agent
  - [x] SubTask 2.5.1: 创建 backend/agents/reflection/ 目录
  - [x] SubTask 2.5.2: 实现 reflection_agent.py（执行结果评估）
  - [x] SubTask 2.5.3: 设计反馈生成逻辑
  - [x] SubTask 2.5.4: 实现 replan 触发条件
  - [x] SubTask 2.5.5: 添加质量评分机制
  - [x] SubTask 2.5.6: 编写单元测试
  - [x] SubTask 2.5.7: 增量测试 - 验证 Reflection 可评估执行结果
  - [x] SubTask 2.5.8: 增量测试 - 验证前序模块（Executor）仍正常工作
  - [x] SubTask 2.5.9: 增量测试 - 集成测试（完整 Agent 工作流）

## 阶段三：记忆系统集成（第 6 周）

- [x] Task 3.1: mem0 集成
  - [x] SubTask 3.1.1: 安装 mem0 库及依赖
  - [x] SubTask 3.1.2: 配置 ChromaDB 向量存储
  - [x] SubTask 3.1.3: 创建 backend/agents/memory/ 目录
  - [x] SubTask 3.1.4: 实现 manager.py（记忆管理器）
  - [x] SubTask 3.1.5: 添加用户隔离机制（user_id + session_id）
  - [x] SubTask 3.1.6: 增量测试 - 验证 mem0 可正常存储和检索记忆
  - [x] SubTask 3.1.7: 增量测试 - 验证前序模块（Agent 核心）仍正常工作

- [x] Task 3.2: 记忆操作接口
  - [x] SubTask 3.2.1: 实现添加记忆接口（add_memory）
  - [x] SubTask 3.2.2: 实现搜索记忆接口（search_memory）
  - [x] SubTask 3.2.3: 实现更新记忆接口（update_memory）
  - [x] SubTask 3.2.4: 实现删除记忆接口（delete_memory）
  - [x] SubTask 3.2.5: 编写单元测试
  - [x] SubTask 3.2.6: 增量测试 - 验证所有记忆操作接口正常工作
  - [x] SubTask 3.2.7: 增量测试 - 验证前序模块（mem0 集成）仍正常工作

- [x] Task 3.3: 用户画像管理
  - [x] SubTask 3.3.1: 实现用户偏好记录
  - [x] SubTask 3.3.2: 实现常用分析方法记录
  - [x] SubTask 3.3.3: 实现数据特征记录
  - [x] SubTask 3.3.4: 实现画像检索接口（get_user_profile）
  - [x] SubTask 3.3.5: 编写单元测试
  - [x] SubTask 3.3.6: 增量测试 - 验证用户画像管理功能正常
  - [x] SubTask 3.3.7: 增量测试 - 验证前序模块（记忆操作接口）仍正常工作

- [x] Task 3.4: 记忆注入 Planner
  - [x] SubTask 3.4.1: 在 Planner 初始化时加载用户画像
  - [x] SubTask 3.4.2: 在生成计划时参考历史分析方法
  - [x] SubTask 3.4.3: 实现记忆摘要机制（Token 预算）
  - [x] SubTask 3.4.4: 编写集成测试
  - [x] SubTask 3.4.5: 增量测试 - 验证 Planner 可获取用户画像
  - [x] SubTask 3.4.6: 增量测试 - 验证前序模块（用户画像管理）仍正常工作
  - [x] SubTask 3.4.7: 增量测试 - 集成测试（记忆系统 + Agent 核心）

## 阶段四：工具系统完善（第 7-8 周）

- [ ] Task 4.1: MCP 集成
  - [ ] SubTask 4.1.1: 安装 langchain-mcp-adapters 库
  - [ ] SubTask 4.1.2: 创建 backend/tools/mcp/ 目录
  - [ ] SubTask 4.1.3: 实现 client.py（使用 MultiServerMCPClient）
  - [ ] SubTask 4.1.4: 配置 MCP 服务器（文件系统、数据库）
  - [ ] SubTask 4.1.5: 实现工具发现机制（使用 client.get_tools()）
  - [ ] SubTask 4.1.6: 实现工具调用接口
  - [ ] SubTask 4.1.7: 编写单元测试
  - [ ] SubTask 4.1.8: 增量测试 - 验证 MCP 客户端可正常连接服务器
  - [ ] SubTask 4.1.9: 增量测试 - 验证前序模块（记忆系统）仍正常工作

- [ ] Task 4.2: Skills 系统
  - [ ] SubTask 4.2.1: 设计 Skill 标准格式（SKILL.md）
  - [ ] SubTask 4.2.2: 创建 backend/tools/skills/ 目录
  - [ ] SubTask 4.2.3: 实现 loader.py（技能加载器）
  - [ ] SubTask 4.2.4: 创建初始技能库：
    - [ ] 描述性统计（descriptive_statistics）
    - [ ] 回归分析（regression_analysis）
    - [ ] 生存分析（survival_analysis）
    - [ ] 数据可视化（data_visualization）
  - [ ] SubTask 4.2.5: 实现技能动态加载
  - [ ] SubTask 4.2.6: 编写单元测试
  - [ ] SubTask 4.2.7: 增量测试 - 验证技能可动态加载和执行
  - [ ] SubTask 4.2.8: 增量测试 - 验证前序模块（MCP 集成）仍正常工作

- [ ] Task 4.3: 数据分析工具
  - [ ] SubTask 4.3.1: 创建 backend/tools/builtin/ 目录
  - [ ] SubTask 4.3.2: 实现 file_ops.py（CSV/XLSX 读取）
  - [ ] SubTask 4.3.3: 实现 data_analysis.py（数据清洗）
  - [ ] SubTask 4.3.4: 实现统计分析工具（pandas、scipy）
  - [ ] SubTask 4.3.5: 实现可视化工具（matplotlib、seaborn）
  - [ ] SubTask 4.3.6: 实现报告生成工具
  - [ ] SubTask 4.3.7: 编写单元测试
  - [ ] SubTask 4.3.8: 增量测试 - 验证数据分析工具正常工作
  - [ ] SubTask 4.3.9: 增量测试 - 验证前序模块（Skills 系统）仍正常工作
  - [ ] SubTask 4.3.10: 增量测试 - 集成测试（工具系统 + Agent 核心）

- [ ] Task 4.4: 工具安全守卫
  - [ ] SubTask 4.4.1: 实现工具权限检查
  - [ ] SubTask 4.4.2: 实现参数验证
  - [ ] SubTask 4.4.3: 实现执行日志记录
  - [ ] SubTask 4.4.4: 实现异常捕获
  - [ ] SubTask 4.4.5: 编写单元测试
  - [ ] SubTask 4.4.6: 增量测试 - 验证工具安全守卫正常工作
  - [ ] SubTask 4.4.7: 增量测试 - 验证前序模块（数据分析工具）仍正常工作

## 阶段五：沙箱环境搭建（第 9 周）

- [ ] Task 5.1: Docker 环境配置
  - [ ] SubTask 5.1.1: 创建 backend/sandbox/ 目录
  - [ ] SubTask 5.1.2: 编写 Dockerfile（Python 数据分析环境）
  - [ ] SubTask 5.1.3: 配置资源限制（CPU、内存）
  - [ ] SubTask 5.1.4: 配置网络隔离
  - [ ] SubTask 5.1.5: 配置文件系统隔离
  - [ ] SubTask 5.1.6: 增量测试 - 验证 Docker 容器可正常启动和销毁
  - [ ] SubTask 5.1.7: 增量测试 - 验证前序模块（工具系统）仍正常工作

- [ ] Task 5.2: 沙箱管理器
  - [ ] SubTask 5.2.1: 实现 manager.py（容器生命周期管理）
  - [ ] SubTask 5.2.2: 实现代码执行接口（execute_code）
  - [ ] SubTask 5.2.3: 实现结果获取接口（get_result）
  - [ ] SubTask 5.2.4: 实现容器清理机制
  - [ ] SubTask 5.2.5: 编写单元测试
  - [ ] SubTask 5.2.6: 增量测试 - 验证沙箱管理器正常工作
  - [ ] SubTask 5.2.7: 增量测试 - 验证前序模块（Docker 环境配置）仍正常工作

- [ ] Task 5.3: 安全策略
  - [ ] SubTask 5.3.1: 实现代码静态检查（禁止危险操作）
  - [ ] SubTask 5.3.2: 实现执行超时控制
  - [ ] SubTask 5.3.3: 实现资源监控
  - [ ] SubTask 5.3.4: 实现异常隔离
  - [ ] SubTask 5.3.5: 编写安全测试
  - [ ] SubTask 5.3.6: 增量测试 - 验证安全策略可拦截危险操作
  - [ ] SubTask 5.3.7: 增量测试 - 验证前序模块（沙箱管理器）仍正常工作
  - [ ] SubTask 5.3.8: 增量测试 - 集成测试（沙箱环境 + Executor Agent）

## 阶段六：后端 API 开发（第 10-11 周）

- [ ] Task 6.1: FastAPI 应用搭建
  - [ ] SubTask 6.1.1: 创建 backend/api/ 目录
  - [ ] SubTask 6.1.2: 实现 main.py（FastAPI 应用实例）
  - [ ] SubTask 6.1.3: 配置 CORS
  - [ ] SubTask 6.1.4: 配置中间件（日志、错误处理）
  - [ ] SubTask 6.1.5: 配置依赖注入
  - [ ] SubTask 6.1.6: 增量测试 - 验证 FastAPI 应用可正常启动
  - [ ] SubTask 6.1.7: 增量测试 - 验证前序模块（沙箱环境）仍正常工作

- [ ] Task 6.2: WebSocket 网关
  - [ ] SubTask 6.2.1: 实现 websocket.py（WebSocket 连接管理）
  - [ ] SubTask 6.2.2: 实现会话管理（session_id）
  - [ ] SubTask 6.2.3: 实现流式输出（使用 LangGraph streaming）
  - [ ] SubTask 6.2.4: 实现打断机制（Human-in-the-loop）
  - [ ] SubTask 6.2.5: 编写集成测试
  - [ ] SubTask 6.2.6: 增量测试 - 验证 WebSocket 连接稳定
  - [ ] SubTask 6.2.7: 增量测试 - 验证前序模块（FastAPI 应用）仍正常工作

- [ ] Task 6.3: REST API
  - [ ] SubTask 6.3.1: 创建 backend/api/routes/ 目录
  - [ ] SubTask 6.3.2: 实现文件上传接口（/upload）
  - [ ] SubTask 6.3.3: 实现文件列表接口（/files）
  - [ ] SubTask 6.3.4: 实现历史记录接口（/history）
  - [ ] SubTask 6.3.5: 实现配置管理接口（/config）
  - [ ] SubTask 6.3.6: 编写 API 文档（Swagger）
  - [ ] SubTask 6.3.7: 增量测试 - 验证所有 REST API 正常工作
  - [ ] SubTask 6.3.8: 增量测试 - 验证前序模块（WebSocket 网关）仍正常工作

- [ ] Task 6.4: 流式输出协议
  - [ ] SubTask 6.4.1: 定义消息格式（JSON Schema）
  - [ ] SubTask 6.4.2: 实现消息序列化
  - [ ] SubTask 6.4.3: 实现进度推送
  - [ ] SubTask 6.4.4: 实现错误推送
  - [ ] SubTask 6.4.5: 编写单元测试
  - [ ] SubTask 6.4.6: 增量测试 - 验证流式输出协议正常工作
  - [ ] SubTask 6.4.7: 增量测试 - 验证前序模块（REST API）仍正常工作
  - [ ] SubTask 6.4.8: 增量测试 - 集成测试（后端 API + Agent 核心）

## 阶段七：前端开发（第 12-14 周）

- [ ] Task 7.1: 项目初始化
  - [ ] SubTask 7.1.1: 创建 frontend/ 目录
  - [ ] SubTask 7.1.2: 初始化 Vue 3 项目（Vite）
  - [ ] SubTask 7.1.3: 配置 TypeScript
  - [ ] SubTask 7.1.4: 安装 UI 库（Element Plus）
  - [ ] SubTask 7.1.5: 配置路由（Vue Router）
  - [ ] SubTask 7.1.6: 配置状态管理（Pinia）
  - [ ] SubTask 7.1.7: 增量测试 - 验证前端项目可正常启动
  - [ ] SubTask 7.1.8: 增量测试 - 验证前序模块（后端 API）仍正常工作

- [ ] Task 7.2: 对话界面
  - [ ] SubTask 7.2.1: 创建 frontend/src/components/ 目录
  - [ ] SubTask 7.2.2: 实现 ChatWindow.vue（消息列表组件）
  - [ ] SubTask 7.2.3: 实现 Markdown 渲染（代码高亮）
  - [ ] SubTask 7.2.4: 实现流式输出显示
  - [ ] SubTask 7.2.5: 实现输入框组件
  - [ ] SubTask 7.2.6: 实现打断按钮
  - [ ] SubTask 7.2.7: 编写组件测试
  - [ ] SubTask 7.2.8: 增量测试 - 验证对话界面正常工作
  - [ ] SubTask 7.2.9: 增量测试 - 验证前序模块（前端初始化）仍正常工作

- [ ] Task 7.3: 文件上传
  - [ ] SubTask 7.3.1: 实现 FileUpload.vue（拖拽上传组件）
  - [ ] SubTask 7.3.2: 实现文件预览组件
  - [ ] SubTask 7.3.3: 实现上传进度显示
  - [ ] SubTask 7.3.4: 实现文件管理界面
  - [ ] SubTask 7.3.5: 编写组件测试
  - [ ] SubTask 7.3.6: 增量测试 - 验证文件上传功能正常
  - [ ] SubTask 7.3.7: 增量测试 - 验证前序模块（对话界面）仍正常工作

- [ ] Task 7.4: 分析结果展示
  - [ ] SubTask 7.4.1: 实现 ResultDisplay.vue（图表渲染组件）
  - [ ] SubTask 7.4.2: 集成 ECharts 图表库
  - [ ] SubTask 7.4.3: 实现表格展示组件
  - [ ] SubTask 7.4.4: 实现结果导出功能（PDF、Word）
  - [ ] SubTask 7.4.5: 实现历史记录查看
  - [ ] SubTask 7.4.6: 编写组件测试
  - [ ] SubTask 7.4.7: 增量测试 - 验证分析结果展示正常
  - [ ] SubTask 7.4.8: 增量测试 - 验证前序模块（文件上传）仍正常工作

- [ ] Task 7.5: WebSocket 客户端
  - [ ] SubTask 7.5.1: 创建 frontend/src/services/ 目录
  - [ ] SubTask 7.5.2: 实现 websocket.ts（连接管理）
  - [ ] SubTask 7.5.3: 实现消息解析
  - [ ] SubTask 7.5.4: 实现断线重连
  - [ ] SubTask 7.5.5: 实现心跳机制
  - [ ] SubTask 7.5.6: 编写单元测试
  - [ ] SubTask 7.5.7: 增量测试 - 验证 WebSocket 客户端正常工作
  - [ ] SubTask 7.5.8: 增量测试 - 验证前序模块（分析结果展示）仍正常工作
  - [ ] SubTask 7.5.9: 增量测试 - 集成测试（前端 + 后端 API）

## 阶段八：集成测试与优化（第 15-16 周）

- [ ] Task 8.1: 端到端测试
  - [ ] SubTask 8.1.1: 创建 tests/e2e/ 目录
  - [ ] SubTask 8.1.2: 编写 E2E 测试用例（Playwright）
  - [ ] SubTask 8.1.3: 测试完整分析流程
  - [ ] SubTask 8.1.4: 测试异常场景
  - [ ] SubTask 8.1.5: 测试并发场景
  - [ ] SubTask 8.1.6: 增量测试 - 验证所有 E2E 测试通过
  - [ ] SubTask 8.1.7: 增量测试 - 验证前序模块（前端）仍正常工作

- [ ] Task 8.2: 性能优化
  - [ ] SubTask 8.2.1: 优化 LLM 调用延迟
  - [ ] SubTask 8.2.2: 优化沙箱启动时间
  - [ ] SubTask 8.2.3: 优化前端渲染性能
  - [ ] SubTask 8.2.4: 添加缓存机制
  - [ ] SubTask 8.2.5: 性能测试（Locust）
  - [ ] SubTask 8.2.6: 增量测试 - 验证性能指标达标（响应时间 < 5s）
  - [ ] SubTask 8.2.7: 增量测试 - 验证前序模块（E2E 测试）仍正常工作

- [ ] Task 8.3: 安全审计
  - [ ] SubTask 8.3.1: 代码安全审查
  - [ ] SubTask 8.3.2: 依赖安全检查（safety）
  - [ ] SubTask 8.3.3: 渗透测试
  - [ ] SubTask 8.3.4: 修复安全漏洞
  - [ ] SubTask 8.3.5: 增量测试 - 验证无高危安全漏洞
  - [ ] SubTask 8.3.6: 增量测试 - 验证前序模块（性能优化）仍正常工作

- [ ] Task 8.4: 文档编写
  - [ ] SubTask 8.4.1: 编写用户手册（docs/user-guide.md）
  - [ ] SubTask 8.4.2: 编写开发文档（docs/developer-guide.md）
  - [ ] SubTask 8.4.3: 编写 API 文档（docs/api-reference.md）
  - [ ] SubTask 8.4.4: 编写部署文档（docs/deployment.md）
  - [ ] SubTask 8.4.5: 增量测试 - 验证文档完整清晰

# Task Dependencies

- Task 1.1 → Task 1.2, Task 1.3, Task 1.4（项目初始化是所有任务的基础）
- Task 1.3 → Task 2.1, Task 2.3, Task 2.4, Task 2.5（LLM 客户端是 Agent 的基础）
- Task 1.4 → Task 4.1, Task 4.2, Task 4.3（工具注册表是工具系统的基础）
- Task 2.2 → Task 2.3, Task 2.4, Task 2.5（LangGraph 工作流是 Agent 的核心）
- Task 2.3, Task 2.4, Task 2.5 → Task 2.2（Planner、Executor、Reflection 共同构成工作流）
- Task 3.1 → Task 3.2, Task 3.3, Task 3.4（mem0 集成是记忆系统的基础）
- Task 3.4 → Task 2.3（记忆注入 Planner）
- Task 5.1 → Task 5.2, Task 5.3（Docker 环境是沙箱的基础）
- Task 5.2 → Task 2.4（沙箱管理器是 Executor 的依赖）
- Task 6.1 → Task 6.2, Task 6.3, Task 6.4（FastAPI 应用是 API 的基础）
- Task 6.2 → Task 7.5（WebSocket 网关是前端 WebSocket 客户端的服务端）
- Task 7.1 → Task 7.2, Task 7.3, Task 7.4, Task 7.5（前端初始化是所有前端任务的基础）
- Task 7.5 → Task 7.2, Task 7.3, Task 7.4（WebSocket 客户端是前端组件的依赖）
- Task 8.1 → 所有其他任务（E2E 测试依赖所有功能完成）

# 增量测试原则

1. **测试顺序**：前序模块验证 → 新增模块测试 → 模块间集成测试
2. **测试覆盖**：每个模块必须有对应的单元测试
3. **集成测试**：模块间集成必须有集成测试
4. **测试调整**：测试逻辑可根据实际需求调整，但必须保证测试目标
5. **自动化**：所有测试应可自动化执行，确保持续集成
