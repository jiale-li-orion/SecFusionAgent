# SecFusionAgent

**智能体驱动的 AI 安全情报融合与研判系统** —— 面向 AI 安全知识情报场景的智能体系统项目，对应“中国电子杯”第三届高校 ICT 产教融合创新大赛赛题九《智能体驱动的 AI 安全知识情报系统设计与实现》（奇安信科技集团股份有限公司）。

当前阶段：**Requirements / 需求评审**。需求文档是待人工 review 的草案，尚未冻结；本仓库目前只承载工程与协作，**文档只维护在 wiki**。

## 索引

| 入口 | 内容 |
| --- | --- |
| [在线交互图](https://jiale-li-orion.github.io/SecFusionAgent/) | archify 交付的单文件交互式需求主链路图；**站点根路径就是这份 HTML** |
| [文档页](https://jiale-li-orion.github.io/SecFusionAgent/home.html) | wiki 文档的静态渲染（首页 / SPEC / 图说明） |
| [Wiki 首页](https://github.com/jiale-li-orion/SecFusionAgent/wiki) | 项目定位、当前需求基线、开发流程与记录原则 |
| [需求主链路图](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-Flow-Diagram) | 节点↔需求 ID 对照、校验证据与重新生成命令 |
| [Requirements SPEC v0.1](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC-v0.1) | 需求基线：需求 ID、约束条件与验收口径 |
| [Issues](https://github.com/jiale-li-orion/SecFusionAgent/issues) · [Pull requests](https://github.com/jiale-li-orion/SecFusionAgent/pulls) | 需求评审与协作 |

## 约定

- 需求变更先更新 SPEC，再进入设计与实现；技术设计必须引用已批准的需求 ID。
- 仓库内不放文档副本。文档写在 wiki（`SecFusionAgent.wiki`）；Pages 站点**根路径直接发布 wiki 中的 `prd-flow/prd-requirements-flow.html`**（archify 单文件交互 HTML，字节原样），其余 wiki 页面由 [`.github/pages/build.mjs`](.github/pages/build.mjs) 渲染为静态页。构建与部署见 [`.github/workflows/pages.yml`](.github/workflows/pages.yml)。
- 站点在 workflow/构建脚本变更时自动重建，并每日 `03:17 UTC` 同步一次 wiki；wiki 提交不会触发本仓库的 workflow，需要即时更新时手动触发 `Pages` workflow。
