# ecom-customer-agent · 电商客服 Agent 平台

> 面向抖店（抖音电商）的智能客服 Agent 系统，兼容淘宝 / 拼多多平台。
> An LLM-powered e-commerce customer service agent with RAG, multi-modal input, function-calling tool loop, and full-path data masking.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green)](#)
[![Tests: 112 passed](https://img.shields.io/badge/tests-112%20passed-brightgreen)](#)

严格 RAG 答疑（少幻觉）、多模态咨询（截图+文字）、
订单/物流/商品实时查询（Function Calling + 抖店开放平台）、敏感信息全路径脱敏、多轮会话持久化。

---

## 功能特性

- **严格 RAG 优先答疑**：FAQ / 商品 / 政策三集合检索（Chroma 召回 → Jina 精排 → DeepSeek 生成），
  System Prompt 强制「只基于检索片段回答」，支持语义等价问题匹配（"下单后多久到" = "发货时间"），无匹配转人工话术
- **多模态咨询**：截图 + 文字 → MiMo-V2.5 结构化视觉（6 字段 JSON）∥ OCR → 决策引擎
  ANSWER / WAIT / BEST_EFFORT 三态 → 查询改写 → RAG
- **Agent 工具循环**：AgentLoop + ToolExecutor 最多 4 步工具调用，
  工具链 `query_order` / `query_logistics` / `query_product` / `handoff_human`
- **平台无关内核**：`PlatformAdapter` 抽象；抖店适配器完整实现 HMAC-SHA256 签名、推送验签（MD5）、
  消息收发与业务查询；淘宝适配器签名校验已实现
- **敏感信息全路径脱敏**：手机 / 订单号 / 身份证 / 银行卡 / 邮箱 / 门牌，
  用户输入 → 工具参数 → LLM 上下文 → DB 落库全链路 mask / restore（16-18 位订单号与银行卡正则优先级已处理）
- **多轮会话持久化**：按 `(platform, buyer_id, shop_id)` 三元组恢复会话，
  SQLAlchemy async + aiosqlite 落库 + 内存 LRU 缓存（上限 500，TTL 30 分钟）
- **管理后台**：5 页面 SPA（仪表盘 / 知识库 CRUD / 会话记录 / 测试问答 / 批量测试），
  批量测试支持 Excel 上传 → 后台异步批量问答 → 人工审核 → 结果导出
- **Provider 可替换**：LLM / VLM / Embedding / Rerank 全部抽象为接口，模型路由可切换
- **112 项自动化测试**：冒烟 / 多模态 / 工具注册执行 / 脱敏 / 抖店适配器 / RAG-LLM 集成 / 会话存储 / Webhook 安全

## 总体架构

```
                         ┌──────────────────────────────────────┐
                         │           统一入口 main.py            │
                         │  uvicorn factory → customer_service   │
                         └──────────────────┬───────────────────┘
                                            │
                         ┌──────────────────▼───────────────────┐
                         │     apps/customer_service_agent       │
                         │  API · Agent · Adapters · CLI · Admin │
                         └─┬────────────┬────────────┬──────────┘
                           │            │            │
              ┌────────────▼──┐  ┌──────▼──────┐  ┌─▼──────────────┐
              │   runtime/    │  │ knowledge_  │  │  tool_center/  │
              │ conversation  │  │  platform/  │  │ registry       │
              │ decision      │  │ service     │  │ executor       │
              │ multimodal    │  │ retriever   │  └────────────────┘
              │ llm providers │  │ ingest      │
              └───────┬───────┘  └────┬────────┘
                      │               │
         ┌────────────▼───────────────▼────────────┐
         │              common/ · security/         │
         │   config · logger · database · masker    │
         └──────────────────────────────────────────┘
                      │
         ┌────────────▼───────────────────────────────┐
         │  data/chroma · SQLite · 外部 LLM/平台 API   │
         └────────────────────────────────────────────┘
```

核心数据流（Webhook + Agent 工具循环）：

```
抖店推送 payload
  → DoudianAdapter.parse_incoming（MD5 签名校验，失败返回 403）
  → SessionStore 按 (platform, buyer_id, shop_id) 恢复会话
  → Masker 脱敏 → DB 落库（脱敏版）
  → AnswerEngine.answer_agent：
       RAG 全集合检索 → LLM + ToolExecutor 工具循环（≤4 步）
       工具参数 restore 真实值 → 执行 → 结果 mask 后入 session
  → 回复 restore 真实值发给买家（DB 存脱敏版）
```

## 技术栈

| 层次 | 技术 | 用途 |
|------|------|------|
| Web 框架 | FastAPI + Uvicorn | HTTP API / Webhook / 管理后台 |
| 生成 LLM | DeepSeek V4 Flash | RAG 生成、查询改写、Agent 工具循环 |
| 视觉 LLM | 小米 MiMo-V2.5 | 截图理解、结构化 Vision、OCR |
| Embedding | 阿里云 DashScope text-embedding-v3 | 知识写入与查询向量化 |
| Rerank | Jina Reranker v2 multilingual | 召回二次精排 |
| 向量库 | ChromaDB（cosine，本地持久化） | FAQ / 商品 / 政策知识检索 |
| 关系库 | SQLAlchemy 2.x async + aiosqlite | 会话 / 消息 / 转人工任务 |
| 安全 | 自研 Masker + RBAC 接口 | 全路径脱敏、角色权限 |
| 测试 | pytest + pytest-asyncio | 112 项测试 |

## 快速开始

```bash
# 1. 安装
pip install -e ".[dev]"

# 2. 配置
cp .env.example .env    # 填入 DEEPSEEK_* / MIMO_* / DASHSCOPE_* / JINA_* 密钥

# 3. 灌库（或通过管理后台在线录入）
python -m knowledge_platform.knowledge_service.ingest \
  --source data/faq.jsonl --collection kb_faq --clear

# 4. 启动服务
python main.py
# 或
uvicorn apps.customer_service_agent.main:create_app --factory --host 0.0.0.0 --port 8000

# 5. 测试
python -m pytest tests/ -q    # 112 项全部通过
```

CLI 本地调试：

```bash
python -m apps.customer_service_agent.cli.qa "你们的尺码准吗"
python -m apps.customer_service_agent.cli.qa --interactive
```

管理后台：浏览器打开 `http://localhost:8000/admin/`

## 核心 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/qa` | 纯文本 FAQ 答疑 |
| POST | `/api/qa/multimodal` | multipart 多模态 / 多轮 |
| POST | `/webhooks/doudian` | 抖店消息推送回调 |
| POST | `/webhooks/taobao` | 淘宝千牛回调（兼容保留） |
| GET | `/admin/` | 管理后台 SPA |

## 设计亮点

1. **RAG 优先 + 少幻觉**：答疑路径强制「只基于检索片段回答」，Embedding 强命中兜底
   （top-1 被 reranker 挤出时强制补回），无匹配走转人工话术而非编造
2. **工具循环的工程化**：ToolRegistry 元数据登记 + ToolExecutor 批量 tool_calls 执行，
   工具参数真实值 restore / 结果 mask 的安全闭环
3. **脱敏优先级工程**：邮箱 → 身份证 → 手机号 → 订单号（15-18位）→ 银行卡（16-19位），
   避免 16-18 位订单号被误判为银行卡
4. **诚实记录的演进**：`方案架构.md` 记录了完整演进蓝图与已知缺口（抖店真实 API 待联调、
   权限/审计待接入、统一会话编排层等）——生产级工程素养的体现

## 目录结构（顶层）

```
apps/customer_service_agent/   # 业务应用：API · Agent · Adapters · CLI · Admin
runtime/                       # 会话编排 · 决策 · 多模态 · LLM Provider
knowledge_platform/            # RAG 流水线 · Chroma 检索 · 灌库（评测/治理预留）
tool_center/                   # 工具注册表 · 执行器
security/                      # 脱敏 Masker · RBAC
common/                        # 配置 · 日志 · DB ORM
tests/                         # 112 项测试
```

## 已知缺口（演进中）

- 抖店真实 API 联调与 Webhook 验签验证（逻辑已实现，待真实 token/推送验证）
- ToolCenter 权限/审计层接入
- AgentLoop 与 ConversationManager 两套会话统一
- 知识库量级增大后迁移 Milvus / Qdrant（ChromaDB `get()` 不支持分页）

详见 [`方案架构.md`](方案架构.md)。
