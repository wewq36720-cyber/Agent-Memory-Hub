# Distiller — Agent Memory Hub

> 上下文蒸馏 MCP 数据库 / Agent Memory Hub
> 长效运营的 agent 记忆基础设施层

distiller 是一个独立运营的 agent 记忆中枢，把多个 agent 项目的"决策、修复、模式、架构、API、笔记"统一沉淀为可检索的真相之源。它对外同时暴露 REST 和 MCP 双接口，对内以 JSONL 日志 + MySQL 派生视图保证写入路径的可审计与可重放。

distiller 自身就是它的第一个客户，但项目独立演进——其他 agent 项目（Claude Code / Cursor / 自研 agent 框架）可以把它当作共享 hub 接入。

## 核心特性

- 17 张表的 hub schema（hub 9 张 + app 8 张，distiller 自身使用 app 库）
- 双接口：REST API + MCP 协议（同一服务进程同时暴露）
- 真相之源 JSONL 日志（fsync 落盘）+ MySQL 派生视图
- 中文 ngram FULLTEXT 全文搜索（utf8mb4_0900_ai_ci）
- trace_id 全链路追踪：REST 入口 → memories → audit_log 三方一致
- 7 种 memory_type 语义分类（decision / pattern / fix / architecture / api / note / event）
- append-only + supersede 版本链（不删旧记忆，只标记 superseded_by）
- 端到端 19 个 pytest 测试，100% 通过

## 快速启动

```bash
# 1. 拉取项目
git clone <repo> distiller && cd distiller

# 2. 配置环境
cp .env.example .env
# 编辑 .env，至少设置 MYSQL_ROOT_PASSWORD 与 MYSQL_DATABASE

# 3. 一键起服务
docker compose up -d

# 4. 验证存活
curl http://localhost:8000/health     # {"status":"ok"}
curl http://localhost:8000/health/db  # {"db":"connected"}

# 5. 跑端到端测试
bash scripts/run-e2e.sh
```

## 接口端点

### REST API（http://localhost:8000）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /health | 存活探针 |
| GET | /health/db | DB 连通探针 |
| POST | /api/v1/memories | 写入记忆（DIST-01 顺序：JSONL → MySQL → audit_log） |
| GET | /api/v1/memories?project_id=&q=&top_k= | FULLTEXT 搜索记忆 |
| POST | /api/v1/zones/{zone_name}/progress | 上报模块进度 |
| POST | /api/v1/zones/{zone_name}/issues | 开 issue |
| GET | /api/v1/projects/{project_id}/patrol | 巡检项目所有 zone |
| POST | /api/v1/reviews | 申请评审 |
| POST | /api/v1/reviews/{request_id}/result | 提交评审结果 |

OpenAPI 自动生成：http://localhost:8000/docs

### MCP 工具（stdio 模式）

7 个工具与 REST 端点一一对应，供 Claude Code / Cursor 等 MCP 客户端直接调用：

| 工具名 | 说明 |
|--------|------|
| write_memory | 写入记忆 |
| search_memory | FULLTEXT 检索 |
| report_progress | 上报模块进度 |
| report_issue | 开 issue |
| patrol | 项目巡检 |
| request_review | 申请评审 |
| submit_review | 提交评审结果 |

启动方式见 `scripts/run-mcp.sh`，配置示例见 `ONBOARDING.md`。

## 架构

详见 `docs/方案说明.md` §2.1。要点：

```
agent ──REST/MCP──► api 进程 ──┬─► JSONL（fsync, 真相之源）
                                ├─► MySQL hub + app（派生视图）
                                └─► audit_log（trace_id 串联）
```

写入路径 DIST-01 强制顺序：先 JSONL fsync，再 MySQL 落库，最后 audit_log；任意一步失败都不会留下"DB 有但 JSONL 没有"的不一致。

## 技术栈

| 类别 | 选型 |
|------|------|
| 语言 | Python 3.11+ |
| Web | FastAPI 0.115 + uvicorn |
| ORM | SQLAlchemy 2.0 |
| DB driver | PyMySQL 1.1 |
| DB | MySQL 8.0（utf8mb4_0900_ai_ci，ngram_token_size=2） |
| MCP | mcp >= 0.9 |
| 校验 | Pydantic 2.9 |
| 测试 | pytest 8.3 + httpx |
| 编排 | Docker Compose |

## 项目结构

```
distiller/
├── docker-compose.yml         # MySQL + api 编排
├── Dockerfile.api             # api 镜像
├── docker/mysql/              # 初始化 SQL（hub + app）
├── pyproject.toml
├── src/distiller/
│   ├── main.py                # FastAPI 入口
│   ├── config.py / db.py
│   ├── models.py              # 17 个 ORM 类
│   ├── repo/                  # 5 个仓储类
│   ├── service/               # 4 个服务类（DIST-01 编排）
│   ├── jsonl/writer.py        # 真相之源写入
│   └── api/
│       ├── rest/              # 7 端点 + DTO
│       └── mcp/               # 7 工具 stdio server
├── tests/e2e/                 # 19 个端到端测试
├── scripts/run-e2e.sh         # 一键端到端
└── docs/                      # 方案说明 / 验收报告
```

## 测试

```bash
bash scripts/run-e2e.sh       # 19/19 全过
```

覆盖：health / memory CRUD / DIST-01 写入顺序 / zone workflow / supersede 链 / FK 约束。

## 文档

- 方案说明：`docs/方案说明.md`
- 接入指南：`ONBOARDING.md`
- 项目验收报告：`docs/项目验收报告.md`
- 数据库设计：`docs/database-design.md`（v2.0 待补齐）

## 状态

| 阶段 | 状态 |
|------|------|
| Phase A 基础设施（17 张表、Docker、健康检查） | 已完成 |
| Phase B 服务层（ORM / Repo / Service / REST / MCP） | 已完成 |
| Phase C 端到端验证（19 测试） | 已完成（19/19） |

## License

待定（占位）。
