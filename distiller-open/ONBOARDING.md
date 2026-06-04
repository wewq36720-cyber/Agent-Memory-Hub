# 接入 distiller 指南

> 本文档面向想把 distiller 作为 memory hub 的新 agent 项目。

## 前置

- 你的项目已有自己的 agent 框架（Claude Code / Cursor / 自研）
- distiller 已部署（`docker compose up -d` 后 `/health` 返回 200）
- 网络可达 distiller api 容器（默认 8000 端口）

## 步骤 1：注册项目（创建 project_id）

distiller 用 `project_id` 做多租户隔离。每个接入方需先在 hub.projects 表创建一行：

```bash
docker compose exec mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" distiller_hub -e "
INSERT INTO projects (project_id, name, description, status)
VALUES ('your-project-id', '你的项目名', '简短描述', 'active');"
```

`project_id` 选短的英文 ID（snake-case 或 kebab-case），后续所有调用都要带上它。

## 步骤 2：选接入方式

### 方式 A：HTTP REST 客户端

适合任意语言，最通用：

```python
import httpx

client = httpx.Client(base_url="http://localhost:8000", timeout=10)

# 写入一条决策类记忆
resp = client.post("/api/v1/memories", json={
    "project_id": "your-project-id",
    "memory_type": "decision",
    "title": "选用 Postgres 而非 MySQL",
    "summary": "评估后决定使用 Postgres",
    "content": "原因 1: ...\n原因 2: ...",
    "tags": ["db", "选型"],
    "importance": 8,
    "agent_name": "your-agent",
    "trace_id": "abc-123"
})
print(resp.json())  # {"memory_id": ..., "jsonl_offset": ..., "trace_id": "abc-123"}

# FULLTEXT 检索
resp = client.get("/api/v1/memories", params={
    "project_id": "your-project-id",
    "q": "Postgres",
    "top_k": 5
})
```

### 方式 B：MCP server 接入（推荐 Claude Code 用户）

distiller 自带 MCP stdio server。在 `~/.claude/settings.json` 或 `claude_desktop_config.json` 里加：

```json
{
  "mcpServers": {
    "distiller": {
      "command": "bash",
      "args": ["/absolute/path/to/distiller/scripts/run-mcp.sh"],
      "env": {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_DATABASE": "distiller_hub",
        "MYSQL_ROOT_PASSWORD": "your-password",
        "JSONL_LOG_DIR": "/absolute/path/to/distiller/logs"
      }
    }
  }
}
```

重启客户端后 7 个工具（write_memory / search_memory / ...）即可在对话中直接调用。

## 步骤 3：使用 trace_id 全链路追踪

distiller 三处都会持久化 `trace_id`：REST 入口日志、memories 行、audit_log 行。

约定：

- 同一次"用户意图"的所有调用复用同一个 trace_id（UUID v4 即可）
- agent 框架在每轮 turn 开始时生成一个 trace_id，传给所有 distiller 调用
- 排查时 `SELECT * FROM audit_log WHERE trace_id = '...';` 能还原整条调用链

## 步骤 4：记忆分类规范（7 种 memory_type）

| memory_type | 适用场景示例 |
|-------------|--------------|
| decision | "决定用 X 而非 Y，因为 ..." |
| pattern | "反复出现的代码模式 / 重构手法" |
| fix | "修复了什么 bug，根因是什么" |
| architecture | "系统模块边界、调用关系" |
| api | "外部接口契约 / 内部模块签名" |
| note | "暂时记下、未来再消化" |
| event | "运行时事件流（部署、告警、回滚）" |

importance（1-10）建议：日常 5，影响 1 模块 7，影响整个项目 9+。

## 步骤 5：常见问题

**Q: 我能直接改 hub schema 吗？**
不能。17 张表是对外契约。需要新字段时走 `schema_versions` 迁移流程，避免接入方相互踩。

**Q: distiller 会不会调用我的 LLM 凭证？**
不会。distiller 只做"写入 + 检索 + 编排"，不内嵌任何 LLM。检索是 MySQL FULLTEXT，不需要 embedding。

**Q: 多个项目数据隔离吗？**
是。所有业务表都有 `project_id` 列，REST/MCP 调用必须传该字段。表级隔离（不是按租户 schema）。

**Q: JSONL 文件会不会无限膨胀？**
按天滚动（`logs/YYYY-MM-DD.jsonl`）。线上需要自行配冷归档。

**Q: 改了一条记忆怎么办？**
不能改。写一条新的同时把 `superseded_by` 指向新行。旧记忆永远保留，便于审计。

**Q: 我的 agent 进程崩了，能从 JSONL 恢复 MySQL 吗？**
理论可以——JSONL 是真相之源，MySQL 是派生视图。本期未提供 replay 工具，本期 Non-goal。

## 现有客户

| 项目 | project_id | 状态 |
|------|------------|------|
| distiller-self-test | test-proj-001 | active（仅 e2e 测试用） |

接入新项目后，请把行追加到本表 PR 备案。
