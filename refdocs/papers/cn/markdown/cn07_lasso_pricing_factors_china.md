---
id: "cn07_lasso_pricing_factors_china"
title: "基于双重选择LASSO模型的我国股市定价因子边际有效性研究"
year: 2024
doi: "10.12011/SETP2023-0831"
venue: "系统工程理论与实践"
market_scope: "我国股市 / A股"
paper_url: "https://sysengi.cjoe.ac.cn/CN/10.12011/SETP2023-0831"
pdf_url: "https://sysengi.cjoe.ac.cn/CN/PDF/10.12011/SETP2023-0831"
---
## Page 1

第 44 卷 第 9 期 系统工程理论与实践 Vol. 44, No. 9
2024 年 9 月 Systems Engineering — Theory & Practice Sept., 2024
doi: 10.12011/SETP2023-0831 中图法分类号: F830.91; F830.59 文献标志码: A
基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究
毛 杰 1,2, 陈宓舟3,4,5, 许 磊 5, 杜树楷5
(1. 上海大学 经济学院 , 上海 200444; 2. 复旦大学 金融研究中心 , 上海 200433; 3. 东方证券股份有限公司博士后
工作站, 上海 200010; 4. 东方证券股份有限公司金融产品总部, 上海 200010; 5. 上海财经大学 金融学院 , 上海 200433)
摘 要 在高维数据背景下, 传统的因子定价估计方法可能无法准确判断定价因子的有效性.
鉴此, 本文构建了双重选择 LASSO 模型, 估计了定价因子的随机贴现因子载荷, 以替代估计
风险溢价的传统因子估计方法 , 籍以在高维数据背景下准确判断出定价因子的边际有效性 .
本文继而收集了 85 个资产定价因子, 构建了我国股市的高维定价因子库, 并发现在 2014 年
之后发现的 15 个定价因子中有 7 个定价因子是边际有效定价因子. 此研究结论在多种稳健
性检验下都基本保持一致, 由此多番验证了本文实证方法的稳健性. 通过进一步分析, 本文还
在时变随机贴现因子的情况下发现了上述定价因子的有效性基本保持一致.
关键词 定价因子边际有效性; 双重选择 LASSO 模型; 随机贴现因子; 机器学习; 因子库
Research on the marginal effectiveness of Chinese stock markets’
pricing factors: Application of double-selection LASSO model
MAO Jie 1,2, CHEN Mizhou 3,4,5, XU Lei 5, DU Shukai 5
(1. School of Economics, Shanghai University, Shanghai 200444, China; 2. Financial Research Center, Fudan University,
Shanghai 200433, China; 3. Postdoctoral Workstation, Orient Securities Co., Ltd., Shanghai 200010, China; 4. Financial
Products Division, Orient Securities Co., Ltd., Shanghai 200010, China; 5. School of Finance, Shanghai University of Finance
and Economics, Shanghai 200433, China)
Abstract In the present era of high-dimensional data, it is quite unlikely that the traditional
methods for estimating pricing factors are capable of judging accurately the marginal effectiveness
of pricing factors applicable to the Chinese stock markets. Hence we construct a double-selection
LASSO model, instead of the traditional methods which estimate stock pricing factors mainly
by estimating risk premium. And then by means of this double-selection LASSO model, we
estimate stochastic discount factors loading, thereby being able to judge accurately the marginal
effectiveness of stock pricing factors while processing high-dimensional data. Next, we gather
together 85 pricing factors applicable to the Chinese stock markets, thus building up a high-
dimensional pricing factor zoo. In addition, we identify 7 marginally effective pricing factors out
of the 15 factors discovered after 2014. Our discovery proves consistent in various robustness
收稿日期: 2023-04-28
作者简介: 毛杰 (1990–), 男, 汉, 上海人, 博士, 讲师, 研究方向: 资产定价理论与实证, E-mail: jiemao@shu. edu.cn;
通信作者: 陈宓舟 (1991–), 男, 汉, 上海人, 博士, 研究方向: 资产定价与机器学习, E-mail: chenmizhou@126.com. 许磊
(1980–), 男, 汉, 上海人, 博士研究生, 研究方向: 资产定价与股权投资, E-mail: brianlxu@163.com; 杜树楷 (1992–), 男,
汉, 河南安阳人, 博士研究生, 研究方向: 资产定价, E-mail: dushukai@163.sufe.edu.cn;
基金项目: 国家社会科学基金重大项目 (20&ZD102); 上海高水平地方高校创新团队项目
F oundation item: Major Program of National Fund of Philosophy and Social Science of China (20&ZD102);
Innovation Fund for Prestigious Universities in Shanghai
中文引用格式: 毛杰, 陈宓舟, 许磊, 等. 基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究 [J]. 系统工程
理论与实践, 2024, 44(9): 2993– 3005.
英文引用格式 : Mao J, Chen M Z, Xu L, et al. Research on the marginal effectiveness of Chinese stock markets’
pricing factors: Application of double-selection LASSO model[J]. Systems Engineering — Theory & Practice, 2024,
44(9): 2993– 3005.


## Page 2

2994 系 统 工 程 理 论 与 实 践 第 44 卷
tests. We further find in the follow-up analysis that the effectiveness of these 7 pricing factors
proves consistent under the conditions of time-varying SDF.
Keywords pricing factors’ marginal effectiveness; double-selection LASSO model; stochastic
discount factor; matching learning; factor zoo
1 引言与文献回顾
自三因子模型 [1] 提出以来, 股票预期横截面收益的解释因子层出不穷 [2−4], 至今已达数百个之
多 [5−7]. 但使用这数百个因子直接对股票市场进行定价会产生多重共线问题、 模型误设问题、 维数诅咒
问题. 因而, 尤有必要考察因子之间的结构、稀疏性、非线性 [8], 从数百个因子的高维数据集合中筛选
出真正有效的定价因子、 过滤掉冗余的定价因子和无效的定价因子, 确定出每一个新因子对于解释股票
横截面预期收益的边际贡献, 才能充分挖掘出数百个因子的高维数据中所蕴藏的真正信息 , 从而更为有
效和准确地对股票市场进行定价. 纵观高维数据下股票市场因子定价的既有文献, 大多使用了主成分分
析 (PCA)[9−14]、LASSO 回归 [15−17]、 弹性网络(Elastic Net) [18] 三种不同的方法.
我国股市的高维因子定价研究尚处于起步阶段 . Jiang 等 [19]、 李斌等 [20]、 姜富伟等 [8,21] 先后
使用主成分分析、 LASSO 回归、 岭回归、 弹性网络等机器学习的基础方法探究了定价因子在股票横
截面收益上的解释能力. 然而, 主成分分析、LASSO 回归、岭回归、弹性网络等基础方法都有着不同
弱点, 譬如: 1) 使用主成分分析所构建的新定价因子 , 往往包含了多个候选定价因子的信息 , 因而新的
PCA 定价因子拥有了多个候选定价因子的经济含义 . 倘若所包含的候选定价因子经济含义之间差异较
大, 那么新 PCA 定价因子的经济含义便非常模糊 . 2) LASSO 模型在小样本情况下往往达不到先知性
质 (Oracle 性质), 使得最后的因子结构过于稀疏, 从而会遗漏重要的定价因子而错误定价. 3) 岭回归方
法通常用于收缩系数, 并不具备降维功效, 而弹性网络方法的降维功效取决于对 L1 范数惩罚权重的大
小, 因而使用这两种方法筛选出的因子模型可能仍有较多的冗余因子和无效因子.
同时, 我国股市作为一个新兴市场 , 存在着不同于成熟市场的显著特征 , 譬如: 1) 就市场参与者而
言, 我国股市约 90% 是散户投资者, 他们的短视预期和非理性行为形成了我国股市的独特风格; 2) 就交
易工具而言, 我国衍生品市场发展相对滞后, 因而我国股市缺少足够的风险管理工具和畅通的卖空机制,
与衍生品相关的定价因子也就无法参与我国股市的因子定价; 3) 就信息披露而言, 我国的会计准则与国
际财务报告准则并不相同 , 因此某些财务定价因子参与我国股市的因子定价就需要考虑我国财务报告
制度的不同 [22−24]. 正是由于我国股市的诸多特征, 形成了我国股市在因子定价上的诸多差异.
有鉴于此, 本文参考 Belloni 等 [25] 和 Feng 等 [17], 构建双重选择 LASSO 模型 (后文简称为 DS-
LASSO 模型), 考察和研究了高维数据背景下我国股市定价因子的边际有效性问题 . 具体而言, 本文根
据既有文献和我国股市的现实情况 , 收集了我国股市的 85 个定价因子, 以此构建了我国股市的高维定
价因子库, 使用了 DS-LASSO 模型考察和研究了我国股市的定价因子对于解释股票横截面预期收益的
边际贡献.
与既有相关文献作比较, 本文大抵有两方面的边际贡献: 1) 本文在研究方向上的边际贡献是率先在
高维数据背景下研究了我国股市定价因子边际有效性问题 . 众多的既有相关文献多是研究我国股市因
子的定价问题 [26], 而鲜有文献研究了定价因子的边际有效性问题 . 有鉴于现有文献在此研究方向上的
不足, 本文拾遗补缺通过构建 DS-LASSO 模型率先在高维数据背景下研究了我国股市定价因子的边际
有效性问题. 2) 本文在研究方法上的边际贡献是率先基于 SDF 载荷研究了我国股市的定价因子. 众多
的既有相关文献都是基于风险溢价来研究我国股市的定价因子 [26], 而风险溢价并不能完全反映定价因
子的有效性. 本文则根植于随机贴现因子理论 , 使用 SDF 载荷研究了高维数据背景下的我国定价因子
的有效性, 具有比较可靠的理论研究基础. 本文的研究不仅深化了高维数据背景下我国股市因子定价的
既有认识, 也为投资者的投资决策起到了一定的指导作用 , 同时也为监管机构在高维背景下监管我国股
市异常波动、 纠正我国股市错误定价、 提高我国股市的定价效率提供了一定的理论借鉴.


