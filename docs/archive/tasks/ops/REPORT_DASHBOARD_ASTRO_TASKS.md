# T6.4｜Report Dashboard Astro 静态报表门户开发计划

> 状态：设计草案。本文只定义模块方案与开发任务，不代表已开始实现。

## T6.4.1 目标

把当前分散在 `reports/` 下的 Markdown、HTML、CSV 报表统一登记、索引、构建为一个本地 Astro 静态 Dashboard，并在 `compare`、`strategy-admission`、`brief`、`maintenance` 等过程结束后自动刷新展示入口。

目标不是重写各模块报表生成逻辑，而是在现有产物之上增加一层“报表发布层”：

- [ ] 所有核心流程结束后可登记本次运行的报表、简报、CSV、HTML 和治理结论。
- [ ] 本地固定端口默认使用 `http://127.0.0.1:4321/` 展示 Dashboard。
- [ ] Dashboard 可以按日期、模块、策略、状态、产物类型过滤和跳转。
- [ ] Dashboard 对 Markdown / HTML / CSV 使用不同展示方式：Markdown 渲染为报告页，HTML 作为 iframe / 外链预览，CSV 作为表格摘要和下载链接。
- [ ] 保持研究口径安全：Dashboard 只展示研究产物，不把 compare / admission 成功误解释为可交易信号。

## T6.4.2 非目标

- [ ] 不在 V1 做用户登录、权限系统或远程部署。
- [ ] 不在 V1 把所有历史报告迁移为新格式。
- [ ] 不在 V1 重写 `phase0` 各命令的业务逻辑。
- [ ] 不在 V1 引入数据库型报表服务；manifest 文件足够。
- [ ] 不把 Dashboard 作为交易执行入口，不输出买卖指令。

## T6.4.3 推荐架构

推荐采用“Python 产物登记层 + Astro 静态渲染层”的解耦方案。

```text
phase0 command
  compare / strategy-admission / brief / maintenance / db-health
        |
        v
phase0.report_registry
  register_artifact()
  register_run()
  scan_reports()
  write_manifest()
        |
        v
reports/report_dashboard/manifest.json
reports/report_dashboard/artifacts/*
        |
        v
dashboard/ Astro app
  reads manifest.json
  renders dashboard pages
        |
        v
localhost:4321
```

核心取舍：

| 方案 | 优点 | 缺点 | 风险 | 推荐度 |
| --- | --- | --- | --- | --- |
| 每个流程直接生成 Astro 页面 | 快速看到页面 | 业务命令耦合前端，后续难维护 | compare/admission/brief 都要懂 Astro | 低 |
| 统一 manifest，Astro 只消费 manifest | 边界清晰，容易测试，可扩展 | 需要先设计登记模型 | manifest schema 需要版本治理 | 高 |
| 独立常驻 Web 服务动态扫描 reports | 实时性好 | 运维复杂，和当前静态报告体系不一致 | 端口、进程、状态管理成本高 | 中 |

推荐方案：统一 manifest。原因是当前项目已经大量生成 Markdown/CSV/HTML 静态产物，最小可验证路径是登记和索引，而不是引入服务端状态。

## T6.4.4 模块边界

### Python 报表登记层

新增模块建议：

- `phase0/report_registry.py`
  - 定义 `ReportArtifact`、`ReportRun`、`ReportManifest`。
  - 提供 `register_run()`、`register_artifact()`、`write_manifest()`、`scan_reports()`。
  - 只处理路径、元数据、分类和状态，不渲染前端。
- `phase0/report_dashboard.py`
  - 提供 Dashboard 构建 / 启动的命令封装。
  - 调用 Node/Astro 命令前先检查依赖和端口。
  - 不包含业务策略判断。
- `tests/test_report_registry.py`
  - 覆盖 manifest schema、路径归一化、缺失文件、重复登记和扫描规则。
- `tests/test_report_dashboard_cli.py`
  - 覆盖 CLI 参数解析、dry-run、端口配置和无 Node 环境时的错误信息。

现有命令集成点：

