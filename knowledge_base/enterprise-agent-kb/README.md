# 企业 Multi-Agent 智能协作平台 - 知识库

> 本知识库供 RAG 系统检索使用，覆盖企业日常运营中的员工自助服务、流程审批、IT支持和Agent运营管理等场景。

## 知识库结构

```
enterprise-agent-kb/
├── README.md                              ← 本文件（知识库索引与使用说明）
│
├── company_policy/                        ← 公司级通用制度（15个文件）
│   ├── employee_handbook.md               ← 员工手册（公司概况、组织架构、入职离职、薪酬福利）
│   ├── code_of_conduct.md                 ← 行为规范（职业道德、信息安全、商务礼仪、奖惩制度）
│   ├── promotion.md                       ← 晋升制度（T/M/P三序列职级、晋升条件与流程）
│   ├── training.md                        ← 培训发展（入职培训、学分制度、导师制度）
│   ├── approval_process.md                ← 审批流程规范（各流程审批链路、操作规范、审计记录）
│   ├── agent_operations.md                ← Agent运营管理指南（监控、错误排查、评测体系）
│   ├── project_initiation.md              ← 项目立项流程（发起条件、审批、驳回重提）✨新增
│   ├── procurement.md                     ← 采购申请制度（金额阈值、审批分级、预算关联）✨新增
│   ├── transfer_process.md                ← 员工调岗与项目移交（调岗流程、移交清单、联动机制）✨新增
│   ├── cross_department_escalation.md     ← 跨部门协作与升级申诉（协作请求、升级路径）✨新增
│   ├── data_access_control.md             ← 数据权限与敏感信息访问控制（数据分级、角色权限）✨新增
│   ├── archive_policy.md                  ← 流程归档与保存制度（保存期限、调阅方式、销毁规则）✨新增
│   ├── delegation_rules.md                ← 代理发起与代办规则（可代办/必须本人、授权方式）✨新增
│   ├── budget_management.md               ← 预算管理制度（预算编制、不足处理、超预算审批）✨新增
│   └── process_operations.md              ← 流程查询与操作指引（发起、审批、撤回、催办）
│
├── hr_policy/                             ← 人力资源政策（2个文件）
│   ├── leave_policy.md                    ← 请假制度（年假、病假、事假、婚假、产假、丧假等）
│   └── reimbursement.md                   ← 报销政策（差旅费、业务招待费、办公用品、通讯费）
│
├── it_service/                            ← IT服务（5个文件）
│   ├── faq.md                             ← IT常见问题（账号密码、网络、设备、安全）
│   ├── software_list.md                   ← 软件清单（办公软件、开发工具、设计工具）
│   ├── ticket_process.md                  ← IT工单处理流程（优先级定义、SLA、提交流程）
│   ├── sla.md                             ← IT服务等级协议（KPI指标、服务时间、升级机制）
│   └── code_release.md                    ← 代码发布流程（Review、测试、灰度、Hotfix）
│
├── admin_service/                         ← 行政服务（4个文件）
│   ├── meeting_room.md                    ← 会议室管理（会议室列表、预约规则、使用规范）
│   ├── office_supplies.md                 ← 办公用品（申领流程、物品清单、费用管理）
│   ├── travel.md                          ← 差旅管理（审批流程、费用标准、报销流程）
│   └── facilities.md                      ← 公司设施（楼层分布、餐饮、健身、停车）
│
└── platform/                              ← 平台架构（1个文件）
    └── agent_architecture.md              ← Multi-Agent平台架构（Agent分工、协作机制、冲突处理）✨新增
```

## 知识库与业务场景映射

