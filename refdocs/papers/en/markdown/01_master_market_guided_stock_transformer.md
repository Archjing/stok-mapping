---
id: "01_master_market_guided_stock_transformer"
title: "MASTER: Market-Guided Stock Transformer for Stock Price Forecasting"
year: 2024
doi: "10.1609/aaai.v38i1.27767"
venue: "Proceedings of the AAAI Conference on Artificial Intelligence"
paper_url: "https://ojs.aaai.org/index.php/AAAI/article/view/27767"
pdf_url: "https://ojs.aaai.org/index.php/AAAI/article/download/27767/27575"
---
## Page 1

MASTER: Market-Guided Stock Transformer for Stock Price Forecasting
Tong Li 1*, Zhaoyang Liu 2, Yanyan Shen 1† , Xue Wang 2, Haokun Chen 2, Sen Huang 2
1 Shanghai Jiao Tong University
2 Alibaba Group
{2017lt, shenyy}@sjtu.edu.cn, {jingmu.lzy, xue.w, hankel.chk, huangsen.huang}@alibaba-inc.com
Abstract
Stock price forecasting has remained an extremely challeng-
ing problem for many decades due to the high volatility of the
stock market. Recent efforts have been devoted to modeling
complex stock correlations toward joint stock price forecast-
ing. Existing works share a common neural architecture that
learns temporal patterns from individual stock series and then
mixes up temporal representations to establish stock correla-
tions. However, they only consider time-aligned stock cor-
relations stemming from all the input stock features, which
suffer from two limitations. First, stock correlations often oc-
cur momentarily and in a cross-time manner. Second, the fea-
ture effectiveness is dynamic with market variation, which af-
fects both the stock sequential patterns and their correlations.
To address the limitations, this paper introduces MASTER, a
MArkert-Guided Stock TransformER, which models the mo-
mentary and cross-time stock correlation and leverages mar-
ket information for automatic feature selection. MASTER el-
egantly tackles the complex stock correlation by alternatively
engaging in intra-stock and inter-stock information aggrega-
tion. Experiments show the superiority of MASTER com-
pared with previous works and visualize the captured realistic
stock correlation to provide valuable insights.
Introduction
Stock price forecasting, which utilizes historical data col-
lected from the stock market to predict future trends, is a
vital technique for profitable stock investment. Unlike sta-
tionary time series that often exhibit regular patterns such
as periodicity and steady trends, the dynamics in the stock
price series are intricate because stock prices fluctuate sub-
ject to multiple factors, including macroeconomic factors,
capital flows, investor sentiments, and events. The mixing
of factors interweaves the stock market as a correlated net-
work, making it difficult to precisely predict the individual
behavior of stocks without taking other stocks into account.
Most previous works (Feng et al. 2019; Xu et al. 2021;
Wang et al. 2021, 2022; Wang, Qu, and Chen 2022) in the
field of stock correlation have relied on predefined concepts,
relationships, or rules and established a static correlation
graph, e.g., stocks in the same industry are connected to each
*This work was done during her internship at Alibaba Group.
† Corresponding author.
Copyright © 2024, Association for the Advancement of Artificial
Intelligence (www.aaai.org). All rights reserved.
time
stock sequences representations predictions
attention map
or 
graph
correlation module 
stocks
Figure 1: The framework of existing works. The dashed lines
represent the underlying momentary and cross-time stock
correlations, which reside between some (stock1, time1),
(stock2, time2) pairs.
other. While these methods provide insights into the rela-
tions between stocks, they do not account for real-time stock
correlations. For example, different stocks within the same
industry can experience opposite price movements on a par-
ticular day. Additionally, the pre-defined relationships may
not be generalizable to new stocks in an evolving market
where events such as company listing, delisting, or changes
in the main business happen normally. Another line of re-
search (Yoo et al. 2021) follows the Transformer architec-
ture (Vaswani et al. 2017) and uses the self-attention mech-
anism to compute dynamic stock correlations. This data-
driven manner is more flexible and applicable to the time-
varying stock sets in the market. Despite different schemes
for establishing stock correlations, the existing methods gen-
erally follow a common two-step computation flow. As de-
picted in Figure 1, the first step is using a sequential encoder
to summarize the historical sequence of stock features and
obtain stock representation, and the second step is to refine
each stock representation by aggregating information from
correlated stocks using graph encoders or attention mecha-
nism. However, such a flow suffers from two limitations.
First, existing works distill an overall stock representa-
tion and blur the time-specific details of stock sequence,
leading to weakness in modeling the de-facto stock corre-
lations, which often occurs momentarily and in a cross-time
manner (Bennett, Cucuringu, and Reinert 2022). To be spe-
cific, the stock correlation is highly dynamic and may re-
side in misaligned time steps rather than holding through the
whole lookback period. This is because the dominating fac-
tors of stock prices constantly change, and different stocks
may react to the same factors with different delays. For in-
stance, upstream companies’ stock prices may react faster to
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
162


## Page 2