- `phase0/cli.py`
  - 新增 `dashboard build`、`dashboard serve`、`dashboard scan`。
  - 在 `strategy-admission`、`strategy-failure-attribution`、`brief daily`、`maintain status` 后追加可选登记。
- `config.yaml`
  - 新增 `report_dashboard` 配置块。

### Astro 静态站点层

新增目录建议：

- `dashboard/package.json`
- `dashboard/astro.config.mjs`
- `dashboard/src/pages/index.astro`
- `dashboard/src/pages/reports/[id].astro`
- `dashboard/src/pages/runs/[run_id].astro`
- `dashboard/src/lib/manifest.ts`
- `dashboard/src/styles/global.css`

Astro 只读取 `reports/report_dashboard/manifest.json`，不直接扫描业务目录。这样可以避免前端重复实现报表分类逻辑。

## T6.4.5 Manifest 数据模型

V1 manifest 建议使用单文件 JSON：

```json
{
  "schema_version": 1,
  "generated_at": "2026-06-23T00:00:00+08:00",
  "project_root": "/home/zj/workspace/stok-mapping",
  "runs": [
    {
      "run_id": "strategy-admission-20260623-001",
      "command": "strategy-admission",
      "module": "strategy",
      "started_at": "2026-06-23T10:00:00+08:00",
      "finished_at": "2026-06-23T10:12:00+08:00",
      "status": "success",
      "summary": "baseline_admission_all_v1 dual-preset admission",
      "tags": ["strategy-admission", "baseline_admission_all_v1", "qfq_asof"],
      "artifact_ids": ["artifact-001", "artifact-002"]
    }
  ],
  "artifacts": [
    {
      "artifact_id": "artifact-001",
      "run_id": "strategy-admission-20260623-001",
      "title": "Strategy Admission Report",
      "path": "reports/strategy_admission_20260623_baseline_admission_all_v1/strategy_admission_report.md",
      "type": "markdown",
      "module": "strategy",
      "created_at": "2026-06-23T10:12:00+08:00",
      "status": "research_only",
      "tags": ["admission", "qfq_asof"],
      "description": "Admission decision, constraints and rejection reasons."
    }
  ]
}
```

字段口径：

- `status` 必须区分 `success`、`warning`、`error`、`research_only`、`reject`、`retest`、`eligible_for_paper_review`。
- `path` 一律使用 repo 相对路径，避免本机绝对路径污染静态站点。
- `tags` 用于过滤，不承载结论。
- `description` 可以为空字符串，但字段必须存在，便于前端稳定渲染。

## T6.4.6 Dashboard 页面设计

V1 页面只做 5 个核心视图：

- [ ] 首页：展示最新运行、失败 / warning 报表、最新 admission 结论和今日 brief。
- [ ] Runs：按运行批次展示命令、状态、耗时、产物数和标签。
- [ ] Reports：按 Markdown / HTML / CSV 类型筛选全部产物。
- [ ] Strategy Governance：集中展示 compare、admission、failure attribution、overfit diagnostic。
- [ ] Maintenance & Data Quality：集中展示 scheduler、maintenance、db-health、backfill audit。

视觉方向：

- 采用 research dashboard 风格，不做默认文档站。
- 页面使用浅色研究台风格：高信息密度、明显状态色、固定左侧导航、右侧报告预览。
- 风险状态使用颜色和文案同时表达，避免只靠颜色。
- 每个策略相关页面固定显示免责声明：`Dashboard 展示研究产物，不构成交易建议；进入 paper review / 模拟账户 / 日报必须通过 admission gate。`

## T6.4.7 CLI 设计

新增命令建议：

```bash
./.venv/bin/python -m phase0.cli dashboard scan --config config.yaml
./.venv/bin/python -m phase0.cli dashboard build --config config.yaml
./.venv/bin/python -m phase0.cli dashboard serve --config config.yaml --host 127.0.0.1 --port 4321
```

命令职责：

