# 2026-07-04 会话增量归档：中文文本事件源与自建 API 计划

## 范围

本轮围绕 A 股公告源、巨潮异常波动 / 风险提示公告、Tushare `cctv_news` 权限替代方案，以及自建中文文本事件 API 的开发计划做了调研和落盘。

按当前目录治理规则，会话归档放入 `memory/session_archive/`，不放入 `logs/`。`logs/README.md` 已明确 `logs/` 只存机器运行日志、调度状态和运行排障痕迹。

## 新增结论

- 当前项目应区分“源头能不能拿到”和“项目是否已落库 / 接入日报”：
  - 源头层面：巨潮公开公告可通过 AkShare `stock_zh_a_disclosure_report_cninfo` 拉取标题、链接和部分公告元信息。
  - 集成层面：正式 `phase0/news_sources.py` / `market_text_events` 统一文本事件层尚未完成。
- Tushare `anns_d` 与 `cctv_news` 均属于权限敏感接口。本轮已验证当前 token 不可直接依赖这些接口作为立即可用数据源。
- AkShare / 巨潮可以作为公告类文本事件的低成本 MVP fallback，但长期仍应保留官方披露源、Tushare 权限源或授权源的可替换 provider 边界。
- CCTV 新闻联播文字稿存在公开网页来源，自建 `cctv_news` 风格 API 技术上可行：
  - 栏目页可定位到日期页。
  - 日期页可列出当日完整节目和分段视频链接。
  - 完整节目页可抽取节目概要。
  - 分段视频页可抽取标题、关键词、摘要、正文和 URL。
- 自建 API 不应只做一个 CCTV 抓取脚本，而应纳入 `T1.3` 新闻源独立模块和统一文本事件模型，后续扩展公告、政策法规、券商研报和央行货币政策执行报告。

## 已执行的关键 probe

- Tushare：
  - `anns_d` 返回无接口访问权限。
  - `cctv_news` 返回无接口访问权限。
- AkShare / 巨潮：
  - `stock_zh_a_disclosure_report_cninfo` 可用。
  - `002080.SZ` 可检索到中材科技历史异常波动公告。
  - 全市场关键词 `股票交易异常波动` 可返回大量最近公告样本。
- 最近 3 天公告专项拉取：
  - 时间窗：`2026-06-30` 至 `2026-07-02`。
  - 关键词：`股票交易异常波动`、`异常波动`、`股票交易风险提示`、`交易风险提示`、`严重异常波动`。
  - 清洗后按 `announcementId` 去重，标题语义过滤，避免泛化 `风险提示` 混入可转债适当性、退市、摊薄等无关公告。
  - 产物：
    - `reports/ad_hoc/akshare_cninfo_abnormal_risk_20260630_20260702.csv`
    - `reports/ad_hoc/akshare_cninfo_abnormal_risk_20260630_20260702.md`
  - 清洗后统计：`raw_rows=402`，`rows=177`；日期分布为 `2026-07-02:42`、`2026-07-01:71`、`2026-06-30:64`；类型分布为 `异常波动:92`、`股票交易风险提示:61`、`异常波动+风险提示:19`、`严重异常波动:5`。
- CCTV：
  - `https://tv.cctv.com/lm/xwlb/` 可访问，页面含新闻联播栏目入口。
  - 现代日期页模式为 `https://tv.cctv.com/lm/xwlb/day/YYYYMMDD.shtml`。
  - 近年单期节目页可抽取 `.video_brief` 作为节目概要。
  - 分段视频页可抽取 `title`、`contentid`、`keywords`、`description`、`.video_brief` 和 `#content_area` 正文。
  - 历史路径存在分段差异，2016-02-03 以前应作为后续兼容任务，不进入 MVP 首批验收。

## 本轮新增/计划变更

- 新增自建中文文本事件 API 计划：
  - `docs/tasks/data-sources/SELF_HOSTED_CHINESE_TEXT_EVENT_API_TASKS.md`
- 更新任务索引：
  - `docs/tasks/README.md` 增加 `T1.3A`，承接 `T1.3` 新闻源独立模块。

## 未完成事项

- 尚未实现 `phase0/news_sources.py` 或任何正式 provider 代码。
- 尚未建立 `market_text_events` SQLite / parquet 表。
- 尚未加入自动抓取、缓存、重试、限流和回放测试。
- 尚未对 CCTV 网站历史页面做全区间兼容性评估。
- 尚未确认 CCTV、公告、研报、政策原文的再分发许可边界；开发时应优先保存来源 URL、哈希和本地审计信息，避免把付费或受限全文作为公开再分发内容。

