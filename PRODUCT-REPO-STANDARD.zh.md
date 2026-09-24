# SecFusionAgent Product Repository Standard

[English](PRODUCT-REPO-STANDARD.md) | 中文

本规范定义 SecFusionAgent 主代码仓库的目录职责、代码 ownership、依赖方向、测试与 benchmark、配置、运行产物、CI/CD、版本演进和 Agent 开发规则。Technical Design 决定具体框架、数据库、Agent runtime 和部署平台；本规范约束这些实现落进仓库后的组织方式。

## 文档与代码的 authority

Wiki 持有 PRD、Technical Design、风险专题、调研、方案比较、设计决策、运行手册、incident/postmortem 和项目演进。主 repo 持有源码、测试、benchmark、部署定义、工程脚本、CI 配置和仓库治理文件。一个事实进入哪个仓库，由谁负责维护也随之确定。

根 `README.md` 是代码仓库入口，包含项目身份、Wiki 链接、开发入口和稳定命令。`PRODUCT-REPO-STANDARD.md` / `.zh.md` 定义仓库规则。`AGENTS.md` 承载对 Agent 每次工作都有效的 standing orders。代码注释与类型声明承载紧贴实现的局部 contract，例如参数语义、异常、状态不变量和安全前置条件。

架构、接口语义、评测协议或运行方式发生变化时，代码和 Wiki 在同一轮 change 中更新。Wiki 页面记录适用的 release、tag 或 commit；checkout 历史版本时据此找到对应设计。

## Repository layout

顶层目录按长期责任划分：

```text
SecFusionAgent/
├── apps/                    # 可启动、可部署的产品入口
│   ├── api/
│   ├── web/
│   └── worker/              # 出现独立后台进程后建立
│
├── packages/                # 产品能力 owner
│   ├── intelligence/        # 安全情报领域语义
│   ├── sources/             # 外部情报源 adapter
│   ├── monitoring/          # 持续采集、增量更新、source health
│   ├── enrichment/          # 富化、关联、版本/PoC/patch 处理
│   ├── investigation/       # Agent investigation 与任务生命周期
│   ├── evaluation/          # eval runner、verifier、metrics
│   ├── security_testing/    # adversarial / security regression
│   └── shared/              # 与业务域无关的共享基础能力
│
├── tests/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│
├── benchmarks/
│   ├── monitoring/
│   ├── enrichment/
│   ├── qa/
│   ├── agent/
│   └── security/
│
├── deploy/
├── scripts/
├── .github/
├── README.md
├── PRODUCT-REPO-STANDARD.md
└── PRODUCT-REPO-STANDARD.zh.md
```

目录随真实责任出现。Technical Design 可以调整名称和语言生态相关的组织方式；`apps`、capability owner、tests、benchmarks、deploy 和 engineering tooling 继续保持独立责任。

`apps/` 拥有进程启动、transport 和 application bootstrap。HTTP route、CLI entry、Web application、worker bootstrap 放在这里。安全情报关联、Agent 调查、评测计算等可复用行为进入对应 capability package。

`packages/` 按 domain / capability 划分。一个行为先确定 owner，再进入该 package。监测的增量语义和 source health 归 `monitoring`；外部来源协议和解析归 `sources`；跨来源富化与关联归 `enrichment`；Agent 调查状态与 orchestration 归 `investigation`。

package 内部出现多个独立变化原因后，再拆 `domain`、`application`、`adapters`、`storage` 等子层。目录结构反映真实边界，文件数量和行数不作为拆分标准。

## Ownership 与依赖

每个稳定行为有一个 owner。其他模块通过 owner 暴露的 public contract 使用该行为。跨 package 依赖形成有向无环图；循环依赖通常说明 ownership、接口位置或状态归属需要重新划分。

接口定义归拥有语义的一侧。provider 实现接口，consumer 调用接口；provider-specific 类型、SDK object 和异常停留在 adapter 边界。替换 provider 时，domain contract 保持稳定。

`shared/` 容纳与安全情报业务无关、被多个稳定 consumer 使用的底层能力，例如通用时间处理、序列化 primitive、受控 retry 基础设施。CVE 版本范围解析、PoC 与目标版本匹配、漏洞严重性判断等行为归对应 domain。

`utils`、`helpers`、`common` 这类名称出现时需要明确具体责任。一个文件持续吸收无关行为时，重新确定 owner 并拆分。

## 外部系统与 adapter

漏洞数据库、厂商公告、安全社区、GitHub、论文源、模型 provider、数据库、消息系统、文件系统、浏览器和第三方 API 都属于外部边界。adapter 把外部格式转换成内部 contract，并负责该边界特有的认证、分页、rate limit、cursor、重试、时间字段和解析规则。

