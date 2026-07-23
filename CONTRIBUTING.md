# Git 协作规范

> 伴行agent 项目 Git 工作流与协作约定

---

## 1. 分支策略

采用 **GitFlow 简化版**，适配 4-5 人小团队。

### 常驻分支

```
main        ← 生产就绪代码，只从 release 合并
develop     ← 日常开发基线，所有功能分支从这里拉
```

### 临时分支

| 分支类型 | 命名格式 | 来源 | 合入 | 说明 |
|---------|---------|------|------|------|
| Feature | `feat/<简短描述>` | `develop` | `develop` | 新功能开发 |
| Bugfix | `fix/<简短描述>` | `develop` | `develop` | 日常 Bug 修复 |
| Hotfix | `hotfix/<简短描述>` | `main` | `main` + `develop` | 生产环境紧急修复 |
| Release | `release/v<版本>` | `develop` | `main` + `develop` | 发布准备 |

### 示例

```bash
# 开发新功能
git checkout develop
git checkout -b feat/memory-page

# 开发完成后
git checkout develop
git merge feat/memory-page

# 准备发布
git checkout -b release/v1.0.0
# 修复测试问题后：
git checkout main
git merge release/v1.0.0
git tag v1.0.0
git checkout develop
git merge release/v1.0.0
```

---

## 2. 分支命名规范

```
feat/<模块>-<简短描述>
fix/<模块>-<简短描述>
hotfix/<问题描述>
release/v<主版本>.<次版本>.<修订>
```

模块标识：

| 模块 | 说明 |
|------|------|
| auth | 注册、登录、认证 |
| soul | SOUL 选择、模板 |
| chat | 对话、SSE 流 |
| memory | 三层记忆、锚点 |
| interview | 面试场景 |
| reminder | 提醒 |
| ui | 前端界面 |
| api | 后端接口 |
| infra | 基础设施、配置 |

示例：
- `feat/soul-custom-editor`
- `fix/chat-sse-timeout`
- `release/v1.1.0`

---

## 3. 提交信息规范

### 格式

```
<type>(<scope>): <subject>

<body>  (可选)
```

### type 类型

| type | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
| refactor | 重构（不新增功能也不修 Bug） |
| style | 样式 / 格式调整（不影响逻辑） |
| docs | 文档变更 |
| test | 测试新增或修改 |
| chore | 构建 / 工具 / 依赖变更 |

### scope 范围

小写英文，对应模块名（auth / soul / chat / memory / interview / reminder / ui / api / infra / docs）。

### 提交示例

```
feat(chat): 添加 SSE 流式消息逐 token 渲染

- 前端新增加 ReadableStream 解析
- 后端文本块事件改为逐 token输出
- 新增流式状态管理 Store
```

```
fix(memory): 修复禁区过滤未生效问题

禁区关键词使用 set 存储，改为小写匹配。
```

```
docs(readme): 更新快速启动步骤
```

---

## 4. 工作流程

### 日常开发

```bash
# 1. 拉取最新开发分支
git checkout develop
git pull origin develop

# 2. 创建功能分支
git checkout -b feat/xxx

# 3. 开发过程中及时提交
git add <文件>
git commit -m "feat(xxx): 描述"

# 4. 推送远程
git push origin feat/xxx

# 5. 创建 Pull Request → 合并到 develop
```

### Code Review 规范

- 每个 PR 至少 1 人 Review 后合并
- PR 标题格式：`<type>(<scope>): <subject>`
- PR 描述：
  - 改动摘要
  - 关联的 Issue / 需求
  - 测试方法

### 合并要求

- ✅ 编译通过
- ✅ 无合并冲突
- ✅ Review 通过
- ✅ 前后端各自可启动

---

## 5. 版本号规范

采用 **语义化版本**：`主版本.次版本.修订`

| 阶段 | 版本 | 说明 |
|------|------|------|
| MVP | v1.0.0 | 首个可发布版本 |
| 迭代开发 | v1.1.0, v1.2.0 | 功能迭代 |
| 修复 | v1.0.1, v1.0.2 | Bug 修复 |

---

## 6. 首次仓库初始化

```bash
# 进入项目目录
cd comate-agent

# 初始化（已完成）
git init

# 添加所有文件
git add .

# 首次提交
git commit -m "chore(init): 项目初始化

- 前后端项目结构
- SOUL 系统 + 三层记忆 + 面试场景
- FastAPI + Vue 3 技术栈
- 8 周 MVP 版本"

# 关联远程仓库（替换为你的仓库地址）
git remote add origin https://github.com/<你的用户名>/comate-agent.git

# 推送到远程
git push -u origin main
```

---

## 7. .gitignore 说明

项目已配置 `.gitignore`，排除以下内容：

- Python 缓存和虚拟环境（`__pycache__/`, `.venv/`）
- Node 依赖（`node_modules/`）
- 构建产物（`dist/`, `build/`）
- 环境配置文件（`.env`）
- IDE 配置（`.vscode/`, `.idea/`）

⚠️ **注意**：`.env` 文件包含敏感信息（API Key、邮箱密码），已被 gitignore 排除。团队成员需各自复制 `.env.example` 后填写自己的配置。