## 下一步

- 按 `T1.3A` 计划先做最小可验证版本：
  - CCTV 新闻联播日期页 + 分段页 parser。
  - 统一事件 schema。
  - fixtures 测试和一次联网 probe。
  - 本地 CSV / parquet / SQLite 查询出口。
- 第二阶段再接入巨潮公告、政策法规、券商研报元数据、央行货币政策执行报告等 provider。

## 追加：国家政策法规库 API 独立调研

用户明确要求不要依赖 Tushare 网站，而是独立研究公开源并制定开发计划。本轮已把 `npr` 风格 API 拆成独立任务单：

- `docs/tasks/data-sources/NATIONAL_POLICY_REPOSITORY_API_TASKS.md`
- `docs/tasks/README.md` 增加 `T1.3B`

独立验证结论：

- 中国政府网政策文件库入口 `https://www.gov.cn/zhengce/zhengcewenjianku/` 会跳转到 `https://sousuo.www.gov.cn/zcwjk/policyDocumentLibrary?q=&t=zhengcelibrary&orpro=`。
- 真实列表接口为 `https://sousuo.www.gov.cn/search-gov/data`，可直接 GET 查询。
- 列表接口返回 `title`、`url`、`pcode`、`puborg`、`childtype`、`pubtime`、`pubtimeStr`、`summary`、`id` 等字段。
- 已验证参数包括 `q`、`t`、`p`、`n`、`puborg`、`bmfl`、`pcodeJiguan`、`childtype`、`subchildtype`、`timetype`、`mintime`、`maxtime`。
- 国务院部门字典可从 `https://www.gov.cn/zhengce/bmzcfwjg.json` 获取。
- 主题分类需要从 `/search-gov/data` 返回的 `ztflTree` 缓存映射，例如 `1088=科技、教育`、`2220=科技`。
- 正文页可通过 `#UCAP-CONTENT` 抽取正文 HTML，通过页面 metadata 和元数据表抽取发布时间、发文机关、发文字号、主题分类等。

代表性验收样例：

- `org=国务院`、`ptype=科技`、`subchildtype=2220`、`pcodeJiguan=国发` 可返回 `国务院关于深入实施“人工智能+”行动的意见`，发文字号 `国发〔2025〕11号`。
- `org=工业和信息化部` 可通过部门文件参数 `bmfl=工业和信息化部` 查询部门政策文件。
- 自定义时间窗可通过 `timetype=timezd`、`mintime`、`maxtime` 过滤。

## 追加：合并为 T1.7｜AI 语料库开发计划

用户要求把 `SELF_HOSTED_CHINESE_TEXT_EVENT_API_TASKS.md` 和国家政策法规库计划合并为一个“AI 语料库”开发计划，并在父级开发计划和周清单中分配任务序号。

已完成落盘：

- 新增统一主计划：`docs/tasks/data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md`
- 原 `SELF_HOSTED_CHINESE_TEXT_EVENT_API_TASKS.md` 改为历史兼容入口，指向 `T1.7` 主计划。
- 原 `NATIONAL_POLICY_REPOSITORY_API_TASKS.md` 改为历史兼容入口，指向 `T1.7` 主计划。
- `docs/tasks/README.md` 移除主索引中的 `T1.3A/T1.3B`，新增 `T1.7｜AI 语料库`。
- `docs/DEVELOPMENT_PLAN.md` 增加 `T1.7` 任务序号、当前优先级、小节说明和第一版验收标准。
- `docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md` 增加 `W2.31｜AI 语料库开发计划（T1.7）`。

合并后口径：

- `T1.3` 仍是新闻源独立模块父任务。
- `T1.7` 承接中文公开语料的实际开发，包括 gov.cn 政策法规库、CCTV 新闻联播、CNInfo / AkShare 公告、PBOC 报告、授权研报元数据和 RAG-ready 索引。
- 首期优先实现 `T1.7.1-T1.7.4`：schema、provider registry、gov.cn 政策库列表 provider、正文 parser、字典缓存和 `npr` 兼容 API。
- CCTV、公告、PBOC 和研报元数据作为后续 provider，必须遵守来源、授权、as-of 和去重审计。
- 语料库只服务研究情报、事件解释和 RAG-ready 检索，不直接接入主 ranker，也不替代策略 admission。

本轮验证：

- `rg` 检查确认主索引、父计划和周清单已引用 `T1.7/W2.31`。
- `git diff --check -- docs/DEVELOPMENT_PLAN.md docs/tasks/README.md docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md` 通过。
- 新增三个数据源任务文件经行尾空白检查通过。
