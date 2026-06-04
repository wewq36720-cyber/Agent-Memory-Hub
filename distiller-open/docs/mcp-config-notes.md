# MCP 服务器配置经验

## 问题：横线 vs 下划线

服务器名 `agent-memory-hub`（横线）导致工具命名空间为  
`mcp__agent-memory-hub__list_memories`，  
但 LLM 实际生成 `mcp__agent_memory_hub__list_memories`（下划线）→ `Error: No such tool available`。

**根因**：LLM 在生成 tool_use 时把服务器名的横线规范化成下划线。

**修复**：

```bash
claude mcp remove agent-memory-hub --scope user
claude mcp add agent_memory_hub --scope user -- node /path/to/mcp-server/dist/index.js
```

## 配置文件位置

```
~/.claude/.mcp.json    ← Claude Code 不读这里
~/.claude.json         ← 正确位置（claude mcp add 自动写）
<CWD>/.mcp.json        ← 项目级配置
```

## 跨机器迁移

- `~/.claude.json` 中 `mcpServers` 路径为绝对路径，换机器需重新配置
- distiller REST（Docker MySQL）为强本地依赖，需在目标机重新 `docker compose up`
- 换机器后：`npm install && claude mcp add agent_memory_hub ...`
