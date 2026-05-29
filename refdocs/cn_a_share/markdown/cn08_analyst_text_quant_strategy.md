---
id: "cn08_analyst_text_quant_strategy"
title: "分析师前瞻性信息对股票投资收益的影响——基于文本分析的量化研究"
year: 2024
doi: "10.12011/SETP2022-2601"
venue: "系统工程理论与实践"
market_scope: "中国股票市场"
paper_url: "https://sysengi.cjoe.ac.cn/CN/10.12011/SETP2022-2601"
pdf_url: "https://sysengi.cjoe.ac.cn/CN/PDF/10.12011/SETP2022-2601"
---
## Page 1

第 44 卷 第 12 期 系统工程理论与实践 Vol. 44, No. 12
2024 年 12 月 Systems Engineering — Theory & Practice Dec., 2024
doi: 10.12011/SETP2022-2601 中图法分类号: F832.5 文献标志码: A
分析师前瞻性信息对股票投资收益的影响
——基于文本分析的量化研究
赵二龙1,2, 孙少龙2, 王峰虎3, 汪寿阳4,5,6
(1. 西安财经大学 统计学院 , 西安 710100; 2. 西安交通大学 管理学院 , 西安 710049; 3. 西北大学 经济与管理学院 ,
西安 710127; 4. 中国科学院 数学与系统科学研究院 , 北京 100190; 5. 中国科学院 预测科学研究中心 , 北京 100190;
6. 上海科技大学 创业与管理学院 , 上海 201210)
摘 要 分析师研报传递出的信息对投资者决策行为具有引导作用 , 进而协同影响着股票价
格波动. 为了量化复杂网络平台下分析师研报对投资者回报的影响关系 , 本研究首先在东方
财富网获取 2017 年 1 月 1 日至 2021 年 12 月 31 日期间 39786 条分析师研报标题文本数
据. 其次, 通过文本挖掘技术构建出分析师研报标题的情感字典 , 并基于 SESTM 模型得到
对应股票情感值, 筛选出情感值大于某阈值的股票 . 最后按等权重的方式进行模拟回测 , 结
果表明这种基于深度学习的分析师前瞻性报告标题构建完整的量化投资交易策略在交易回
测时具有较高的投资收益. 本研究对于理解分析师研报前瞻性分析 , 有效引导理性投资行为
具有重要理论和实践意义.
关键词 分析师研报; 情感字典; 情感指标; 量化策略
The impact of analysts’ forward-looking information on stock
investment returns — A quantitative study based on
textual analysis
ZHAO Er’long 1,2, SUN Shaolong 2, W ANG Fenghu 3, W ANG Shouyang 4,5,6
(1. School of Statistics, Xi’an University of Finance and Economics, Xi’an, 710100, China; 2. School of Management, Xi’an
Jiaotong University, Xi’an 710049, China; 3. School of Economics & Management, Northwest University, Xi’an 710127, China;
4. Academy of Mathematics and Systems Science, Chinese Academy of Sciences, Beijing 100190, China; 5. Center for
Forecasting Science, Chinese Academy of Sciences, Beijing 100190, China; 6. School of Entrepreneurship and Management,
ShanghaiTech University, Shanghai 201210, China)
Abstract The information conveyed by analysts’ research reports has a guiding effect on in-
vestors’ decision-making behavior, which in turn synergistically affects stock price volatility. To
quantify the relationship between the impact of analysts’ research reports on investor returns
收稿日期: 2022-10-23
作者简介: 赵二龙 (1992–), 男, 河南漯河人, 博士研究生, 研究方向: 大数据挖掘, 经济与金融预测, E-mail: Zhaoerlong@
stu.xjtu.edu.cn; 通信作者: 孙少龙 (1988–), 男, 陕西宝鸡人, 教授, 研究方向: 经济分析与预测, 数智创新与管理, E-mail:
sunshaolong@xjtu.edu.cn; 王峰虎 (1970–), 男, 陕西宝鸡人, 副教授, 研究方向: 量化投资理论与实践 , 金融理论与实
践, E-mail: 836911788@qq.com; 汪寿阳 (1958–), 男, 江苏盐城人, 研究员, 研究方向: 系统工程, 经济预测, E-mail:
sywang@amss.ac.cn.
基金项目: 国家自然科学基金 (72101197, 71988101)
F oundation item: National Natural Science Foundation of China (72101197, 71988101)
中文引用格式: 赵二龙, 孙少龙, 王峰虎, 等. 分析师前瞻性信息对股票投资收益的影响——基于文本分析的量化研究 [J].
系统工程理论与实践, 2024, 44(12): 3851– 3861.
英文引用格式: Zhao E L, Sun S L, Wang F H, et al. The impact of analysts’ forward-looking information on stock
investment returns — A quantitative study based on textual analysis[J]. Systems Engineering — Theory & Practice,
2024, 44(12): 3851– 3861.


## Page 2

