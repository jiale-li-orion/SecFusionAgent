# SecFusionAgent

[English](README.md) | 中文

[![CI](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml) [![Pages](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml)

**证据优先的 AI 安全情报系统**
**智能体驱动的 AI 安全情报融合与研判系统**

SecFusionAgent 面向 AI 安全漏洞、研究进展与安全事件构建持续演进的情报系统。系统从公开漏洞库、项目仓库、安全公告、研究论文和事件来源持续获取新增或变化的内容，把外部数据固定为可追溯的证据，再完成规范化、关联、富化、事件跟踪与后续调查。

这里的 Agent 建立在可验证的数据平面之上。外部读取带有采集溯源，重要结论能够回到原始观测与产物，历史版本保留、当前视图可重建；Agent 后续承担调查、tool call 与推理，不取代证据权威。

[架构视图](https://jiale-li-orion.github.io/SecFusionAgent/) · [项目 Wiki](https://github.com/jiale-li-orion/SecFusionAgent/wiki) · [Requirements-SPEC](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC) · [Technical-Design](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design) · Website：[jiale-li-orion.github.io/SecFusionAgent](https://jiale-li-orion.github.io/SecFusionAgent/)

## 项目状态

SecFusionAgent 当前处于 **M1–M3 数据平面首轮实现 / 集成探针** 阶段。第一轮实现覆盖多种来源生命周期、canonical knowledge、provider-backed 富化、Incident Watch、受管文档、当前投影，以及 Investigation Experience 的存储边界；PostgreSQL、Redis、MinIO 与 Celery 的真实基础设施集成仍在验证。

当前本地质量门：

```text
ruff        代码风格、import 与 Python 正确性检查
mypy        静态类型检查
pytest      领域、重放、状态迁移与契约测试
```

主仓库 CI 持续运行 `ruff`、`mypy` 与 `pytest`。快速测试主要使用 fixture 与轻量本地数据库验证确定性契约，不取代 PostgreSQL 事务、队列恢复、对象存储、并发与部署层的集成测试。

## 系统概览

公开文档站提供两张由 authoritative specification 生成的 Archify 交互视图：

- [Technical Design — Data Plane](https://jiale-li-orion.github.io/SecFusionAgent/tech-design.html) 展示 Acquisition、四种 `retention_mode` 生命周期、Evidence boundary、durable state 与异步 consumer。
- [Requirements — 模块数据流](https://jiale-li-orion.github.io/SecFusionAgent/requirements.html) 展示 M1–M8 产品模块、C1–C3 横切约束与验收语义。

系统把来源协议、运行时生命周期、canonical knowledge 与 derived 读模型分开维护：provider 适配器解释外部协议；采集运行时记录每次 scheduled / on-demand 读取；EvidenceIngress 固定原始版本；canonical knowledge 保存长期事实与溯源；投影、缓存与后续 retrieval 索引都属于可重建状态。

## 已实现的数据通路

| 通路 | 当前实现 | 用途 |
| --- | --- | --- |
| Hot Bug Stream | NVD CVE API → 规范化 → Redis 热工作集 → durable 晋升 | 保持高频漏洞 feed 的新鲜度，同时避免把全部历史漏洞复制进本地长期库 |
| Vulnerability Enrichment | OSV / GitHub Global Advisory / CISA KEV → child AcquisitionRun → EvidenceIngress → claims / relations | 为已晋升进 durable knowledge 的漏洞补充 package、修复、KEV 与公告信息 |
| Managed Content | arXiv Atom discovery → versioned PDF 产物 → 文档版本 → page-oriented 切块 | 建设可长期演进、可回到具体版本与页面的研究语料 |
| Structured Source Index | GitHub target repositories → repo revision 游标 → `Repo` 对象 / claims | 持续维护重点 AI 基础设施仓库的结构化状态 |
| Incident Watch | RSS breaking source → strong anchor 关联 → candidate watch → durable 事件时间线 | 把突发消息与后续独立证据组织成持续累积富化的安全事件 |
| Current Projection | knowledge / incident 变化 → 事务性 outbox → 投影重建 | 为 API 与后续 retrieval 提供低成本的当前视图，同时保留底层历史与冲突 |
| Investigation Memory | Case → append-only Trajectory → Experience candidate / version / evaluation | 为后续 Agent 调查保存可评测、可版本化的 procedural experience |

内置来源定义位于 [`config/sources/`](config/sources/)；来源是否进入热缓存、durable 语料、结构化索引或 incident staging，由 `SourceDefinition.retention_mode` 明确决定。

## 证据与知识模型

SecFusionAgent 把来源发布的内容与系统当前认为可用的知识分开存储。

`Observation`（观测）描述一次外部对象版本的获取；`EvidenceArtifact` 固定需要长期保留的原始内容产物；`EvidenceLink` 把对象、claim 或 relation 回连到观测/产物与 locator。长期知识用 `Object / ExternalIdentifier / Claim / Relation` 表达，并通过知识版本保存演进历史。

snapshot 型 provider 的新版本会取代**同一来源**此前的 current claim / relation；来自其他来源的差异继续并存，由当前投影暴露冲突与备选。修正因此不会覆盖历史，多源冲突也不会在 ingest 阶段被静默裁决。

富化产生的每次新的外部读取都会重新进入 `AcquisitionRun → IngestEnvelope → EvidenceIngress`；processor 不会把没有记录过的 HTTP response 直接写成知识。

## 事件情报

Incident Watch 使用独立的生命周期。breaking source 先进入短期的 `SignalItem / IncidentCandidate` 工作集，只有满足晋升条件的事件才进入 durable 事件存储。

多源确认按“**独立来源支持同一个可验证的 strong anchor**”计算。`upstream_source` 用于识别转载依赖，避免多家媒体重复同一条原始消息被误计为独立印证。当前 strong anchor 包括 CVE/GHSA、transaction hash、address、IOC、domain/IP、incident/advisory ID 与 commit 等可验证标识。

事件进入 durable 状态后保留 append-only 时间线与来源链接；后续官方说明、forensic 分析、资金流变化与影响范围更新继续追加，而不是反复覆盖一条静态新闻记录。

## 调查经验

调查过程建模为 `Case` 与 append-only `Trajectory`。Trajectory 记录 provider query、tool call、证据引用、所使用的 experience 版本、outcome、latency 与 cost，为后续 Agent Eval 与重放提供基础数据。

可复用的经验（experience）进入独立的版本化生命周期：

```text
Trajectory
    ↓ 抽取
ExperienceCandidate
    ↓ 评测 / 重放
validated
    ↓ 激活
active
    ↓ 被取代或失效
 deprecated
```

Experience 保存适用范围、触发条件、推荐动作、证据预期、失败模式、停止条件与 fallback。它属于 planning memory，不拥有安全证据权威；后续任务仍需重新取得当前证据后才能形成事实结论。

## 仓库结构

```text
SecFusionAgent/
├── apps/
│   ├── api/                 # FastAPI 应用与 HTTP 路由
│   └── worker/              # Celery 任务、调度器与 outbox 消费者
│
├── packages/
│   ├── sources/             # provider 契约、注册表与来源适配器
│   ├── monitoring/          # 采集生命周期与 retention-mode 采集器
│   ├── intelligence/        # 证据、canonical knowledge、incident 与投影
│   ├── enrichment/          # provider-backed 漏洞富化
│   ├── investigation/       # Case、Trajectory 与 Experience 生命周期
│   └── shared/              # 配置、数据库与通用 outbox 原语
│
├── config/
│   ├── sources/             # 声明式 SourceDefinition 注册表
│   └── env.example          # 运行时配置接口
│
├── alembic/                 # 前向数据库迁移历史
├── deploy/                  # 本地/运行时部署定义
├── scripts/                 # 工程与探针入口
├── tests/                   # 仓库级架构测试与 fixture
├── .github/                 # 仓库自动化
├── PRODUCT-REPO-STANDARD.md
├── PRODUCT-REPO-STANDARD.zh.md
└── AGENTS.md
```

package 归属与依赖方向属于仓库契约，而不是目录约定。`packages/sources` 不拥有调度器状态；`packages/monitoring/acquisition` 拥有 durable 采集生命周期；`packages/intelligence/knowledge` 拥有 canonical knowledge 契约与写入。[`tests/test_architecture_dependencies.py`](tests/test_architecture_dependencies.py) 自动检查这些依赖方向。

## 开发

### 前置条件

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/)
- 支持 Compose 的 Docker，用于本地 PostgreSQL / Redis / MinIO 栈

运行时没有云厂商依赖。容器镜像仓库 mirror、proxy 与凭据属于 host 级配置，被有意排除在仓库契约之外。

### 安装依赖

```bash
make sync
```

等价命令：

```bash
uv sync --dev
```

### 配置环境

[`config/env.example`](config/env.example) 定义受支持的配置面。导出所需的 `SECFUSION_*` 变量，或通过本地环境管理加载等价值。

默认开发拓扑使用相互隔离的 Redis 故障域：

- `redis-broker`：采用 `noeviction` policy 的 durable-ish 任务传输；
- `redis-cache`：Hot Bug 与 incident staging 使用的有界 LFU 工作集。

允许匿名访问的来源可以不配置 API key，但 provider rate limit 会明显降低。密钥一律不得提交进仓库。

### 启动本地基础设施

```bash
make dev-up
make migrate
make sync-sources
```

这会启动本地 PostgreSQL/pgvector、Redis Broker、Redis Hot Cache 与 MinIO 服务，应用 Alembic 迁移，然后把声明式来源定义同步进运行时状态。

停止本地栈：

```bash
make dev-down
```

### 运行 API

```bash
uv run uvicorn apps.api.main:app --reload
```

当前 HTTP 面包括：

```text
GET /health/live
GET /api/v1/vulnerabilities/{cve_id}
```

API 读取 canonical knowledge 与当前仓库状态，不会绕过 ingest 与证据通路直接查询 provider。

### 运行采集与后台 worker

启动调度器：

```bash
make scheduler
```

当前任务拓扑为 collection、enrichment 与 indexing/projection 工作使用相互独立的 Celery 队列。完整本地开发时，启动订阅这些队列的 worker：

```bash
uv run celery -A apps.worker.celery_app:celery_app worker \
  -l INFO \
  -Q collection,enrichment,indexing
```

`make worker` 目前只启动 collection 队列，用于隔离 M1 采集行为。

### 运行聚焦探针

把一小段 NVD 变更窗口采集进 Hot Bug 工作集：

```bash
make probe-nvd
```

把一条缓存 CVE 晋升为 durable 证据与 canonical knowledge：

```bash
make promote-hot CVE=CVE-YYYY-NNNN
```

探针用于回答有边界的集成问题。稳定的产品行为应落在 package、迁移与测试中，而不是在 scripts 里不断累积。

## 质量门

提交变更前运行完整本地质量门：

```bash
make check
```

针对聚焦变更迭代时可单独运行：

```bash
make lint
make typecheck
make test
```

`make check` 是开发期间使用的仓库级可复现质量门。涉及 persistence、队列、外部适配器或部署的变更，在对应基础设施可用后还需运行相关集成探针。

## 工程不变量

当前实现围绕若干不变量组织，这些不变量应在 code review 中保持可见：

1. 重要知识始终可追溯到证据。
2. durable 原始证据不可变；派生状态可重建。
3. 外部内容是不可信输入，包括后续会被 LLM 消费的内容。
4. 新的 provider 读取产生可观测的采集状态，而不是绕过 M1/M2。
5. 重放与 retry 依赖稳定的幂等键与版本化状态。
6. 同源修正保留历史；跨源分歧保持显式。
7. Agent trajectory 与可复用经验可观测、可版本化。
8. package 依赖遵循归属方向并保持无环。

这些决策的详细理由、失败场景与重新审视条件维护在项目 Wiki 中，而不重复写进源码注释或本 README。

## 文档

代码仓库与 Wiki 拥有不同的职责边界：

- **Repository** — 可执行源码、测试、迁移、部署定义、scripts、CI 与仓库治理。
- **Wiki** — requirements、Technical Design、数据源语义、安全领域专题、设计决策、探针、运行手册与项目演进。

建议从以下内容开始：

- [Requirements-SPEC](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC) — 产品范围、约束与验收语义。
- [Technical-Design](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design) — runtime 架构、存储语义、M1–M3 处理通路与实现基线。
- [01-Data-Sources-and-Processing](https://github.com/jiale-li-orion/SecFusionAgent/wiki/01-Data-Sources-and-Processing) — 来源分类、生命周期与数据语义。
- [02-CTI-Baseline-Reuse-and-Ownership](https://github.com/jiale-li-orion/SecFusionAgent/wiki/02-CTI-Baseline-Reuse-and-Ownership) — CTI 能力边界与复用策略。
- [03-Normative-Knowledge-and-Policy](https://github.com/jiale-li-orion/SecFusionAgent/wiki/03-Normative-Knowledge-and-Policy) — 标准、policy 与规范性知识。
- [04-AI-Model-Data-and-Agent-Application-Security](https://github.com/jiale-li-orion/SecFusionAgent/wiki/04-AI-Model-Data-and-Agent-Application-Security) — AI 特定风险语义。
- [05-Incident-News-Intelligence](https://github.com/jiale-li-orion/SecFusionAgent/wiki/05-Incident-News-Intelligence) — incident 来源角色、关联与事件生命周期。

仓库组织与贡献规则由 [`PRODUCT-REPO-STANDARD.md`](PRODUCT-REPO-STANDARD.md) 和 [`PRODUCT-REPO-STANDARD.zh.md`](PRODUCT-REPO-STANDARD.zh.md) 定义。涉及 Agent 的变更还需遵循 [`AGENTS.md`](AGENTS.md)。

GitHub Pages、Archify、双语展示与 CI/CD 发布规则见 [`WEB-PRESENTATION-STANDARD.zh.md`](WEB-PRESENTATION-STANDARD.zh.md)。

## 路线图

下一个工程边界是从首轮数据平面过渡到经过验证的 runtime 与 retrieval 基础设施：

- 完成 PostgreSQL / Redis / MinIO / Celery 集成探针与恢复测试；
- 把 GitHub 监控从 repository metadata 扩展到 issue / PR / commit / release 关系；
- 在第一条 RSS breaking-source 通路之外补充 primary 与 forensic 的 incident 来源；
- 把 Managed Content 扩展到 HTML 来源与语义抽取；
- 在 current/canonical knowledge 之上实现可重建的 sparse + dense retrieval 与 query construction；
- 把 Investigation Case / Trajectory 状态接入 Agent runtime；
- 为富化、retrieval、QA、Agent trajectory 与 Experience 激活建立固定的 M7 评测协议；
- 针对被投毒来源、indirect prompt injection、恶意 tool output 与权限边界补充安全回归。

Requirements-SPEC 仍是产品范围的权威；路线图排序依据依赖与集成风险，而不是 UI 完成度。