- `dashboard scan`：扫描已知 report 目录，生成 / 刷新 manifest。
- `dashboard build`：生成 manifest 后执行 Astro build。
- `dashboard serve`：检查 manifest，启动 Astro preview 或 dev server。

推荐配置：

```yaml
report_dashboard:
  enabled: true
  manifest_path: reports/report_dashboard/manifest.json
  site_dir: dashboard
  host: 127.0.0.1
  port: 4321
  auto_register:
    strategy_admission: true
    strategy_failure_attribution: true
    brief: true
    maintenance: true
    db_health: true
  scan_roots:
    - reports
  exclude_globs:
    - reports/tmp_validation/**
    - reports/**/__pycache__/**
```

## T6.4.7.1 依赖：T6.5 Report Output Path Standardization

Dashboard ingestion 优先消费标准 run 目录：

```text
reports/runs/YYYY-MM-DD/YYYYMMDD_HHMMSS__<command>__<scope>/
```

历史目录保持 scan-compatible，但不再作为新命令的目标格式。当前 scanner 分类契约：

- `standard_run`
- `legacy_root_flat`
- `legacy_module_dir`
- `legacy_date_dir`
- `legacy_experiment_dir`
- `legacy_latest_mirror`
- `legacy_scratch`

## T6.4.8 自动登记策略

V1 采用“显式登记优先，扫描补全兜底”：

- [ ] `strategy-admission` 完成后登记 `strategy_admission_report.md`、`strategy_admission_governance_report.md`、window matrix、constraint review、candidate folds、overfit diagnostic。
- [ ] `strategy-failure-attribution` 完成后登记 attribution Markdown 和 CSV。
- [ ] `brief daily` 完成后登记今日 HTML brief、watchlist CSV、account bill。
- [ ] `maintain status` 完成后登记 maintenance Markdown 状态报告。
- [ ] `db-health` 完成后登记 summary CSV、findings CSV、Markdown report。
- [x] `dashboard scan` 对标准 run 与旧历史目录做补全，旧产物缺少 run_id 时生成稳定兼容 run_id。

## T6.4.9 错误处理

- [ ] 如果登记的文件不存在，manifest 写入 `status=warning`，并记录 `missing=true`，不让整个业务命令失败。
- [ ] 如果 Astro 依赖未安装，`dashboard build/serve` 必须输出明确修复命令，不影响 `compare/admission` 主流程。
- [ ] 如果 `127.0.0.1:4321` 被占用，`dashboard serve` 默认失败并提示 `--port` 覆盖；不自动随机换端口。
- [ ] 如果 Markdown 解析失败，Dashboard 显示原始文本链接，不阻断站点构建。
- [ ] 如果 CSV 超大，V1 只预览前 200 行，并提供文件链接。

## T6.4.10 安全与数据治理边界

- [ ] Dashboard 默认只绑定 `127.0.0.1`，不监听 `0.0.0.0`。
- [ ] 不复制 `.env`、数据库、密钥或日志中的敏感 token。
- [ ] HTML 产物默认以 sandbox iframe 展示；后续如需内联 HTML，必须先做安全审查。
- [ ] CSV / Markdown 中的路径应使用 repo 相对路径，避免泄露主机目录结构。
- [ ] 策略页必须保留 research-only / admission gate 边界说明，避免把研究报告误读为交易建议。

## T6.4.11 开发任务拆解

### P0：只读 Manifest MVP

- [x] 新增 `phase0/report_registry.py`，定义 dataclass 和 manifest 写入。
- [x] 新增 `tests/test_report_registry.py`，验证登记 Markdown / HTML / CSV 产物。
- [x] 新增 `dashboard scan` CLI，只扫描 `reports/` 并生成 `reports/report_dashboard/manifest.json`。
- [x] 对 `reports/strategy_admission/`、`reports/2026-06-23/`、`reports/database_health/` 做样本扫描验收。

验收标准：

- [x] `./.venv/bin/python -m pytest tests/test_report_registry.py -q` 通过。
- [x] `./.venv/bin/python -m phase0.cli dashboard scan --config config.yaml` 能生成 manifest。
- [x] manifest 至少包含 Markdown、HTML、CSV 三类产物。