3852 系 统 工 程 理 论 与 实 践 第 44 卷
under the complex online platform, this study first obtains the headline text data of 39,786 an-
alysts’ research reports for the period of January 1, 2017 to December 31, 2021 on Eastmoney.
Second, the sentiment dictionary of analysts’ research reports is constructed by text mining
technology, and the corresponding stock sentiment values are obtained based on the SESTM
model, and stocks with sentiment values greater than a certain threshold are screened out. Fi-
nally, simulated backtesting is conducted by equal weighting, and the results show that this deep
learning-based analyst forward-looking report headline construction of a complete quantitative
investment trading strategy has a high investment return in trading backtesting. This study is
of great theoretical and practical significance for understanding the forward-looking analysis of
analysts’ research reports and effectively guiding rational investment behavior.
Keywords analyst research report; emotional dictionary; emotional indicators; quantitative
strategy
1 引言
近年来随着人工智能和大数据技术的发展 , 人工智能的深度应用成为社会各界关注的焦点 . 在金
融领域, 深度学习方法的应用正日益广泛 [1], 这不仅在很大程度上改变了金融行为相关决策的范式 , 还
引发了金融市场的重大变革 . 特别是, 自然语言处理技术和在线平台的共同推动 , 不仅改变了信息传播
的速度和范围, 更深刻地重塑着个体的认知和决策行为 . 在线新闻、 社交媒体等文本数据正在逐渐成
为塑造个人投资行为的重要因素, 这一现象为金融领域的各种问题提供了新的研究途径 , 而文本挖掘技
术成为解决这些问题的有力工具 . 国内外很多学者借助文本挖掘的方法去解决金融领域相关问题 [2–5].
例如, 王晓丹等 [6], 孟雪井等 [7], 龙文等 [8] 等运用文本挖掘方法构建了互联网新闻舆情指数 , 通过量化
新闻媒体对股市的影响, 得出互联网新闻数量增加会加快投资者交易频率 , 从而引起股票价格波动的结
论. 同样, 部慧等 [9], 金秀等 [10] 等以股吧帖子股评数据为基础 , 建立了投资者情绪指标, 并揭示了股吧
评论对当日收盘价的影响. 孙书娜等 [11] 基于计量方法构建了雪球关注度指标 , 发现网络论坛对股票价
格的影响, 并采用滞后天数策略进行了验证. 此外, 田婧倩等 [12] 通过构建微博舆情传播有效性指数, 证
实了微博情感对股票市场的影响 . 国外学者 Antweiler 等 [13], Sanjiv 等 [14], Bollen 等 [15] 对雅虎财经、
RagingBull.com 和 Iwitter 等数据构建出了投资者情绪指标, 并且通过情绪指标研究出了对股票价格的
影响关系. Feldman 等 [16] 则通过分析公司披露的文本数据, 构建情感指标, 探索了这些指标与未来股价
变化之间的关系. 这些研究都表明, 通过文本挖掘构建情绪指标在金融领域有助于发现文本信息传递出
的情绪因素 [17,18] 对个体投资者的决策有一定影响, 从而通过股票价格的波动得以体现.
然而, 相较于非专业股票分析信息, 如股吧、搜索数据、新闻数据等, 分析师作为专业的金融中介,
在证券交易中扮演着沟通企业和投资者的重要角色 [19,30], 其发布的研究报告往往在很大程度上代表了
上市公司经营情况. 分析师研报作为对上市公司基本面回顾以及对未来展望的表达, 具备着一定的前瞻
性和有效性 [20,21], 并且, 已有文献 [22, 23] 证明, 根据近期研报进行投资通常会取得正收益 , 这促使许
多投资者进行跟风操作购买相关上市公司的股票 [24,25]. 然而, 在现实世界中, 由于诸多摩擦因素的存在,
大多数投资者在阅读和理解研报时存在偏差, 从而导致他们在股票市场中无法取得预期的正向收益. 这
一过程既包括了因看不懂研报而进行随机购买的情况 [26], 也涉及了理解研报但因心理因素难以承受回
撤而进行过度交易等情况 [27–29]. 由于股票价格波动瞬息万变 , 分析师研报的更新速度往往跟不上市场
变化, 这进一步加大了投资者的分析难度.
虽然在金融领域的文本分析研究中 , 一些学者 [30–33] 对分析师报告的内容进行了分析和挖掘 , 但对
于分析师研报标题的挖掘却相对较少 . 然而, 研报标题作为对研究内容的高度概括 , 往往体现了分析师
的情感倾向, 且相较于内容分析, 处理标题的样本更为干净且高效. 此外, 情感分析是对带有情感色彩的
文本观点、 情绪和极性进行分析、 推理、 归纳和判断的过程[34]. 因此, 分析师标题情感分析以及其与股
票投资收益影响关系的研究, 对于数据赋能、 构建量化数字生态等方面具有重要意义.
基于此, 本研究提出了一种基于文本挖掘的情感分析方法 , 并根据情感分析结果分析复杂网络平台


## Page 3