## Page 3

第 9 期 毛杰, 等: 基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究 2995
2 实证原理与方法
2.1 实证原理: 随机贴现因子载荷
定价因子在解释股票横截面收益上是否有效 , 关键在于其随机贴现因子载荷 (SDF loadings) 的显
著性, 而不是其风险溢价的显著性 [27]. 因而本文假设随机贴现因子的线性规范表达式为:
mt ≜ γ−1
0 − γ−1
0 λ⊤
v vt, (1)
式 (1) 中, mt 表示随机贴现因子, γ0 表示 0-beta 收益率, vt 表示高维的定价因子向量, λv 表示 vt 的随
机贴现因子载荷. 倘若 SDF 载荷 λv 显著异于零, 定价因子 vt 便是有效的. 然而, 随机贴现因子 mt 是
不可直接观测的. 根据随机贴现因子的性质, 随机贴现因子 mt 和股票预期收益率 rt 之间满足:
E (rt) = 1 nγ0 − Cov (rt, mt) γ0, (2)
式 (2) 中, rt 表示 n × 1 的股票预期收益率向量, 1n 表示 n × 1 的的单位向量, Cov (rt, mt) 表示随机贴
现因子与股票预期收益率的协方差. 将式 (1) 代入式 (2) 中便可得到高维因子向量与股票预期收益率的
之间协方差与股票预期收益率的关系:
E (rt) = 1 nγ0 + Cov (rt, vt) λv, (3)
式 (3) 中, Cov (rt, vt) 表示因子向量与股票预期收益率的协方差. 本文不失一般性地假设对因子向量 vt
进行了中心化处理, 即 E (vt) = 0 .
然而, 高维因子向量中的因子并非都是有效的定价因子 (即因子的 SDF 载荷显著异于零), 还包含
了大量的冗余因子 (即因子的 SDF 载荷为零、 但因子的风险溢价显著异于零) 和大量的无效因子 (即因
子的 SDF 载荷和风险溢价同时为零). 换言之, 只有筛选出有效因子、 淘汰掉无效因子和冗余因子, 才能
在高维因子向量中得到真正的定价因子. 为此, 本文将高维因子向量 vt 分为两个部分: p 维的初始定价
因子 (existing factors) 向量 ht 和 d 维的候选定价因子 (testing factors) 向量 gt. 此时, 式 (3) 可改写为
E (rt) = 1 nγ0 + Cov (rt, ht) λh + Cov (rt, gt) λg, (4)
式 (4) 中, Cov (rt, ht) 表示初始定价因子向量与股票收益率的协方差 , 而 Cov (rt, gt) 则表示候选定价
因子与股票收益率的协方差, λh 和 λg 分别表示初始定价因子和候选定价因子的 SDF 载荷. 当候选定
价因子的 SDF 载荷 λg 显著异于零时, 此候选定价因子对股票横截面预期收益的解释便有着边际贡献 ,
即此候选定价因子是有效的定价因子, 应作为真正的因子参与定价, 故而 λg 便是本文考察的重点.
2.2 实证方法: DS-LASSO 模型
如前文所述, 定价因子在解释股票横截面收益上是否有效, 关键在于其 SDF 载荷的显著性, 而不是
其风险溢价的显著性. 鉴此, 本文参考 Belloni 等 [25] 和 Feng 等 [17], 构建 DS-LASSO 模型, 从候选定
价因子中筛选出真正的定价因子, 并据此对我国股票市场进行因子定价. DS-LASSO 模型能够使得无效
定价因子和冗余定价因子的 SDF 载荷为零, 得以符合定价因子有效性的定义. 整个 DS-LASSO 模型分
为三步: 1) 横截面的 LASSO 回归
将股票收益的样本均值对初始定价因子与股票收益率的样本协方差进行横截面的 LASSO 回归:

bγ, bλ

=arg min
γ,λ
n
n−1
¯r − 1nγ − λ dCov (rt, ht)

2
+ τ1n−1∥λ∥1
o
, (5)
式 (5) 中, ¯r 表示股票收益的时间序列均值, dCov (rt, ht) = 1
T
PT
t=1 (rt − r)(ht − h) 表示初始定价因子向
量与股票收益率的样本协方差, n 表示样本量, τ1 表示 LASSO 回归的正则化参数, ∥.∥1 表示 L1 范数,
∥.∥2 表示 L2 范数, bγ 和 bλ 是横截面 LASSO 回归的估计结果. 若第 i 个初始定价因子的 LASSO 回归


## Page 4

2996 系 统 工 程 理 论 与 实 践 第 44 卷
结果 bλi 显著异于零, 那么此因子便作为有效因子进入定价模型 , 反之则是无效因子或冗余因子剔除出
定价模型. 本文将筛选出的所有有效因子归入集合 {I1} 中, 作为第一重选择 LASSO 模型的结果.
2) 逐步 LASSO 回归
由于第一步的横截面 LASSO 回归可能会过度稀疏从而导致遗漏变量问题, 本文继而进行第二步的
逐步 LASSO 回归. 本文将每个候选定价因子与股票收益率的样本协方差对初始定价因子向量与股票收
益率的样本协方差逐一进行 LASSO 回归

bξj, dχj,i

= arg min
ξj ,χj,i
n
n−1


dCov (rt, gt,j) − 1nξj − dCov (rt, ht) χ⊤
j,i

2
+ τ2jn−1χ⊤
j,i

1
o
, (6)
式 (6) 中, i = 1, · · · , p 表示第 i 个初始定价因子, j = 1, · · · , d 表示第 j 个候选定价因子, dCov (rt, gt,j)
表示第 j 个候选定价因子与股票收益率的样本协方差 , τ2j 表示第 j 次 LASSO 回归的正则化参数, bξj
和 dχ⊤
j,i = ( dχj,1, dχj,2, . . . , dχj,p)⊤ 是第 j 次 LASSO 回归的估计结果. 若在第 j 次 LASSO 回归中, 第 i 个
初始定价因子的 LASSO 回归结果 dχj,i 显著异于零, 那么此因子便重新作为有效因子进入定价模型, 反
之则仍然判定为无效因子或冗余因子剔除出定价模型 . 本文而后将共 d 次筛选出的所有新的有效因子
归入集合 {I2} 中, 作为第二重选择 LASSO 模型的结果, 由此得以避免横截面 LASSO 回归的过度稀疏
而导致的遗漏变量问题.
3) 筛选后的 OLS 回归
本文最后将前两步中所筛选出的初始定价因子和候选定价因子共同纳入定价模型之中进行 OLS 回
归, 来对股票横截面预期收益率进行解释

bγ0, cλh, cλg

= arg min
γ0,λh,λg
n¯r − 1nγ0 − λh dCov (rt, ht) − λg dCov (rt, gt,j)

