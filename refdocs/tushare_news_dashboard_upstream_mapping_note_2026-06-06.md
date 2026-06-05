# Tushare 聚合新闻看板上游来源调查与映射表

日期：2026-06-06  
类型：主题调查 note  
调查对象：`https://tushare.pro/news/sina` 及其同类聚合新闻看板  
目的：判断这些渠道新闻更接近哪些上游站点与页面流，而不是仅停留在 Tushare 自身接口名层面

---

## Abstract

本调查围绕 `tushare.pro/news/sina` 这类聚合新闻看板，目标不是判断 Tushare 是否存在某个新闻接口，而是尽可能推断这些聚合看板背后真实依赖的上游内容来源。调查结论是：这类看板高度可能建立在若干新闻站点的网页流、移动页、滚动页或内部 JSON/XHR 之上，而不一定对应每个渠道都有正式对外开放 API。就当前可验证信息来看，`major_news`、`cctv_news`、`realtime_quote`、`dc_hot` 等 Tushare 接口更像是它的产品层抽象；而真正上游来源更接近新浪财经、央视网、华尔街见闻、财联社、中证网、第一财经、凤凰财经、新华网等站点自身的页面流或抓取入口。

## 1. 调查范围与限制

### 1.1 调查范围

本次调查主要围绕以下问题：

1. `tushare.pro/news/sina` 这种渠道聚合页是否直接暴露可见 API
2. 如果没有直接暴露，可否通过现有文档和开源适配器反推它更可能依赖哪些上游站点
3. 哪些来源更接近“站点网页流”，哪些更接近“结构化可调用接口”

### 1.2 限制

- 该页面在无登录态下会进入前端壳和登录流程，无法直接看到最终新闻数据请求。
- 本次没有浏览器登录态抓包，因此不能对 Tushare 前端内部 XHR 路径做最终实锤。
- 本调查目标是“推断上游来源”，不是逆向恢复 Tushare 前端完整内部接口。

## 2. 当前能确认的事实

### 2.1 聚合页不是静态新闻列表

`https://tushare.pro/news/sina` 在无登录态下不是一个可直接抓取的静态新闻页，而是一个前端应用入口，并会转到登录态流程。这说明：

- 页面主体新闻内容不是直接写死在 HTML 中
- 实际数据大概率由前端运行后再请求
- 仅靠 `curl`/纯 HTML 很难直接看见最终数据源

### 2.2 Tushare 文档层的“渠道分类”与站点来源能对上

Tushare 官方 `major_news` 文档把渠道来源直接列成：

- 新华网
- 凤凰财经
- 同花顺
- 新浪财经
- 华尔街见闻
- 中证网
- 财新网
- 第一财经
- 财联社

这说明 Tushare 自己的产品层已经在按“上游新闻站点”组织来源，而不是只有一套自营内容库。

### 2.3 央视类来源可从开源适配器直接反推

本地 `akshare` 中的 `news_cctv` 实现直接抓取：

- `https://tv.cctv.com/lm/xwlb`
- `https://tv.cctv.com/lm/xwlb/day/YYYYMMDD.shtml`

文件位置：

- [news_cctv.py](/home/zj/workspace/stok-mapping/.venv/lib/python3.14/site-packages/akshare/news/news_cctv.py)

这说明“央视/新闻联播”这一类数据，在业界通用实践里本来就是直接抓央视网页正文，而不是依赖一个公开的正式 API。Tushare 的 `cctv_news` 很可能也是同类来源。

### 2.4 新浪财经存在历史可调用滚动新闻接口

新浪财经历史上有公开可拼接的滚动新闻接口：

```text
http://roll.news.sina.com.cn/interface/rollnews_ch_out_interface.php
```

第三方整理文档里明确记录过它的参数和频道编码，其中财经、股市、美股等频道都有对应 ID。虽然这不能直接证明 `tushare.pro/news/sina` 此刻一定使用该接口，但它说明：

- 新浪财经的新闻聚合并非只能靠 HTML 抓取
- 站内确实长期存在过结构化调用入口