第 12 期 赵二龙, 等: 分析师前瞻性信息对股票投资收益的影响——基于文本分析的量化研究 3853
中分析师标题数据所传达信息与个体认知及决策的关系 , 进而辅助个体进行金融决策, 从而避免不必要
的投资行为. 具体而言, 本文以 2017 年至 2021 年沪深 300 指数成分股的分析师研报标题为对象, 通过
(sentiment extraction via screening and topic modeling, SESTM) 模型 [35] 构建分析师情感指数, 并在
情感指数大于特定阈值时, 筛选出相应股票进入股票池 . 随后, 以等权重方式对股票池内的股票进行回
测交易, 同时定期对股票池进行轮换, 构建完整的基于文本挖掘的量化策略. 最终, 本研究通过策略回测
结果验证了本文提出量化策略的有效性.
本文利用 SESTM 模型提出了一种基于文本挖掘的情感分析方法 , 用于构建股票池并进行模拟交
易, 从而减少投资者自身非理性行为可能带来的错误决策 , 进而提高金融市场的稳定性 . 本研究的主要
贡献如下. 1) 使用文本挖掘技术识别和量化分析师研报标题的情感 . 相比国内学者常使用微博、股吧
等非专业数据, 本文通过爬虫技术获取专业金融中介发布的研报数据 , 并运用文本挖掘技术对其进行情
感分析, 从而拓宽了金融文本研究的数据源; 2) 从专业的公司经营情况报告者的角度探索股价波动的另
一解释. 与现有文献从投资者情感要素对股价波动的共同影响角度不同, 本研究以分析师研报所传递的
前瞻性效应为切入点, 揭示了股价波动的影响因素 . 同时, 量化了分析师研报与个体行为之间的情感交
互行为对股价波动的影响程度; 3) 提出了 SESTM 模型来提取文本信息. 相较其他模型, SESTM 模型
具有较高的透明度, 能够直观地展现数据运算的过程 ; 4) 在已有研究基础上, 提供了完整的分析师研报
情感策略实证研究. 当前文本分析研究多为结果的分析和验证, 缺少对基于分析结果的完整量化策略研
究. 本研究从投资者行为角度, 为市场参与者提供了重要的决策参考.
本文余下部分安排如下: 第二部分介绍了 SESTM 模型来提取文本信息相关方法与评价指标; 第三
部分实证部分, 本部分利用 SESTM 模型构建的基于研报标题情绪的预测方法, 对中证 500 指数成分股
进行实证分析研究, 并给出了评价结果分析; 第四部分对本文进行了总结.
2 研究方法
2.1 基于 SESTM 模型情绪值计算
H
O
P
图 1 SESTM 模型情绪值计算示意图
本研究以 SESTM 模型作为主要工具 , 来进行文
本信息的提取和情感分析 . SESTM 模型的主要步骤
如下: 第一, 特征词汇筛选. 在这一步骤中, SESTM 模
型会对海量文本进行分析 , 去除噪声后从中筛选出蕴
含信息的特征词汇 . 具体来说, 在 SESTM 模型中, 这
一过程的目标是找到与股票收益信号高度相关且共现
频率较高的词汇 , 这些特征词汇将作为情感分析的基
础. 第二, 情感权重计算. SESTM 模型使用基于概率
方法并考虑词频的权重计算方式 , 通过已有的语料库
对在上一步骤中筛选出的特征词汇进行情感权重的训
练, 这一步骤的目的是为每个特征词汇赋予一个情感
权重, 以便在后续的情感分析中使用 . 第三, 研报情感
分析. 在这一步骤中, SESTM 模型利用训练集中的话
题向量以及特征词汇的词频向量 , 对样本外的分析师研报标题进行情感打分 . 具体而言, 模型使用最大
似然概率估计法综合考虑各个特征词汇的情感权重, 计算出每篇研报标题的情感值. 这些情感值将被用
于后续的股票池构建和量化策略制定 . 该模型的计算流程详细描述如图 1, 详细的 SESTM 模型介绍
如下:
假设有 n 篇研报标题以及 m 个单词的字典, 第 i 篇研报标题的词频记为向量形式 di, di,j 表示单词
j 出现在研报标题 i 中的次数. 将 n 篇研报标题均表达为同一个词典的向量形式, 可得到一个 n × m 的
矩阵 D, D = [ d1, d2, · · · , dn]. 由于词典中并非所有词都和该研报标题表达的情绪相关 , 所以需要从该
词典中识别出情绪敏感词的集合 S, 并用集合 S 向量化表示 n 篇研报, 记相应的矩阵为 D[S], 用 d[S],i


## Page 4

3854 系 统 工 程 理 论 与 实 践 第 44 卷
表示新矩阵 D[S] 的行向量, 记研报标题 i 在发布日的对应股票收益为 yi.
首先, 设置变量 pi 来代表收集到的每一篇研报标题的情绪分值 , 其中 pi ∈ [0, 1], pi 值越大表示该
研报标题的积极情绪越强. 相关的研究表明 pi 是一个有效的影响着股票收益率的变量, 并且在 pi 给定
的情况下, 变量 di 和 yi 存在着相互独立的关系. 此外, 本文引入了表示给定 pi 条件下股票收益 yi 分
布和表示给定 pi 条件下研报标题词向量 di 的分布的两个额外成分解释数据生成过程. 具体地, 对于条
件收益分布, 假设:
P (sgn(yi) = 1) = g(pi), (1)
其中, 公式 (1) 中的 sgn 为符号函数, 根据符号函数的特点当股票收益 yi > 0 时值为 1, 当股票收益
yi < 0 时值为 0. 该假设表明了研报标题的情绪值 pi 和实现正收益的可能性成正相关.
其次, 假设研报标题词向量 di 为情绪敏感词 S 与中性词 N 的集合. d[S],i 词频向量为情绪敏感词
S 的集合, d[N ],i 词频向量为情绪中性词 N 的集合. 在模型 SESTM 中假设词频向量中的 d[S],i 和 d[N ],i
是相互独立的, 从 d[N ],i 的定义中发现, 该集合中主要是中性词, 该集合中的词语对于研报标题的情绪分
析没有影响, 所以不对 d[N ],i 进行相关的分析. 此时, 模型假设情绪敏感词的词频向量 d[S],i 服从混合二
项分布:
d[S],i ∼ Multinomial(si, piO+ + (1 − piO−)), (2)
公式 (2) 中的 si 表示第 i 个研报标题中情绪为敏感词的总数 . 同时, 为了对单个情绪敏感词概率进行
建模, 该模型采用了两话题模型, 公式 (2) 中的 O+ 为当研报标题情绪分值 pi = 1 时情绪敏感词集合 S
的词频概率分布, O− 为当研报标题情绪分值 pi = 0 时情绪敏感词集合 S 的词频概率分布, 词频向量可
拆分成两个话题向量的概率结合.
再次, 用特征提取技术得到情绪敏感词集合 S 对应股票的收益情况代表研报标题的情绪反映 . 具
体地, 当研报标题中某个词出现且对应的股票经常反映出上涨的情况 , 则认为这篇研报标题的情绪为正
向. 基于此, 为了获得到与股票正向收益关联度最高的词汇 , 使用公式 (3) 计算得出每个词汇对股票收
益贡献频率:
fj = 包含词语 j 同时正向收益的研报数量
包含词语 j 的研报数量 . (3)
然后, 获得情绪敏感词集合 S 后, 需要对话题向量 O 进行训练, O = [O+, O−], 该话题向量决定了
研报标题中对应敏感词的生成 . 用参数 pi 表示每篇研报标题的情绪分值 , 该情绪分值代表了研报标题
对于积极词分布的依赖程度. 同时, 使用 hi =
d[S],i
Si
代表词频向量, 则有
E(hi) = E d[S],i
Si
= piO+ + (1 − piO−). (4)
用矩阵形式表达, 得到:
E(H) = OW , (5)
其中, W =
[
p1 · · · pn
1 − p1 · · · 1 − pn
]
, H = [ h1, h2, · · · , hn], W 代表语料库文本的情绪矩阵, 组成元素为
每篇研报标题情绪的估计值 ˆpi, ˆpi 通过数据样本对股票的收益率排序后得到, 计算方法如公式 (6):
ˆpi = rank of yi in {yl}n
l=1
n . (6)
最后, 在得到 ˆS 和 ˆO 之后, 使用最大似然估计法来估计研报标题的情绪值 pi. 为了解决研报标题
所含情绪敏感词不足和低信噪比的问题 , 在估计方程中添加一项惩罚项 . 相应地, 通过公式 (7) 可以得


