# SecFusionAgent Web Presentation Standard

本规范定义 SecFusionAgent 的 GitHub README、Wiki、GitHub Pages、Archify 架构图与相关 GitHub Actions 的职责、authority、发布流程和质量门。它约束的是**如何向人展示项目，以及如何保证展示层不偏离真实工程状态**；产品语义仍由 Requirements / Technical Design 持有，代码行为仍由主仓库实现与测试持有。

## 1. 展示层 authority

展示资产按以下顺序确定 authority：

1. `Requirements-SPEC`：产品范围、模块职责、C1–C3 约束与验收语义。
2. `Technical-Design` 与 01–05 专题：进程、存储、接口、数据生命周期、领域语义与设计边界。
3. 主代码仓库：可执行行为、schema、migration、测试、deploy、CI/CD 与 runtime contract。
4. `site/specs/*.json`：对 authoritative Wiki 文档的 typed visual projection。
5. `site/diagrams/*.html`：由 Archify spec 交付的 generated artifact。
6. GitHub Pages 页面与 README：面向读者的导航、解释和工程状态展示。

下层展示内容不得重新定义上层 authority。页面、图或 README 与正文不一致时，先修展示层；不能通过改正文来迁就旧图。

## 2. 各页面职责

### 主仓库 README

README 是代码仓库入口，面向第一次进入项目的人。它回答：项目做什么、当前阶段、主要系统边界、如何运行、质量门在哪里、去哪里看完整设计。

README 不承担完整 Technical Design，也不维护第二份 Mermaid 架构副本。复杂架构统一链接 GitHub Pages 的 Archify view。工程状态尽量引用 CI / Pages 等可验证信号，避免长期手写容易漂移的测试数量与 commit 信息。

### Wiki

Wiki 保存 Requirements、Technical Design、专项语义、风险研究、设计演进与运行知识。中英文页面保持同一语义结构；中文是默认编辑面，英文为对应翻译，不独立发明需求或设计。

### GitHub Pages

Pages 是 **engineering portal**，负责降低系统理解成本，而不是复制 Wiki。

首页提供：

- 项目定位与当前阶段；
- 可计算工程状态；
- System lifecycle walkthrough；
- Requirements / Technical Design 交互视图入口；
- Evidence Lifecycle Explorer；
- 工程阶段与文档 authority map。

Pages 可以使用静态交互解释复杂机制，但示例必须明确区分 synthetic data 与真实情报事实。

### Evidence Lifecycle Explorer

Lifecycle Explorer 用一个合成对象演示真实的 contract、owner、storage 与数据转换，例如：

`External Source → AcquisitionRun → Hot Working Set → Promotion → Observation/Artifact → Canonical Knowledge → Provider-backed Enrichment → Current Projection`

Explorer 的对象名、package path 与状态迁移必须能在当前代码或 Technical Design 中找到依据；不得为了视觉连贯创造不存在的 runtime behavior。

## 3. Archify 规范

Requirements 图使用 `workflow` spec；Technical Design 图使用 `architecture` spec。

中文与英文 spec 必须保持相同 topology：

- Requirements：相同 node IDs 与 edge pairs；
- Technical Design：相同 component IDs 与 connection pairs。

文字可以按语言压缩，但不能通过翻译增加或删除系统节点。

Technical Design first-screen architecture 优先表达主路径和边界，不要求把所有 async feedback、provider、queue 和 derived view 都画成主节点。复杂回环可以放入 guided view / card，只要语义仍然可追溯到正文。

Archify change 使用：

```bash
ARCHIFY=/home/orion/.agents/skills/archify/bin/archify.mjs
W=/home/orion/agent-system-learning/SecFusionAgent.wiki

node $ARCHIFY validate architecture $W/site/specs/tech-design.architecture.json --quality showcase --json
node $ARCHIFY deliver architecture $W/site/specs/tech-design.architecture.json $W/site/diagrams/tech-design.zh.html --quality showcase --json
node $ARCHIFY visual-check $W/site/diagrams/tech-design.zh.html --json
```

英文 spec/HTML 与 Requirements workflow 按相同流程执行。`visual-check` 产生的 PNG、contact sheet 与 receipt 只作为过程证据，不进入 Git。

## 4. 视觉与交互原则

视觉语言服务于工程语义：

