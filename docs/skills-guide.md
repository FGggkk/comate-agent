# Matt Pocock Skills 操作指南

通过 `/skill <名称>` 调用。以下按使用场景分类。

---

## 🔥 审查与追问

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill grill-me` | 对你的想法/计划进行严厉追问，直到达成共识。不需要代码仓库，纯脑子里的想法也能盘。 | 有了一个想法但还没写代码，想先被怼一轮看看有没有漏洞 |
| `/skill grill-with-docs` | 跟 grill-me 一样追问，但会生成 `CONTEXT.md` 和 ADR 文档保留下来。 | 有代码仓库了，想边盘边把决策落地成文档 |
| `/skill batch-grill-me` | 跟 grill-me 一样追问，但一轮问完所有问题，不一个个来。 | 想更快过完追问流程，批量处理 |
| `/skill grilling` | grill-me 和 grill-with-docs 背后的核心追问引擎。普通情况直接用上面两个就行。 | 基本不用手动调用 |

---

## 📋 需求与规范

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill to-spec` | 把 issue 或 ticket 转成一份清晰的规范文档。 | 有一个需求 ticket 但欠缺详细描述，需要展开成可执行的 spec |
| `/skill to-tickets` | 把 spec 或设计拆成可执行的 ticket 列表。 | 方案确认后，要拆成一个个可执行的任务 |
| `/skill qa` | 审查 spec/PRD/issue，生成一份问题清单让作者回答。 | 别人给了你一份需求文档，你想挑出漏洞和遗漏 |
| `/skill to-questionnaire` | 把需求转成问卷形式。 | 想用问答方式收集需求信息 |

---

## 🧠 设计与建模

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill domain-modeling` | 梳理项目的领域语言——消除模糊术语、记录关键决策为 ADR。 | 发现同一个词在不同地方意思不一样，领域边界模糊 |
| `/skill codebase-design` | 深度学习"深模块"设计理念——如何设计接口、找 seam、提高可测试性。 | 设计/重构模块接口，想让代码更容易测试和修改 |
| `/skill design-an-interface` | 用多个并行的子 agent 生成完全不同的接口设计方案，然后对比选优。 | 要设计一个关键模块的接口，想看看多种方案再选 |
| `/skill ubiquitous-language` | 统一项目中的术语，建立通用语言。 | 团队沟通中术语不一致，需要统一词汇表 |

---

## 🐛 调试与修复

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill diagnosing-bugs` | 硬核 bug 诊断流程——先建立快速 pass/fail 反馈环，再定位根因。 | 遇到很难复现或很难定位的 bug / 性能回退 |
| `/skill resolving-merge-conflicts` | 协助解决合并冲突。 | git merge 冲突不知道怎么处理 |

---

## 🛠 实现与开发

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill implement` | 从 ticket 或 spec 出发，内部用 TDD 实现功能，最后 code review 再提交。 | 拿到一个明确的任务，准备开始写代码 |
| `/skill tdd` | TDD 工作流——红-绿-重构循环。 | 想严格按照测试驱动开发流程来写代码 |
| `/skill prototype` | 快速写一个用完就扔的小程序，回答一个设计问题。 | 不确定某个方案行不行，先快速验证 |
| `/skill qa` | 对实现进行 QA 测试。 | 功能写完了，要做端到端的质量检查 |

---

## 🔄 协作与交接

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill handoff` | 把当前对话压缩成一份 markdown 交接文档，下个会话接着干。 | 当前 context 太长了，想开新会话但不想丢失上下文 |
| `/skill claude-handoff` | 把当前对话交给一个后台新 agent 立即接着干。 | 想后台异步继续跑任务，不用等 |
| `/skill loop-me` | 多轮交互循环——agent 问问题 → 你回答 → 执行 → 问是否继续。 | 需要反复确认的交互式任务，让你控制节奏 |

---