2
, λh,i = 0, ∀i /∈ I1
[
I2
o
,
(7)
式 (7) 中, bγ0、cλh、cλg 表示 OLS 回归的估计结果, 其中的 cλg 便是式 (4) 所示的重点考察对象. 倘若
cλg 显著异于零, 候选定价因子 gt 则对于股票横截面预期收益的解释具有边际贡献. 尤需说明, 倘若第 i
个初始定价因子未在第一和第二步中被确定为有效的定价因子, 此定价因子便不在集合 {I1
S I2} 之中,
那么此定价因子的 SDF 载荷便为零, 即 λh,i = 0.
在 LASSO 回归式 (5) 和 (6) 中, 参数估计是依赖于两个正则化参数 τ1 和 τ2j. 本文借鉴 Hastie
等 [28], 使用交叉验证方法 (Cross Validation) 校验了两个正则化参数. 具体而言, 本文使用 4 折交叉验
证 (4-fold CV) 校验了 DS-LASSO 模型的这两个正则化参数 τ1 和 τ2j 1: 将样本随机地划分成四个不相
交的子样本, 其中三个子样本作为训练集 (training set), 剩余的一个子样本作为验证集 (validation set),
根据 4 种情况训练得到模型的最优参数. 有鉴于样本划分的随机性, 本文使用了 200 个不同的随机数种
子 (random seed) 进行了 200 次不同的 4 折交叉验证, 每个随机数种子的交叉验证都遍历 100 个正则
化参数 τ1 和 τ2j, 根据最小 MSE 准则校验出一组最优的正则化参数 τ1 和 τ2j, 并使用最优的正则化参
数 τ1 和 τ2j 来估计 DS-LASSO 模型.
3 变量选取与样本描述
3.1 变量选取
本文实证分析的自变量是已被挖掘出的定价因子 , 具体而言, 本文根据既有文献和我国股市的实际
情况收集了我国股市的 85 个定价因子 (包括 48 个财务基本面因子、12 个分析师行为因子、9 个波动因
子等), 并以此构建了高维定价因子库来考察和研究定价因子边际有效性. 定价因子的具体计算过程可分
为三种. 1) 对于一般性的定价因子, 本文按相关特征与公司规模进行双重排序, 构建多空投资组合并计
算而得: 将股票的月收益率按相关特征的高低分为高 30%、中 40%、低 30% 三组, 同时将股票的月收
益率按公司规模 (流通市值的对数值) 分成大小两组, 由此 3 × 2 双重排序共分得 6 组; 再在每组组内计
1出于稳健考虑, 本文也使用了 10 折交叉验证来校验 DS-LASSO 模型的两个正则化参数 τ1 和 τ2j, 具体结果篇幅而
无法刊告, 但已留存备索.


## Page 5

第 9 期 毛杰, 等: 基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究 2997
算个股市值加权的平均收益率 ; 最后构建多空组合计算出此特征的定价因子 . 2) 对于特别的定价因子,
本文按文献所指定的方法进行计算 , 譬如: 动量因子 UMD 是将动量特征十等分, 然后将高动量组合的
收益率减去低动量组合的收益率计算而得, 投资因子 HXZIA 和盈利因子 HZXROE 按投资、盈利、规
模 3×3×2 三重排序共分得 18 组, 由此构建多空组合计算出定价因子 . 3) 对于需要通过定价模型回归
的定价因子, 本文均以 Fama-French 三因子模型为基准进行回归提取其残差项进行计算, 如特质波动因
子 IVOL 和特质动量因子 IMOM. 尤需说明, 按照既有文献, 本文在构建定价因子的过程中会在每年 6
月底对多空投资组合进行调仓, 重新调整投资组合内的股票.
为了考察和研究因子的边际有效性 , 需要将定价因子划分为初始定价因子和候选定价因子两个部
分. 本文以 2014 年为分割界限, 将 2014 年之前被挖掘的 70 个定价因子设为初始定价因子, 而将 2014
年之后才被挖掘出的 15 个定价因子设为候选定价因子, 以保证定价因子在时间序列上有足够的观测.
本文实证分析的因变量是股票投资组合的预期收益率. 有鉴于单个股票的因子暴露并不稳定、 信噪
比较低 [17], 而基于少数几个特征的投资组合可能会导致估计有偏 [29], 本文根据 Lewellen 等 [30] 基于大
量特征构建投资组合, 将投资组合的预期收益率作为实证分析的因变量 . 具体而言, 本文按公司规模和
剩余 84 个特征进行 2×3 的投资组合分类, 共得到 504 个投资组合的预期收益率.
3.2 变量来源与描述性统计
本文数据来源于 WinD 数据库. 本文实证样本为沪深 A 股股票 (但不包括 A 股中 ST 股票、 退市公
司股票、 每期刚上市不满两周的公司股票); 按照我国股市的行业习惯, 无风险利率为 3 个月整存整取定
期利率的月化利率. 实证样本的时间跨度为 2006 年 1 月至 2019 年 12 月, 共 14 个年度 168 个月度. 本
文还对特征变量进行中心化处理 [22], 以确保不同行业下公司特征具有可比性 . 本文使用 Matlab2015b
完成了所有数据处理和实证分析. 实证分析中定价因子的定义和描述性统计详见本文附录.
在高维数据背景下, 因子库中的定价因子往往具有较强的相关性 . 本文因而对 85 个定价因子进行
相关性分析, 相关系数的热力图详见图 1.
图 1 因子相关系数的热力图


## Page 6

2998 系 统 工 程 理 论 与 实 践 第 44 卷
在图 1 中, 上横轴和左竖轴表示了第 1 至第 85 号定价因子的因子序号 ; 下横轴的颜色表示了
Pearson 相关系数的大小, 对应于图 1 中的左下三角区域, 其中深色表示两定价因子相关, 而白色表示两
定价因子不相关; 右竖轴代表了 Pearson 相关系数的显著性, 对应于图中的右上三角区域 , 其中灰色表
示 Pearson 相关系数显著 (即 P 值小于 5%), 而白色表示 Pearson 相关系数不显著 (即 P 值大于 5%).
如图 1 的左下三角区域所示, 区域的格点大多呈深色, 表明我国股市中的大部分定价因子之间都有
较强的相关性. 再如图 1 的右上三角区域所示, 区域的格点大多呈灰色, 表明我国股市中定价因子之间
的相关性大多较为显著. 由此显见, 在高维数据背景下直接使用定价因子库中的因子对股票横截面预期
收益进行解释和预测, 直接使用定价因子库中的因子检验定价因子的有效性 , 容易导致定价的错误和非
有效. 因而, 使用定价因子库中的因子时需要进行降维处理 , 从因子库中正确筛选出有效定价因子、剔
除出无效定价因子和冗余定价因子, 才能正确检验我国股市定价因子的有效性.
4 实证检验与分析
4.1 第一步: 横截面的 LASSO 回归
根据前文的实证方法, 本文首先将投资组合的预期收益率对 70 个初始定价因子与投资组合收益率
的样本协方差进行横截面的 LASSO 回归. 横截面 LASSO 回归的结果详见图 2 和图 3.
如图 2 所示, 在第一步横截面 LASSO 回归中, 70 个初始定价因子 ht 在 200 次随机抽取过程中多
数定价因子被剔除了, 只有少量定价因子留下了. 平均而言, 每次随机抽取筛选出 7 个有效的定价因子,
多数情况下仅筛选出 1 至 2 个有效的定价因子.
再如图 3 所示, 在 200 次随机抽取过程中, 70 个初始定价因子中规模因子 SMB 被筛选中次数最
多, 有接近 70% 的概率被筛选成有效因子. 此外, 换手率因子 Turn、分析师预测偏差因子 AF_Error、
分析师覆盖因子 AF_Num、分析师预测分歧因子 AF_Div2、特质波动因子 IVOL、收入存货比因子
OR/Inv 依次也具有较高的概率被筛选成有效因子. 而其余因子被筛选为有效因子的概率不足 25%.
第一步横截面 LASSO 回归的结果, 意味着只有少数定价因子被筛选成了有效因子纳入了定价模
型. 因而, 第一步横截面 LASSO 回归的结果过于稀疏, 从而引致遗漏变量问题, 最终引发因子定价的错
误和非有效. 具体而言, 在判断候选定价因子的有效性、考察候选定价因子在解释股票横截面预期收益
的边际贡献时, 候选定价因子很可能与初始定价因子中的遗漏因子有关 , 由此候选定价因子的有效性很
可能来源于其与遗漏因子的相关性, 而并非缘于候选定价因子是真正有效的定价因子.
0
10
20
30
40
50
60
70
80
0 50 100 150 200
被选中因子个数
随机子样本
图 2 200 次随机抽取子样本下筛选出的定价
因子个数
 图 3 第一步横截面 LASSO 回归下定价因子