## Page 5

第 12 期 赵二龙, 等: 分析师前瞻性信息对股票投资收益的影响——基于文本分析的量化研究 3855
到研报标题预测情绪值:
ˆp = arg max
{
ˆs−1
ˆs∑
j=1
dj log(pO+,j + (1 − pO−,j) + λ log(p(1 − p))
}
. (7)
2.2 策略评价指标
为了全面评价所提出策略的效果, 本研究从多个角度选择了一系列关键指标. 以下是对四个指标的
详细介绍:
1) 年化收益率
年化收益率 TR 是一项常用于金融领域的评价指标 , 该指标将累积收益转化为以年为计算周期的
收益率, 以便对不同时间周期下的策略效果进行比较. R 为策略的收益, t 为策略回测天数.
TR = ((1 + R)
250
t − 1) × 100%. (8)
2) 夏普比率
夏普比率指股票投资组合收益超过无风险利率的部分与投资组合标准差的比, 夏普值 SR 越大表示
承受一单位总风险带来的收益也越高. Rp 为策略年化收益, Rf 为无风险利率, 本文使用 2% 作为无风
险利率, σp 策略收益的标准差.
SR = (Rp − Rf )
σp
. (9)
3) 最大回撤
最大回撤 MDD 是描述策略可能遭受的最大亏损情况的指标. 在特定时间段内, 策略总市值从高点
Px, 下降到低点 Py.
MDD = Max(Px − Py)
Px
. (10)
4) 卡玛比率
卡玛比率 Calmar 指策略每承担一单位回撤损失时能获得的收益水平, 用于衡量策略的年化收益相
对于最大回撤的综合表现. Rp 为策略年化收益, MDD 为最大回撤.
Calmar = Rp
MDD . (11)
3 实证研究
3.1 数据来源及预处理
证券分析师的研究报告一直扮演着引导投资者决策的重要角色 . 这些研究报告通过对上市公司的
公开信息、实地调研等方法的综合运用 , 为投资者提供了关于上市公司基本面和未来展望的深入分析 .
这些报告不仅在学术界具有影响力, 而且在实践中也发挥着重要作用, 因为它们能够为投资者提供有价
值的投资建议. 与此同时, 随着互联网和在线平台的迅速发展 , 分析师的研究报告通过各种渠道广泛传
播, 并影响着股票市场的波动 [20]. 基于此, 本文使用东方财富作为数据源 , 东方财富网在国内有较大的
影响力, 可以提供证券多方面的信息.
本文首先通过 Python 爬虫技术对选择的网站上的分析师研报标题进行数据的采集 , 样本时间从
2017 年 1 月 1 日至 2021 年 12 月 31 日, 共获取 39786 条数据, 得到的数据包括发布时间、标题、股
票代码和股票名称, 部分数据示例如表 1 所示. 为了模拟现实中投资的逻辑并确保研究的准确性和有效
性, 本研究将数据集划分为训练集和测试集 , 具体而言, 本研究将 2019 年 12 月 31 日之前的数据 (共
26443 条) 作为训练集, 将 2019 年 12 月 31 日之后的数据 (共 13343 条) 作为测试集. 通过这种划分,
本研究能够在训练集上构建模型并优化参数, 然后在测试集上验证本研究的策略效果.


## Page 6

