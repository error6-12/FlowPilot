# FlowPilot - 企业员工服务与流程协同平台

FlowPilot 是面向企业员工自助服务的 Multi-Agent 协作平台。任务协调 Agent 负责将请求路由到知识咨询或 Workflow Agent，支持企业制度问答、请假、报销、IT 工单和会议室/资源预订。平台通过 Agentic RAG、确定性状态机、MCP 工具治理、审计持久化和运营可观测完成业务闭环。

## 项目背景

企业员工往往需要在多个系统之间查找制度、询问办事入口并重复填写流程信息。FlowPilot 将“查知识”和“办流程”统一在同一会话入口，并用可审计、可评测的 Agent 执行链降低业务耦合。

## 核心能力

- **结构化任务路由**：识别知识咨询、请假、报销、IT 工单和资源预订，输出意图、目标 Agent、置信度和澄清标记。
- **Multi-Agent 协作**：任务协调、知识咨询和 Workflow Agent 分工处理复杂请求。
- **RAG 知识咨询**：使用 FAISS Dense 与 BM25 双路召回，通过 RRF 融合和可插拔 Reranker 重排；结合大模型生成自然语言回答，支持流式输出和确定性来源引用。
- **企业流程执行**：支持请假、报销、IT 工单和资源预订的多轮字段收集、确认、取消与审计持久化。
- **MCP 与工具治理**：使用 Tool Registry 统一处理 Schema、权限、超时、重试、幂等和调用审计。
- **Embedding 缓存优化**：通过数据库缓存和文件缓存减少重复向量计算，提高知识检索性能。
- **数据管理能力**：支持知识库、企业资源、流程记录和用户行为数据的维护，并在数据变化后自动更新相关索引。
- **索引治理**：支持文档级增量 upsert/delete、索引版本状态和向量维度保护。
- **运营调试后台**：访问 `/ops` 查看 Agent Trace、工具成功率和知识索引状态。
- **Prompt 版本治理**：持久化路由、知识问答和 Workflow Prompt 版本，并在 Trace 中记录生效版本快照。
- **日志与兜底机制**：保留关键处理过程日志，在信息不足或异常情况下提供更稳定的降级处理。

## 系统架构

项目采用严格的五层架构，核心原则是：**下层不能反向调用上层**。这样可以避免循环依赖，让业务逻辑、数据访问和接口编排保持清晰边界。

```text
Web & Application Layer
    ↓  app.py, web/：页面、路由入口、系统启动
API Layer
    ↓  api/：外部接口、请求编排、响应封装
Agents Layer
    ↓  agents/：AI Agent、任务路由、对话流程控制
Services Layer
    ↓  services/：业务逻辑、推荐算法、向量处理
DB Layer
    ↓  db/：数据模型、数据库连接、Repository
```

### 允许的调用方向

- Web 层调用 API 层
- API 层调用 Agents 层或 Services 层
- Agents 层调用 Services 层
- Services 层调用 DB 层

### 禁止的调用方式

- 下层反向调用上层
- Web 层绕过 API 直接访问 Services 或 DB
- Agents 层绕过 Services 直接访问 DB
- Services 层调用 Agents、API 或 Web

## Agent 设计

### Task Classification Agent

任务分类 Agent 是系统的主调度器，负责分析用户输入、判断任务类型，并把请求分发给合适的专业 Agent。

```text
用户输入 → 意图分析 → Agent 路由 → 响应协调
```

主要职责：

- 判断用户意图
- 维护对话状态
- 控制不同 Agent 之间的切换
- 处理无法分类或超出能力范围的问题

### Consultation Agent

咨询 Agent 负责知识问答场景，使用 RAG 流程从知识库中检索相关内容，再结合大模型生成回答。

```text
任务分类 → Dense/BM25 双路召回 → RRF 融合 → Reranker → 流式回答与来源引用
```

主要职责：

- 区分咨询问题类型
- 从知识库检索相关内容
- 构建提示词
- 生成自然语言回答

### Appointment Agent

预约 Agent 负责预约相关流程，包括解析用户输入、匹配技师、检查预约信息、生成确认消息等。

```text
任务分类 → 解析预约需求 → 技师匹配 → 预约确认
```

主要职责：

- 提取预约时间、服务项目、技师偏好等信息
- 匹配合适技师
- 处理信息缺失时的追问
- 生成预约结果和提醒

### User Behavior Agent

用户行为 Agent 更偏向后台智能分析，不完全依赖用户显式请求。它会根据交互记录、预约历史和偏好数据分析用户行为，为后续推荐提供依据。

```text
行为记录 → 模式分析 → 偏好更新 → 个性化推荐
```

主要职责：

- 记录用户行为
- 分析偏好模式
- 生成推荐依据
- 支持主动反馈和个性化服务

## 核心设计思想

### 1. 用任务分类降低系统复杂度

系统并不让一个 Agent 处理所有事情，而是先判断用户意图，再分发给对应模块。这样可以让咨询、预约、行为分析等逻辑保持独立，也更容易扩展新的 Agent。