被筛选出的概率
4.2 第二步: 逐步 LASSO 回归
为了解决横截面 LASSO 回归结果过于稀疏的问题, 本文继而将每个候选定价因子与投资组合收益
率的样本协方差对初始定价因子向量与投资组合收益率的样本协方差进行逐步 LASSO 回归, 籍以增补
遗漏的初始定价因子. 逐步 LASSO 回归的结果详见图 4 和图 5.
如图 4 和图 5 所示, 在第二步逐步 LASSO 回归下, 每个候选定价因子都会增补一部分初始定价因


## Page 7

第 9 期 毛杰, 等: 基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究 2999
子作为有效因子, 平均而言有 24 个初始定价因子会被增补为有效因子, 多数情况下有 12 至 13 个初始
因子会被增补为有效因子, 其中被增补概率最高的初始定价因子依次为市盈率因子 EP、分析师预测分
歧因子 AF_Div2、 预期外盈利因子SUE1、 营业收入增长因子dOR、 上市时间因子ListAge、 总资产周
转率因子 TAT. 通过增补第二步逐步 LASSO 回归所得出的定价因子, 便可解决第一步横截面 LASSO
回归结果过于稀疏的问题, 缓解遗漏变量问题从而有助于因子正确有效地定价2.
0
10
20
30
40
50
候选因子入选个数
图 4 第二步逐步 LASSO 回归下每个候选因子平均增补
初始因子的个数
 图 5 第二步逐步 LASSO 回归下初始因子被增补的概率
4.3 第三步: 筛选后的 OLS 回归
本文最后将横截面的 LASSO 回归和逐步 LASSO 回归所筛选出的初始定价因子和候选定价因子
共同纳入定价模型之中进行 OLS 回归, 来考察候选定价因子在解释股票横截面预期收益的边际贡献 ,
籍以判断候选定价因子的边际有效性. 基于 DS-LASSO 模型的检验结果详见表 1.
如表 1 第 3 列的基于 DS-LASSO 模型结果所示, 在 15 个候选定价因子中 , 低 Beta 因子 BAB、
盈利因子 RMW、盈利因子 HXZROE、投资因子 HXZIA、管理费用因子 dSGA、预期投资增长因子
HXZq5、 隔夜收益率因子Overnight 的估计系数均至少在 5% 的置信水平下显著. 此实证检验的结果表
明: 在控制了初始定价因子影响后, 仅有这七个候选定价因子对股票横截面预期收益的解释有着显著的
边际贡献、 可作为有效定价因子, 而剩余的八个候选定价因子并没有显著的边际贡献、 应该作为冗余定
价因子或无效定价因子.
本文还展示了单一选择 LASSO 回归 (后文简称为 SS-LASSO 模型)、Fama-French三因子模型 (后
文简称为 FF3 模型)、Carhart 四因子模型 (后文简称为 CH4 模型)、 简单OLS 回归 (后文简称为 OLS
模型) 的结果, 与 DS-LASSO 模型的结果作对比.
如表 2 第 4 列的 SS-LASSO 模型结果所示, 在 15 个候选定价因子中, 盈利因子 HXZROE、投资
因子 HXZIA、 经营成本因子OC/TA、 管理费用因子dSGA、 异常换手率因子ATurn、 隔夜收益率因子
Overnight 的估计系数均至少在 5% 的置信水平下显著. 对比表 1 第 3 列和第 4 列, 可以发现: 1) 盈利
因子 HXZROE、投资因子 HXZIA、管理费用因子 dSGA、隔夜收益率因子 Overnight 这四个定价因
子的估计系数在 DS-LASSO 模型和 SS-LASSO 模型中都保持显著; 2) 经营成本因子 OC/TA、 异常换
手率因子 ATurn 这两个定价因子的估计系数仅在 SS-LASSO 模型中保持显著, 而在 DS-LASSO 模型
中并不显著, 这有可能是在初始定价因子筛选时遗漏了真正的定价因子 , 从而使得这两个与真正定价因
子相关的定价因子在形式上变得显著了 ; 3) 低 Beta 因子 BAB、盈利因子 RMW、预期投资增长因子
HXZq5 这三个定价因子的估计系数仅在 DS-LASSO 模型中保持显著, 而在 SS 模型中并不显著, 这有
可能是在初始定价因子筛选时遗漏了真正的定价因子, 从而降低了 SDF 载荷估计的有效性.
再对比表 1 第 3 列和第 5、 第 6 列, 可以发现: 1) 低 Beta 因子 BAB、 盈利因子 HXZROE、
投资因子 HXZIA、 管理费用因子 dSGA、 隔夜收益率因子 Overnight 这五个定价因子的估计系数在
DS-LASSO 模型、 FF3 模型、 CH4 模型三种模型中大多都保持显著 , 表明这四个定价因子始终有效 ,
2第二步逐步 LASSO 回归下每个候选定价因子的实证结果囿于篇幅而无法刊告, 但已留存备索.


## Page 8

3000 系 统 工 程 理 论 与 实 践 第 44 卷
是有效定价因子 ; 2) 盈利因子 RMW 和预期投资增长因子 HXZq5 这两个定价因子的估计系数仅在
DS-LASSO 模型中保持显著, 而在 FF3 模型和 CH4 模型中并不显著, 但它们仍是有效定价因子, 个中
缘由是 Fama-French 三因子模型和 Carhart 四因子模型可能会引发遗漏变量问题最终导致定价错误或
者定价非有效; 3) 偏度因子 Skew、 盈利因子ROA、 异常换手率因子ATurn、 日内累计收益因子Inday
这四个定价因子的估计系数仅在 FF3 模型和 CH4 模型中保持显著, 而在 DS-LASSO 模型中并不显著,
表明这三个定价因子是冗余定价因子, 它们对于解释股票横截面预期收益的边际贡献并不明显; 4) 投资
因子 CMA、经营成本因子 OC/TA、管理费用因子 SGA/TA、低相关系数因子 BAC 这四个定价因子
的估计系数在 DS-LASSO 模型、FF3 模型、CH4 模型三种模型中大多都不显著, 表明这四个定价因子
是无效定价因子.
还如表 1 第 7 列的 OLS 模型结果所示, 在 15 个候选定价因子中, 仅有盈利因子 RMW 和盈利因
子 ROA 的估计系数在 5% 的置信水平下显著. 然而, 使用简单 OLS 回归所得的估计系数仅仅是因子
的风险溢价, 而不是因子的 SDF 载荷, 无法代表因子的定价能力.
为了细化表 1 第 3 列 DS-LASSO 模型的结果, 考察候选定价因子边际贡献的稳健性 , 本文进而
以热点图方式展现出 200 次交叉验证下候选定价因子估计系数的显著性随正则化参数调整的变化趋势.
调整正则化参数的热点图详见本文附录.
表 1 基于 DS-LASSO 模型的检验结果
ID Factor DS-LASSO SS-LASSO FF3 CH4 OLS
71 低 Beta 因子 BAB
302.56*** −50.49 −243.39*** −219.01*** 304.90
[3.64] [−0.84] [−5.16] [−4.54] [1.73]
72 偏度因子 Skew 38.57 46.31 −66.56*** −44.18** −42.24
[1.23] [1.85] [−5.16] [−2.98] [ −0.66]
73 盈利因子 RMW 460.15*** 41.28 5.52 27.94 597.47**
[6.30] [0.78] [0.20] [0.99] [3.06]
74 盈利因子 ROA −103.37 81.52 94.98** 148.42*** 878.25*
[−0.49] [0.63] [2.87] [4.05] [2.62]
75 投资因子 CMA −54.05 32.18 −24.96 7.22 58.88
[−0.91] [0.95] [−1.19] [0.33] [0.58]
76 盈利因子 HXZROE −123.69** −89.87** −121.95*** −104.69*** −99.45
[−2.80] [−2.83] [−3.42] [−3.15] [ −1.08]
77 投资因子 HXZIA −119.76* −127.52* −171.71** −158.39** 21.22
[−2.06] [−2.08] [−2.92] [−2.63] [0.17]
78 经营成本因子 OC/TA 5.60 −49.19* 22.07 13.97 −32.09
[0.18] [−2.14] [1.56] [0.97] [−0.45]
79 管理费用因子 SGA/TA −61.33 14.75 −2.14 20.46 −15.68
[−1.06] [0.56] [−0.13] [1.27] [−0.22]
80 管理费用因子 dSGA 243.85*** 58.33** 27.90 55.40*** −62.71
[7.43] [2.70] [1.89] [3.72] [−0.77]
81 预期投资增长因子 HXZq5 57.23* 9.01 −9.14 24.13 −32.52
[2.05] [0.49] [−0.51] [1.23] [−0.48]
82 异常换手率因子 Aturn −66.14 −74.28* −280.93*** −283.98*** −3.62
[−0.95] [−2.00] [−7.55] [−7.29] [ −0.03]
83 日内累计收益因子 Inday 41.00 −23.01 −90.92*** −62.46** 28.79
[0.67] [−0.60] [−5.13] [−3.16] [0.20]
84 隔夜收益率因子 Overnight −47.43*** −61.13*** −36.40* −24.21 77.13
[−2.61] [−4.20] [−2.06] [−1.41] [1.43]
85 低相关系数因子 BAC
108.11 −25.43 27.05 −11.63 140.20
[1.44] [−0.64] [0.94] [−0.38] [1.15]
注: 估计系数的单位为 bp, 估计系数下方括号内的数值为估计系数的 t 值, * 、**、*** 分别表示估计系数
在 5%、1%、1h 的置信水平下显著.