a shortage of raw materials than those of downstream com-
panies, and individual stocks exhibit a lot of catch-up and
fall-behind behaviors.
Since the stock correlation may underlie between every
stock pair and time pair, a straightforward way to simu-
late the momentary and cross-time correlation is to gather
the τ × |S| feature vectors for pair-wise attention computa-
tion, where τ is the lookback window length and S is the
stock set. However, in addition to the increased computa-
tional complexity, this approach faces practical difficulties
because the stock forecasting task is in intense data hunger.
Intuitively, there are only around 250 trading days per year,
producing limited observations on stocks. When the model
adopts such a large attention field with insufficient training
samples, it often struggles to optimize and may even fall
into suboptimal solutions. Although clustering approaches
like local sensitive hashing (Kitaev, Kaiser, and Levskaya
2020) have been proposed to reduce the size of the attention
field, they are sensitive to initialization, which is a fatal issue
in a data-hungry domain like stock forecasting. To address
these challenges, we propose a novel stock transformer ar-
chitecture specifically designed for stock price forecasting.
Rather than directly modeling the τ × |S| attention field or
using clustering-based approximation methods, our model
aggregates information from different time steps and differ-
ent stocks alternately to model the realistic stock correlation
and facilitate model learning.
Another limitation of existing works is that they ignore
the impact of varying market status. In long-term practice
with the market variation, one essential observation by in-
vestors is that the features come into effect and expire dy-
namically. The effectiveness of features influences both the
intra-stock sequential pattern and the stock correlation. For
instance, in a bull market, the correlations among stocks are
more significant due to the investors’ optimism. Traditional
investors repeatedly conduct statistical examinations to se-
lect effective features, which are exhaustive and face a gap
when integrated with learning-based methods. To save hu-
man efforts, we are motivated to equip our stock transformer
with a novel gating mechanism, which incorporates the mar-
ket information to perform automatic feature selection. We
name the proposed method MASTER, standing forMArket-
Guided Stock TransformER. To summarize, our main con-
tributions are as follows.
• We propose a novel stock transformer for stock price
forecasting to effectively capture the stock correlation. To
the best of our knowledge, we are the first to mine the
momentary and cross-time stock correlation with learning-
based methods.
• We introduce a novel gating mechanism that integrates
market information to automatically select relevant features
and adapt to varying market scenarios.
• We conducted experiments to validate the designs of our
proposed method and demonstrated its superiority compared
to baselines. The visualization results provided valuable in-
sights into the real-time dynamics of stock correlations.
Methodology
Problem Formulation
The indicators of each stock u ∈ S are collected at every
time step t ∈ [1, τ] to form the feature vector xu,t ∈ RF .
Following existing works on stock market analysis (Feng
et al. 2018; Sawhney et al. 2020; Huynh et al. 2023), we
focus on the prediction of the change in stock price rather
than the absolute value. The return ratio, ˜ru = (c u,τ +d −
cu,τ +1)/cu,τ +1, is the relative close price change in d days,
where cu,t denotes the close price of stock u at time step
t, and d represents the predetermined prediction interval.
The return ratio normalizes the market price variety be-
tween different stocks in comparison to the absolute price
change. Since stock investment is to rank and select the
most profitable stocks, we perform daily Z-score normaliza-
tion of return ratio to encode the label with the rankings,
ru = Norm S (˜ru), as in previous work (Yang et al. 2020).
Definition 1 (Stock Price Forecasting) Given stock fea-
tures {xu,t}u∈S,t∈[1,τ ], the stock price forecasting is to
jointly predict the future normalized return ratio {ru}u∈S.
Overview
Figure 2 depicts the architecture of our proposed method
MASTER, which consists of five steps. (1)Market-Guided
Gating. We construct a vector representing the current mar-
ket status mτ and leverage it to rescale feature vectors by
a gating mechanism, achieving market-guided feature selec-
tion. (2) Intra-Stock Aggregation. Within the sequence of
each stock, at each time step, we aggregate information from
other time steps to generate a local embedding that preserves
the temporal local details of the stock while collecting all
important signals along the time axis. The local embedding
hu,t will serve as relays and transport the collected signals to
other stocks in subsequent modules. (3)Inter-Stock Aggre-
gation. At each time step, we compute stock correlation with
the attention mechanism, and each stock further aggregates
the local embeddings of other stocks. The aggregated infor-
mation zu,t, which we refer to as temporal embedding, con-
tains not only the information of the momentarily correlated
stocks at t but also preserves the personal information of u.
(4) Temporal Aggregation. For each stock, the last tempo-
ral embedding queries from all historical temporal embed-
dings to produce a comprehensive stock embedding eu. (5)
Prediction. The comprehensive stock embedding is sent to
prediction layers for label prediction. We elaborate on the
details of MASTER step by step in the following subsec-
tions.
Market-Guided Gating
Market Status Representation First, we propose to com-
bine information from two aspects into a vector mτ to give
an abundant description of the current market status. (1)
Market index price. The market index price is a weighted
average of the prices of a group of stocks S ′ by their share
of market capitalization. S ′ is typically composed of top
companies with the most market capitalization, represent-
ing a particular market or sector, and may differ from user-
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
163


## Page 3