source adapter 负责可靠取得和解释来源数据。跨来源 dedup、entity resolution、富化和安全研判进入相应 capability。来源协议变化时，改动收敛在 adapter 及其 contract tests。

第三方异常在边界转换成项目内部的明确 failure。业务逻辑消费稳定错误类型和状态，运行日志保留定位外部问题所需的 provider context。

## State、data 与 migration

Git 保存源码、schema、migration、fixture、benchmark case、gold/reference 和承担 contract 的 snapshot。运行数据库、抓取缓存、真实用户数据、本地日志、临时下载、大模型批量输出和一次性分析结果进入 runtime artifact 或外部存储。

schema 与持久化格式随 release 向前演进。已发布 migration 保持原内容；后续修正通过新 migration 表达。数据库升级路径能够从 migration history 重建，不兼容变更在 release 前给出升级或恢复路径。

fixture 保持小、稳定、来源明确。真实网页或 API response 进入 fixture 时裁剪到测试依赖的字段，并保留足够 provenance 解释样本。安全测试 payload 标记用途和执行边界。

## Tests 与 benchmarks

测试验证 deterministic contract，benchmark 衡量 AI / system quality。两类资产分别维护 failure、版本和运行成本。

unit test 与 capability owner 同目录，覆盖局部规则、状态迁移、边界条件和 failure path。`tests/integration/` 覆盖 package 边界、持久化、队列和外部 adapter 的组合行为。`tests/e2e/` 从真实产品入口验证完整用户路径。bug fix 同时增加能够稳定复现该 failure 的 regression case。

`benchmarks/` 保存固定任务、gold/reference、verifier、runner 配置和冻结输入。case 与 gold 都有版本；gold 发生语义变化时产生新版本并记录原因。普通运行结果进入 artifact；release baseline、比赛提交基线和承担长期 regression contract 的结果可以版本化保存。

监测、富化、QA、Agent 和 security benchmark 分开维护，因为它们使用不同样本、verifier 和 failure model。聚合指标从原始指标计算，原始结果继续保留。

Agent Eval 记录 task success、tool selection、arguments、trajectory、recovery、timeout、latency 和 cost。Security benchmark 覆盖 direct/indirect prompt injection、poisoned source、malicious tool output、hallucinated evidence、tool misuse、privilege violation，以及 Web、backend、storage 等确定性组件的安全测试。

## Config、secret 与环境

部署环境会改变的值进入显式配置。配置项拥有稳定名称、类型、默认值和校验；缺失关键配置时启动阶段直接报告错误。

secret、token、cookie、私钥和真实账号通过 secret store、环境变量或本地未跟踪文件注入。`.env.example` 描述配置接口和示例格式。测试、benchmark、CI 与生产环境使用同一配置语义。

安全不变量和协议常量保留在代码 contract 中。test double 通过明确接口注入，使测试路径和生产路径共享同一业务行为。

## Scripts 与 generated artifacts

`scripts/` 编排已有能力：环境检查、代码生成、migration、fixture 构造、release helper、benchmark orchestration。业务规则归对应 package，脚本调用 package 暴露的稳定入口。

高频开发动作通过统一命令暴露。CI 调用同一命令，使本地复现和 CI 执行共享入口。workflow YAML 负责 orchestration，具体检查由仓库脚本或语言原生命令持有。

generated artifact 标明 source of truth 和生成命令。可重建的临时产物进入 ignore；发布 contract、baseline 或 snapshot 需要版本控制时，generator 与生成结果在同一 change 中更新。

## CI/CD 与 release

CI gate 按风险组织。普通 change 运行 formatter/linter、静态分析、类型检查、unit test 和相关 integration/security checks。影响 package contract、schema、Agent 行为、evaluation 或 deploy 的 change 运行对应 e2e 与 benchmark regression。耗时较高的全量矩阵可以进入 main、nightly 或 release gate。

每个 gate 有明确 owner 和稳定命令。规则发生变化时，gate、实现和对应 Wiki 说明一起更新。CI 失败保留原始失败信号，修复代码、测试、环境或规则本身。

release artifact 从版本控制中的 source 通过固定构建过程产生。tag、artifact、migration 和 benchmark baseline 能够互相对应。生产修复回到 source 并进入下一次 release，服务器状态与 repo 保持可追溯关系。

rollback 由可回退 artifact、配置和数据兼容性共同决定。不可逆 migration 在 release 前定义 forward-fix、备份恢复或数据迁移方案。