## Page 9

第 9 期 毛杰, 等: 基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究 3001
本文还对多空投资组合进行了扩充, 按公司规模和剩余 84 个特征进行 5×5 的投资组合分类, 共构
建了 2100 个投资组合, 来研究我国股市定价因子的边际有效性 . 此稳健性检验的结果与前文结论基本
吻合, 仅在显著性水平上略有差异, 由此得以再度验证了本文实证结论的稳健性3.
4.4 因子筛选方法的比较
除了 DS-LASSO 模型中的 LASSO 回归可以对定价因子进行筛选之外, 弹性网络、 主成分分析、 逐
步回归都可以对定价因子进行降维和系数收缩. 由此, 本文分别使用 1) DS-LASSO 模型、2) 弹性网络
(后文简称为 EN 模型)、3) PCA-LASSO 模型 (后文简称为 PCA 模型)[18]、4) BIC 前向逐步回归 (后
文简称为 Stepwise 模型)[31], 比较四种方法的有效性. 因子筛选方法的检验结果详见表 2.
由表 2 可知, 使用 EN 模型对因子进行筛选后发现, 70 个初始因子都会被选入模型, 因而使用 EN
模型无法起到很好的筛选和降维的效果; 而使用 PCA 模型后发现, 仅有 3 个初始因子会被选入模型, 由
表 2 因子筛选方法的检验比较
ID Factor DS-LASSO EN PCA Stepwise
71 低 Beta 因子 BAB
302.56*** 242.94* 117.74 192.67
[3.64] [2.09] [1.37] [1.31]
72 偏度因子 Skew 38.57 −35.86 55.78** −26.00
[1.23] [−0.59] [2.83] [−0.44]
73 盈利因子 RMW 460.15*** 597.47*** 370.24** 637.33***
[6.30] [4.91] [2.90] [4.60]
74 盈利因子 ROA −103.37 869.51*** 73.62 697.11*
[−0.49] [2.96] [0.37] [2.55]
75 投资因子 CMA −54.05 58.88 210.93** 46.07
[−0.91] [0.77] [2.91] [0.56]
76 盈利因子 HXZROE −123.69** −64.59 −113.29** −98.99
[−2.80] [ −0.77] [ −3.16] [ −1.27]
77 投资因子 HXZIA −119.76* 34.14 −129.44** 31.70
[−2.06] [0.31] [−2.12] [0.28]
78 经营成本因子 OC/TA 5.60 −28.44 −45.74 −41.64
[0.18] [−0.66] [ −1.59] [ −0.65]
79 管理费用因子 SGA/TA −61.33 −15.68 37.17 −59.23
[−1.06] [ −0.25] [0.69] [−0.99]
80 管理费用因子 dSGA 243.85*** −63.38 150.52*** −63.50
[7.43] [−1.11] [3.83] [−1.08]
81 预期投资增长因子 HXZq5 57.23* 10.14 −17.91 −20.79
[2.05] [0.20] [−0.98] [ −0.43]
82 异常换手率因子 ATurn −66.14 −3.62 −134.85*** 49.67
[−0.95] [ −0.04] [ −4.11] [0.55]
83 日内累计收益因子 Inday 41.00 28.79 250.59* 75.7
[0.67] [0.30] [2.53] [0.69]
84 隔夜收益率因子 Overnight −47.43** 41.21 −124.77*** 37.24
[−2.61] [1.33] [−6.06] [0.89]
85 低相关系数因子 BAC 108.11 140.20 43.63 47.38
[1.44] [1.49] [0.80] [0.43]
初始因子筛选数 12 70 3 52
注: 估计系数的单位为 bp, 估计系数下方括号内的数值为估计系数的 t 值, * 、**、*** 分
别表示估计系数在 5%、1%、1h 的置信水平下显著.
3具体结果囿于篇幅而无法刊告, 但已留存备索.


## Page 10

3002 系 统 工 程 理 论 与 实 践 第 44 卷
此使用 PCA 模型会导致模型过于稀疏; 而使用 DS-LASSO 模型和 Stepwise 模型后发现, 分别有 12 个
初始因子和 52 个初始因子会被选入模型. 这一结果表明, 使用 DS-LASSO 模型既能大幅删除冗余因子
又能使得入选因子不过于稀疏, 可见使用 DS-LASSO 模型最具有有效性.
本文还在 5×5 的投资组合分类下比较了四种方法的有效性 , 此结果与表 2 的结果基本吻合. 而且
无论在 5×5 的投资组合还是在 3×2 的投资组合中, 使用 DS-LASSO 模型具有最高的稳定性, 由此得以
再度验证了 DS-LASSO 模型的有效性4.
4.5 文献发表前后的异质性分析
定价因子有效性往往会因论文发表而逐年衰减 , 即定价因子在文献发表之初具有显著的有效性 , 而
随着时间推移和数据量增长, 他们对股票横截面预期收益的解释力度会逐渐衰减 [6]. 由此, 本文以 2014
年作为初始年份, 使用改变时间窗口的递归 DS-LASSO 模型来考察定价因子在文献发表前后有效性的
变化. 具体而言, 1) 在考察和研究文献发表前的因子有效性时, 本文将文献发表当年所发现的定价因子
作为候选定价因子, 而将当年之前所发现的定价因子作为初始定价因子, 以当年之前的时间段作为样本,
来考察候选定价因子在发表前的因子有效性; 2) 在考察和研究文献发表后的因子有效性时, 本文则以当
年及当年之后的时间段作为样本, 来考察候选定价因子在发表后的因子有效性; 3) 将候选定价因子在文
献发表前的因子有效性与文献发表后的因子有效性进行对比 , 籍以揭示定价因子的有效性在文献发表
前后的异质性. 使用递归 DS-LASSO 模型的文献发表前后异质性分析结果详见表 3.
如表 3 第 3 列所示, 在文献发表前, 低 Beta 因子 BAB、 盈利因子RMW、 盈利因子HXZROE、 投
资因子 HXZIA、 管理费用因子dSGA、 日内收益累计因子Inday、 隔夜收益率因子Overnight 这七个候
选定价因子的估计系数在均至少在 5% 的置信水平下显著. 此检验结果表明, 这七个候选定价因子在文
献发表前是有效的定价因子. 比较表 1 基于 DS-LASSO 模型结果与上述递归 DS-LASSO 模型结果可
知, 使用 DS-LASSO 模型所筛选出的候选定价因子大多在文献发表前都是有效的定价因子 . 但随着时
间推移和数据量增长, 定价因子的有效性也发生了变化 . 如表 3 第 4 列所示, 在文献发表后, 仅有盈利
因子 RMW 和投资因子 CMA 两个候选定价因子的估计系数在 5% 的置信水平下显著. 此检验结果表
明, 仅有这两个候选定价因子在文献发表后是有效的定价因子. 再如表 3 第 5 列所示, 在文献发表前有
效的七个定价因子中有六个定价因子的有效性在文献发表后逐步衰减 , 而在文献发表前不有效的八个
定价因子中有一个定价因子的有效性在文献发表后逐步增强. 上述检验结果表明, 使用改变时间窗口的
递归 DS-LASSO 模型便可在一定程度上判断有效定价因子的时变性: 定价因子的有效性确有时变特征,
多数定价因子的有效性会随时间衰减. 此检验结果也在一定程度上印证了 McLean 和 Pontiff[6] 的结论.
5 进一步分析
5.1 时变 SDF 下的因子有效性检验
本文已使用 DS-LASSO 模型检验了定价因子的有效性. 但此番检验的前提是基于传统资产定价理
论的假设——即 SDF 和风险溢价都是稳定时不变的 . 然而, 在现实市场中, 无论是因子载荷 β 还是随
机贴现因子 SDF 都可能具有时变性. 由此, 本节通过滚动 5 年时间窗口, 从 2011 年开始滚动计算每个
月定价因子与投资组合收益率在时间序列上的协方差, 使用滚动 DS-LASSO 模型计算出 SDF 载荷 λt,
籍以在时变 SDF 的情况下考察和研究定价因子有效性的变化. 时变 SDF 下的 DS-LASSO 模型的检验
结果详见表 4.
如表 4 所示, 低 Beta 因子 BAB、盈利因子 RMW、盈利因子 HXZROE、投资因子 HXZIA、管
理费用因子 dSGA、 预期投资增长因子HXZq5、 日内累计收益因子Inday、 隔夜收益率因子Overnight
的估计系数均至少在 5% 的置信水平下显著 . 上述时变 SDF 下 DS-LASSO 模型的检验与表 1 基于
DS-LASSO 模型结果基本一致, 表明在考虑到时变 SDF 的情况下定价因子的有效性依然保持显著.
4具体结果囿于篇幅而无法刊告, 但已留存备索.