### P1：Astro Dashboard MVP

- [ ] 新增 `dashboard/` Astro 项目骨架。
- [ ] 实现首页、Runs、Reports、Report Detail 四类页面。
- [ ] 实现 Markdown 渲染、CSV 前 200 行预览、HTML sandbox iframe。
- [ ] 新增 `npm` scripts：`dev`、`build`、`preview`。

验收标准：

- [ ] `npm --prefix dashboard run build` 通过。
- [ ] `npm --prefix dashboard run preview -- --host 127.0.0.1 --port 4321` 可在本地打开。
- [ ] 至少一个 admission Markdown、一个 brief HTML、一个 CSV 可从首页跳转查看。

### P2：核心流程自动登记

- [ ] `strategy-admission` 完成后自动登记本次输出目录。
- [ ] `strategy-failure-attribution` 完成后自动登记归因产物。
- [ ] `brief daily` 完成后自动登记 HTML 和 CSV。
- [ ] `maintain status` 与 `db-health` 完成后自动登记运维 / 数据质量产物。

验收标准：

- [ ] 运行 scoped admission 后 manifest 自动出现新 run。
- [ ] 运行 brief 后 Dashboard 首页出现最新 brief。
- [ ] 自动登记失败不影响原业务命令退出码，除非用户显式传入 `--dashboard-required`。

### P3：本地服务体验与调度集成

- [ ] 新增 `dashboard serve`，封装 Astro preview / dev server。
- [ ] 新增端口占用检查，默认固定 `127.0.0.1:4321`。
- [ ] 将每日调度结束后的 report manifest refresh 接入 scheduler，但不自动启动长期 Web 进程。
- [ ] 在 `system status` 输出 Dashboard manifest 时间、产物数量和预览地址。

验收标准：

- [ ] `dashboard serve` 在端口可用时启动成功。
- [ ] 端口被占用时明确失败并提示 `--port`。
- [ ] `system status` 可只读展示 Dashboard 状态，不写入数据库或报告。

## T6.4.12 测试计划

- [x] Unit：manifest schema、路径归一化、CSV 类型识别、标准 run 与 legacy category 分类。
- [x] CLI：`dashboard scan` 参数、配置默认值、manifest 生成与统计输出。
- [ ] CLI：`dashboard build/serve` 参数、错误信息、配置默认值。
- [ ] Integration：scoped `strategy-admission` 后 manifest 自动新增 run。
- [ ] Frontend build：Astro build 必须通过。
- [ ] Manual smoke：打开 `http://127.0.0.1:4321/`，检查首页、Runs、Reports、一个 Markdown 报告、一个 HTML brief、一个 CSV 预览。

## T6.4.13 风险与控制

| 风险 | 影响 | 控制 |
| --- | --- | --- |
| 报表命名不统一 | 扫描结果不完整 | 显式登记优先，扫描只兜底 |
| Astro 依赖引入 Node 复杂度 | 本地环境失败 | Python 主流程不依赖 Astro 成功 |
| CSV 文件过大 | 页面卡顿 | 只预览前 200 行 |
| HTML 报表含脚本 | XSS / 本地风险 | sandbox iframe，不内联执行 |
| 用户误读策略结论 | 研究风险 | 策略页固定 admission gate 声明 |
| 端口冲突 | 预览失败 | 固定端口 + 明确错误 + `--port` 覆盖 |

## T6.4.14 推荐实施顺序

1. 先做 P0 manifest，只读扫描，不引入 Astro。
2. 再做 P1 Astro MVP，只消费 manifest。
3. 再把 `strategy-admission` 和 `brief` 接入自动登记。
4. 最后接入 `maintenance/db-health/system status`，避免一开始扩大运维边界。

当前推荐下一步：先实现 P0。原因是 manifest 是所有后续 Dashboard、调度集成和前端展示的共同边界；没有稳定 manifest，Astro 页面会被迫直接解析历史目录，后续维护成本高。