𝑦1,1 𝑦1,𝜏
time
𝑦1,2 …
ℎ1,1
stocks
𝑧1,1 𝑧1,𝜏𝑧1,2
𝑒𝑢
𝑒1
4. Temporal Aggregation
2. Intra-Stock Aggregation
5. Prediction
ℎ𝑢,1
ℎ1,2
ℎ𝑢,2
ℎ1,𝜏
ℎ𝑢,𝜏
𝑢
𝑣
𝑖
𝑗
𝑧𝑢,𝑖
ℎ𝑣,𝑖
y𝑣,𝑗
Time Step 𝒊
Stock 𝒗
cross-time correlationƸ𝑟𝑢
Ƹ𝑟1
3. Inter-Stock Aggregation
1. Market-Guided Gating
𝑚𝜏 Gate
෤𝑥1,1
𝑥1,1
Feature Layer
…
…
…
Figure 2: Overview of the MASTER framework.
interested stocks in investing S. We include both the cur-
rent market index price at τ and the historical market index
prices, which are described by the average and standard de-
viation in the past d′ days to reveal the fluctuations. Here,d′
specifies the referable interval length to introduce historical
market information in applications. (2) Market index trading
volume. The trading volumes of S ′ reveal the investors in-
volvement, reflecting the activity of the market. We include
the average and standard deviation of market index trading
volume in the past d′ days, to reveal the actual size of the
market. S ′ and d′ are identical to the aforementioned defi-
nitions. Now we present the market-guided stock price fore-
casting task.
Definition 2 (Market-Guided Stock Price Forecasting)
Given {xu,t}u∈S,t∈[1,τ ] and the constructed market status
vector mτ , market-guided stock price forecasting is to
jointly predict the future normalized return ratio {ru}u∈S.
Gating Mechanism The gating mechanism generates one
scaling coefficient for each feature dimension to enlarge or
shrink the magnitude of the feature, thereby emphasizing
or diminishing the amount of information from the feature
flowing to the subsequent modules. The gating mechanism
is learned by the model training, and the coefficient is op-
timized by how much the feature contributes to improve
forecasting performance, thus reflecting the feature effec-
tiveness.
Given the market status representation mτ , |mτ | = F ′,
we first use a single linear layer to transform mτ into the
feature dimension F = |xu,t|. Then, we perform Softmax
along the feature dimension to obtain a distribution.
α(mτ ) = F · softmaxβ(Wαmτ + bα),
where Wα, bα are learnable matrix and bias,β is the temper-
ature hyperparameter controlling the sharpness of the output
distribution. Softmax compels competition among features
to distinguish the effective ones and ineffective ones. Here,
a smaller temperature β encourages the distribution to fo-
cus on certain dimensions and the gating effect is stronger
while a larger β makes the distribution inclined to even and
the gating effect is weaker. Note that we enlarge the value at
each dimension by F times as the scaling coefficient. This
operation compares the generated distribution with a uni-
form distribution where each dimension is 1/F , to deter-
mine whether to enlarge or shrink the value. The intuition
to generate coefficients from mτ is that the effectiveness of
features are influenced by market status. For example, if the
model learns moving average (MA) factor is useful during
volatile market periods, it will emphasize MA when the mar-
ket becomes volatile again. Under the samemτ , α are shared
for {xu,t}, u ∈ S , t ∈ [1, τ], in that we incorporate the most
recent market status to perform unified feature selection. The
rescaled feature vectors are ˜xu,t = α(mτ ) ◦ xu,t, where ◦ is
the Hadamard product.
Intra-Stock Aggregation
In MASTER, we use intra-stock aggregation followed by
inter-stock aggregation to break down the large and complex
attention field. Although the entire market is complicated
with diverse behaviors of individual stocks, the patterns of
a specific stock tend to be relatively continuous. Therefore,
we perform intra-stock aggregation first due to its smaller at-
tention field and simpler distribution. In our proposed intra-
stock aggregation, the feature at each time step aggregates
information from other time steps and forms a local embed-
ding. Compared with existing works which initially mix the
feature sequence into one representation (Yoo et al. 2021),
we maintain a sequence of local embeddings which are ad-
vised with the important signals in sequence through intra-
stock aggregation while reserving the local details.
We first send the rescaled feature vectors to a feature en-
coder and transform them into the embedding space, yu,t =
f (˜xu,t), |yu,t| = D. We simply use a single linear layer as
f (·). Then, we apply a bi-directional sequential encoder to
obtain the local output at each time step t. Inspired by the
success of transformer-based models in modeling sequential
patterns, we instantiate the sequential encoder with a single-
layer transformer encoder (Vaswani et al. 2017). Each fea-
ture vector at a particular time step is treated as a token, and
we add a fixed D-dimensional sinusoidal positional encod-
ing pt to mark the chronic order in the lookback window.
Yu = ||t∈[1,τ ]LN(f (˜xu,t) + pt),
where || denotes the concatenation of vectors and LN the
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
164


## Page 4

