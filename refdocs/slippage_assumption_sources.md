# A股个人交易滑点假设来源整理

> 生成日期：2026-05-31  
> 调研问题：普通个人 A 股交易者用于回测的合理滑点参数是多少？  
> 项目结论：`slippage = 0.001` 可作为基础研究假设；若要更接近普通个人实盘模拟，建议使用 `0.00246` 作为主测试值，并用 `0.003`、`0.005` 做压力测试。  
> 用途：记录本项目 `slippage` 参数取值依据。  
> 结论用途：仅用于回测研究假设，不构成实盘成交承诺。

## 1. Brave Search 插件检查

本机 OpenClaw 插件列表中存在 Brave Search provider：

- 插件名称：`Brave`
- 插件 ID：`brave`
- 状态：`enabled`
- 搜索 provider 状态：`available=true`、`configured=true`、`selected=true`
- 依赖环境变量：`BRAVE_API_KEY`

执行检查命令：

```bash
openclaw plugins list
openclaw infer web providers
```

但当前通过 CLI 调用搜索时报错：

```text
TypeError: (0 , _providerWebSearch.readPositiveIntegerParam) is not a function
```

因此，本次没有通过 OpenClaw Brave CLI 完成可复现下载。以下资料基于网页检索和公开页面整理，保留来源链接、关键依据和项目内结论，不保存网页全文。

## 2. 参考来源

### 2.1 JoinQuant / 聚宽

来源：

- https://cdn.joinquant.com/help/img/JoinQuantAPI.pdf
- https://www.joinquant.com/community/post/detailMobile?limit=20&postId=21365&tag=new

可采信点：

- 聚宽支持 `set_slippage` 设置回测滑点。
- 其股票百分比滑点示例/默认值中出现过 `PriceRelatedSlippage(0.00246)` 这一量级。
- `0.00246` 约等于 `0.246%`，接近本项目建议的普通个人实盘模拟主值 `0.20%` 到 `0.30%` 区间。

项目内解读：

- 对普通个人交易者，若使用非极速行情、非专业交易终端和普通网络，`0.001` 可能偏乐观。
- `0.00246` 更适合作为实盘模拟主值，`0.003` 适合作为保守压力值。

### 2.2 RiceQuant / RQAlpha

来源：

- https://www.ricequant.com/doc/rqalpha-plus/doc/advance-tutorial

可采信点：

- RQAlpha 支持价格比例滑点模型，例如 `PriceRatioSlippage`。
- 示例中可见 `--slippage 0.001` 这一量级。
- `0.001` 等于 `0.10%`，适合作为较乐观或研究基础假设。

项目内解读：

- 本项目当前 `slippage = 0.001` 不算离谱，但更像研究阶段基础假设。
- 若要模拟普通个人实盘，建议将主测试滑点提高到 `0.00246`。

### 2.3 PTrade / QMT 类接口资料

来源：

- https://quant.csdn.net/6874be0fbb9d8e0ecec2348d.html

可采信点：

- PTrade/QMT 类回测接口文章中常见 `set_slippage(slippage=0.001)` 示例。
- 这说明 `0.001` 是常见演示或基础回测量级。

项目内解读：

- `0.001` 可保留为“当前/基础”场景。
- 它不能单独代表普通个人交易者的稳定实盘成交质量。

### 2.4 滑点成因资料

来源：

- https://capital.com/zh-hans/learn/trading-strategies/price-slippage
- https://www.shinnytech.com/articles/reference/slippage

可采信点：

- 滑点来自预期成交价和实际成交价之间的偏差。
- 主要影响因素包括流动性、市场波动、下单类型、成交时点、盘口深度。
- 对普通个人交易者，硬件和网络速度只是因素之一，盘口厚度和行情波动通常更关键。

项目内解读：

- 同一滑点参数无法覆盖所有股票和所有行情。
- 大票、成交活跃、限价成交时，滑点可能低于 `0.001`。
- 小票、盘口薄、开盘跳动、追价成交时，`0.003` 甚至 `0.005` 都可能不够。

## 3. 本项目建议滑点区间

针对“硬件普通、软件普通、权限普通、网络速度普通”的个人交易者，本项目建议：

| 场景 | 滑点 | 含义 |
| --- | ---: | --- |
| 乐观 | `0.0005` | 流动性好、大票、限价成交、非急单 |
| 基础 | `0.0010` | 研究阶段基础假设 |
| 实盘模拟主值 | `0.00246` | 更适合普通个人交易者的默认实盘模拟 |
| 保守 | `0.0030` | 开盘成交、流动性一般、行情波动较大 |
| 压力 | `0.0050` | 小票、急涨急跌、盘口薄、追价成交 |

当前配置：

```yaml
slippage: 0.001
```

建议后续主测试配置：

```yaml
slippage: 0.00246
```

建议敏感性测试组合：

```text
0.0005 / 0.0010 / 0.00246 / 0.0030 / 0.0050
```

## 4. 结论

`slippage = 0.001` 可以继续作为基础研究假设，但对普通个人交易者偏乐观。若要让回测更接近实盘，应把 `0.00246` 作为主模拟值，并用 `0.003`、`0.005` 做压力测试。

后续与账户级仿真联动时，还应同时加入：

- 最低佣金
- A股 `100` 股整手
- 现金约束
- 停牌约束
- 涨跌停无法成交约束
- 开盘成交与收盘成交的成交价差异
