# SecFusionAgent

[English](README.md) | 中文

[![CI](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml) [![Pages](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml)

**智能体驱动的 AI 安全情报融合与研判系统。** 持续采集漏洞、研究、代码、公告与安全事件，保留可追溯证据，提供情报阅读、事件时间线、资料检索和带引用的问答调查。

当前 `main` 已包含 M1–M3 数据平面、M4–M6 调查与研判、任务执行控制、评测基础设施及账户化 Product Web。本文描述当前可运行产品；逐项验收与剩余缺口见 [当前验收台账](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Current-Acceptance)。

## 产品入口

| 空间 | 当前行为 |
| --- | --- |
| World | 八类来源入口、来源健康、材料显影与热点索引；热点包括重点事件、工具和分页 CVE，驻留缓存与持久证据分开标识 |
| Intelligence | 公开研报摘要、推荐与关注、事件时间线、可按类别/来源/多标签主题筛选的资料库；原文、引用和技术坐标可展开 |
| Ask | 自然语言问题、多轮会话、带引用研判；需要补证时进入调查，逐回合保留报告与证据/模型/任务审计 |
| Workspace | 账户、兴趣、会话与调查；Operations 提供任务执行和服务健康详情 |

Web 路径为 `/product/`。共享资料与公开研报可以匿名阅读；私人会话、调查、研报和任务由服务端校验账户归属。公开 HTML 研报必须有显式发布记录，私人调查不会自动公开。

界面采用本地字体、开放阅读布局与按页面内容变化的颗粒显影/扩散动效；支持减少动态效果、离屏暂停、键盘操作与移动端。事件库沿时间线展开，资料库主题是检索分类，不冒充模型完成的语义聚类。Hot 入口集中在 World。

## 当前运行方式

本地 Compose 与示例配置默认关闭非必要后台模型调用：

```dotenv
SECFUSION_BACKGROUND_LLM_ENABLED=false
SECFUSION_EDITORIAL_ENABLED=false
```

| 继续运行 | 暂停的自动任务 |
| --- | --- |
| 来源采集、原文与证据入库、词法索引、确定性富化、当前投影 | 文档 embedding、语义/规范模型提取、自动编研、新 WATCH 唤醒 |
| 用户发起的问答、调查、手工研报生成 | 无人交互触发的上述模型处理 |
| 已有公开/私人 HTML 研报读取（确定性渲染） | 不影响已有内容浏览 |

独立启动进程时应显式加载这两个配置；基础 `Settings` 保留后台模型开启的兼容默认值。修改后重建/重启 scheduler、worker 与 Task Event scheduler；已经执行中的模型请求可能结束后才停止。恢复开关不会自动补跑已跳过的历史任务。没有新增每日金额硬上限；用户交互仍会消耗 token。操作细节见 [worker README](apps/worker/README.md)。

## 数据与报告链路

```text
注册来源 → AcquisitionRun → 原始 Observation / Artifact
         → Evidence / Knowledge / DocumentRevision
         → 词法索引、结构化富化、事件与当前投影
         → 情报阅读 / 受控调查 / 带引用研判
         → 独立摘要、审校、受控 HTML 渲染
```

- 外部内容是数据；模型输出必须经过引用和状态校验才能成为研判。
- 原文与版本保留；同源纠错不覆盖历史，多源分歧不会静默合并。
- 资料质量门排除错误页、投递模板与无正文材料；维护工具可从留存证据重解析。
- 调查具备本地感知、官方 NVD、已注册公开网页与指定 GitHub 仓库开发记录读取；每次外部读取经过权限、预算、采集与证据提升。
- 研报先生成有引用的独立摘要，再生成正文和分析，经审校后由固定 schema 渲染 HTML。阅读不调用模型，模型不能注入脚本或扩大访问权限。
- Task Runtime 保留幂等、取消、事件/SSE、委派、恢复和预算轨迹；完整旧世界重执行仍有验收缺口。

## 本地开发

需要 Python 3.12、uv、Node.js 22、Docker Compose。凭据通过环境或本地未跟踪配置注入，不进入 Git。

```bash
uv sync --dev --frozen
# 按 config/env.example 设置本地环境；下面启动数据库和独立 Redis。
make dev-up
make migrate
make sync-sources
uv run uvicorn apps.api.main:app --reload
```

另一终端启动前端：

```bash
cd apps/web
npm ci
npm run dev
```

Vite 代理 `/api` 到本地 API；使用其他端口时设置 `SECFUSION_API_PROXY`。持续运行整个采集/任务栈使用 `make data-plane-up`，通过 `make data-plane-status`、`make data-plane-logs` 检查；数据与 artifacts 保存在卷和 `.local/secfusion-artifacts`，不随终端关闭丢失。`make data-plane-down` 停止运行进程，`make dev-down` 停止本地服务。生产发布契约见 [部署说明](deploy/PRODUCT-DEPLOY.md)。

## 检查与验收

```bash
make check
cd apps/web && npm run lint && npm run build
# 回到仓库根目录：
python scripts/check_product_gate.py --static-only
python scripts/check_product_deploy.py
make evidence-doc-check
```

PostgreSQL/Redis 与 S3 兼容集成分别使用 `make integration-core`、`make integration-object-store`。`make source-inventory-check` 校验来源清单；联网探测和收费模型评测是独立操作，不属于上述离线检查。

2026-10-16 的代码基线 `6654199` 已通过 890 项非集成测试（12 项集成测试未运行）、Ruff、mypy、前端构建和发布门，远端 CI 已通过。该结果不等于当天重新完成模型质量评测、生产容灾或全部来源可用性验收。

## 模块维护入口

| 模块 | 维护内容 |
| --- | --- |
| [apps/web](apps/web/README.md) | Product Web、组件与动效 |
| [apps/api](apps/api/README.md) | HTTP、账户、SSE 与访问控制 |
| [apps/application](apps/application/README.md) | 问答、调查、情报与研报用例 |
| [apps/worker](apps/worker/README.md) | 采集与任务进程、后台模型开关 |
| [packages/sources](packages/sources/README.md) | 来源配置与适配器 |
| [packages/monitoring](packages/monitoring/README.md) | 采集调度、重试与游标 |
| [packages/intelligence](packages/intelligence/README.md) | 证据、知识、资料、事件与投影 |
| [packages/enrichment](packages/enrichment/README.md) | 结构化、语义和规范富化 |
| [packages/task_runtime](packages/task_runtime/README.md) | 任务、上下文、事件和委派 |
| [packages/runtime](packages/runtime/README.md) | 权限、预算、执行与模型记账 |
| [packages/investigation](packages/investigation/README.md) | 调查状态、感知、技能与回放 |
| [packages/reasoning](packages/reasoning/README.md) | 带引用研判、摘要、审校与 HTML |
| [packages/evaluation](packages/evaluation/README.md) | 冻结样本、评测与证据闭包 |
| [packages/shared](packages/shared/README.md) | 配置、数据库与基础协议 |

## 留存评测与来源配置

`current.json` 表示最近一次已保存的结果，并非实时健康或当前 HEAD 的新评测。以下数字保留原 deployment、样本和时间窗口；代码更新不会改写这些历史结果。

<!-- BEGIN GENERATED SCOREBOARD -->
## 留存评测摘要与当前来源配置

| 指标 | 留存正式结果 |
| --- | ---: |
| 来源类别覆盖 | **8/8**（目标 ≥7） |
| M1 监测时效 | **p50 357.709s (5.96min) / p95 7241.893s (2.01h) / ≤6h 100.000%（12/12）** |
| M3 富化 Precision / Recall | **99.659% / 99.659%（TP=292, FP=1, FN=1）** |
| Controlled fault recovery | **100.000%（3/3）** |
| M6 QA | **Accuracy 100.000% / interactive max 3.655s** |

**当前来源配置（非在线健康）：106 个 catalog entries → 71 个 executable sources → 43 个 scheduled monitors；8 类产品覆盖，其中 7/8 类存在主动定时监测，`assets` 保持按需查询。**
**留存运行快照：`2026-10-08T19:18:08.614492+00:00`；监测记账起点：`2026-10-02T04:19:42+08:00`；该快照 scheduled source 健康状态 36 healthy / 1 degraded / 2 blocked；epoch 内 Evidence 物理完整性 100.000%。**
**快照结束前 1h 运行面：Run OK 85.714%；Provider-boundary fail 14.286%；Runtime-owned fail 0.000%；Queue p95 102.077s (1.70min)；Execution p95 108.106s (1.80min)。**

上表全部数字由 benchmark/source config 自动导出，不手抄；详细 run/deployment/provenance 在下方正式评测区。
<!-- END GENERATED SCOREBOARD -->

<details>
<summary>评测来源与复现</summary>

<!-- BEGIN GENERATED EVALUATION STATUS -->
## 留存正式评测证据（自动生成）

本段由 `benchmarks/**/current*.json` 自动渲染。修改评测结果后运行 `make evidence-doc`；`make evidence-doc-check` 会在 Markdown 与结构化结果漂移时失败。

| 留存数值目标 | 指标 | 留存值 | 阈值 | 状态 |
| --- | --- | ---: | ---: | --- |
| `source_category_coverage` | `m1.source_category_count` | 8 | >= 7 | **pass** |
| `enrichment_precision` | `m3.micro_precision` | 99.659% | >= 95.000% | **pass** |
| `enrichment_recall` | `m3.micro_recall` | 99.659% | >= 95.000% | **pass** |
| `qa_accuracy` | `m6.answer_accuracy` | 100.000% | >= 95.000% | **pass** |
| `qa_interactive_latency` | `m6.interactive_latency_seconds` | 3.655s | <= 5.000s | **pass** |

留存 CompetitionReport：`eb0a1c43-a786-434e-904a-fd976d751105`；Deployment：`deployment:2713f58f83915b2d0d0a9621ed4b7ac7`；生成于 `2026-10-08T15:37:32.851706Z`，不是当前 HEAD 的重测结果。

M1 固定窗口 `2026-10-01T10:00:00+00:00` → `2026-10-01T14:02:00+00:00`：12/12 个样本可评，p50 357.709s (5.96min)，p95 7241.893s (2.01h)，≤6h 100.000%；source category=8。

M3 当前选定 run 聚合：TP=292，FP=1，FN=1，precision=99.659%，recall=99.659%。工程故障恢复 `engineering-fault-recovery@6` 为 100.000%（3 cases）。

当前 CompetitionReport 未纳入的评测域：M2 parser/entity/evidence diagnostics、Agent runtime、Long Investigation completion、Security adversarial hard gates、Security adversarial breadth。这些域的独立 controlled/diagnostic evidence 不会被混入本报告的 6-run 正式口径。

全评测基础设施按当前 MetricDefinition 统计为 85/87 个核心指标已有 durable observation；15 个 metric groups observed / 2 个 partial。当前唯一未观测核心指标为 `runtime.capability_external_cost`、`runtime.model_provider_cost`；它们都是 provider/executor 未返回的精确货币成本，不从 token 或公开价目表推算。

复现入口：`make benchmark-query METRIC=m3.micro_precision` 直接回查 PostgreSQL 的 BenchmarkRun/MetricObservation；`make competition-render-doc` 重新渲染报告；`make evidence-doc` 更新全部证据投影；`make evidence-doc-check` 做无写入一致性检查。
<!-- END GENERATED EVALUATION STATUS -->

</details>

## 待验收边界

完整历史 Knowledge reader 与 Agent 重执行、真实 OpenShell/Firecracker 隔离验收、完整 A2A 写入/订阅传输、M3 模型预算结算、生产备份恢复与告警、广泛困难问题和外部能力的在线效果分母仍未关闭。账户邮件验证、找回密码和 OAuth 尚未实现；通用手工 resume 与语义非精确检索复用也未交付。

具体证据、关闭条件和优先级统一维护在 [当前验收台账](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Current-Acceptance)，不再在多个 README 复制过期 TODO。

## 设计与协作

[Wiki 首页](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Home) · [PRD](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC) · [TD1 数据平面](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-1) · [TD2 调查运行时](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-2) · [TD2A 产品接口](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-2A) · [TD3 评测](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-3) · [公开文档站](https://jiale-li-orion.github.io/SecFusionAgent/)

仓库保存代码、测试、迁移、配置、模块说明和可复现命令；Wiki 保存需求、跨模块设计、验收与历史复查。遵循 [仓库规范](PRODUCT-REPO-STANDARD.zh.md) 和 [AGENTS](AGENTS.md)。密钥、运行数据库、下载语料和模型输出不进入 Git。

本地初赛交付件（技术报告、PPT、源码提交包）集中存放在相邻 `../SecFusionAgent.wiki/交付成果/`，演示视频母版及编辑工程在本仓库 `.local/video-production/`；两个目录均已排除在公开 Git 之外，不在主仓库与 Wiki 之间重复复制二进制资料。