### 2. 用 RAG 解决专业知识回答

按摩服务相关的项目介绍、注意事项、适用人群等内容更适合通过知识库维护。RAG 能让回答基于可控知识来源，而不是完全依赖大模型自由生成。

### 3. 用用户行为让推荐更个性化

系统会记录用户的咨询、预约和偏好信息。后续在推荐技师或服务项目时，可以结合历史行为，而不是每次都从零开始询问。

### 4. 用分层架构保证可维护性

Agent 负责智能流程，Service 负责业务逻辑，Repository 负责数据访问。每层只关心自己的职责，减少后期修改时的连锁影响。

### 5. 为真实业务场景预留扩展空间

项目目前以本地 SQLite 和单体服务为主，但架构上预留了模型提供商切换、MCP 外部服务接入、后台任务、缓存优化和云端部署的扩展方向。

## 架构图

![System Architecture](./architecture%20.jpg)

## 技术栈

- **后端框架**：FastAPI、Uvicorn
- **AI 框架**：LangChain
- **大模型接入**：兼容 OpenAI 格式的模型提供商，例如 Qwen、DeepSeek、Zhipu、OpenAI、Azure OpenAI
- **混合检索**：FAISS、BM25、RRF、可插拔 Reranker
- **数据库**：SQLite、SQLAlchemy
- **RAG 能力**：Embedding、向量索引、知识库检索、提示词构建
- **流式响应**：Python AsyncGenerator
- **前端页面**：Jinja2 模板、静态 CSS
- **外部服务扩展**：MCP，用于天气等外部信息接入
- **配置管理**：python-dotenv
- **后台任务**：schedule

## 项目结构

```text
Smart appointment AI agent/
├── agents/                         # 多 Agent 智能层
│   ├── task_classification_agent.py # 任务分类与主路由
│   ├── consultant_agent.py          # RAG 咨询 Agent
│   ├── appointment_agent.py         # 智能预约 Agent
│   ├── user_behavior_agent.py       # 用户行为分析 Agent
│   ├── task_classification/         # 意图识别、状态管理、路由逻辑
│   ├── consultant/                  # 知识检索、提示词、回答生成
│   ├── appointment/                 # 预约解析、技师匹配、消息构建
│   └── user_behavior/               # 行为记录、偏好管理、模式分析
├── api/                             # API 编排层
│   ├── appointment.py               # 预约接口
│   ├── consultation.py              # 咨询接口
│   ├── task.py                      # 任务分类接口
│   ├── chat_handler.py              # 流式聊天处理
│   ├── technician.py                # 技师管理接口
│   ├── knowledge.py                 # 知识库管理接口
│   └── user_behavior_analysis.py    # 用户行为分析接口
├── services/                        # 业务逻辑层
│   ├── appointment_service.py       # 预约业务逻辑
│   ├── knowledge_service.py         # 知识库管理
│   ├── recommendation_service.py    # 推荐逻辑
│   ├── technician_service.py        # 技师信息管理
│   ├── text_embedding.py            # Embedding 与向量处理
│   └── user_behavior_service.py     # 用户行为服务
├── db/                              # 数据持久化层
│   ├── models.py                    # SQLAlchemy 模型
│   ├── db_router.py                 # 数据库路由
│   ├── local_db.py                  # 本地数据库操作
│   ├── base/                        # 数据库基础接口
│   └── repositories/                # Repository 数据访问封装
├── config/                          # 配置模块
│   ├── constants.py                 # 常量与枚举
│   ├── database.py                  # 数据库配置
│   ├── model_provider.py            # 模型与 Embedding Provider 工厂
│   ├── settings.py                  # 应用配置
│   └── time_config.py               # 时间与排班配置
├── web/                             # Web 页面层
│   ├── routes.py                    # 页面路由
│   ├── templates/                   # HTML 模板
│   └── static/                      # 静态资源
├── mcp-server/                      # MCP 外部服务扩展
├── data/                            # 数据库与缓存目录
├── tests/                           # 测试用例
├── app.py                           # 应用入口
├── requirements.txt                 # Python 依赖
├── .env.example                     # 环境变量模板
└── README.md                        # 项目说明
```

## 快速开始

### 1. 创建虚拟环境

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows CMD：

```cmd
.venv\Scripts\activate.bat
```

macOS 或 Linux：

```bash
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

Windows PowerShell 可以使用：

```powershell
Copy-Item .env.example .env
```

然后在 `.env` 中填写模型和数据库配置。项目支持 OpenAI 兼容格式的大模型与 Embedding 服务。

```env
MODEL_PROVIDER=qwen
LLM_API_KEY=your_llm_api_key_here
LLM_BASE_URL=your_openai_compatible_chat_base_url_here
LLM_MODEL=your_chat_model_name_here