- 中性色为主，强调色表示信息层级，而不是装饰；
- monospace 用于 identifier、contract、commit、path 与 payload；
- cyan/blue 可表示 acquisition/data path，green 表示 validated/durable，amber 表示 transient/probing/warning，red 只用于 conflict/failure；
- 不使用与工程含义无关的 AI 紫色渐变、粒子背景或高频动画；
- 支持系统 dark mode；
- 支持 `prefers-reduced-motion`；
- 交互必须可由键盘或标准 button/link 访问；
- mobile 下首先保证文本和操作可用，架构图允许进入独立全屏页面。

首页信息层次遵循：`identity → system model → architecture → engineering state → documentation`。新增模块前先判断它是否改变读者决策；纯装饰模块不进入首页。

## 5. 双语规则

站点默认中文，提供 English 切换。语言状态通过 URL/local storage 保留，但 URL 不应改变页面 authority。

双语要求：

- 标识符、代码类型、provider 名和 package path 保留英文原形；
- 中文负责自然解释，不机械翻译全部术语；
- 英文版本与中文保持同一事实、阶段与 topology；
- 修改一侧页面结构时，同一 change 中检查另一侧。

## 6. 机器生成的工程状态

Pages 不手工维护 commit、source 数量、migration 数量等可计算信息。主仓库 `scripts/build_site_status.py` 在 Pages build 中生成 `project-status.json`，当前字段包括：

- `main_sha`；
- `wiki_sha`；
- source definition 数量；
- migration 数量；
- test file 数量；
- quality gate 名称；
- 当前 phase label。

页面在本地缺少 `project-status.json` 时必须有可理解的 fallback，不应因此无法浏览。

新增指标前先确认它能够稳定从版本控制或 CI 计算。模型质量、benchmark score、在线 SLA 等需要独立 benchmark/observability authority，不允许由前端自行推导。

## 7. CI / CD

### CI

`.github/workflows/ci.yml` 是主仓库基础 gate：

```text
uv sync --dev --frozen
make check
  ├── ruff
  ├── mypy
  └── pytest
docker compose ... config --quiet
```

README badge 只代表该 workflow 的结果，不替代 integration / benchmark / security gate。

### Pages

`.github/workflows/pages.yml`：

1. checkout 主仓库；
2. clone Wiki；
3. 执行 `make site-check WIKI_PATH=wiki`；
4. 执行 `make site-status ...` 生成 `project-status.json`；
5. 复制 `wiki/site/` 形成 Pages artifact；
6. 使用 GitHub Pages 官方 action 发布。

Wiki 仓库本身没有 Actions，因此 Wiki-only update 通过 manual dispatch 或 daily schedule同步到 Pages；主仓库 `main` push 会自动重新发布工程状态。

## 8. Site contract validator

`scripts/validate_site.py` 至少检查：

- 关键页面、asset、diagram 与 spec 是否存在；
- HTML 中相对 `href/src` 是否可解析；
- Requirements / Technical Design 中英文 spec topology 是否一致；
- diagram 目录是否误提交 visual-check PNG / receipt；
- spec 是否使用正确 diagram type。

该 validator 是发布前的最低机械门槛。Archify showcase validation 与浏览器 visual-check仍需在架构图发生视觉变化时运行。

## 9. Change ownership

| Change | Required updates |
| --- | --- |
| Requirements 模块/验收语义改变 | Wiki Requirements + bilingual page + Requirements Archify spec/artifact |
| Technical Design 进程/存储/接口/retention 改变 | Technical Design + Technical Archify spec/artifact + relevant code |
| 页面信息架构或交互改变 | Wiki `site/` + site validator if contract changes |
| CI gate 改变 | workflow + Makefile/stable command + repository standard if policy changes |
| Pages 发布方式改变 | `pages.yml` + 本规范 + Wiki local README |
| 可计算状态字段改变 | `build_site_status.py` + page rendering + 本规范 |

展示层 change 不应顺手修改产品需求；产品需求 change 也不应只更新网站而跳过 authoritative Wiki。

## 10. Review baseline

Web / docs change review 使用以下问题：

- 页面是否明确它在解释什么 authority？
- 是否复制了一份以后会漂移的事实？
- 动态状态能否由 build/CI 计算？
- 双语 topology 和事实是否一致？
- 相对链接、资源和 iframe 是否通过 site validator？
- Archify spec 是否通过 showcase validation？
- 架构视觉变化是否跑过真实浏览器 visual-check？
- 1440×900 与移动端是否仍可读？
- synthetic demo 是否被误写成真实安全事实？
- Pages failure 能否在 Action log 中定位到 validation/build/deploy 某一层？

展示层的目标是减少理解系统所需的认知跳转，同时保持每个事实都能回到唯一 owner。