## 🏗 架构改进

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill code-review` | 从"编码规范"和"需求符合度"两个维度并行 review 代码 diff。 | 代码写完了准备提交，想从两个角度检查一遍 |
| `/skill improve-codebase-architecture` | 扫描代码库，找出"深化机会"——哪些模块可以更深、seam 更干净。 | 代码库越来越乱，想系统性地找出重构点 |
| `/skill request-refactor-plan` | 生成详细的重构计划。 | 找到了需要重构的地方，想要一个具体执行方案 |
| `/skill codebase-design` | 代码库设计评审。 | 新模块设计或老模块重构，想检查设计质量 |
| `/skill wayfinder` | Issue/PR 方向探索——通过 issue 依赖树找到下一个最该做的事。 | 有很多 issue / ticket 不知道先干什么，让系统帮你找优先级最高的 |

---

## 📝 写作

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill writing-beats` | 写作节奏——一个段落一个段落地写/改。 | 写文章、文档，想逐段打磨 |
| `/skill writing-shape` | 先定文章结构，再填充内容。 | 写长文前先规划整体框架 |
| `/skill writing-fragments` | 从零散的片段/笔记整合成连贯的文章。 | 有很多零散想法和笔记，要整理成文 |
| `/skill writing-great-skills` | 教你如何写好的 skill（元技能）。 | 自己想写一个 SKILL.md 时参考 |
| `/skill edit-article` | 从原始素材（草稿/转录稿）编辑成文。 | 有原始素材需要润色成正式文章 |

---

## 🎓 学习与教学

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill teach` | 教学/指导模式——解释概念、带练、检查理解。 | 想学习一个新概念或让别人学习 |
| `/skill research` | 对某个主题做研究并输出报告。 | 需要调研某个技术或领域，产出结构化报告 |

---

## 🔧 配置与工具

| Skill | 作用 | 什么时候用 |
|-------|------|-----------|
| `/skill setup-matt-pocock-skills` | 初始化项目的 issue tracker、triage 标签、domain docs 配置。 | 第一次用这套 skills 时跑一次初始化 |
| `/skill triage` | Issue/PR 分类分诊——标记 needs-triage / ready-for-agent 等状态。 | 有新的 issue 或 PR 需要分类处理 |
| `/skill setup-pre-commit` | 配置 pre-commit hooks。 | 想给项目加代码检查钩子 |
| `/skill setup-ts-deep-modules` | 配置 TypeScript 深度模块结构。 | 想优化 TypeScript 项目模块组织 |
| `/skill scaffold-exercises` | 脚手架练习题模板。 | 想生成编程练习题 |
| `/skill migrate-to-shoehorn` | 把测试中的 `as` 类型断言迁移到 `@total-typescript/shoehorn`。 | 测试代码里用了很多 `as` 强转，想换成类型安全的写法 |
| `/skill obsidian-vault` | 创建或同步 Obsidian 知识库目录结构。 | 想用 Obsidian 管理项目文档 |
| `/skill git-guardrails-claude-code` | 安装 git 保护脚本，防止执行危险 git 命令。 | 怕手滑执行 `git push --force` 或 `rm -rf` |

---

## 🤔 不知道用哪个？

| Skill | 作用 |
|-------|------|
| `/skill ask-matt` | 描述你的场景，它会推荐该用哪个技能或流程。 |

---

## 典型工作流

```
┌─ 想法阶段 ─────────────────────────────┐
│  /skill grill-me         盘一下这个想法   │
│  /skill grill-with-docs  盘完落地成文档   │
└─────────────────────────────────────────┘
          ↓
┌─ 设计阶段 ─────────────────────────────┐
│  /skill to-spec            想法转规格    │
│  /skill domain-modeling    统一术语      │
│  /skill design-an-interface 设计接口     │
│  /skill qa                 审查规格      │
└─────────────────────────────────────────┘
          ↓
┌─ 执行阶段 ─────────────────────────────┐
│  /skill to-tickets         拆成任务      │
│  /skill implement / tdd    实现 / TDD   │
│  /skill code-review        代码审查      │
└─────────────────────────────────────────┘
          ↓
┌─ 迭代阶段 ─────────────────────────────┐
│  /skill handoff            交接待办      │
│  /skill wayfinder          下一步方向     │
└─────────────────────────────────────────┘
```