layer normalization. Then, the feature embedding at each
time step queries from all time steps in the stock sequence.
We introduce multi-head attention mechanisms, denoted as
MHA(·), with N1 heads to perform different aggregations in
parallel. We also utilize feed-forward layers,FFN(·), to fuse
the information obtained from the multi-head attention.
Q1
u = W 1
QYu, K 1
u = W 1
KYu, V 1
u = W 1
V Yu,
H 1
u = ||t∈[1,τ ]hu,t = FFN1(MHA1(Q1
u, K1
u, V 1
u ) + Yu),
where FFN is a two-layer MLP with ReLU activation and
residual connection. As a result, the local embedding hu,t
both reserves the local details and encodes indicative signals
from other time steps.
Inter-Stock Aggregation
Then, we consider aggregating information from correlated
stocks. Compared with existing works that distill an over-
all stock correlation, we establish a series of momentary
stock correlations corresponding to every time step. Instead
of using pre-defined relationships that face a mismatch with
the proximity of real-time stock movements, we propose to
mine the asymmetric and dynamic inter-stock correlation
via attention mechanism. The quality of the correlation will
be measured by its contribution to improving the forecast-
ing performance, and automatically optimized by the model
training process.
Specifically, at each time step, we gather the local embed-
dings of all stocks H 2
t = ||u∈S hu,t and perform multi-head
attention mechanism with N2 heads.
Q2
t = W 2
QH 2
t , K 2
t = W 2
KH 2
t , V 2
t = W 2
V H 2
t ,
Zt = ||u∈S zu,t = FFN2(MHA2(Q2
t , K2
t , V 2
t ) + H 2
t ).
With the residual connection of FFN, the temporal embed-
ding zu,t is encoded with both the information from momen-
tarily correlated stocks and the personal information of stock
u itself. Our stock transformer is able to model the cross-
time correlation of stocks, as shown in Figure 2 (Right). The
local details of yv,j can first be conveyed tohv,i by the intra-
stock aggregation of stock v, and then transmitted to zu,i
by inter-stock aggregation at time step i, hence modeling
the correlation from any (v, j) to (u, i). We further visualize
and explain the captured cross-time correlation in the exper-
iments section.
Temporal Aggregation
In contrast with existing works which obtain one embedding
for each stock after modeling stock correlation (Feng et al.
2019), our approach produces a series of temporal embed-
dings zu,t, t ∈ [1, τ]. Each zu,t is encoded with information
from stocks that are momentarily correlated with (u, t). To
summarize the obtained temporal embeddings, we employ a
temporal attention layer along the time axis.
λu,t = exp(zT
u,tWλzu,τ )
P
i∈[1,τ ] exp(zT
u,iWλzu,τ ) , e u =
X
t∈[1,τ ]
λu,tzu,t,
where we use the latest temporal embedding zu,τ as the
query vector, and compute the attention score λu,t in a hid-
den space with transformation matrix Wλ.
Prediction and Training
Finally, the comprehensive stock embedding eu is fed into
a predictor g(·) for label regression. We use a single linear
layer as the predictor, and the forecasting quality is mea-
sured by the MSE loss. In each batch, MASTER is jointly
optimized for all u ∈ S on a particular prediction date. A
training epoch is composed of multiple batches correspond-
ing to different prediction dates in the training set.
ˆru = g(eu), L =
X
u∈S
MSE(ru, ˆru).
Discussions
Relationships with Existing Works Modeling stock cor-
relations has long been an indispensable research direc-
tion for stock price prediction. Today, many researchers
and quantitative analysts, still opt for linear models, sup-
port vector machines, and tree-based methods for stock price
forecasting (Nugroho, Adji, and Fauziati 2014; Chen and
Guestrin 2016; Kamble 2017; Xie et al. 2013; Li et al. 2015;
Piccolo 1990). The aggregation of correlation information
within and between stocks is often achieved through fea-
ture engineering, which relies heavily on manual expertise
and constantly faces the risk of factor decay. Inspired by
the success of neural sequential data analysis, researchers
are driven to take into account the stock feature sequences
and learn the temporal correlation automatically. They de-
sign various sequential models, such as RNN-based (Feng
et al. 2019; Sawhney et al. 2021; Yoo et al. 2021; Huynh
et al. 2023), CNN-based (Wang et al. 2021), and attention-
based models(Liu et al. 2019; Ding et al. 2020), to mine the
internal temporal dynamics of a stock. Recent researches
focus on the modeling of stock correlation, which adds
a correlation module posterior to the sequential model as
illustrated in Figure 1. They propose to use graph-based
(Feng et al. 2019; Xu et al. 2021; Wang et al. 2021, 2022),
hypergraph-based (Sawhney et al. 2021; Huynh et al. 2023)
and attention-based (Yoo et al. 2021; Xiang et al. 2022)
modules to build the overall stock correlation and perform
joint prediction. Our MASTER is dedicated to momentary
and cross-time stock correlation mining. To do so, we de-
velop a novel model architecture as in Figure 2 that is
genuinely different from all existing methods. Furthermore,
MASTER is specialized for stock price forecasting, which
is distinct in data form and task properties from existing
transformer-based models in spatial-temporal data (Bulat
et al. 2021; Cong et al. 2021; Xu et al. 2020; Li et al. 2023)
or multivariate time series domains (Zhang and Yan 2022;
Nie et al. 2022).
Complexity Analysis We now analyze the computation
complexity of our proposed method. Let M = |S|, the
market-guided gating rescale M × τ feature vectors of
dimension F . In intra-stock aggregation, the calculation
amount of pair-wise attention is τ 2 for each stock at
each attention head. In inter-stock aggregation, the calcu-
lation amount is M 2 at each time step and each atten-
tion head. In temporal aggregation, we compute τ atten-
tion scores for each stock. The overall computation com-
plexity is O(F M τ + N1M τ2D2 + N2M 2τ D2 + M τ D2),
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
165


## Page 5

