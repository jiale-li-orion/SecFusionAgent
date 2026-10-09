# SecFusionAgent

[English](README.md) | 中文

[![CI](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml) [![Pages](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml)

<!-- BEGIN GENERATED SCOREBOARD -->
## 决赛硬指标

| 指标 | 当前正式结果 |
| --- | ---: |
| 来源类别覆盖 | **8/8**（目标 ≥7） |
| M1 监测时效 | **p50 357.709s (5.96min) / p95 7241.893s (2.01h) / ≤6h 100.000%（12/12）** |
| M3 富化 Precision / Recall | **99.659% / 99.659%（TP=292, FP=1, FN=1）** |
| Controlled fault recovery | **100.000%（3/3）** |
| M6 QA | **Accuracy 100.000% / interactive max 3.655s** |

**来源运行口径：101 个 catalog entries → 66 个 executable sources → 39 个 scheduled monitors；8 类产品覆盖，其中 7/8 类存在主动定时监测，`assets` 保持按需查询。**
**持续监测记账起点：`2026-10-02T04:19:42+08:00`；当前 scheduled source 健康状态 36 healthy / 1 degraded / 2 blocked；epoch 内 Evidence 物理完整性 100.000%。**
**最近 1h 运行面：Run OK 85.714%；Provider-boundary fail 14.286%；Runtime-owned fail 0.000%；Queue p95 102.077s (1.70min)；Execution p95 108.106s (1.80min)。**

上表全部数字由 benchmark/source config 自动导出，不手抄；详细 run/deployment/provenance 在下方正式评测区。
<!-- END GENERATED SCOREBOARD -->

**证据优先的 AI 安全情报系统**
**智能体驱动的 AI 安全情报融合与研判系统**

SecFusionAgent 面向 AI 安全漏洞、研究进展与安全事件构建持续演进的情报系统。系统从公开漏洞库、项目仓库、安全公告、研究论文和事件来源持续获取新增或变化的内容，把外部数据固定为可追溯的证据，再完成规范化、关联、富化、事件跟踪与后续调查。

这里的 Agent 建立在可验证的数据平面之上。外部读取带有采集溯源，重要结论能够回到原始观测与产物，历史版本保留、当前视图可重建；Agent 后续承担调查、tool call 与推理，不取代证据权威。

[架构视图](https://jiale-li-orion.github.io/SecFusionAgent/) · [项目 Wiki](https://github.com/jiale-li-orion/SecFusionAgent/wiki) · [Requirements-SPEC](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC) · [Technical Design 1](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-1) · [Technical Design 2](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-2) · Website：[jiale-li-orion.github.io/SecFusionAgent](https://jiale-li-orion.github.io/SecFusionAgent/)

<!-- BEGIN GENERATED EVALUATION STATUS -->
## 当前正式评测证据（自动生成）

本段由 `benchmarks/**/current*.json` 自动渲染。修改评测结果后运行 `make evidence-doc`；`make evidence-doc-check` 会在 Markdown 与结构化结果漂移时失败。

| 决赛目标 | 指标 | 当前值 | 阈值 | 状态 |
| --- | --- | ---: | ---: | --- |
| `source_category_coverage` | `m1.source_category_count` | 8 | >= 7 | **pass** |
| `enrichment_precision` | `m3.micro_precision` | 99.659% | >= 95.000% | **pass** |
| `enrichment_recall` | `m3.micro_recall` | 99.659% | >= 95.000% | **pass** |
| `qa_accuracy` | `m6.answer_accuracy` | 100.000% | >= 95.000% | **pass** |
| `qa_interactive_latency` | `m6.interactive_latency_seconds` | 3.655s | <= 5.000s | **pass** |

当前 CompetitionReport：`eb0a1c43-a786-434e-904a-fd976d751105`；Deployment：`deployment:2713f58f83915b2d0d0a9621ed4b7ac7`。

M1 固定窗口 `2026-10-01T10:00:00+00:00` → `2026-10-01T14:02:00+00:00`：12/12 个样本可评，p50 357.709s (5.96min)，p95 7241.893s (2.01h)，≤6h 100.000%；source category=8。

M3 当前选定 run 聚合：TP=292，FP=1，FN=1，precision=99.659%，recall=99.659%。工程故障恢复 `engineering-fault-recovery@6` 为 100.000%（3 cases）。

当前 CompetitionReport 未纳入的评测域：M2 parser/entity/evidence diagnostics、Agent runtime、Long Investigation completion、Security adversarial hard gates、Security adversarial breadth。这些域的独立 controlled/diagnostic evidence 不会被混入本报告的 6-run 正式口径。

全评测基础设施按当前 MetricDefinition 统计为 85/87 个核心指标已有 durable observation；15 个 metric groups observed / 2 个 partial。当前唯一未观测核心指标为 `runtime.capability_external_cost`、`runtime.model_provider_cost`；它们都是 provider/executor 未返回的精确货币成本，不从 token 或公开价目表推算。

复现入口：`make benchmark-query METRIC=m3.micro_precision` 直接回查 PostgreSQL 的 BenchmarkRun/MetricObservation；`make competition-render-doc` 重新渲染报告；`make evidence-doc` 更新全部证据投影；`make evidence-doc-check` 做无写入一致性检查。
<!-- END GENERATED EVALUATION STATUS -->

## 项目状态

SecFusionAgent 当前已经形成 **M1–M3 常态数据面 + 可执行的 Agent / QA / Evaluation 控制面**。scheduled acquisition、Evidence/Knowledge ingestion、enrichment、projection 与 indexing 可以长期运行并持续积累真实 corpus；其上已经落地 durable Task Runtime/TaskEvent、M4 Investigation State 与 Perception、有界 InvestigationRole episode、Context/Skill/Capability/Policy/Budget/Execution 控制面、WATCH wake/resume、M6 typed Decision/Product Question、多轮 Product session、Case-read/continuation、durable RetrievalInvocation provenance、M7 replay/regression/Experience→Skill promotion gate，以及 TD3 DeploymentRevision/BenchmarkSuite/Run/MetricObservation/CompetitionReport 证据链。

当前正式 same-deployment batch 已覆盖 M1、structured M3、CSAF/VEX、controlled recovery、Product QA 与 session QA，并发布一份 CompetitionReport；所选 case 的 runtime/Evidence provenance 也已经闭环。M2、M5 runtime、long-Investigation、retrieval、security 与 evaluation-infrastructure 由各自 controlled/diagnostic suite 持有，不会为了填满比赛报告而被静默混进这 6-run 正式口径。production external Capability binding、OpenShell/Firecracker substrate 验收与更宽的 live denominator 继续保持显式工程边界。historical replay 在旧 M1–M3 Knowledge world 无法精确读取时仍 fail closed，不会拿 latest projection 冒充历史世界。

仓库质量门：

```text
ruff        代码风格、import 与 Python 正确性检查
mypy        静态类型检查
pytest      领域、重放、状态迁移与契约测试
```

主仓库 CI 持续运行 `ruff`、`mypy` 与 `pytest`，PostgreSQL/Redis 与显式 S3 compatibility integration gate 保持独立执行。当前比赛指标不再手写进正文；上方 generated block 直接从 benchmark JSON 渲染，`make evidence-doc-check` 会检查 README 与结构化结果是否漂移。

## Product Web 与账户

`/product/` 提供相互联通的六个空间：WORLD 追踪实时来源材料和 Hot CVE；INTELLIGENCE 打开证据档案并按所选维度提交富化；INVESTIGATIONS 跟进持久 Case；AGENTS 呈现真实 Role/Task；OBSERVATORY 展示有测量时间的服务和 worker 状态；START 创建或恢复真实问答会话。产品界面不设置比赛演示、冻结证明或人为延时路径。视觉与联调契约见 [`apps/web/README.md`](apps/web/README.md)。

问答页可继续加载更早的账户会话和回合。调查完成后，页面展示由同一份已验证 Decision 生成、带证据引用的自然段落研究报告；结构化回答与结论仍用于审计和评测。

视觉标识现采用独立的“证据汇聚孔径”品牌符号、八类来源与实际来源徽记，以及三位 Agent 各自的 WebGL/SVG 雕塑。它们只表达视觉身份，旁边的运行状态仍由真实 Product read model 提供。

情报页的“漏洞”筛选现读取真实 Hot CVE 窗口，并分别显示载入条数和驻留总量。打开漏洞时保留 Hot 坐标，持久档案独立核验；不会再把近期原文精选窗口为空误呈现为系统没有漏洞。
WORLD 热区索引按页浏览驻留来源记录，完整 CVE 编号可跨当前页面检索整个驻留池，不再受首次载入窗口限制。

“事件”筛选读取独立的候选观察投影，展示经过保守安全事件筛选的来源标题和原文链接，并明确标记候选状态。宽泛新闻源现在先筛掉普通新闻再关联候选；Redis 工作集中较早的无关条目也会在产品读取时排除。候选不会被说成已获独立佐证或持久事件档案。

托管 HTML 文章解析现优先读取正文容器，避免把“相关文章”卡片误配给文章标题。真实 Product 中发现的微软安全博客标题/摘要错配，已通过新的按需 Observation 与解析器 v2 文档版本修复；历史原文仍保留用于审计。

情报自由文本检索在提交时按当前输入直接请求 API；快速输入后回车不会误用上一轮延迟建议，打开错误对象。

用户在 `/product/auth` 注册或登录。服务端会话使用 HttpOnly Cookie 中的随机令牌，数据库仅存令牌哈希；业务写操作校验 Origin 与 CSRF。提问、会话、Case、Decision、Task、推荐和反馈按账户隔离，共享 Evidence/Knowledge 保持可读。用户可保存关注范围、查看有证据的推荐和理由、反馈、发起调查，再次登录后继续原会话。邮箱验证、密码找回与 OAuth 尚未实现，属于独立账户生命周期工作。

上方正式评测数字只适用于记录的部署和样本，不代表当前版本整体准确率或覆盖率。[决赛标准复查](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Finals-Readiness-Review-2026-10-08)按赛题保留持续监测广度、开放维度富化、当前版本 QA 质量和运维验收的剩余边界。

[生产部署手册](deploy/PRODUCT-DEPLOY.md)规定私有 TLS 边界、重启策略、版本化应用镜像、数据库与证据文件备份，以及考虑数据库版本的回退步骤。本地开发环境与生产发布分别管理。

## 系统概览

公开文档站提供两张由 authoritative specification 生成的 Archify 交互视图：

- [Technical Design 1](https://jiale-li-orion.github.io/SecFusionAgent/tech-design.html) 展示 Acquisition、四种 `retention_mode` 生命周期、Evidence boundary、durable state 与异步 consumer。
- [Technical Design 2](https://jiale-li-orion.github.io/SecFusionAgent/diagrams/tech-design-lower.zh.html) 展示任务路由、Perception、Investigation State、有界执行与 Decision 流程。
- [Requirements](https://jiale-li-orion.github.io/SecFusionAgent/requirements.html) 展示 M1–M8 产品模块、C1–C3 横切约束与验收语义。

系统把来源协议、运行时生命周期、canonical knowledge 与 derived 读模型分开维护：provider 适配器解释外部协议；采集运行时记录每次 scheduled / on-demand 读取；EvidenceIngress 固定原始版本；canonical knowledge 保存长期事实与溯源；投影、缓存与后续 retrieval 索引都属于可重建状态。

Product QA 和 Case 决策的模型调用现已在每次 attempt 前预留 token 与重试额度，有 provider 精确用量时按实结算；缺失用量则按配置上界保守结算，审计记录仍明确标记为未知。`SECFUSION_MODEL_TOKEN_RESERVATION_PER_ATTEMPT` 可调整预留上界；货币成本和 M3/M5 的 token 结算尚未接入。

## 已实现的数据通路

| 通路 | 当前实现 | 用途 |
| --- | --- | --- |
| Hot Bug Stream | NVD + CVE Program/cvelistV5 → provider 投影 → Redis 热工作集 → durable canonical 晋升 | 保持高频漏洞 feed 的新鲜度，同时避免把全部历史漏洞复制进本地长期库 |
| Vulnerability Enrichment | OSV / GitHub Global Advisory / CISA KEV → child AcquisitionRun → EvidenceIngress → claims / relations | 为已晋升进 durable knowledge 的漏洞补充 package、修复、KEV 与公告信息 |
| Managed Content | PDF / plain text / HTML / XHTML durable 文档版本/切块 → lexical FTS + provider-neutral dense embedding → evidence-gated semantic extraction | 建设 retrieval-ready 研究语料，并让语义 claim 继续回到具体来源版本与原文片段 |
| Structured Source Index | GitHub target repositories + advisory 显式引用 → Repo / Issue / PullRequest / Commit / Release 对象与确定性关系 | 维护重点 AI 基础设施状态与 development graph，同时避免用语义相似度猜 fix relation |
| Incident Watch | RSS / BlockBeats HTML breaking signal → deterministic anchor extraction → candidate 关联 → durable 事件时间线 | 把突发消息与后续独立证据组织成事件，同时避免把转载当成 corroboration |
| Current Projection | knowledge / incident 变化 → 事务性 outbox → vulnerability / affected-version / fix-status / repo-security / incident 视图 | 为后续 retrieval 提供低成本当前状态，同时保留底层历史、证据与冲突 |
| Internet Asset Observation | on-demand Shodan / Censys / FOFA / ZoomEye → provider-normalized AssetObservation → 显式 EvidenceIngress promotion | 保留 query/provider/time provenance，同时避免把高时效资产结果默认变成长久知识 |
| Investigation Memory | Case → append-only Trajectory → Experience candidate / version / evaluation | 为后续 Agent 调查保存可评测、可版本化的 procedural experience |
| Task / Investigation Runtime | TaskContract → durable TaskRun/TaskEvent → versioned ContextManifest → bounded Role episode → wait/resume/replay | 给 Agent 工作明确的生命周期、委派、上下文与完成语义，避免退化为无界 chat loop |
| Canonical VERIFY | VerifyFixBoundary Skill + ModelInvestigationPlanner → Perception → Capability/Policy/Budget → Evidence promotion 或 delegated EnrichmentRole → StatePatch Gate | 让 fix boundary 验证通过 durable evidence 闭环，同时保持 model output 不拥有事实权威 |

内置来源定义位于 [`config/sources/`](config/sources/)；来源是否进入热缓存、durable 语料、结构化索引或 incident staging，由 `SourceDefinition.retention_mode` 明确决定。

Website 投影的具体来源承诺由 [`config/source-inventory.json`](config/source-inventory.json) 跟踪。[`config/sources/`](config/sources/) 下的全部 `SourceDefinition` 由 `make sync-sources` 幂等同步到真实 PostgreSQL registry；来源数量从配置与 runtime state 自动得到，不再手抄到 README。`make source-inventory-check` 检查中文 catalog identity 与中英文 catalog structural parity，`make verify-data-sources` 继续运行确定性的 source/runtime ownership tests；`make probe-live-sources` 只保留为手动连通性报告。Lifecycle tests 进一步要求每条来源都有可执行的数据流归属：`time_bounded` source 不进入 scheduler 且必须有 downstream consumer，Hot Bug adapter 必须同时拥有 hot/durable normalizer，Incident adapter 必须注册 signal extractor。

## 证据与知识模型

SecFusionAgent 把来源发布的内容与系统当前认为可用的知识分开存储。

`Observation`（观测）描述一次外部对象版本的获取；`EvidenceArtifact` 固定需要长期保留的原始内容产物；`EvidenceLink` 把对象、claim 或 relation 回连到观测/产物与 locator。长期知识用 `Object / ExternalIdentifier / Claim / Relation` 表达，并通过知识版本保存演进历史。

snapshot 型 provider 的新版本会取代**同一来源**此前的 current claim / relation；来自其他来源的差异继续并存，由当前投影暴露冲突与备选。修正因此不会覆盖历史，多源冲突也不会在 ingest 阶段被静默裁决。

富化产生的每次新的外部读取都会重新进入 `AcquisitionRun → IngestEnvelope → EvidenceIngress`；processor 不会把没有记录过的 HTTP response 直接写成知识。

Canonical enrichment vocabulary 与 provider 原始字段分开版本化。deterministic/source-asserted processor 只能写已注册的 canonical 或 source-specific term；semantic processor 的未注册发现保留为有证据的 `exploratory` 结果，在 vocabulary review 前不进入正式 enrichment P/R。`packages/evaluation/m1_m3.py` 已固定 八类产品数据源 taxonomy 与 coverage contract、monitoring latency sample 语义与 evidence-aware closed-set enrichment scorer，供后续 M7 benchmark 复用。

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
│   ├── application/         # Product use case 与稳定 application DTO
│   └── worker/              # Celery 任务、调度器与 outbox 消费者
│
├── packages/
│   ├── sources/             # provider 契约、注册表与来源适配器
│   ├── monitoring/          # 采集生命周期与 retention-mode 采集器
│   ├── intelligence/        # 证据、canonical knowledge、incident 与投影
│   ├── enrichment/          # provider-backed 漏洞富化
│   ├── task_runtime/        # Task/Context/Event/delegation 执行协议
│   ├── runtime/             # Capability/Policy/Budget/Execution/Sandbox 控制面
│   ├── investigation/       # M4 state、Perception、InvestigationRole、Skill/Experience
│   ├── reasoning/           # typed M6 Decision/QA contract 与校验
│   ├── evaluation/          # M1-M7/TD3 benchmark、replay 与证据契约
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

模块级 implementation design 跟随代码 owner 保存：

- [`packages/sources/README.md`](packages/sources/README.md)：source definition、adapter、taxonomy/retention mapping、扩展步骤；
- [`packages/monitoring/README.md`](packages/monitoring/README.md)：scheduler、AcquisitionRun、cursor、retry/recovery 语义；
- [`packages/intelligence/README.md`](packages/intelligence/README.md)：Evidence/Knowledge 持久化、document、incident、projection、artifact storage；
- [`packages/enrichment/README.md`](packages/enrichment/README.md)：deterministic/semantic M3 processing、provider query composition、processor 扩展约束；
- [`packages/task_runtime/README.md`](packages/task_runtime/README.md)：durable Task/Context/Event 协议、delegation 与 queued-role execution；
- [`packages/runtime/README.md`](packages/runtime/README.md)：Capability/Policy/Budget/Execution/Sandbox enforcement 与 runtime provenance；
- [`packages/investigation/README.md`](packages/investigation/README.md)：M4 state/Perception、有界 InvestigationRole、Skill/Experience 与 replay coordinate；
- [`packages/reasoning/README.md`](packages/reasoning/README.md)：typed M6 Decision/Continuation contract 与 evidence/citation validation；
- [`packages/evaluation/README.md`](packages/evaluation/README.md)：M1–M7/TD3 denominator、frozen world、runtime metric、replay 与 report provenance；
- [`packages/shared/README.md`](packages/shared/README.md)：共享基础设施、配置、outbox、model protocol；
- [`apps/web/README.md`](apps/web/README.md)：六空间 Product Web、账户入口、视觉归属与本地 API 联调；
- [`apps/application/README.md`](apps/application/README.md)：Product use-case composition 与稳定 application boundary；
- [`apps/api/README.md`](apps/api/README.md)：HTTP bootstrap 与 transport boundary；
- [`apps/worker/README.md`](apps/worker/README.md)：后台进程、outbox topic 与 Celery task composition。

这些 README 承接 Technical Design 1/2/3 以下的实现级设计。package 内部实现变化更新 owner README；一旦变化触及跨模块 ownership、evidence authority、processing path、持久化语义、安全边界或 evaluation protocol，仍需在同一轮更新 Wiki Technical Design / Requirements。

## 开发

### 前置条件

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/)
- 支持 Compose 的 Docker，用于本地 PostgreSQL / Redis runtime 与可选 S3-compatible integration profile

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

`make dev-up-core` 与 `make dev-up` 启动 PostgreSQL/pgvector 与 Redis failure domains。默认 ArtifactStore 改为宿主机 `.local/secfusion-artifacts` 下的 content-addressed filesystem；LocalStack 只在显式 S3 integration 路径启动。

无人值守运行使用 `make data-plane-up`。它完成依赖、迁移、source/Skill 同步，再启动 acquisition scheduler、Task Event dispatcher/scheduler、独立 collection worker 与通用 enrichment/investigation/indexing worker。PostgreSQL 与 durable Redis 使用 named volume，Evidence/runtime artifact 落在宿主机 content-addressed filesystem，hot cache 仍按设计可重建。关闭终端不会停止采集或 queued Role 分发，Docker daemon 恢复后这些服务按 `restart: unless-stopped` 回来。`make data-plane-status` 同时检查 M1–M3 数据面与 TD2 Task Event 控制面，`make data-plane-metrics` 导出 1h/6h/24h/7d 运行指标与小时曲线，`make data-plane-logs` 查看最近日志。正式 QA batch 仍只在冻结 Knowledge head 时短暂停三个 writer，并通过 `finally` 恢复它们。

模型评测使用 OpenAI-compatible 配置。正式跑分前先探测 endpoint：

```bash
export SECFUSION_MODEL_BASE_URL='https://provider.example/v1'
export SECFUSION_MODEL_API_KEY='...'
make model-provider-probe
make qa-live
```

若 `/models` 只暴露一个可用 chat model，probe 会自动解析；多模型 endpoint 必须显式设置 `SECFUSION_MODEL_NAME`，避免正式分数依赖随机模型选择。`make qa-live-preflight` 不调用模型，只把 reviewed QA gold 临时 rebase 到当前 Knowledge head 并重新校验证据；`make qa-live` 则冻结一个 clean DeploymentRevision，在同一 deployment 下完成 Product QA、session QA、M1、M3 structured/CSAF 与 fault-recovery，并自动重建 CompetitionReport 和 README 证据投影。endpoint identity、timeout 与 retry policy 进入 DeploymentRevision，API key 不进入。

停止本地栈：

```bash
make dev-down
```

### 运行 API

```bash
uv run uvicorn apps.api.main:app --reload
```

当前主要 Product 路由包括：

```text
GET  /health/live, /health/ready
POST /api/v1/auth/register, /api/v1/auth/login, /api/v1/auth/logout
GET  /api/v1/auth/me
GET  /api/v1/world/overview, /api/v1/world/stories, /api/v1/world/hot, /api/v1/world/hot/search
GET  /api/v1/intelligence/objects/{object_id}, /api/v1/intelligence/recommendations
PUT  /api/v1/intelligence/preferences
POST /api/v1/intelligence/objects/{object_id}/enrichment/runs
POST /api/v1/questions
GET  /api/v1/questions/sessions, /api/v1/decisions/{decision_id}
GET  /api/v1/investigations, /api/v1/observatory/system
```

Product Web 可运行 `cd apps/web && npm ci && npm run dev`；Vite 将 `/api` 代理到本机 API。API 使用其他端口时设置 `SECFUSION_API_PROXY`。

API 读取 canonical knowledge 与当前仓库状态，不会绕过 ingest 与证据通路直接查询 provider。

### 运行采集与后台 worker

启动调度器：

```bash
make scheduler
```

当前任务拓扑为 collection、enrichment、investigation 与 indexing/projection 工作使用相互独立的 Celery 队列。完整本地开发时，以 Make target 作为队列订阅的统一入口：

```bash
make worker
```

`make worker` 启动当前仓库使用的 collection、enrichment、investigation 与 indexing/projection 队列；隔离 M1 采集行为时使用 `make worker-collection`。

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

迭代代码时运行 fast gate：

```bash
make check
```

改变 M3 handoff 边界前运行完整阶段 gate：

```bash
make verify-m3
```

也可以单独运行：

```bash
make integration-core
make integration-object-store
make source-inventory-check
make verify-data-sources
make probe-live-sources
```

`make probe-live-sources` 只生成手动时点连通性报告，不属于 `verify-m3` 或 `verify-data-sources`；反爬、地区网络、限流和凭据问题在后续 provider hardening 中处理。

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
- [Technical Design 1](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-1) — M1–M3 runtime 架构、存储语义、处理通路与实现基线。
- [Technical Design 2](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-2) — M4–M6 任务路由、Perception、Investigation State、有界执行与 Decision 契约。
- [01-Data-Sources-and-Processing](https://github.com/jiale-li-orion/SecFusionAgent/wiki/01-Data-Sources-and-Processing) — 来源分类、生命周期与数据语义。
- [02-CTI-Baseline-Reuse-and-Ownership](https://github.com/jiale-li-orion/SecFusionAgent/wiki/02-CTI-Baseline-Reuse-and-Ownership) — CTI 能力边界与复用策略。
- [03-Normative-Knowledge-and-Policy](https://github.com/jiale-li-orion/SecFusionAgent/wiki/03-Normative-Knowledge-and-Policy) — 标准、policy 与规范性知识。
- [04-AI-Model-Data-and-Agent-Application-Security](https://github.com/jiale-li-orion/SecFusionAgent/wiki/04-AI-Model-Data-and-Agent-Application-Security) — AI 特定风险语义。
- [05-Incident-News-Intelligence](https://github.com/jiale-li-orion/SecFusionAgent/wiki/05-Incident-News-Intelligence) — incident 来源角色、关联与事件生命周期。

仓库组织与贡献规则由 [`PRODUCT-REPO-STANDARD.md`](PRODUCT-REPO-STANDARD.md) 和 [`PRODUCT-REPO-STANDARD.zh.md`](PRODUCT-REPO-STANDARD.zh.md) 定义。涉及 Agent 的变更还需遵循 [`AGENTS.md`](AGENTS.md)。

GitHub Pages、Archify、双语展示与 CI/CD 发布规则见 [`WEB-PRESENTATION-STANDARD.zh.md`](WEB-PRESENTATION-STANDARD.zh.md)。

## 路线图

下一个工程边界从 canonical VERIFY 闭环之后继续推进：

- 完成 Sandbox v1 的真实 substrate 验收，覆盖 filesystem/network/credential isolation、OpenShell container 与 Firecracker microVM；
- 跑 TD2 `reference vs summary` Context 对照，测 token cost、critical-context retention 与 stale-context failure rate；
- 增加 M1–M3 versioned historical read path，并把 M7 replay executor 接到真实 Agent re-execution，而不是在历史 world 不可用时读取 latest projection；
- 在冻结 deployment 配置下跑一次真实 semantic+dense provider E2E，并在合适 target-repo OSV `GIT fixed` 样本上验证 deterministic fix-boundary promotion；
- 继续显式维护 provider blocker，并在现有 frozen v1 production-boundary security suite 之上增加更强攻击变体与 model red-team case。

Requirements-SPEC 仍是产品范围的权威；路线图排序依据依赖与集成风险，而不是 UI 完成度。