| 业务场景 | 对应知识库文件 |
|---------|--------------|
| "出差住宿标准是多少？" | `admin_service/travel.md`, `hr_policy/reimbursement.md` |
| "试用期有多少天年假？" | `hr_policy/leave_policy.md`, `company_policy/employee_handbook.md` |
| "报销需要哪些材料？" | `hr_policy/reimbursement.md` |
| "公司的代码发布流程是什么？" | `it_service/code_release.md` |
| "帮我请明天年假" | `hr_policy/leave_policy.md`, `company_policy/approval_process.md` |
| "提交一个报销单" | `hr_policy/reimbursement.md`, `company_policy/approval_process.md` |
| "帮我提一个IT工单" | `it_service/ticket_process.md`, `it_service/faq.md` |
| "预订明天下午的会议室" | `admin_service/meeting_room.md` |
| "查看我的请假审批到哪了" | `company_policy/approval_process.md`, `company_policy/process_operations.md` |
| "驳回这个报销申请" | `company_policy/approval_process.md` |
| "查看Agent最近的错误日志" | `company_policy/agent_operations.md` |
| "如何优化Prompt效果？" | `company_policy/agent_operations.md` |
| "电脑连不上WiFi" | `it_service/faq.md`, `it_service/ticket_process.md` |
| "可以申请安装Photoshop吗？" | `it_service/software_list.md` |
| "新员工入职全流程" | `company_policy/employee_handbook.md`, `company_policy/training.md` |
| "公司有什么福利？" | `company_policy/employee_handbook.md`, `company_policy/promotion.md` |
| "项目立项申请怎么发起？" | `company_policy/project_initiation.md` |
| "立项被驳回了怎么办？" | `company_policy/project_initiation.md` |
| "采购申请金额怎么划分审批？" | `company_policy/procurement.md` |
| "员工调岗项目怎么移交？" | `company_policy/transfer_process.md` |
| "审批人不处理怎么办？" | `company_policy/approval_process.md`, `company_policy/cross_department_escalation.md` |
| "流程提交后信息填错了能撤回吗？" | `company_policy/process_operations.md` |
| "超过处理时限系统怎么处理？" | `company_policy/approval_process.md` |
| "审批人请假了怎么办？" | `company_policy/approval_process.md`（审批委托） |
| "能帮同事提交请假吗？" | `company_policy/delegation_rules.md` |
| "历史流程记录保存多久？" | `company_policy/archive_policy.md` |
| "报销时预算不足怎么办？" | `company_policy/budget_management.md` |
| "Agent之间怎么共享信息？" | `platform/agent_architecture.md` |
| "Agent结论冲突怎么处理？" | `platform/agent_architecture.md` |
| "敏感信息谁能看？" | `company_policy/data_access_control.md` |

## RAG 切分建议

### 切分参数
| 参数 | 推荐值 | 说明 |
|------|--------|------|
| chunk_size | 512-1024 tokens | 每个文档片段大小 |
| overlap | 50-100 tokens | 片段间重叠，避免截断上下文 |
| separator | 段落/标题 | 优先按 Markdown 标题和段落切分 |

### 元数据建议
为每个chunk附加以下元数据，便于过滤检索：
```json
{
  "source_file": "hr_policy/leave_policy.md",
  "department": "hr",
  "category": "policy",
  "topic": "请假",
  "last_updated": "2024-03-01"
}
```

### 检索策略建议
- **混合检索**：Dense Embedding + BM25 关键词检索，通过 RRF 融合排序
- **Reranker**：检索后通过 Reranker 精排，提高最终输入 LLM 的文档质量
- **引用回溯**：返回答案时附带来源文件名和原文片段，方便用户核实

### 关键词索引
每个文件末尾都包含「关键词」段落，可用于：
1. 增强 BM25 关键词检索的召回率
2. 作为 metadata 标签辅助过滤
3. 意图识别时辅助判断应检索哪个知识库分区

## Agent路由建议

根据用户问题中的关键词，可初步判断应路由到哪个Agent和知识库分区：

| 关键词 | 路由Agent | 检索分区 |
|--------|----------|---------|
| 请假/年假/病假/事假/休假 | HR Agent | hr_policy/ |
| 报销/发票/费用/差旅费 | HR Agent | hr_policy/ + admin_service/travel.md |
| 密码/网络/打印机/软件/电脑 | IT Agent | it_service/ |
| 会议室/办公用品/停车/设施 | Admin Agent | admin_service/ |
| 入职/离职/晋升/培训/考勤/薪酬 | HR Agent | company_policy/ + hr_policy/ |
| 审批/驳回/撤回/流程状态 | 流程 Agent | company_policy/approval_process.md + process_operations.md |
| 代码发布/上线/部署/Hotfix | IT Agent | it_service/code_release.md |
| 日志/监控/评测/Prompt/运营 | 运营 Agent | company_policy/agent_operations.md |
| 出差/差旅/机票/酒店 | Admin Agent | admin_service/travel.md |
| 项目立项/PMO/可行性 | 流程 Agent | company_policy/project_initiation.md |
| 采购/比价/供应商 | 流程 Agent | company_policy/procurement.md |
| 调岗/移交/交接 | HR Agent | company_policy/transfer_process.md |
| 跨部门/协作/升级/申诉 | 协调 Agent | company_policy/cross_department_escalation.md |
| 预算/预算不足/超预算 | 财务 Agent | company_policy/budget_management.md |
| 权限/敏感/脱敏/数据分级 | 流程 Agent | company_policy/data_access_control.md |
| 归档/保存期限/调阅/历史 | 流程 Agent | company_policy/archive_policy.md |
| 代办/代理/授权/代为发起 | HR Agent | company_policy/delegation_rules.md |
| Agent分工/共享信息/冲突 | 平台 Agent | platform/agent_architecture.md |

## 更新记录

| 日期 | 更新内容 | 操作人 |
|------|---------|--------|
| 2024-03-01 | 初始版本，创建全部知识库文件 | Agent |
| 2024-03-01 | 新增9个文件：project_initiation、procurement、transfer_process、cross_department_escalation、data_access_control、archive_policy、delegation_rules、budget_management、agent_architecture | Agent |
