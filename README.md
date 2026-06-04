# Agent-Memory-Hub
> **Agent Memory Hub (Distiller)** — 多 Agent 共享记忆层基础设施。 > > 将多个 AI agent 项目的决策、修复、模式、架构、接口、笔记统一沉淀为可检索的结构化记忆，通过 REST API + MCP 协议双接口暴露，使任意 agent 框架（Claude Code / Cursor / 自研 agent）都能读写共享上下文。采用 JSONL（真相之源）+ MySQL（派生视图）双写架构，支持 append-only 版本链、中文全文搜索、trace_id 全链路追踪。
