# Coding Style Rules

## General Principles

* 优先可读性，其次性能，其次优雅性
* 避免隐式行为，所有关键逻辑必须显式表达
* 保持函数与模块职责单一（Single Responsibility Principle）
* 禁止“聪明代码”（clever code），允许“直白冗长代码”

---

## Naming Conventions

* 使用语义明确的命名，而非缩写
* 函数名必须是动词开头（createUser, fetchData）
* 布尔变量必须表达状态（isLoaded, hasPermission）
* 避免单字母变量（循环索引除外）

---

## Function Design

* 单函数建议 ≤ 50 行（超过必须拆分）
* 参数 ≤ 4 个，超过则使用对象封装
* 避免深层嵌套（建议 ≤ 3 层）
* 禁止副作用隐藏在函数内部

---

## Error Handling

* 所有 I/O 必须显式处理 error
* 不允许 silent failure（吞异常）
* 错误必须包含上下文信息
* 使用统一 error format（code + message + context）

---

## State Management

* state 必须集中管理，不允许分散 mutation
* 禁止跨模块隐式修改共享状态
* 所有 state change 必须可追踪

---

# Architecture Constraints

## Core Architecture Principles

* 强制模块化（Modular First）
* 分层清晰：UI / Service / Domain / Infrastructure
* 禁止跨层调用（UI → DB 直接访问禁止）

---

## Dependency Rules

* 依赖方向必须单向（top-down）
* domain 层不得依赖 infrastructure
* service 层不得依赖 UI

---

## System Design Constraints

* 所有系统必须支持水平扩展（stateless first）
* 数据访问必须抽象 repository layer
* 外部服务调用必须封装 adapter

---

## Performance Constraints

* 默认考虑 O(n) 或更优
* 避免在 request path 中执行重计算
* 所有 cache 必须有失效策略

---

## Security Constraints

* 所有 input 必须 validate + sanitize
* 默认最小权限原则（least privilege）
* 敏感数据禁止 log

---

# Repo Conventions

## Directory Structure

* `/src`：核心业务代码
* `/domain`：领域模型
* `/services`：业务服务层
* `/infra`：基础设施（DB, API, cache）
* `/tests`：测试代码
* `/scripts`：工具脚本

---

## File Naming

* kebab-case（user-service.ts）
* 测试文件：*.test.ts
* 工具文件：*.util.ts 或 *.helper.ts（尽量减少）

---

## Module Rules

* 一个模块一个明确职责
* index 文件仅用于 re-export，不写逻辑
* 禁止循环依赖（必须显式检测）

---

## Documentation

* 每个模块必须有 README 或 header comment
* API 必须有 input/output 示例
* 复杂逻辑必须解释“why not just what”

---

# Workflow (Test / Lint / Commit)

## Development Workflow

标准流程必须遵循：

1. 理解需求
2. 设计方案（可选但推荐）
3. 实现最小可运行版本
4. 补齐边界情况
5. 添加测试
6. 运行 lint + format
7. 提交代码

---

## Testing Rules

* 新功能必须附带测试
* bug fix 必须添加 regression test
* 测试必须覆盖：

  * 正常路径
  * 边界条件
  * 错误输入

---

## Test Types

* Unit tests：逻辑验证
* Integration tests：模块交互
* E2E tests：关键用户路径

---

## Lint Rules

* lint 必须 zero warning 才允许 commit
* format 自动化（prettier / equivalent）
* 禁止手动格式化代码风格

---

## Commit Conventions

采用 conventional commits：

* feat: 新功能
* fix: bug 修复
* refactor: 重构（无行为变化）
* test: 测试相关
* chore: 工程/工具链
* docs: 文档

---

## Commit Rules

* 一个 commit 只做一件事
* commit message 必须描述“做了什么 + 为什么”
* 禁止大杂烩 commit

---

## Pull Request Rules

* 必须有描述（problem / solution / impact）
* 必须通过 CI
* 必须 review 才能 merge

---

# Execution Discipline

所有代码变更必须满足：

* 可运行
* 可测试
* 可回滚
* 可解释

任何“临时 hack”必须标记 TODO + reason

---

# Non-Negotiable Principle

如果存在更简单方案：

优先选择更简单的方案，而不是更“高级”的方案。