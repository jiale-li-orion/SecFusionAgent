# SecFusionAgent

**智能体驱动的 AI 安全情报融合与研判系统** —— 面向 AI 安全知识情报场景的智能体系统项目，对应“中国电子杯”第三届高校 ICT 产教融合创新大赛赛题九《智能体驱动的 AI 安全知识情报系统设计与实现》（奇安信科技集团股份有限公司）。

当前阶段：**Requirements / 需求评审**。需求文档是待人工 review 的草案，尚未冻结；本仓库目前只承载工程与协作，**文档只维护在 wiki**。

## 索引

| 入口 | 内容 |
| --- | --- |
| [文档站点](https://jiale-li-orion.github.io/SecFusionAgent/) | wiki 文档的静态站点，含在线交互版需求主链路图 |
| [Wiki 首页](https://github.com/jiale-li-orion/SecFusionAgent/wiki) | 项目定位、当前需求基线、开发流程与记录原则 |
| [需求主链路图](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-Flow-Diagram) | PRD 主链路，含节点↔需求 ID 对照、验收基线与证据 |
| [Requirements SPEC v0.1](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC-v0.1) | 需求基线：需求 ID、约束条件与验收口径 |
| [Issues](https://github.com/jiale-li-orion/SecFusionAgent/issues) · [Pull requests](https://github.com/jiale-li-orion/SecFusionAgent/pulls) | 需求评审与协作 |

## 约定

- 需求变更先更新 SPEC，再进入设计与实现；技术设计必须引用已批准的需求 ID。
- 仓库内不放文档副本。文档写在 wiki（`SecFusionAgent.wiki`），文档站点由 [`.github/workflows/pages.yml`](.github/workflows/pages.yml) 构建时拉取 wiki 生成并发布到 GitHub Pages，构建脚本见 [`.github/pages/build.mjs`](.github/pages/build.mjs)。
- 文档站点在 workflow 文件变更时自动重建，并每日 `03:17 UTC` 同步一次 wiki；wiki 提交不会触发本仓库的 workflow，需要即时更新时手动触发 `Pages` workflow。