## 3. 上游来源判断逻辑

本次调查采用的判断逻辑是：

1. 若官方文档明确写出 `src` 支持某渠道，则先认定 Tushare 产品层按该渠道分类。
2. 若该渠道在开源适配器或公开站点上存在稳定页面流，则优先视为真实上游来源候选。
3. 若无正式开放 API 证据，则默认更可能是网页流、移动页或内部 JSON/XHR，而非合作 OpenAPI。

## 4. Tushare 聚合新闻看板上游来源映射表

| 看板渠道 / 主题 | Tushare 产品层最可能对应 | 最可能真实上游来源 | 公开可见入口 | 更像正式 API 还是页面流 | 置信度 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 新浪财经 | `major_news(src='新浪财经')` | 新浪财经网页流、移动页、滚动新闻接口 | `finance.sina.com.cn` / `finance.sina.cn` / `roll.news.sina.com.cn` | 页面流 + 历史结构化接口混合 | 中高 | 能确认新浪是来源渠道；无法在无登录态下确认 Tushare 当前调用的是哪一个具体 endpoint |
| 华尔街见闻 | `major_news(src='华尔街见闻')` | 华尔街见闻快讯流 | `https://wallstreetcn.com/live` | 更像页面流或站内 JSON/XHR | 中高 | 可确认来源站点，未抓到内部 JSON 路径 |
| 财联社 | `major_news(src='财联社')` | 财联社电报流 | `https://m.cls.cn/telegraph` | 更像页面流或站内 JSON/XHR | 中高 | 很适合电报式聚合，但未见公开稳定官方 API |
| 第一财经 | `major_news(src='第一财经')` | 第一财经快讯/新闻流 | `www.yicai.com` | 更像页面流 | 中 | 可确认作为来源渠道存在，具体抓取入口未定位 |
| 中证网 | `major_news(src='中证网')` | 中证快讯 / 中证网新闻栏目 | `https://www.cs.com.cn/` / `https://www.cs.com.cn/sylm/jsbd/list.html` | 页面流 | 中高 | 对财经快讯类聚合较自然 |
| 凤凰财经 | `major_news(src='凤凰财经')` | 凤凰财经新闻流 | `finance.ifeng.com` | 页面流 | 中 | 来源站点明确，具体接口未定位 |
| 新华网 | `major_news(src='新华网')` | 新华网财经频道 | `www.news.cn` | 页面流 / 站内稿件流 | 中 | 更接近权威转载源 |
| 财新网 | `major_news(src='财新网')` | 财新新闻流 | `www.caixin.com` | 页面流，正文可能有付费墙 | 中 | 可做标题级聚合，正文抓取稳定性较差 |
| 同花顺 | `major_news(src='同花顺')` | 同花顺资讯流 | `stock.10jqka.com.cn` 等 | 页面流 | 中 | 更像聚合站点资讯来源，不像正式开放新闻 API |
| 央视 / 新闻联播 | `cctv_news` | 央视网新闻联播栏目页和日页 | `https://tv.cctv.com/lm/xwlb` / `https://tv.cctv.com/lm/xwlb/day/YYYYMMDD.shtml` | 页面流 | 高 | 有开源适配器直接证明此路径是可用来源 |
| 与新闻并排的实时价格 / 行情信息 | `realtime_quote(src='sina'/'dc')` | 新浪行情 / 东方财富行情接口 | `hq.sinajs.cn`、东方财富行情页 | 更像结构化行情接口 | 中 | 这部分不是新闻正文，但在看板中可能与新闻混排 |
| 热榜 / 题材 / 板块热度 | `dc_hot` / `dc_index` / `dc_concept` | 东方财富数据中心与概念板块页 | 东方财富站内接口与页面 | 页面流 + 结构化接口混合 | 中 | 不是新闻，但很可能出现在资讯看板侧边栏 |

## 5. 重点渠道补充说明

### 5.1 新浪财经

新浪财经是最值得单独盯住的来源，因为它兼具：