## Page 11

第 9 期 毛杰, 等: 基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究 3003
表 3 文献发表前后的异质性分析结果
ID Factor 发表前 发表后 差异
71 低 Beta 因子 BAB
285.34** 67.29 218.05*
[2.84] [0.96] [2.47]
72 偏度因子 Skew 43.59 38.09 5.51
[1.08] [1.10] [0.14]
73 盈利因子 RMW 264.46** 224.31** 40.15
[2.98] [2.63] [0.45]
74 盈利因子 ROA −61.61 512.50 −574.11
[−0.20] [1.82] [ −1.90]
75 投资因子 CMA −92.92 154.92* −247.87***
[−1.54] [2.04] [ −3.70]
76 盈利因子 HXZROE −149.85* −29.96 −119.89
[−2.6] [ −0.40] [ −1.89]
77 投资因子 HXZIA −254.5** 39.67 −294.26***
[−2.73] [1.45] [ −4.18]
78 经营成本因子 OC/TA 17.46 −54.17 71.64
[0.54] [ −0.17] [0.77]
79 管理费用因子 SGA/TA 39.53 3.82 35.71
[0.68] [0.02] [0.40]
80 管理费用因子 dSGA 274.12*** −81.87 356.00***
[5.94] [ −0.64] [5.53]
81 预期投资增长因子 HAZq5 5.81 65.50 −59.68
[0.17] [0.85] [ −1.43]
82 异常换手率因子 Aturn 128.71 190.29 −61.58
[1.78] [0.67] [ −0.70]
83 日内累计收益因子 Inday 247.83** 30.80 217.04**
[3.18] [0.63] [2.82]
84 隔夜收益率因子 Overnight −90.50*** 382.65 −473.20***
[−3.83] [0.79] [ −8.28]
85 低相关系数因子 BAC
−44.15
[−0.56]
注: 估计系数的单位为 bp, 估计系数下方括号内的数值为估计
系数的 t 值, * 、**、*** 分别表示估计系数在 5%、1%、1h 的
置信水平下显著; 由于低相关系数因子 BAC 的文献发表时间为
2020 年, 不在本文样本时间区间之内, 故而无法统计.
表 4 时变 SDF 下 DS-LASSO 模型的检验结果
ID Factor DS-LASSO
71 低 Beta 因子 BAB
111.43***
[5.75]
72 偏度因子 Skew 12.91
[1.93]
73 盈利因子 RMW 95.97***
[4.78]
74 盈利因子 ROA −978.33
[−1.00]
75 投资因子 CMA −16.59
[−1.02]
76 盈利因子 HXZROE −115.60***
[−19.00]
77 投资因子 HXZIA −58.49***
[−4.27]
78 经营成本因子 OC/TA −21.68
[−0.33]
79 管理费用因子 SGA/TA −52.35
[−1.31]
80 管理费用因子 dSGA 54.15***
[3.88]
81 预期投资增长因子 HAZq5 −80.81***
[−9.87]
82 异常换手率因子 Aturn 13.21
[0.77]
83 日内累计收益因子 Inday 44.59**
[2.58]
84 隔夜收益率因子 Overnight −57.07***
[−10.67]
85 低相关系数因子 BAC
42.57
[1.62]
注: 估计系数的单位为 bp, 估计系数下方括号内的
数值为估计系数的 t 值, * 、**、*** 分别表示估计
系数在 5%、1%、1h 的置信水平下显著.
5.2 样本外预测
本文已然探究了因子的边际有效性 , 但需要进一步分析所选因子的样本外预测表现 . 鉴此, 本文将
前 70% 的样本作为训练集, 后 30% 的样本作为测试集, 以各只股票的月收益率数据为目标, 使用 OLS
模型、GBDT 模型、XGBoost 模型和 LSTM 模型, 根据上一期的基本特征数据来预测下一期的股票收
益率. 样本外预测的结果详见图 ??.
如图 ?? 所示, 真正边际有效因子的样本外 R2 值接近于 1%, 而无效因子和冗余因子的样本外 R2
值大多低于 0%, 由此说明使用 DS-LASSO 方法所选出的定价因子的确是边际有效的, 其在样本外具有
边际上的解释能力.


## Page 12

3004 系 统 工 程 理 论 与 实 践 第 44 卷
-2%
-1%
0%
1%
OLS GBT XGB LSTM
注: 盈利因子 HXZROE 和盈利因子 RMW 是使用同一个特征构造的, 投资因子 HXZIA 与投资因子 CMA 也是
使用同一个特征构造的, 为避免重复本文仅展示了 RMW 因子的盈利特征和 CMA 因子的投资特征.
图 6 样本外预测的 R2
6 结论与政策启示
高维数据情形下使用传统的因子估计方法可能无法准确判断定价因子的有效性 . 鉴此, 本文构建了
双重选择 LASSO 模型, 估计了定价因子的随机贴现因子载荷、而非风险溢价 , 得以在高维数据背景下
准确判断出定价因子的边际有效性 . 本文根据既有文献收集了我国股市的 85 个定价因子, 以此构建了
我国股市的高维定价因子库, 并从中分析了定价因子的边际有效性. 本文发现, 在 2014 年之后发现的定
价因子中, 低 Beta 因子 BAB、盈利因子 RMW、盈利因子 HXZROE、投资因子 HXZIA、管理费用
因子 dSGA、 预期投资增长因子HXZq5、 隔夜收益率因子Overnight 这七个定价因子是有效定价因子.
且较之于使用弹性网络模型、PCA 模型、 逐步回归模型, 使用 DS-LASSO 模型来考察定价因子的有效
性更具稳健性. 通过进一步使用滚动窗口的 DS-LASSO 模型, 本文还发现了有效因子的时变性特征, 即
在考虑到时变 SDF 的情况下, 上述定价因子仍基本保持有效.
本文的研究不仅深化了高维数据背景下我国股市因子定价的既有认识, 也为投资者投资决策起到一
定的启示作用, 同时也为监管机构在高维数据背景下监管我国股市异常波动、纠正我国股市错误定价、
提高我国股市的定价效率提供了一定的实践指导 : 1) 只有从高维因子库中筛选出真正的有效定价因子 ,
才能对股市正确地进行定价, 进而才能使股市发挥好资源配置的功能 , 最终服务好实体经济发展; 2) 定
价因子的有效性随时空转移而发生变化 , 我国股市的因子定价也是动态变化的, 由此对于我国股市错误
定价、异常波动等方面的监管也应该是动态的, 才能时刻应对我国股市可能发生的风险 , 严防股市风险
蔓延至实体经济引发系统性金融风险.
参考文献
[1] Fama E F, French K R. Common risk factors in the returns on stocks and bonds[J]. Journal of Financial
Economics, 1993, 33(1): 3–56.
[2] Hou K, Xue C, Zhang L. Digesting anomalies: An investment approach[J]. The Review of Financial Studies,
2015, 28(3): 650–705.
[3] Fama E F, French K R. A five-factor asset pricing model[J]. Journal of Financial Economics, 2015, 116(1): 1–22.
[4] Barillas F, Shanken J. Comparing asset pricing models[J]. The Journal of Finance, 2018, 73(2): 715–754.
[5] Harvey C R, Liu Y, Zhu H. · · · and the cross-section of expected returns[J]. The Review of Financial Studies,
2016, 29(1): 5–68.
[6] Mclean R D, Pontiff J. Does academic research destroy stock return predictability?[J]. The Journal of Finance,
2016, 71(1): 5–32.