EMBEDDING_PROVIDER=qwen
EMBEDDING_API_KEY=your_embedding_api_key_here
EMBEDDING_BASE_URL=your_openai_compatible_embedding_base_url_here
EMBEDDING_MODEL=your_embedding_model_name_here

DATABASE_URL=sqlite:///./data/smart_appointment.db

DEBUG=True
LOG_LEVEL=INFO
```

常见配置方向：

- Qwen：使用阿里云百炼或 DashScope 的模型、Base URL 和 API Key。
- DeepSeek：可用于聊天模型，Embedding 可搭配其他兼容服务。
- Zhipu：可配置智谱的聊天模型和向量模型。
- Azure OpenAI：将 `MODEL_PROVIDER` 设置为 `azure`，并补充对应的 Azure OpenAI 环境变量。

### 4. 启动服务

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

如果 8000 端口已被占用，可以换成 8001：

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

启动后可以访问：

- Web 页面：http://127.0.0.1:8000
- API 文档：http://127.0.0.1:8000/docs
- ReDoc 文档：http://127.0.0.1:8000/redoc

### 5. 启动企业工具 MCP Server

四类企业流程工具与 Web Agent 共用同一套 Tool Registry、Schema 和审计逻辑。使用 stdio 方式启动：

```bash
python mcp_server.py
```

MCP Server 暴露 `submit_leave_request`、`submit_reimbursement`、`create_it_ticket` 和 `book_enterprise_resource`。工具调用指标可通过以下只读接口查询：

- `GET /api/observability/tools/summary`
- `GET /api/observability/tools/calls?limit=50`
- `GET /api/observability/tools/calls?tool_name=create_it_ticket`

## 测试

当前企业知识库位于 `knowledge_base/enterprise-agent-kb/`。重新摄取并替换旧版知识：

```bash
python scripts/import_enterprise_kb.py
```

运行企业知识库真实检索冒烟测试：

```bash
python scripts/verify_enterprise_kb.py
```

验证 Workflow Agent 的创建、确认、SQLite 持久化和审计闭环：

```bash
python scripts/verify_workflow_semantics.py
```

已提交的流程可通过 `GET /api/workflows/{workflow_id}` 查询，或使用
`GET /api/workflows?conversation_id=...` 查看指定会话的流程记录。

运行默认离线测试（不调用外部模型 API）：

```bash
pytest
```

运行真实模型与完整业务链路集成测试：

```bash
pytest -m integration
```

集成测试可能调用已配置的 DeepSeek、智谱等服务并产生费用。默认测试与集成测试通过 `pytest.ini` 中的 Marker 策略隔离。

运行单个测试文件：

```bash
pytest tests/test_task_classification_agent.py
```

## 主要页面

- 首页聊天与预约入口：`web/templates/index.html`
- 知识库管理：`web/templates/knowledge_management.html`
- 技师管理：`web/templates/technician.html`
- 技师排班：`web/templates/technician_schedule.html`
- 用户行为分析：`web/templates/user_behavior_analysis.html`

## 后续规划

### 更强的 Agent 自主能力

- 增加 Agent 自我反思机制，让系统能够评估回答质量和预约成功率。
- 引入更完整的多轮推理链，提升复杂预约和冲突处理能力。
- 根据真实用户反馈优化推荐策略。

### 更完整的多 Agent 协作

- 增加 Agent-to-Agent 通信机制，减少所有任务都依赖主分类器转发的问题。
- 将用户行为 Agent 的后台分析能力做得更稳定，支持定时任务和主动触达。
- 把预约、推荐、咨询之间的上下文记忆打通得更自然。

### 生产化能力

- 增加用户登录、权限控制和数据隔离。
- 增加更完整的异常处理和边界场景覆盖。
- 优化向量检索性能、缓存策略和响应速度。
- 支持 Docker 部署、云数据库和更标准的日志监控。

## 项目价值

这个项目把多 Agent、RAG、用户行为分析、预约调度和外部工具接入放在同一个真实业务场景中验证。它既是一个按摩门店智能前台原型，也可以作为学习 AI Agent 工程化、分层架构、RAG 系统和业务自动化的综合实践项目。



------------------------------------------------------------
这个项目是我最早开始自学大模型做的项目。上面的内容是当时（2025年7月左右完成的）。
其实我在计划做更加复杂，符合时代趋势的Agent，预计在9月份完成，会分享在笔记中。
但是很多朋友问我这个项目能不能参考，所以我索性总结开源了除了。值得一提的是，上面的内容是25年写的，当时如何配置环境，都是传统方法，写在README中，自己配置。 但是在2026年，不管是vibe coding的方法，还是环境配置的方法，都有了极大改进。

我的项目配置的方法，现在都推荐使用SKILL，所以这里有setup-envrionment skill，一键配置。
我也总结了更多的这个项目，放在2026年，如何包装，如何使用配套资源，面试真题，视频讲解，使用建议在我的大模型笔记中。
👉 **请关注小红书：[不转到大模型不改名]（id:4740535877) 获取以上所有资源。**
👉 b站： 骑猪撞宝马71