where M ≫ τ. Therefore, MASTER is of O(N2M 2τ D2)
time complexity. Compared with directly operating on the
M × τ attention field with N attention heads, which is
in O(N M 2τ 2D2), we reduce the computation cost by
about τ times and achieve modeling cross-time correla-
tions between stocks more efficiently. The overall param-
eters to be trained in MASTER are transformation matri-
ces W 1
Q, W 1
K, W 1
V , W 2
Q, W 2
K, W 2
V , Wλ, which is in shape
D × D, and parameters in MLP layers α, f, FFN1, FFN2
and g.
Experiments
In this section, we conduct experiments to answer the fol-
lowing four research questions:
• RQ1 How is the overall performance of MASTER com-
pared with state-of-the-art methods?
• RQ2 Is the proposed stock transformer architecture ef-
fective for stock price forecasting?
• RQ3 How do hyper-parameter configurations affect the
performance of MASTER?
• RQ4 What insights on the stock correlation can we get
through visualizing the attention map?
Datasets We evaluate our framework on the Chinese stock
market with CSI300 and CSI800 stock sets. CSI300 and
CSI800 are two stock sets containing 300 and 800 stocks
with the highest capital value on the Shanghai Stock Ex-
change and the Shenzhen Stock Exchange. The dataset
contains daily information ranging from 2008 to 2022 of
CSI300 and CSI800. We use the data from Q1 2008 to Q1
2020 as the training set, data in Q2 2020 as the validation
set, and the last ten quarters, i.e., Q3 2020 to Q4 2022, are
reserved as the test set. We apply the public Alpha158 in-
dicators (Yang et al. 2020) to extract stock features from
the collected data. The lookback window length τ and pre-
diction interval d are set as 8 and 5 respectively. For mar-
ket representation, we constructed 63 features with CSI300,
CSI500 and CSI800 market indices, and refereable interval
d′ = 5, 10, 20, 30, 60.
Baselines We compare the performance of MASTER with
several stock price forecasting baselines from different cate-
gories. • XGBoost (Chen and Guestrin 2016): A decision-
tree based method. According to the leaderboard of Qlib
platform (Yang et al. 2020), it is one of the strongest base-
lines. • LSTM (Graves and Graves 2012), GRU (Cho et al.
2014), TCN (Bai, Kolter, and Koltun 2018), and Trans-
former (Vaswani et al. 2017): Sequential baselines that lever-
age vanilla LSTM/GRU/temporal convolutional network/-
Transformer along the time axis for stock price forecasting.
• GAT (Veliˇckovi´c et al. 2017): A graph-based baseline,
which first uses sequential encoder to gain stock presenta-
tion and then aggregates information by graph attention net-
works1. • DTML (Yoo et al. 2021): A state-of-the-art stock
correlation mining method, which follows the framework in
Figure 1. DTML adopts the attention mechanism to mine the
1More discussion is provided in the supplementary materials.
dynamic correlation among stocks and also incorporates the
market information into the modeling.
Evaluation We adopt both ranking metrics and portfolio-
based metrics to give a thorough evaluation of the model
performance. Four ranking metrics, Information Coefficient
(IC), Rank Information Coefficient (RankIC), Information
Ratio-based IC (ICIR) and Information Ratio-based RankIC
(RankICIR) are considered. IC and RankIC are the Pearson
coefficient and Spearman coefficient averaged at a daily fre-
quency. ICIR and RankICIR are normalized metrics of IC
and RankIC by dividing the standard deviation. Those met-
rics are commonly used in literature (e.g., Xu et al. 2021 and
Yang et al. 2020) to describe the performance of the forecast-
ing results from the value and rank perspectives. Further-
more, we employ two portfolio-based metrics to compare
the investment profit and risk of each method. We simulate
daily trading using a simple strategy that selects the top 30
stocks with the highest return ratio and reports the Excess
Annualized Return (AR) and Information Ratio (IR) met-
rics. AR measures the annual expected excess return gener-
ated by the investment, while IR measures the risk-adjusted
performance of an investment.
Implementation We implemented MASTER 2 with Py-
Torch and build our methods based on the open-source quan-
titative investment platform Qlib (Yang et al. 2020). For
DTML, we implement it based on the original paper since
there is no official implementation publicly. For other base-
lines, we use their Qlib implementations. For hyperparame-
ters of each baseline method, the layer number and model
size are tuned from {1, 2, 3} and {128, 256, 512} respec-
tively. The learning ratelr is tuned among{10−i}i∈{3,4,5,6},
and we selected the best hyperparameters based on the IC
performance in the validation stage. For hyperparameters of
MASTER, we tune the model size D and learning rate lr
among the same range as the baselines, and the final selec-
tion is D=256, lr=10−5 for all datasets; we set N1=4, N2=2
for all datasets and β=5 and β=2 for CSI300 and CSI800
respectively. More implementation details of baseline meth-
ods are summarized in the supplementary materials. Each
model is trained for at most 40 epochs with early stopping.
All the experiments are conducted on a server equipped with
Intel(R) Xeon(R) Platinum 8163 CPU, 128GB Memory, and
a Tesla V100-SXM2 GPU (16GB Memory). Each experi-
ment was repeated 5 times with random initialization and
the average performance was reported.
Overall Performance (RQ1)
The overall performance is reported in Table 1 MAS-
TER achieves the best results on 6/8 of the ranking met-
rics, and consistently outperforms all benchmarks in the
portfolio-based metrics. In particular, MASTER achieve
13% improvements in ranking metrics and 47% improve-
ments in portfolio-based metrics compared to the second-
best results in the average sense. Note that ranking metrics
are computed with the whole set and portfolio-based metrics
2Code and supplementary materials are at https://github.com/
SJTU-Quant/MASTER
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
166


## Page 6