## Page 13

第 9 期 毛杰, 等: 基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究 3005
[7] Hou K, Xue C, Zhang L. Replicating anomalies[J]. The Review of Financial Studies, 2020, 33(5): 2019–2133.
[8] 姜富伟, 马甜, 张宏伟. 高风险低收益? 基于机器学习的动态 CAPM 模型解释 [J]. 管理科学学报, 2021, 24(1): 109–
126.
Jiang F W, Ma T, Zhang H W. High risk low return? Explanation from machine learning based conditional
CAPM model[J]. Journal of Management Sciences in China, 2021, 24(1): 109–126.
[9] Giglio S, Xiu D. Asset pricing with omitted factors[J]. Journal of Political Economy, 2021, 129(7): 1947–1990.
[10] Kelly B T, Pruitt S, Su Y. Characteristics are covariances: A unified model of risk and return[J]. Journal of
Financial Economics, 2019, 134(3): 501–524.
[11] Kelly B T, Pruitt S, Su Y. Instrumented principal component analysis[R]. A vailable at SSRN Working Paper
No.2983919, 2017.
[12] Kelly B T, Moskowitz T J, Pruitt S. Understanding momentum and reversal[J]. Journal of Financial Economics,
2021, 140(3): 726–743.
[13] Lettau M, Pelger M. Factors that fit the time series and cross-section of stock returns[J]. The Review of Financial
Studies, 2020, 33(5): 2274–2325.
[14] Lettau M, Pelger M. Estimating latent asset-pricing factors[J]. Journal of Econometrics, 2020b, 218(1): 1–31.
[15] Demiguel V, Martin UtrerA A, Nogales F J, et al. A portfolio perspective on the multitude of firm characteris-
tics[R]. 2017, CEPR Discussion Paper: DP12417.
[16] Freyberger J, Neuhierl A, Weber M. Dissecting characteristics nonparametrically[J]. The Review of Financial
Studies, 2020, 33(5): 2326–2377.
[17] Feng G, Giglio S, Xiu D. Taming the factor zoo: A test of new factors[J]. The Journal of Finance, 2020, 75(3):
1327–1370.
[18] Kozak S, Nagel S, Santosh S. Shrinking the cross-section[J]. Journal of Financial Economics, 2020, 135(2):
271–292.
[19] Jiang F, Tang G, Zhou G. Firm characteristics and chinese stocks[J]. Journal of Management Science and
Engineering, 2018, 3(4): 259–283.
[20] 李斌, 邵新月, 李玥阳. 机器学习驱动的基本面量化投资研究 [J]. 中国工业经济, 2019(8): 61–79.
Li B, Shao X Y, Li Y Y. Research on machine learning driven quantamental investing[J]. China Industrial
Economics, 2019(8): 61–79.
[21] 姜富伟, 薛浩, 周明. 大数据提升了多因子模型定价能力吗? —— 基于机器学习方法对我国 A 股市场的探究 [J]. 系
统工程理论与实践, 2022, 42(8): 2037–2048.
Jiang F W, Xue H, Zhou M. Does big data improve multifactor asset pricing models? Exploration of China’s
A-share market with machine learning[J]. Systems Engineering — Theory & Practice, 2022, 42(8): 2037–2048.
[22] Ma T, Leong W J, Jiang F. A latent factor model for the Chinese stock market[J]. International Review of
Financial Analysis, 2023, 87: 102555.
[23] Mao J, Shao J, Wang W. Risk premium principal components for the Chinese stock market[R]. SSRN Working
Paper, 2023: 4635632.
[24] Mao J, Xia T. The estimation of risk premia with omitted variable bias: Evidence from China[J]. Risks, 2023,
11(12): 215.
[25] Belloni A, Chernozhukov V, Hansen C. Inference on treatment effects after selection among high-dimensional
controls[J]. The Review of Economic Studies, 2014, 81(2): 608–650.
[26] Liu J, Stambaugh R F, Yuan Y. Size and value in China[J]. Journal of Financial Economics, 2019, 134(1):
48–69.
[27] Cochrane J. Asset pricing[M]. Princeton: Princeton University Press, 2009.
[28] Hastie T, Tibshirani R, Friedman J H, et al. The elements of statistical learning: Data mining, inference, and
prediction[M]. New York: Springer, 2009.
[29] Litzenberger R H, Ramaswamy K. The effect of personal taxes and dividends on capital asset prices: Theory
and empirical evidence[J]. Journal of Financial Economics, 1979, 7(2): 163–195.
[30] Lewellen J, Nagel S, Shanken J. A skeptical appraisal of asset pricing tests[J]. Journal of Financial Economics,
2010, 96(2): 175–194.
[31] Harvey C R, Liu Y. Lucky factors[J]. Journal of Financial Economics, 2021, 141(2): 413–435.


## Page 14

第 9 期 毛杰, 等: 基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究 I
附录
附录 A 因子的定义和描述性统计
表 5 各因子的详细信息表
ID 英文缩写 中文含义 均值% 标准差% 夏普比% 作者 发表年份
1 MKT 市场因子 0.8 3.01 81.36 Fama and MacBeth 1973
2 EP 市盈率因子 0.08 2.69 10.07 Basu 1977
3 dNI/ME 净利润市值比因子 −0.11 1.79 −15.77 Basu 1977
4 SUE2 预期外净利润权益比因子 −0.11 1.83 −18.35 Rendelman, Jones and Latane 1982
5 SUE1 预期外净利润资产比因子 −0.18 1.90 −32.70 Rendelman, Jones and Latane 1982
6 SUR 预期外营业收入资产比因子−0.10 1.86 −24.20 Rendelman, Jones and Latane 1982
7 Lev 杠杆因子 −0.01 1.94 −1.34 Bhandari 1988
8 Current 流动比率因子 0.13 1.54 32.24 Ou and Penman 1989
9 OR/Cash 收入现金比因子 −0.10 1.46 −19.75 Ou and Penman 1989
10 OR/Inv 存货周转因子 0.34 1.73 55.33 Ou and Penman 1989
11 dOR/Inv 营业收入增长存货比因子 0.39 1.68 85.32 Ou and Penman 1989
12 OR/Rec 资金回收率因子 0.05 1.80 11.16 Ou and Penman 1989
13 Quick 速动比率因子 0.02 1.43 3.63 Ou and Penman 1989
14 dQuick 速动变化率因子 0.01 1.31 1.39 Ou and Penman 1989
15 Dep/PPE 折旧率因子 0.00 1.58 −0.90 Holthausen and Larcker 1992
16 dDep 折旧变化率因子 0.15 1.79 23.05 Holthausen and Larcker 1992
17 UMD 动量因子 −0.18 2.96 −19.09 Jegadeesh and Titman 1993
18 HML 价值因子 0.07 2.06 10.95 Fama and French 1993
19 SMB 规模因子 0.65 4.43 42.81 Fama and French 1993
20 dOR 营业收入增长率因子 −0.01 2.10 −2.02 Lakonishok Shleifer and Vishny 1994
21 ACC/NI 应计利润比净利润因子 −0.15 1.51 −40.40 Sloan 1996
22 ACC/TA 应计利润资产比因子 −0.01 1.42 −5.46 Sloan 1996
23 OR/ME 营业收入市值比因子 0.11 1.66 22.23 Barbee and Mukherji and Raines 1996
24 Turn 换手率因子 −1.45 3.42 −283.45 Datar and Naik and Radcliffe 1998
25 d(OP−Inv) 营业利润减存货增长率因子−0.15 1.76 −21.88 Abarbanell and Bushee 1998
26 d(OR−Inv) 营业收入减存货增长率因子0.11 1.69 18.77 Abarbanell and Bushee 1998
27 d(OR−Rec) 营业收入减应收账款增长率因子0.03 1.87 5.51 Abarbanell and Bushee 1998
28 d(OR−SGA) 营业收入减管理费用增长率因子0.09 1.7 21.23 Abarbanell and Bushee 1998
29 CoSkew 协偏度因子 0.07 2.18 11.25 Harvy and Siddique 2000
30 Volume 成交量因子 −1.54 2.56 −245.74 Chordia Subrahmanyam and Anshuman 2001
31 Std_Volume 成交量波动因子 −1.68 2.30 −228.76 Chordia Subrahmanyam and Anshuman 2001
32 RD/OR 研发收入比因子 0.36 2.14 53.41 Chan and Lakonishok and Sougiannis 2001
33 RD/ME 研发市值比因子 0.26 1.49 60.53 Chan and Lakonishok and Sougiannis 2001
34 Illiquidity 非流动指标因子 0.76 2.48 101.93 Amihud 2002
35 dInv 存货变化因子 −0.01 1.76 1.18 Thomas and Zhang 2002
36 dInv/TA 存货增长率因子 −0.03 1.49 −4.96 Thomas and Zhang 2002
37 IMOM 特质动量因子 −1.00 2.20 −127.67 Ali and Hwang and Trombley 2003
38 IVOL 特质波动因子 −1.35 2.66 −191.74 Ang Hodrick Xing and Zhang 2006
39 MaxPrice 最高5 日价格因子 −0.77 3.51 −72.5 George T J Chuan‐Yang Hwang 2004
40 Std_EBIT/TA 盈利波动因子 −0.09 1.83 −17.6 Francis and LaFond and Olsson and Schipper 2004
41 Delay 价格滞后因子 −0.10 1.62 −26.12 Hou and Moskowitz 2005
42 dBE 权益增长率因子 −0.14 1.84 −23.05 Richardson and Sloan and Soliman and Tuna 2005
43 ListAge 上市时间因子 0.13 2.15 36.55 Jiang and Lee and Zhang 2005
44 Volatility 波动率因子 −0.60 3.09 −80.54 Ang Hodrick Xing and Zhang 2006
45 Debt/ME 债务市值比因子 0.25 1.50 51.44 Penman and Richardson and Tuna 2007
46 dLev 杠杆率变化因子 0.09 1.53 17.9 Cooper Gulen and Schill 2008
47 RNA 收入权益比因子 0.02 2.52 3.71 Soliman 2008
48 PM 利润率因子 −0.13 2.37 −13.52 Soliman 2008
49 d(GR−OR) 营业外利润增长率因子 −0.03 2.14 −7.31 Soliman 2008
50 PPE/OR 固定资产因子 0.02 1.54 4.26 Lyandres and Sun and Zhang 2008