- 大量财经滚动新闻
- 历史上长期存在可拼接的滚动接口
- 现成的行情实时接口体系

但对本项目而言，需要区分三层：

1. **新闻正文与标题流**
2. **7x24 或滚动新闻流**
3. **行情实时数据**

这三者不一定来自同一接口。

### 5.2 华尔街见闻与财联社

这两类更像“快讯/电报流”来源，适合：

- 事件时间线
- 市场情绪解释
- 盘前盘中情绪辅助

但如果要做可复现研究，必须增加：

- 去重
- 同事件合并
- 时间戳统一
- 标题与正文清洗

### 5.3 央视

央视类数据是目前最容易确定来源的，因为：

- 来源站点单一
- 版式相对稳定
- 开源适配器已证明可抓

它适合做：

- 宏观政策背景梳理
- 官方叙事观察
- 长文本解释层

不适合做高频即时交易信号。

## 6. 对本项目的工程建议

### 6.1 如果目标是复刻聚合新闻看板

不必先执着于逆向 Tushare 自己的前端内部接口。更务实的路径是直接围绕这些上游来源建自己的聚合层：

- 新浪财经
- 华尔街见闻
- 财联社
- 中证网
- 央视网
- 第一财经
- 新华网

### 6.2 如果目标是正式接入研究系统

建议优先顺序：

1. 官方公告与法定披露：优先 `anns_d` 或官方公告源
2. 券商研报：`research_report`
3. 结构化主新闻流：`major_news`
4. 主题化快讯源：华尔街见闻 / 财联社 / 新浪 7x24

不要把单一页面抓取直接当作长期主源，除非：

- 已验证可稳定访问
- 有明确去重策略
- 有错误恢复与回补机制
- 已接受页面结构变化的维护成本

## 7. 当前调查结论

本次调查能较稳地确认：

1. `tushare.pro/news/sina` 这类看板不是静态页，新闻数据在前端运行后才加载。
2. Tushare 的聚合新闻产品层很可能就是把多个上游站点按渠道统一包装。
3. 这些上游来源多数更像网页流、移动页或内部 JSON/XHR，而不是公开正式 OpenAPI。
4. `央视` 是目前最容易确认真实来源的一类，基本可视为直接来自 `tv.cctv.com`。
5. `新浪财经` 最可能来自其网页流、移动页或历史滚动新闻接口，但当前无登录态下无法实锤到具体 endpoint。

## 8. 参考资料

- Tushare `major_news` 文档：<https://tushare.pro/document/2?doc_id=195>
- Tushare `cctv_news` 文档：<https://tushare.pro/document/2?doc_id=154>
- Tushare `realtime_quote` 文档：<https://www.tushare.pro/document/2?doc_id=315>
- Tushare `dc_hot` 文档：<https://tushare.pro/document/2?doc_id=321>
- Tushare `dc_index` 文档：<https://tushare.pro/document/2?doc_id=362>
- Tushare `dc_concept` 文档：<https://tushare.pro/document/2?doc_id=421>
- 开源适配器 `news_cctv.py`：[`akshare/news_cctv.py`](/home/zj/workspace/stok-mapping/.venv/lib/python3.14/site-packages/akshare/news/news_cctv.py)
- 新浪滚动新闻历史接口整理：<https://www.cnblogs.com/MDK-L/p/3785925.html>
- 新浪行情接口示例整理：<https://www.cnblogs.com/zeroes/p/sina_stock_api.html>
- 华尔街见闻快讯页：<https://wallstreetcn.com/live>
- 财联社电报页：<https://m.cls.cn/telegraph>
- 中证快讯页：<https://www.cs.com.cn/sylm/jsbd/list.html>

## 9. 局限

- 本次没有登录态浏览器抓包，因此不能直接证明 Tushare 前端内部调用了哪一条 XHR。
- 对新浪财经的“真实 endpoint”判断目前仍是高概率推断，不是网络层实锤。
- 外部站点页面、移动页和历史接口都可能变化，不能把本 note 当作长期不变的事实表。