Dataset Model IC ICIR RankIC RankICIR AR IR
CSI300
XGBoost 0.051 ± 0.001 0.37 ± 0.01 0.050 ± 0.001 0.36 ± 0.01 0.23 ± 0.03 1.9 ± 0.3
LSTM 0.049 ± 0.001 0.41 ± 0.01 0.051 ± 0.002 0.41 ± 0.03 0.20 ± 0.04 2 .0 ± 0.4
GRU 0.052 ± 0.004 0.35 ± 0.04 0.052 ± 0.005 0.34 ± 0.04 0.19 ± 0.04 1 .5 ± 0.3
TCN 0.050 ± 0.002 0.33 ± 0.04 0.049 ± 0.002 0.31 ± 0.04 0.18 ± 0.05 1 .4 ± 0.5
Transformer 0.047 ± 0.007 0.39 ± 0.04 0.051 ± 0.002 0.42 ± 0.04 0.22 ± 0.06 2 .0 ± 0.4
GAT 0.054 ± 0.002 0.36 ± 0.02 0.041 ± 0.002 0.25 ± 0.02 0.19 ± 0.03 1 .3 ± 0.3
DTML 0.049 ± 0.006 0.33 ± 0.04 0.052 ± 0.005 0.33 ± 0.04 0.21 ± 0.03 1 .7 ± 0.3
MASTER 0.064∗ ± 0.006 0.42 ± 0.04 0.076 ∗ ± 0.005 0.49 ± 0.04 0.27 ± 0.05 2.4 ± 0.4
CSI800
XGBoost 0.040 ± 0.000 0.37 ± 0.01 0.047 ± 0.000 0.42 ± 0.01 0.08 ± 0.02 0 .6 ± 0.2
LSTM 0.028 ± 0.002 0.32 ± 0.02 0.039 ± 0.002 0.41 ± 0.03 0.09 ± 0.02 0 .9 ± 0.2
GRU 0.039 ± 0.002 0.36 ± 0.05 0.044 ± 0.003 0.39 ± 0.07 0.07 ± 0.04 0 .6 ± 0.3
TCN 0.038 ± 0.002 0.33 ± 0.04 0.045 ± 0.002 0.38 ± 0.05 0.05 ± 0.04 0 .4 ± 0.3
Transformer 0.040 ± 0.003 0.43 ± 0.03 0.048 ± 0.003 0.51 ± 0.05 0.13 ± 0.04 1 .1 ± 0.3
GAT 0.043 ± 0.002 0.39 ± 0.02 0.042 ± 0.002 0.35 ± 0.02 0.10 ± 0.04 0 .7 ± 0.3
DTML 0.039 ± 0.004 0.29 ± 0.03 0.053 ± 0.008 0.37 ± 0.06 0.16 ± 0.03 1.3 ± 0.2
MASTER 0.052∗ ± 0.006 0.40 ± 0.06 0.066 ± 0.007 0.48 ± 0.06 0.28∗ ± 0.02 2.3 ∗ ± 0.3
Table 1: Overall performance comparison. The best results are in bold and the second-best results are underlined. And * denotes
statistically significant improvement (measured by t-test with p-value < 0.01) over all baselines.
Model IC ICIR RankIC RankICIR AR IR
(MA)STER 0.064 ± 0.003 0.43 ± 0.02 0.074 ± 0.004 0.48 ± 0.04 0.25 ± 0.03 2.1 ± 0.3
(MA)STER-Bi 0.058 ± 0.005 0.38 ± 0.04 0.066 ± 0.008 0.41 ± 0.05 0.19 ± 0.03 1.6 ± 0.2
Naive 0.041 ± 0.008 0.30 ± 0.05 0.046 ± 0.007 0.32 ± 0.04 0.18 ± 0.05 1.6 ± 0.6
Clustering 0.044 ± 0.003 0.36 ± 0.02 0.049 ± 0.005 0.39 ± 0.04 0.18 ± 0.04 1.7 ± 0.3
Table 2: Experiments on CSI300 to validate the effectiveness of proposed stock transformer architecture. The best results are in
bold and the second-best results are underlined.
mostly consider the 30 top-performed stocks. The achieve-
ments in both types of metrics imply that MASTER is of
good predicting ability on the whole stock set without sacri-
ficing the accuracy of the important stocks. The significant
improvements cast light on the importance of stock corre-
lation modeling, so that each stock can also benefit from
the historical signals of other momentarily correlated stocks.
We also observed all methods gain better performance on
CSI300 over CSI800. We believe it is because CSI300 con-
sists of companies with larger capitalization whose stock
prices are more predictable. When compared to the exist-
ing stock correlation method (i.e., DTML), MASTER out-
performs in all 6 metrics, which tells the proposed Market-
Guided Gating and aggregation techniques are more effi-
cient in mining cross-stock information than existing liter-
ature.
Stock Transformer Architecture (RQ2)
We validate the effectiveness of our specialized stock trans-
former architecture by experiments on four settings. (1)
(MA)STER, which is our stock transformer without the gat-
ing. (2) (MA)STER-Bi, in which we substitute the single-
layer transformer encoder with a bi-directional LSTM to
evince that the effectiveness of our proposed architecture
is not coupled with strong sequential encoders. (3) Naive,
which directly performs information aggregation amongτ ×
|S| tokens. (4) Clustering, in which we adapt the Local Sen-
sitive Hashing (Kitaev, Kaiser, and Levskaya 2020) to allo-
cate all tokens into 10 buckets by similarity and perform ag-
gregation within each group, which is a classic task-agnostic
technique to reduce the scale of the attention field. For a fair
comparison, in (3) and (4), we first use the same transformer
encoder to extract token embedding and then use the same
multi-head attention mechanism as in our stock transformer,
so the only difference is the attention field. Due to resource
limits, we only experiment on CSI300 dataset. The results
in Table ?? illustrate the efficacy of our tailored stock trans-
former architecture, which performs intra-stock aggregation
and inter-stock aggregation alternatively.
Ablation Study (RQ3)
First, we conduct ablation study on (N1, N2) combination.
The results of CSI300 are shown in Figure 3 and the results
on CSI800 are similar. The difference among head combina-
tions is not significant compared with the inherent variance
under each setting. In the studied range, most settings con-
sistently performed better than the baselines.
Second, we study the influence of temperature β in the
gating mechanism. As explained before, a smaller β forces
a stronger feature selection while a largerβ turns off the gat-
ing effect. Figure 4 shows the performance with varying β.
The CSI300 is a relatively easier dataset where most fea-
tures are quite effective, so the temperature is expected to
be larger to relax the feature selection, while more powerful
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
167


## Page 7

