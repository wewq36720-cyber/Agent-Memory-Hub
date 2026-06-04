# 通用开发规范 v1.0

适用范围：跨项目通用，任意接入 distiller 的 agent 项目都应遵守。  
项目自有规范优先级高于本规范，但项目自有规范不存在或未覆盖时按本规范执行。

## 必读顺序（新会话开干前）

1. 本文件（HUB 总索引）
2. [规则分级 P0-P4 + 优先级链 + 退出条款](#规则分级)
3. [四阶段工作流 Define→Plan→Build→Verify](#四阶段工作流)
4. [模块汇报格式](#汇报格式)
5. [Evidence Card 模板 + 反模式禁词](#evidence-card)
6. [Aegis 硬规则触发表](#aegis-触发表)
7. [跨会话上下文载体决策（distiller / docs 二选一）](#上下文载体)
8. [新项目接入清单](#接入清单)

---

## 规则分级

| 级别 | 关键词 | 含义 | 违反后果 |
|------|-------|------|---------|
| P0 | NEVER / MUST NOT | 阻断红线 | 立即停止待人工介入 |
| P1 | MUST | 强制 | 偏离需书面理由 + 人工审批 |
| P2 | SHOULD | 建议 | 偏离注明理由即可 |
| P3 | SHOULD NOT | 不建议 | 同上 |
| P4 | MAY | 可选 | 自由裁量 |

**优先级链（高 → 低）**

1. 项目宪法 / constitution.md（P0 红线集合）
2. 项目级开发规范 / dev-standards.md
3. 架构规范 / architecture-spec.md
4. 测试清单 / testing-checklist.md
5. 技能库 / .claude/skills/（任务前先查）
6. 通用开发规范（本文档）

**退出条款（必须违反 P0/P1 时）**

1. 陈述要违反的规则编号
2. 说明业务理由
3. 列出缓解措施
4. 等待人工审批
5. 写入 reference-log.md 或 distiller decision 记忆

---

## 四阶段工作流

| 阶段 | 输出物 | 审批点 |
|------|--------|--------|
| Define 定义 | 需求描述 + Non-goals | 🚦 Gate 1 用户审批计划 |
| Plan 设计 | 实施步骤（≤10 步）+ 文件清单 + 验证方式 | 🚦 Gate 2 用户审批方案 |
| Build 构建 | 代码变更 + 编译日志 | 每模块完成后等用户确认 |
| Verify 验证 | 测试报告 + Evidence Card | 🚦 Gate 3 最终审批 |

**Build 阶段每模块内循环**

设计说明 → 修改文件 → 编译验证 → 按汇报格式汇报 → **等用户确认才能进入下一模块**

**反模式（禁止）**

- ❌ 一次性改完所有文件
- ❌ 跳过 plan 直接编码
- ❌ 不等用户确认就推进

---

## 汇报格式

每个模块完成后必须按以下格式汇报，等用户确认才能进入下一模块：

```
## 模块 N 完成: [模块名]

**创建的文件：** `path/File.py` — 职责
**修改的文件：** `path/Old.py` — 改了什么
**编译结果：** ✅ 通过 / ❌ 失败 + 错误摘要
**设计决策：** [非显而易见的选择，给出理由]
**下一步：** 模块 N+1（等待确认）
```

---

## Evidence Card

宣布"完成 / 通过 / 已修复 / 已验证 / 可以提交"前必贴：

```
Evidence Card:
- Command / Check: <实际跑过的命令>
- Exit Status: <退出码或对应判定>
- Covered: <这次验证证明了什么>
- Not Covered: <仍未验证的部分>
- Residual Risk: <已知风险>
- Confidence: A | B | C
```

| 级别 | 含义 |
|------|------|
| A | 直接证据充分（命令实跑、断言全过、单测全绿）|
| B | 间接证据 / 部分覆盖 |
| C | 主要靠推断 |

**反模式禁词**（宣布完成时禁用，除非已贴 Evidence Card）：  
"应该" / "看起来" / "基本上" / "大概" / "差不多" / "Great!" / "Perfect!" / "Done!"

---

## Aegis 触发表

| 触发场景 | 强制动作 |
|---|---|
| 即将宣布"完成/通过/已修复"前 | 必贴 Evidence Card |
| 遇到 bug、报错 | 复现 → 读全 traceback → 列假设 → 逐个证伪。禁直接打补丁 |
| 同方案失败 ≥ 2 次 | 质疑前提，找最小必要约束 |
| 用户给模糊大目标 | 明确 goal / success evidence / stop condition / non-goals 四件套 |
| 2+ 独立子任务 | 必并行 launch Agent，禁止串行 |
| 多步跨 session 任务 | 显式写 memory，禁靠记忆 |
| 写代码前 | 先出 plan |
| 架构级决策 | 写 ADR |

---

## 上下文载体

**判断树**

```
项目是否接 distiller？
├─ 是 → 跨会话上下文走 distiller，docs/ 只放稳定设计文档
└─ 否 → 跨会话上下文走 .claude/docs/，每次新会话 Read 入 context
```

**走 distiller 时的规则**

- Plan / Evidence Card / 进度报告 / 接力索引 → `write_memory()`
- 新会话首次 → `search_memory(关键词, top_k=10)` 召回
- 决策走 supersede（保留旧版作 history）
- ❌ 不在 docs/ 重复落盘（双写会碎片化）

---

## 策略下沉原则

业务策略 = **确定性 Python 代码**，不是"让 LLM 判断"。

| 任务类型 | 写代码 | 交 LLM |
|---------|-------|--------|
| 过滤 / 检索 / 排序 | ✅ SQL / Python | ❌ |
| 数学评分 / 阈值判断 | ✅ 公式 | ❌ |
| 字典查表 / 角色分发 | ✅ dict / match | ❌ |
| 自然语言摘要 / 翻译 | ❌ | ✅ |
| 代码生成 / 规划 / 创意 | ❌ | ✅ |

---

## 接口与实现分离

```
Protocol（core/protocols.py）        ← 纯抽象，零策略，仅方法签名
   ↓
真实现（core/<layer>/from_xxx.py）   ← 承载策略 + 厂商协议适配
   ↓ HTTP / 文件 / SDK
后端服务（distiller / ollama / ...）
```

骨架阶段同时存在 Mock（from_dict / from_echo），跑通骨架再接真实现。

---

## Token 压缩 CTX-01~07

- 70% → 软触发：整理可丢弃的探索过程
- 85% → 硬触发：主动压缩并通知用户

**压缩保留五要素**

| 编号 | 要素 |
|------|------|
| CTX-01 | 会话意图（用户原始目标 + 当前阶段）|
| CTX-02 | 已修改文件（路径 + 改了什么）|
| CTX-03 | 已做决策（关键决策 + 理由）|
| CTX-04 | 未解决问题（卡点 / 待回复）|
| CTX-05 | 下一步（即将做的最小单位动作）|

文件路径、函数名、错误码、命令字符串**逐字保留不改写**。

---

## LANG-01 语言规范

- AI 回复全程中文（解释、计划、汇报、Evidence Card）
- 技术术语首次出现必须加括号解释
- 代码注释 / docstring 中文
- 代码本身（变量名 / 函数名）按编程语言惯例用英文

---

## 接入清单

### 首次会话 5 分钟启动流程

**1. 判断上下文载体**
- [ ] 项目是否接 distiller？确认 project_id 已建

**2. 必查记忆 / 文档**

走 distiller 的项目：
```python
dc = DistillerClient(project_id="<project-id>")
recs = dc.search_memory("handoff 接力索引", top_k=5)
```

**3. 项目宪法是否就绪**
- [ ] 是否有 P0 红线集合？
- [ ] 是否有强制 P1（语言、工作流、汇报格式）？
- [ ] 通用规范是否需要项目级覆盖？

**目录结构建议**

```
<project>/
├── .claude/
│   ├── constitution.md     ← 项目宪法（P0 红线）
│   ├── dev-standards.md    ← 项目规范
│   └── docs/               ← plan / evidence / handoff
├── docs/                   ← 给"读项目的人"看的稳定文档
│   ├── plan.md
│   ├── system-design.md
│   └── architecture.md
├── src/
└── tests/
```

接 distiller 的项目可省 `.claude/docs/`，跨会话工件全走 distiller。