3856 系 统 工 程 理 论 与 实 践 第 44 卷
表 1 数据类型示例
发布时间 标题 股票代码 股票名称
2019-12-20 股权变动点评: 宝能减持至 5% 以下, 股权之争落幕在即 000002 万科 A
2019-12-18 冲破 3400 亿市值! 如此之大体量, 还能连番暴涨! 什么情况? 000002 万科 A
2019-12-09 公司 11 月销售同比增速回升, 拿地总额增速稳健, 维持 “买入” 评级 000002 万科 A
2019-12-03 2019 年 11 月月销售数量点评: 销售暂弱, 拿地谨慎 000002 万科 A
图 2 全行业词云图
在得到的原始数据后需要对数据进行初步的
预处理, 首先对于原始爬取出的数据中存在的一
些异常无关的字符、HTML 标签等异常无关符号
进行过滤去除步骤. 其次, 对上一步得到的过滤后
的文本数据进行中文文本的分词 , 得到分析师研
报标题中有语义特征的词语 , 从而获得词的集合 .
最后, 通过停用词表去掉无意义的词语和符号, 如
中文 “的” “ 在” “ 依” 等词汇. 根据词语的频率绘
制词云图 (如图 2 所示), 从图 2 中可以发现 “增
长” “ 持续” “ 预期” “ 盈利” “ 提升” 等词语在研报标题中的出现频率较高, 这些高频词汇的存在一定程度
上反映了分析师在撰写研究报告时所关注的主要方面.
3.2 话题寻优
在情感分析框架下, 对于研报标题的情感进行分类是一项重要任务 , 其中情感分类的细分对于不同
问题的分析和结论可能产生不同影响 . 例如, 研报标题的情绪可以分为 “积极、消极” 两类或者 “积极、
消极、中性” 三类, 而不同分类个数的情感分类情况会导致结论的差异 . 为了更精准地得到情感分类的
个数, 本文首先基于潜在狄利克雷分布模型 (latent Dirichlet allocation, LDA) 来得到合适的情感分类
的个数. LDA 是一种有效的文本分析方法, 能够从大规模文档集合和语料库中提取隐含的主题, 以实现
降维和信息提取 [4]. 其次, 为了得到研报标题的情绪值得分 , 本文使用研报发布后对应股票的涨跌幅来
表征. 由于市场反应存在时滞效应以及部分机构会在非交易日发布相关研报导致的研报发布当天的股
票的涨跌幅可能存在误差 , 因此本文以研报发布时间后三个交易日内股票的涨跌值作为情绪反映的衡
量指标. 例如, 当某个股票在研报发布后三个交易日是上涨的则认为这些研报标题中的词语为积极情感
词, 同时将研报发布后三个交易日内上涨的股票标记为 1, 相反地, 下跌的股票标记为 0.
总的来说, 为了以更精准有效地从文本词汇中挖掘出情感信息 , 本文采用了话题寻优模型对情感分
图 3 研报 LDA 主题数寻优
类的个数进行确定 . 同时, 以对应股票的涨跌幅
作为判断指标所得出的词典作为输入的情感词典,
利用余弦相似度作为判断指标 , 以话题个数作为
循环对象, 提取 LDA 模型输出的主题词, 并构造
出主题词的词频向量 , 计算出每个话题个数情况
下的平均余弦相似度, 得到的研报 LDA 主题寻优
的结果如图 3 所示. 从图 3 中可以发现在 LDA
的话题个数为 2 时, 文本向量之间的余弦相似度
已经接近于 0, 且存在着拐点的现象, 这反映了当
话题个数为 2 时文本的区分效果最好. 因此, 本文
将话题向量个数设置为 2, 即将情绪值分为积极和
消极两类的情景更适合本研究的实际情况.


## Page 7

第 12 期 赵二龙, 等: 分析师前瞻性信息对股票投资收益的影响——基于文本分析的量化研究 3857
3.3 基于 SESTM 模型的情绪值计算
表 2 词语正收益共现频率
词语 包含该词语
的标题数
包含该词语且
收益为正数
该词语与正收益
共现的频率
增超 17 13 0.7647
油价 76 31 0.4078
中标 33 24 0.7272
大超 101 73 0.7227
渗透 32 23 0.7187
免税 38 28 0.7368
为了预测训练集中标题文本的所蕴含的情绪
值进而根据预测出的情绪值进行买卖决策 , 本文
进行了如下三个步骤.
首先, 为了找出词典中最能代表研报标题情
绪的积极词和消极词 , 本文采用中文情感极性词
典 (NTUSD) 作为原始词典 , 通过遍历词典中的
词语计算出训练样本中包含该词语的研报标题数
目以及该词语且标的股票的收益为正的研报数目,
从而得到该词语与正向收益共现的频率 , 部分结
果如表 2 所示.
其次, 为了对每篇研报标题的情绪矩阵进行估计 , 本文将研报标题对应股票的涨跌幅进行排序后 ,
作为衡量估计研报情绪的指标, 得到情绪矩阵 W , 部分计算结果如表 3 所示.
再次, 为了获取训练集中所有研报的词频矩阵 D, 本文使用上述步骤得到的词典来构造每一篇研报
标题的词频向量. 具体来说, 遍历每一个情绪词, 得到词典中每个词语在一篇研报标题中的词频 . 在此
基础上构建出整个语料库的词频矩阵 D, 该矩阵的行索引为情绪敏感词, 列索引为每篇研报标题. 在得
到了语料库的情绪矩阵和词频矩阵的基础上计算得到两话题向量 O, 部分结果如表 4 所示.
最后, 分析训练样本得到话题向量 , 预测新研报标题所蕴含的情绪值 . 以一篇样本外的研报标题为
例, 该研报标题为” 年报业绩符合预期 , 新冠检测有望持续放量 , 新平台增量可期 ” . 首先, 计算情绪敏
感词在该研报标题中的词频向量, 其次结合标题中出现的词语在话题向量中的数值大小 , 接着使用极大
似然估计方法, 得到在 1 倍惩罚系数下研报标题的情绪分值 0.6572, 其词频与话题向量对应数值如表 5
所示.
表 3 研报收益标准排序
标题 标签 涨跌幅 收益排序 情绪
事件点评: 收购武汉孚安特, 强化锂原电池领先地位 1 0.0238 18737 0.7085
控股股东引战投成为国改典型, 有望开启二次腾飞 0 −0.0104 8805.5 0.3329
并购天天快递, 完善新零售物流生态体系, “1 +1 大于 2” 效果凸显 0 −0.0183 6761 0.2556
收入增长持续超预期, 供不应求批价仍具上行空间 1 0.0484 22657 0.8556
内外同步改善, 次高端再崛起可期 1 0.0275 19474 0.7364
业绩快报点评: 息差降幅趋缓, 不良确认提速 0 −0.0083 9416 0.3560
多元业务终结果, 业绩增量超预期 1 0.0131 16181 0.6119
超额完成年度目标, 2017 年迎新品周期 0 −0.0052 10417 0.3939
表 4 沪深 300 两话题向量
积极 消极
石化 0.0054 0.0027
转债 0.0057 0.0020
内销 0.0069 0.0005
成效 0.0101 0.0018
资源 0.0025 0.0082
上市 0.0022 0.0140
加强 0.0009 0.0067
外销 0.0004 0.0066
优异 0.0013 0.0070
表 5 研报标题词频与对应话题向量示例
频次 积极 消极
放量 1 0.0291 0.0212
可期 1 0.0449 0.0373
新冠 1 0.0070 0.0044
增量 1 0.0058 0.0062
平台 1 0.0106 0.0106
持续 1 0.1299 0.1248
符合 1 0.0855 0.0897
有望 1 0.0659 0.0682