N11
2
4
N2
1
2
4
0.056
0.064
IC
N11
2
4
N2
1
2
4
0.40
0.44
ICIR
N11
2
4
N2
1
2
4
0.06
0.07
0.08
RankIC
N11
2
4
N2
1
2
4
0.40
0.48
RankICIR
N11
2
4
N2
1
2
4
0.18
0.24
0.30
AR
N11
2
4
N2
1
2
4
1.6
2.0
2.4
IR
Figure 3: The average and standard deviation of metrics with different (N1, N2) combinations on CSI300.
1 2 5 10 20
0.040
0.048
0.056
0.064
IC
1 2 5 10 20
0.32
0.36
0.40
0.44
ICIR
1 2 5 10 20
0.056
0.064
0.072
0.080
RankIC
1 2 5 10 20
0.40
0.44
0.48
0.52
RankICIR
1 2 5 10 20
0.15
0.20
0.25
0.30
AR
1 2 5 10 20
1.2
1.6
2.0
2.4
2.8
IR
CSI300
CSI800
Figure 4: MASTER performance with varying β. The horizontal dash lines are performance without market-guided gating.
1
8
CNPC(SH601857)
1
8
ICBC(SH601398)
1
8
CATL(SZ300750)
Avg.
0.01
0.02
0.03
Figure 5: The correlation towards three target stocks on Aug
19th, 2022. The y-axis is time steps in the lookback win-
dow and the x-axis is source stocks. Avg. denotes the evenly
distributed value.
feature selection intervention is needed for the sophisticated
CSI800 dataset whose β of the best performance is smaller.
Visualization of Attention Maps (RQ4)
We show how MASTER captures the momentary and cross-
time stock correlation that previous methods are not ex-
pressive enough to model. Figure 5 shows the inter-stock
attention map at different time steps in the lookback win-
dow. We choose three representative stocks as the target
and sample 100 random stocks as sources for visualiza-
tion. The highlighted part is scattered instead of exhibit-
ing neat strips, implying that the correlation is momentary
rather than long-standing. Also, the inter-stock correlation
is sparse, with only a few stocks having strong correlations
toward the target stocks. Figure 6 displays the correlation
between stock pairs to show how the correlation resides in
time. From source stock v to target stock u, we compute
Iu←v[i, j] = S 1
v[i, j]S2
i [u, v] as the τ × τ correlation map,
while S1 and S2 are the intra-stock and inter-stock attention
map. First, the highlighted blocks are not centered on the di-
agonal, because the stock correlation is usually cross-time
rather than temporally aligned. Second, the left two figures
1 2 3 4 5 6 7 8
1
2
3
4
5
6
7
8
CNPC CATL, 19th
1 2 3 4 5 6 7 8
1
2
3
4
5
6
7
8
CATL CNPC, 19th
1 2 3 4 5 6 7 8
1
2
3
4
5
6
7
8
CNPC ICBC, 19th
1 2 3 4 5 6 7 8
1
2
3
4
5
6
7
8
CNPC ICBC, 25th
Avg.
0.001
0.002
Figure 6: Cross-time correlation of stock pairs on Aug 19th
and 25th, 2022. The x-axis is the source time steps and the
y-axis is the target time steps.
are totally different, illustrating that correlations are highly
asymmetric between u ← v and v ← u. Third, the impor-
tance of mined correlation changes slowly when the look-
back window slides to forecast on different dates. For exam-
ple, blocked regions in the right two figures correspond to
the same absolute time scope of different prediction dates,
whose patterns are to a certain degree similar.
Conclusion
We introduce a novel method MASTER for stock price fore-
casting, which models the realistic stock correlation and
guides feature selection with market information. MAS-
TER consists of five steps, market-guided gating, intra-stock
aggregation, inter-stock aggregation, temporal aggregation,
and prediction. Experiments on the Chinese market with 2
stock universe show that MASTER achieves averagely 13%
improvements on ranking metrics and 47% on portfolio-
based metrics compared with all baselines. Visualization of
attention maps reveals the de-facto momentary and cross-
time stock correlation. In conclusion, we provide a more
granular perspective for studying stock correlation, while
also indicating an effective application of market informa-
tion. Future work can explore mining stock correlations of
higher quality and study other uses of market information.
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
168


## Page 8