## Page 15

II 系 统 工 程 理 论 与 实 践 第 44 卷
表 5 ( 续)
ID 英文缩写 中文含义 均值% 标准差% 夏普比% 作者 发表年份
51 PPEInv/TA 固定资产存货因子 −0.04 1.66 −7.22 Lyandres and Sun and Zhang 2008
52 TAT 总资产周转率因子 0.16 1.69 37.57 Soliman 2008
53 EAR 盈余公告后3 日异常收益因子0.04 1.22 8.76 Brandt Kishore Santa −Clara and Venkatachala 2008
54 A Vol 异常波动因子 0.11 1.49 30.11 Lerman and Livnat and Mendenhall 2008
55 AF 分析师预测因子 0.35 2.42 62.64 Scherbina 2008
56 AF_Div 分析师分歧因子 −0.07 1.84 −10.27 Scherbina 2008
57 AF_Error 分析师偏差因子 0.18 1.98 26.82 Scherbina 2008
58 AF_Num 分析师覆盖因子 −0.07 2.98 −5.79 Scherbina 2008
59 AF_Div2 分析师EPS分歧因子 −0.04 2.02 −3.22 Scherbina 2008
60 Price 当月均价因子 −0.57 3.77 −62.27 Baker Malcolm Greenwood and Wurgler 2009
61 ISKEW 特质偏度因子 −0.33 1.55 −67.82 Boyer Mitton and Vorkink 2010
62 ACC/OR 应计利润收入比因子 −0.23 1.96 −54.05 Bandyopadhyay and Huang and Wirjanto 2010
63 ROE 净利润权益比因子 0.04 2.51 6.46 Balakrishnan Bartov and Faurel 2010
64 ROA2 净利润资产比因子 −0.13 2.83 −16.64 Balakrishnan Bartov and Faurel 2010
65 MaxRt 近一月最高5 日收益均值因子−1.01 2.75 −159.55 Bali Cakici and Whitelaw 2011
66 Kurt 峰度因子 −0.09 1.63 −19.42 Amaya Christoffersen Jacobs and Vasquez 2011
67 Cash 现金比率因子 0.20 1.73 39.58 Berardino Palazzo 2012
68 GP 毛利率因子 −0.09 2.92 −11.63 Novy−Marx 2013
69 dGP 毛利率增长因子 −0.11 2.00 −22.95 Novy−Marx 2013
70 HMLDevil 月频市值因子 0.43 2.40 57.94 Asness and Frazzini 2013
71 BAB 低 Beta因子 −0.16 2.96 −16.66 Frazzini and Pedersen 2014
72 Skew 偏度因子 −0.47 1.81 −106.45 Amaya Christoffersen Jacobs and Vasquez 2015
73 RMW 盈利因子 0.16 2.64 22.56 Fama and French 2015
74 ROA 盈利因子 0.00 2.89 −1.28 Fama and French 2015
75 CMA 投资因子 0.11 1.98 16.36 Fama and French 2015
76 HXZROE 盈利因子 −0.16 2.90 −23.94 Hou Xue and Zhang 2015
77 HXZIA 投资因子 0.30 3.53 32.46 Hou Xue and Zhang 2015
78 OC/TA 经营成本因子 0.02 1.53 3.29 Huang Jiang Tu and Zhou 2017
79 SGA/TA 管理费用因子 0.17 1.68 31.98 Huang Jiang Tu and Zhou 2017
80 dSGA 管理费用因子 0.07 1.70 15.40 Huang Jiang Tu and Zhou 2017
81 HXZq5 预期投资增长因子 0.13 2.04 20.59 Hou Xue and Zhang 2018
82 ATurn 异常换手率因子 −0.94 2.78 −162.17 Liu Stambaugh and Yuan 2019
83 Inday 日内累计收益因子 −1.12 2.71 −160.38 Lou Polk and Skouras 2019
84 Overnight 隔夜收益率因子 0.09 1.86 15.94 Lou Polk and Skouras 2019
85 BAC 低相关系数因子 0.43 2.52 58.97 Asness Clifford Frazzini Gormsen Pedersen 2020
附录 B 调整正则化参数的热点图
在附图 1 中, 15 张热点图分别对应着 15 个候选定价因子 ; 每张热点图的横轴表示第一步横截面
LASSO 回归的正则化参数 τ1 的对数值, 纵轴表示第二步逐步 LASSO 回归的正则化参数 τ2 的对数值;
背景颜色表示候选定价因子估计系数的 t 值, 颜色越深蓝表示 t 值越接近于 2, 颜色越白表示 t 值越接
近于 0, 而颜色越深红 t 值越接近于 −2; 黑点坐标表示 200 次交叉验证对应的正则化参数, 而红叉坐标
表示 200 次交叉验证的正则化参数平均值.
如附图 1 所示, 1) 低 Beta 因子 BAB、 盈利因子 RMW、 盈利因子 HXZROE、 管理费用因子
dSGA、隔夜收益率因子 Overnight 对应热力图中的大部分黑点都集中在深色区域 , 表明这五个因子的
确对股票横截面预期收益有着显著的解释能力 , 确实是有效的定价因子; 2) 偏度因子 Skew、异常换手
率因子 ATurn、 日内累计收益因子Inday 对应热力图中的黑点一半在深色区域、 另一半在浅色区域, 表
明这三个因子对股票横截面预期收益的解释能力并不稳健、 其边际贡献程度十分有限, 确实是冗余的定
价因子; 3) 经营成本因子 OC/TA 和管理费用因子 SGA/TA 对应热力图中的大部分黑点都集中在浅色
区域甚至集中在白色区域, 表明这两个因子对股票横截面预期收益基本没有解释能力 , 确实是无效的定
价因子. 附图 1 的上述结果细化了候选定价因子对解释股票横截面预期收益边际贡献的意义, 也印证了
表 1 实证结果的稳健性.


## Page 16

第 9 期 毛杰, 等: 基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究 III
附图 1 调整正则化参数的热点图