## Page 8

3858 系 统 工 程 理 论 与 实 践 第 44 卷
3.4 研报情绪策略结果
基于研报情绪策略构建过程主要分为三部分 , 分别是标题情绪值的计算, 阈值设定和基于阈值的决
策分析. 具体如下: 首先, 通过对测试集中所有研报标题采用 SESTM 模型进行文本情绪值的计算得到
对应标的情感值; 其次, 为了初步验证 SESTM 模型在实际交易中的可行性 , 并证明不同阈值下模型结
果具有线性区分度, 对模型结果进行回测 , 将情感值大于某一阈值的股票纳入股票池 , 对股票池中的股
票按等权重买入持有, 选择 3 天作为持仓周期, 为了简化计算过程, 回测不考虑手续费、滑点等现实交
易因素, 以股票 3 天内的收益率作为单只股票的持仓收益率 , 通过分析净值走势, 对比不同阈值下的净
值曲线, 以探究是否存在区分度. 最后, 通过评价指标判断本文构建的情绪值能否正确反映研报情绪, 并
对未来的股票涨跌有预测作用. 不同阈值下实证结果如图 4 所示, 从图 4、表 6 中可以看到, 随着阈值
的增加, 股票池内股票的净值表现逐渐提升. 具体而言, 年化收益率增加, 最大回撤减小, 夏普比率与卡
玛比率呈现增加趋势, 这种趋势验证了情绪值在区分股票收益方面具有一定能力 . 同时, 这一结果也在
一定程度上支持了本研究所采用的 SESTM 模型在实际应用中的实用性.
为了验证本文构建的情绪值模型的普适性及鲁棒性, 本文使用 2020 年 1 月 1 日至 2021 年 12 月 31
日中证 500 成分股数据进行检验. 通过前文 SESTM 模型构造股票情绪值, 筛选不同阈值下的股票进行
回测, 回测结果如图 5、 表7 所示. 实证结果显示, 在中证 500 指数成分股下不同阈值仍具有区分度, 阈
值的提升带来了更高的年化收益率、较小的最大回撤、更优越的夏普比率和卡玛比率等风险收益指标 .
因此, 在不同市场环境下, 本研究所提出的情绪值构建方法均呈现出显著的优势 . 这也证实了所提出的
情绪值在区分股票收益方面的能力, 同时也说明了本研究所采用的方法具有一定的普适性和稳健性.
图 4 沪深 300 不同情绪阈值净值走势
表 6 沪深 300 不同阈值下股票绩效表现
情绪阈值 年化收益 最大回撤 夏普比率 (以 2% 作为无风险收益率) 卡玛比率
0.5 −7.17% −57.85% −0.3100 −0.1200
0.6 3.06% −50.42% 0.0700 0.0600
0.7 15.90% −49.87% 0.5100 0.3200
表 7 中证 500 不同阈值下股票绩效表现
情绪阈值 年化收益 最大回撤 夏普比率 (以 2% 作为无风险收益率) 卡玛比率
0.5 13.55% −39.43% 0.5600 1.1300
0.6 21.10% −34.06% 0.8700 0.6200
0.7 26.68% −29.46% 1.1300 0.9100


## Page 9

第 12 期 赵二龙, 等: 分析师前瞻性信息对股票投资收益的影响——基于文本分析的量化研究 3859
图 5 中证 500 不同情绪阈值净值走势
4 研究结论
本文通过构建了基于分析师前瞻性分析的文本挖掘策略 , 为个体参与者在复杂金融环境下的行为
决策场景中的认知现象提供了一种思路 , 也为数字化市场监管和预警提供了新的解决方案 . 具体地, 本
文首先对分析师研报标题进行文本分析 , 运用 SESTM 模型构建了情绪值指标. 接着, 通过设定一定的
阈值, 筛选出情绪值较高的股票 , 并以等权重的方式进行回测交易 , 同时定期对股票池进行轮换 . 回测
结果显示, 本文构建的情绪值对于股票收益的区分具有显著影响 . 实证策略研究的主要结论主要如下 .
1) 析师的前瞻性分析文本具有一定价值 , 尤其对于那些信息不对称或无法进行详尽调研的投资者而言 ,
分析师的研报标题分析可为其提供有价值的指导. 结合文本分析挖掘技术, 可以从分析师的标题中获得
有参考价值的股票池. 2) 在复杂的网络平台环境下, 个体投资者的理性投资决策时机至关重要. 尽管通
过分析师研报标题的文本分析可以挑选出值得投资的标的 , 但投资者的不理性金融行为可能导致无法
获得正收益. 这一情况下, 合理的调仓周期可有效地弥补投资者行为的不足 , 从而获得超额收益. 3) 进
一步研究发现, 理性投资行为和复杂场景中的金融决策行为是金融市场稳定的基础 , 即金融市场中所有
参与者都需要一个完善的策略对各自参与角色进行行为指导 , 具体而言监管机构需要找到一个策略发
现存在问题的公司, 投资者需要策略找到获得收益的公司.
此外, 本文所构建的基于预测结果的量化策略对投资者具有实际借鉴意义 , 为投资者提供了一种可
行的投资方向. 同时, 本研究将分析师标题作为数据源, 扩展了预测股票走势的有效数据来源. 然而, 本
文对文本数据进行了相对简单的处理, 未考虑一些可能包含情感信息的标点符号. 未来的研究可以将标
点符号视为外生变量, 进一步深入分析其对结果的影响.
参考文献
[1] 马长峰, 陈志娟, 张顺明. 基于文本大数据分析的会计和金融研究综述 [J]. 管理科学学报, 2020, 23(9): 19–30.
Ma C F, Chen Z J, Zhang S M. A survey on accounting and finance research based on textual big data analysis[J].
Journal of Management Sciences in China, 2020, 23(9): 19–30.
[2] Kumar B S, Ravi V. A survey of the applications of text mining in financial domain[J]. Knowledge-Based
Systems, 2016, 114: 128–147.
[3] Loughran T, Mcdonald B. Textual analysis in accounting and finance: A survey[J]. Journal of Accounting
Research, 2016, 54(4): 1187–1230.
[4] 凌爱凡, 彭伟, 王千千, 等. 金融研究中自然语言处理技术的应用进展 [J/OL]. 系统工程理论与实践 , 2024, 44(1):
387–421.
Ling A F, Peng W, Wang Q Q, et al. A comprehensive research progress of applying NLP in financial problems[J].
Systems Engineering — Theory & Practice, 2024, 44(1): 387–421.
[5] 王芳, 王宣艺, 陈硕. 经济学研究中的机器学习: 回顾与展望 [J]. 数量经济技术经济研究, 2020, 37(4): 146–164.


