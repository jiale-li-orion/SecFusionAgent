# SecFusionAgent

**智能体驱动的 AI 安全情报融合与研判系统** —— 面向 AI 安全知识情报场景的智能体系统项目

当前代码阶段：M1–M3 Data Plane 的 Foundation / Hot Bug vertical slice。

项目需求、数据源语义与 Technical Design 维护在项目 Wiki；主仓库保存可执行源码、测试、benchmark、部署与工程规则。开始修改代码前阅读 [`PRODUCT-REPO-STANDARD.zh.md`](PRODUCT-REPO-STANDARD.zh.md) 和根 [`AGENTS.md`](AGENTS.md)。

## Development

环境：Python 3.12+、`uv`、Docker Compose。

```bash
make sync
make dev-up
make migrate
make sync-sources
make check
```

本地配置接口见 `config/env.example`，通过 `SECFUSION_*` 环境变量注入。Redis Broker 与 Redis Hot Cache 是不同故障域：Broker 禁止 eviction，Hot Cache 用于有界 working set。

第一条可运行 probe 使用 NVD CVE API 2.0 的最近修改窗口，将漏洞写入 Redis hot working set：

```bash
make probe-nvd
```

当前 probe 验证 `SourceAdapter → IngestEnvelope → HotBugIngress → Redis`。长期 Evidence / Promotion、canonical knowledge 和 M3 enrichment 按 Technical Design 的后续 vertical slice 继续实现。