Acknowledgements
The authors would like to thank the anonymous review-
ers for their insightful reviews. This work is supported
by the National Key Research and Development Program
of China (2022YFE0200500), Shanghai Municipal Sci-
ence and Technology Major Project (2021SHZDZX0102),
and SJTU Global Strategic Partnership Fund (2021SJTU-
HKUST).
References
Bai, S.; Kolter, J. Z.; and Koltun, V . 2018. An empirical
evaluation of generic convolutional and recurrent networks
for sequence modeling. arXiv preprint arXiv:1803.01271.
Bennett, S.; Cucuringu, M.; and Reinert, G. 2022. Lead–
lag detection and network clustering for multivariate time
series with an application to the US equity market. Machine
Learning, 111(12): 4497–4538.
Bulat, A.; Perez Rua, J. M.; Sudhakaran, S.; Martinez, B.;
and Tzimiropoulos, G. 2021. Space-time mixing attention
for video transformer. Advances in neural information pro-
cessing systems, 34: 19594–19607.
Chen, T.; and Guestrin, C. 2016. Xgboost: A scalable tree
boosting system. In Proceedings of the 22nd acm sigkdd
international conference on knowledge discovery and data
mining, 785–794.
Cho, K.; Van Merri ¨enboer, B.; Gulcehre, C.; Bahdanau,
D.; Bougares, F.; Schwenk, H.; and Bengio, Y . 2014.
Learning phrase representations using RNN encoder-
decoder for statistical machine translation. arXiv preprint
arXiv:1406.1078.
Cong, Y .; Liao, W.; Ackermann, H.; Rosenhahn, B.; and
Yang, M. Y . 2021. Spatial-temporal transformer for dynamic
scene graph generation. In Proceedings of the IEEE/CVF in-
ternational conference on computer vision, 16372–16382.
Ding, Q.; Wu, S.; Sun, H.; Guo, J.; and Guo, J. 2020. Hier-
archical Multi-Scale Gaussian Transformer for Stock Move-
ment Prediction. In IJCAI, 4640–4646.
Feng, F.; Chen, H.; He, X.; Ding, J.; Sun, M.; and Chua,
T.-S. 2018. Enhancing stock movement prediction with ad-
versarial training. arXiv preprint arXiv:1810.09936.
Feng, F.; He, X.; Wang, X.; Luo, C.; Liu, Y .; and Chua, T.-
S. 2019. Temporal relational ranking for stock prediction.
ACM Transactions on Information Systems (TOIS), 37(2):
1–30.
Graves, A.; and Graves, A. 2012. Long short-term mem-
ory. Supervised sequence labelling with recurrent neural
networks, 37–45.
Huynh, T. T.; Nguyen, M. H.; Nguyen, T. T.; Nguyen, P. L.;
Weidlich, M.; Nguyen, Q. V . H.; and Aberer, K. 2023. Ef-
ficient integration of multi-order dynamics and internal dy-
namics in stock movement prediction. In Proceedings of the
Sixteenth ACM International Conference on Web Search and
Data Mining, 850–858.
Kamble, R. A. 2017. Short and long term stock trend predic-
tion using decision tree. In 2017 International Conference
on Intelligent Computing and Control Systems (ICICCS) ,
1371–1375. IEEE.
Kitaev, N.; Kaiser, Ł.; and Levskaya, A. 2020. Reformer:
The efficient transformer. arXiv preprint arXiv:2001.04451.
Li, L.; Duan, L.; Wang, J.; He, C.; Chen, Z.; Xie, G.;
Deng, S.; and Luo, Z. 2023. Memory-Enhanced Trans-
former for Representation Learning on Temporal Heteroge-
neous Graphs. Data Science and Engineering, 8(2): 98–111.
Li, Q.; Jiang, L.; Li, P.; and Chen, H. 2015. Tensor-based
learning for predicting stock movements. In Proceedings of
the AAAI Conference on Artificial Intelligence, volume 29.
Liu, J.; Lin, H.; Liu, X.; Xu, B.; Ren, Y .; Diao, Y .; and
Yang, L. 2019. Transformer-based capsule network for stock
movement prediction. In Proceedings of the first workshop
on financial technology and natural language processing ,
66–73.
Nie, Y .; Nguyen, N. H.; Sinthong, P.; and Kalagnanam, J.
2022. A Time Series is Worth 64 Words: Long-term Fore-
casting with Transformers. In The Eleventh International
Conference on Learning Representations.
Nugroho, F. S. D.; Adji, T. B.; and Fauziati, S. 2014. Deci-
sion support system for stock trading using multiple indica-
tors decision tree. In 2014 The 1st International Conference
on Information Technology, Computer, and Electrical Engi-
neering, 291–296. IEEE.
Piccolo, D. 1990. A distance measure for classifying
ARIMA models. Journal of time series analysis, 11(2): 153–
164.
Sawhney, R.; Agarwal, S.; Wadhwa, A.; Derr, T.; and Shah,
R. R. 2021. Stock selection via spatiotemporal hypergraph
attention network: A learning to rank approach. In Proceed-
ings of the AAAI Conference on Artificial Intelligence, vol-
ume 35, 497–504.
Sawhney, R.; Agarwal, S.; Wadhwa, A.; and Shah, R. R.
2020. Spatiotemporal hypergraph convolution network for
stock movement forecasting. In 2020 IEEE International
Conference on Data Mining (ICDM), 482–491. IEEE.
Vaswani, A.; Shazeer, N.; Parmar, N.; Uszkoreit, J.; Jones,
L.; Gomez, A. N.; Kaiser, Ł.; and Polosukhin, I. 2017. At-
tention is all you need. Advances in neural information pro-
cessing systems, 30.
Veliˇckovi´c, P.; Cucurull, G.; Casanova, A.; Romero, A.; Lio,
P.; and Bengio, Y . 2017. Graph attention networks. arXiv
preprint arXiv:1710.10903.
Wang, H.; Li, S.; Wang, T.; and Zheng, J. 2021. Hierarchi-
cal Adaptive Temporal-Relational Modeling for Stock Trend
Prediction. In IJCAI, 3691–3698.
Wang, H.; Wang, T.; Li, S.; Zheng, J.; Guan, S.; and Chen,
W. 2022. Adaptive long-short pattern transformer for stock
investment selection. In Proceedings of the Thirty-First
International Joint Conference on Artificial Intelligence ,
3970–3977.
Wang, Y .; Qu, Y .; and Chen, Z. 2022. Review of graph con-
struction and graph learning in stock price prediction. Pro-
cedia Computer Science, 214: 771–778.
Xiang, S.; Cheng, D.; Shang, C.; Zhang, Y .; and Liang, Y .
2022. Temporal and Heterogeneous Graph Neural Network
for Financial Time Series Prediction. In Proceedings of
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
169


## Page 9

the 31st ACM International Conference on Information &
Knowledge Management, 3584–3593.
Xie, B.; Passonneau, R.; Wu, L.; and Creamer, G. G. 2013.
Semantic frames to predict stock price movement. In Pro-
ceedings of the 51st annual meeting of the association for
computational linguistics, 873–883.
Xu, M.; Dai, W.; Liu, C.; Gao, X.; Lin, W.; Qi, G.-J.; and
Xiong, H. 2020. Spatial-temporal transformer networks for
traffic flow forecasting. arXiv preprint arXiv:2001.02908.
Xu, W.; Liu, W.; Wang, L.; Xia, Y .; Bian, J.; Yin, J.; and Liu,
T.-Y . 2021. Hist: A graph-based framework for stock trend
forecasting via mining concept-oriented shared information.
arXiv preprint arXiv:2110.13716.
Yang, X.; Liu, W.; Zhou, D.; Bian, J.; and Liu, T.-Y . 2020.
Qlib: An ai-oriented quantitative investment platform.arXiv
preprint arXiv:2009.11189.
Yoo, J.; Soun, Y .; Park, Y .-c.; and Kang, U. 2021. Accu-
rate multivariate stock movement prediction via data-axis
transformer with multi-level contexts. In Proceedings of the
27th ACM SIGKDD Conference on Knowledge Discovery &
Data Mining, 2037–2045.
Zhang, Y .; and Yan, J. 2022. Crossformer: Transformer uti-
lizing cross-dimension dependency for multivariate time se-
ries forecasting. In The Eleventh International Conference
on Learning Representations.
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
170