## Page 10

3860 系 统 工 程 理 论 与 实 践 第 44 卷
Wang F, Wang X Y, Chen S. Machine learning in economics research: Review and prospective[J]. The Journal
of Quantitative & Technical Economics, 2020, 37(4): 146–164.
[6] 王晓丹, 尚维, 汪寿阳. 互联网新闻媒体报道对我国股市的影响分析 [J]. 系统工程理论与实践, 2019, 39(12): 3038–
3047.
Wang X D, Shang W, Wang S Y. The effects of online news on the Chinese stock market[J]. Systems Engineering
— Theory & Practice, 2019, 39(12): 3038–3047.
[7] 孟雪井, 杨亚飞, 赵新泉. 财经新闻与股市投资策略研究——基于财经网站的文本挖掘 [J]. 投资研究, 2016, 35(8):
29–37.
Meng X J, Yang Y F, Zhao X Q. Research on financial news and stock market investment strategy: Text mining
based on financial website[J]. Review of Investment Studies, 2016, 35(8): 29–37.
[8] 龙文, 毛元丰, 管利静, 等. 财经新闻的话题会影响股票收益率吗 ? —— 基于行业板块的研究 [J]. 管理评论, 2019,
31(5): 18–27.
Long W, Mao Y F, Guan L X, et al. Can topics in financial news impact the return of stock market? A research
based on market segment[J]. Management Review, 2019, 31(5): 18–27.
[9] 部慧, 解峥, 李佳鸿, 等. 基于股评的投资者情绪对股票市场的影响 [J]. 管理科学学报, 2018, 21(4): 86–101.
Bu H, Xie Z, LI J H, et al. Investor sentiment extracted from internet stock message boards and its effect on
Chinese stock market[J]. Journal of Management Sciences in China, 2018, 21(4): 86–101.
[10] 金秀, 姜尚伟, 苑莹. 基于股吧信息的投资者情绪与极端收益的可预测性研究 [J]. 管理评论, 2018, 30(7): 16–25.
Jin X, Jiang S W, Yuan Y. Investor sentiment from Guba messages and the predictability of stock extreme
returns[J]. Management Review, 2018, 30(7): 16–25.
[11] 孙书娜, 孙谦. 投资者关注和股市表现——基于雪球关注度的研究 [J]. 管理科学学报, 2018, 21(6): 60–71.
Sun S N, Sun Q. Investor attention and market performance: Evidence based on “Xueqiu attention”[J]. Journal
of Management Sciences in China, 2018, 21(6): 60–71.
[12] 田婧倩, 刘晓星. 舆情传播, 风险感知与投资者行为——基于系统模糊控制的视角 [J]. 系统工程理论与实践 , 2021,
41(12): 3147–3162.
Tian J Q, Liu X X. Public opinion dissemination, risk perception and investor behavior: Based on system fuzzy
control[J]. Systems Engineering — Theory & Practice, 2021, 41(12): 3147–3162.
[13] Antweiler W, Frank M Z. Is all that talk just noise? The information content of internet stock message boards[J].
Journal of Finance, 2004, 59(3): 1259–1294.
[14] Das R, Chen M Y. Yahoo! For Amazon: Sentiment extraction from small talk on the web[J]. Operations
Research, 2008, 53: 1375–1388.
[15] Bollen J, Mao H, Zeng X. Twitter mood predicts the stock market[J]. Journal of Computational Science, 2011,
2(1): 1–8.
[16] Feldman R, Govindaraj S, Livnat J. Management’s tone change, post earnings announcement drift and accru-
als[J]. Review of Accounting Studies, 2010, 15(4): 915–953.
[17] 任飞, 罗靖怡, 陈张杭健, 等. 分析师深度研究报告向市场传递的信息含量——基于 “新”, “ 旧” 信息的文本分解 [J].
系统工程理论与实践, 2020, 40(12): 3034–3058.
Ren F, Luo J Y, Chen Z H J, et al. Information content transmitted to the market by the analysts’ in-depth
reports: A text decomposition based on “new” and “old” information[J]. Systems Engineering — Theory &
Practice, 2020, 40(12): 3034–3058.
[18] 张宗新, 吴钊颖. 媒体情绪传染与分析师乐观偏差——基于机器学习文本分析方法的经验证据 [J]. 管理世界, 2021,
37(1): 170–185.
Zhang Z X, Wu Z Y. Media’s emotional contagion and analyst optimistic bias: Evidence based on the technique
of machine learning[J]. Management World, 2021, 37(1): 170–185.
[19] 王谨乐, 霍达, 史永东, 等. 股价信息含量能够提升分析师预测质量吗?[J]. 系统工程理论与实践, 2021, 41(8): 1974–
1989.
Wang J L, Huo D, Shi Y D, et al. Can information content of stock prices improve analyst forecast quality?[J].
Systems Engineering — Theory & Practice, 2021, 41(8): 1974–1989.
[20] 李洋, 王春峰, 房振明, 等. 中国分析师预告的有效性研究——基于投资者间信息不对称的研究视角 [J]. 预测, 2019,
38(1): 55–62.