## Observability 与 failure

日志记录事件、状态、identifier 和错误上下文。一次采集、富化、Agent investigation 与最终回答共享稳定的 request/task/case identifier，支持跨进程追踪。secret 与敏感内容在写日志前处理。

metrics 描述长期系统状态，例如 source freshness、任务成功率、队列积压、provider latency、tool failure 和 benchmark regression。trace 描述一次请求穿过哪些组件。日志、metrics、trace 分别服务事件记录、聚合观察和调用路径分析。

failure 分成可恢复错误、任务终止错误和程序 bug。网络抖动、rate limit 等条件进入受控 retry；参数非法、权限不足等条件直接终止当前操作；违反内部 invariant 的状态立即暴露。retry 带次数、退避、超时和幂等语义。

## Git 与 change management

一个 commit 表达一个可独立解释的变化。重构、行为修改、benchmark 调整和大规模格式化分开提交，便于 review 和回归定位。bug fix 与对应 regression test 放在同一个 change 中。

PR 以行为或 capability 为单位。跨 package change 说明各 owner 为什么同时变化。一个 feature 长期触碰多个互不相关 package 时，重新检查 capability 边界。

主分支保持可构建、可测试和可部署。个人分支需要重写远端历史时使用 `--force-with-lease`，并先确认 remote state。多人共享分支通过 rebase、merge 或新的修复提交保留他人已发布历史。

## Naming 与 source rules

顶层 package 使用明确 domain 名称，例如 `monitoring`、`enrichment`、`investigation`。类、函数和文件名描述拥有的对象或动作。`manager`、`helper`、`common`、`misc`、`base` 这类宽泛名称进入 review 时需要说明具体责任。

语言内部采用对应生态的 canonical naming。跨语言模块保持 capability 名称可定位，文件命名服从各自语言工具链。

注释记录代码本身难以表达的 contract：状态不变量、时序、failure、兼容性、安全条件和外部约束。设计理由和演进历史进入 Wiki。TODO 写明缺失行为或触发条件，并使用统一优先级约定。

## Agent-assisted development

Agent 修改仓库前读取根规则、当前 capability 和相关 Wiki。完成 change 后运行覆盖该行为的最小检查集，并记录实际执行的命令和结果。

根 `AGENTS.md` 保存 repo-wide standing orders 和各规则 owner 的链接。capability 出现局部约束时，在对应 subtree 建立 scoped `AGENTS.md`。局部规则覆盖局部行为，根规则继续保持全局语义。

prompt、临时 plan、scratch、交接文本和模型输出属于工作产物。稳定设计结论进入 Wiki；长期执行的机械规则进入 CI gate、linter、schema verifier 或 scoped instruction。

大规模 Agent change 按可独立验证的行为拆分。domain 语义、schema、API、前端、benchmark 和 deploy 同时变化时，change 需要说明它们之间的产品依赖；独立变化拆成独立 review 单元。

## Repo evolution

package 的形成依赖独立状态、接口、测试和生命周期。几个局部 helper 留在现有 owner；形成稳定 capability 后再独立成 package。

仓库定期检查 `shared/utils` 膨胀、feature 跨大量 package 修改、循环依赖和 deep import。这些信号用于判断 ownership 是否偏离真实变化边界。

删除 capability 时同步清理入口、测试、benchmark、配置、CI gate 和 deploy 引用。兼容期由明确 compatibility layer 承担；Git 保存历史实现。

## Review baseline

工程 change review 使用同一组问题：

| 问题 | 通过条件 |
| --- | --- |
| 行为由谁负责？ | 能定位到一个 capability owner |
| 依赖方向是否稳定？ | package graph 无循环，consumer 依赖 public contract |
| 外部系统在哪里收口？ | provider/source/storage 细节停留在 adapter 边界 |
| failure 如何传播？ | 错误状态、retry、timeout 和 termination 可观察 |
| correctness 如何验证？ | 对应 unit / integration / e2e / regression 层有检查 |
| AI 质量如何比较？ | 行为受模型或 Agent 影响时有固定 benchmark |
| 数据如何演进？ | schema、migration、fixture 和升级路径可重建 |
| secret 如何保护？ | source、日志、fixture、artifact 没有真实敏感值 |
| CI 能否本地复现？ | gate 调用仓库中的稳定命令 |
| 文档由谁维护？ | 产品事实进入 Wiki，仓库治理进入主 repo |
| release 能否重建？ | source、build、artifact、migration、baseline 可以对应 |

新增规则需要对应真实 failure、明确 contract 或可预见的高成本风险。目录风格本身不构成规则来源。