## Page 11

第 12 期 赵二龙, 等: 分析师前瞻性信息对股票投资收益的影响——基于文本分析的量化研究 3861
Li Y, Wang C F, Fang Z M, et al. The effectiveness of Chinese analyst forecasts: Based on the perspective of
information asymmetry among investors[J]. Forecasting, 2019, 38(1): 55–62.
[21] Brav A, Lehavy R. An empirical analysis of analysts’ target prices: Short-term informativeness and long-term
dynamics[J]. Journal of Finance, 2001(58): 1933–1967.
[22] 张然, 汪荣飞, 王胜华. 分析师修正信息、 基本面分析与未来股票收益[J]. 金融研究, 2017(7): 156–174.
Zhang R, Wang R F, Wang S H. Analysts’ revisions, fundamental analysis and future stock returns[J]. Journal
of Financial Research, 2017(7): 156–174.
[23] 刘永泽, 高嵩. 信息披露质量、 分析师行业专长与预测准确性——来自我国深市 A 股的经验证据 [J]. 会计研究,
2014(12): 60–65.
Liu Y Z, Gao S. Disclosure quality, analysts’ industry expertise and forecast accuracy: Empirical evidence from
Chinese Shenzhen A-share stock market[J]. Accounting Research, 2014(12): 60–65.
[24] 张一锋, 雷立坤, 魏宇. 羊群效应的新测度指数及其对我国股市波动的预测作用研究 [J]. 系统工程理论与实践, 2020,
40(11): 2810–2824.
Zhang Y F, Lei L K, Wei Y. A new herd index and volatility forecasting of China’s stock market[J]. Systems
Engineering — Theory & Practice, 2020, 40(11): 2810–2824.
[25] Park A, Sabourian H. Herding and contrarian behavior in financial markets[J]. Econometrica, 2011, 79(4):
973–1026.
[26] 王克敏, 王华杰, 李栋栋, 等. 年报文本信息复杂性与管理者自利——来自中国上市公司的证据 [J]. 管理世界, 2018,
34(12): 120–132.
Wang K M, Wang H J, Li D D, et al. Complexity of annual report and management self-interest: Empirical
evidence from Chinese listed firms[J]. Management World, 2018, 34(12): 120–132.
[27] 谭松涛. 行为金融理论: 基于投资者交易行为的视角 [J]. 管理世界, 2007(8): 140–150.
Tan S T. Behavioral finance theory: From the perspective of investors’ trading behavior[J]. Management World,
2007(8): 140–150.
[28] 李洋, 王春峰, 向健凯, 等. 交易者有限理性、信息披露质量与价格发现效率 [J]. 系统工程理论与实践, 2020, 40(7):
1682–1693.
Li Y, Wang C F, Xiang J K, et al. Limited rationality of traders, information disclosure quality and price
discovery eﬀiciency[J]. Systems Engineering — Theory & Practice, 2020, 40(7): 1682–1693.
[29] 邓晴元, 刘舟, 张顺明. 交易者过度自信与信息相关性暖昧的资产定价 [J]. 系统工程理论与实践, 2022, 42(7): 1755–
1769.
Deng Q Y, Liu Z, Zhang S M. Asset pricing with overconfident traders and information correlation ambiguity[J].
Systems Engineering — Theory & Practice, 2022, 42(7): 1755–1769.
[30] 马黎珺, 吴雅倩, 伊志宏, 等. 分析师报告的逻辑性特征研究 : 问题, 成因与经济后果 [J]. 管理世界, 2022, 38(8):
217–234.
Ma L J, Wu Y Q, Yi Z H, et al. A study on the logicality of analyst reports: The problem, its causes and
economic consequences[J]. Management World, 2022, 38(8): 217–234.
[31] 吴武清, 赵越, 闫嘉文, 等. 分析师文本语调会影响股价同步性吗? —— 基于利益相关者行为的中介效应检验 [J]. 管
理科学学报, 2020, 23(9): 108–126.
Wu W Q, Zhao Y, Yan J W, et al. Does textual tone in analyst reports affect stock price synchronicity? An
analysis based on mediating effects of stakeholders’ behavior[J]. Journal of Management Sciences in China, 2020,
23(9): 108–126.
[32] Suzuki M, Sakaji H, Izumi K. Forecasting net income estimate and stock price using text mining from economic
reports[J]. Information, 2020, 11(6): 292.
[33] 吴偎立, 张峥, 乔坤元. 信息质量、 市场评价与激励有效性——基于 《新财富》 最佳分析师评选的证据[J]. 经济学 (季
刊), 2016, 15(2): 723–744.
Wu W L, Zhang Z, Qiao K Y. Information quality, market evaluation and incentive effectiveness: Evidence from
the New Fortune’s analysts ranking[J]. China Economic Quarterly, 2016, 15(2): 723–744.
[34] 洪巍, 李敏. 文本情感分析方法研究综述 [J]. 计算机工程与科学, 2019, 41(4): 180–187.
Hong W, Li M. A review: Text sentiment analysis methods[J]. Computer Engineering & Science, 2019, 41(4):
180–187.
[35] Ke Z, Kelly B T, Xiu D. Predicting returns with text data[J]. SSRN Electronic Journal, 2019: 1–66.
