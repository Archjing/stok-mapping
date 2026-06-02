---
id: "02_mdgnn_stock_investment_prediction"
title: "MDGNN: Multi-Relational Dynamic Graph Neural Network for Comprehensive and Dynamic Stock Investment Prediction"
year: 2024
doi: "10.1609/aaai.v38i13.29381"
venue: "Proceedings of the AAAI Conference on Artificial Intelligence"
paper_url: "https://ojs.aaai.org/index.php/AAAI/article/view/29381"
pdf_url: "https://ojs.aaai.org/index.php/AAAI/article/download/29381/30608"
---
## Page 1

MDGNN: Multi-Relational Dynamic Graph Neural Network for Comprehensive
and Dynamic Stock Investment Prediction
Hao Qian1, Hongting Zhou1, Qian Zhao1, Hao Chen1, Hongxiang Yao2,
Jingwei Wang1, Ziqi Liu1, Fei Yu1, Zhiqiang Zhang1, Jun Zhou1*
1Ant Group,Hangzhou,China
2Alibaba Group,Hangzhou,China
{qianhao.qh,zhouhongting.zht,zq317110,chuhu.ch,wangjingwei.wjw,ziqiliu,lingyao.zzq,jun.zhoujun}@antgroup.com
henry.yhx@alibaba-inc.com
Abstract
The stock market is a crucial component of the financial sys-
tem, but predicting the movement of stock prices is challeng-
ing due to the dynamic and intricate relations arising from
various aspects such as economic indicators, financial reports,
global news, and investor sentiment. Traditional sequential
methods and graph-based models have been applied in stock
movement prediction, but they have limitations in capturing
the multifaceted and temporal influences in stock price move-
ments. To address these challenges, the Multi-relational Dy-
namic Graph Neural Network (MDGNN) framework is pro-
posed, which utilizes a discrete dynamic graph to comprehen-
sively capture multifaceted relations among stocks and their
evolution over time. The representation generated from the
graph offers a complete perspective on the interrelationships
among stocks and associated entities. Additionally, the power
of the Transformer structure is leveraged to encode the tem-
poral evolution of multiplex relations, providing a dynamic
and effective approach to predicting stock investment. Fur-
ther, our proposed MDGNN framework achieves the best per-
formance in public datasets compared with state-of-the-art
(SOTA) stock investment methods.
Introduction
The stock market is a crucial component of the financial
system, offering investors a marketplace to trade shares of
a wide range of assets. Nevertheless, predicting the move-
ment of stock prices is challenging due to the dynamic and
intricate relations arising from various aspects. The active
trading behaviors of investors, such as buying and selling,
drive the fluctuations in stock prices. Additionally, the stock
market is influenced by several factors, including economic
indicators, financial reports, global news, political events, in-
vestor sentiments, and many others. Hence, it’s indispens-
able to integrate comprehensive and multifaceted relations
to capture the dynamics of the stock markets accurately.
Two lines of research have been applied to stock move-
ment prediction. Traditional sequential methods (Hochre-
iter and Schmidhuber 1997; Chung et al. 2014; Feng et al.
2019a; Lin et al. 2021; Zhang, Aggarwal, and Qi 2017) pro-
pose to capture the temporal patterns of stock movement
*Corresponding author
Copyright © 2024, Association for the Advancement of Artificial
Intelligence (www.aaai.org). All rights reserved.
by optimizing the temporal dependency encoder, which em-
ploys sequential extraction techniques (Jain and Medsker
1999; Devlin et al. 2019). Nevertheless, the majority of these
methods still assume that stocks are independent of each
other and overlook the influence of complex relations. In
addition, graph-based models (Xu et al. 2021a; Chen and
Robert 2021a; Wang et al. 2021a; Sawhney et al. 2021;
Wang et al. 2022) incorporate heterogeneous information
explicitly from data or implicitly mine it from textual data to
capture the interdependence of stocks by designing various
graph representation methods. However, these approaches
could still be dissatisfactory due to the following two issues.
(1) Multifacetedness. The stock price movement is influ-
enced not only by a single factor but also by multiple re-
lations among stocks, industries, investment banks, etc. For
example, changes in the stock prices in a particular industry
can be caused by a variety of factors, such as high prod-
uct demand, new government policies, the rise of raw mate-
rial costs, and negative earnings reports from large compa-
nies. Similarly, investment banks can influence stock prices
in numerous ways, including conducting research on com-
panies, releasing positive or negative reports, and trading
shares. Therefore, accurately predicting the movement of
stock prices requires consideration of the multifaceted rela-
tions among stocks. Previous graph-based methods for stock
investment prediction have only utilized single relations be-
tween stocks, ignoring the potential of incorporating other
complex relations as auxiliary information.
(2) Temporal. The movement of stock prices and the
multifaceted relations among stocks are not static but ex-
hibit temporal evolution. Stock prices can change rapidly
due to external factors such as economic conditions, political
events, and regulatory changes, while internal factors such
as company earnings and industry performance can also in-
fluence the movement of stock prices over time. Relation-
ships among stocks change over time due to factors such as
investment banks trading stocks, common shareholders co-
holding stocks, and companies releasing products into new
industries. Hence, accurately predicting the movement of
stock prices and anticipating the impacts of these changes
requires a dynamic approach that considers the historical
trends and evolving relationships among stocks.
To address the aforementioned issues, we introduce a
novel framework to underline the multifacetedness and tem-
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
14642


## Page 2

poral influences in stock investment prediction and pro-
pose a Multi-relational Dynamic Graph Neural Network
(MDGNN). Overall, we utilize the discrete dynamic graph
framework to tackle the stock investment prediction. Specif-
ically, to comprehensively capture the multifacetedness na-
ture of stocks, we construct each graph snapshot with daily
stock information and relationship data, which is then an-
alyzed with a multi-relational graph embedding layer. The
generated representation from the multi-relational graph of-
fers a thorough and complete perspective on the interrela-
tionships among stocks and associated entities. Addition-
ally, we leverage the power of the Transformer structure to
encode the temporal evolution of multiplex relations, pro-
viding a dynamic and effective approach to predicting stock
investment. Our contributions are summarized as follows:
• We discuss the multifacetedness and temporal in the con-
text of stock investment prediction tasks. We also provide
insights on modeling complex stock relations based on
empirical evidence.
• We propose to capture the multifaceted and temporal
evolution nature of stocks with a multi-relational dy-
namic graph and generate a comprehensive representa-
tion of the stock market.
• We perform extensive experiments on public datasets to
verify the superiority of our proposed framework. With
detailed analysis, we demonstrate the effectiveness of the
multi-relational dynamic graph in tackling the stock in-
vestment prediction task.
Related Work
Stock Trend Prediction. In quantitative trading, the ability
to anticipate stock trends is crucial. To accomplish this task,
a multi-factor model is commonly employed, as detailed in
Nagel’s recent work (Nagel 2021). This model considers
several influential factors from an econometrics standpoint,
including trading volumes and prices, as well as company-
specific fundamental data like earnings and debt ratio.
When utilizing learning-based methods, it’s a common
practice to start with linear regression (Gu, Kelly, and Xiu
2020). Moreover, (Roy et al. 2015) utilized ordinary least
squares equipped with regularization, such as ridges and
lasso, to overcome the over-fitting issues. However, linear
models have limitations in capturing complicated patterns
in stock price trends. To overcome this limitation, attempts
have been made to incorporate more complex learning tech-
niques. XGBoost (Han, Kim, and Enke 2023) based method
is developed and evaluated through an empirical analysis of
companies listed on the NASDAQ. Neural-network-based
LSTM (Nelson, Pereira, and De Oliveira 2017) is utilized in
predicting future trends of stock prices and shows potential
to tackle the challenge of an immensely complex, chaotic,
and dynamic environment for the stock market.
Dynamic Graph Neural Networks. The above-mentioned
methods for predicting stock trends primarily concentrate
on individual stocks and disregard the interdependence and
resulting interactions between various stocks. For instance,
stocks that belong to the same supply chain are interrelated
due to profit transmission.
In recent years, GNN has gained great success owing to its
powerful capability of representing complex relations. Tra-
ditional GNN methods (e.g., GCN (Kipf and Welling 2017),
GAT (Veliˇckovi´c et al. 2018)) are mostly based on static
graphs where nodes and edges don’t change over time. How-
ever, many real-world relations (e.g., financial transactions,
social relations) are continuously evolving, in which dy-
namic graphs are indispensable to capture the advancing re-
lations. Several approaches have been proposed to represent
dynamic graphs. One method is RSR (Feng et al. 2019b),
which incorporates sector and supply chain relation informa-
tion into its temporal graph convolution. Another approach
is MGRN (Chen and Robert 2021b), which utilizes more re-
lationships such as historical price. This is calculated by the
correlation coefficient of two stocks’ daily return time series.
The multi-graph embedding combined with text embedding
extracted from the news is then fed into an LSTM network
to predict the stock trend. HATR (Wang et al. 2021b) takes
this further by introducing topicality associations in graph
modeling. Additionally, Concept-oriented shared informa-
tion for stock trend forecasting (Xu et al. 2021b) proposed to
mine hidden relations by designing a hidden concept mod-
ule. This approach successfully mined information beyond
that carried by predefined concepts. Evolvegcn (Pareja et al.
2020) exploits the combination of graph convolution and
RNN (Jain and Medsker 1999) to capture both the topologi-
cal structures and temporal relations.
Preliminary
Definition 1. Problem Formulation. Given that the rela-
tionships between stocks are multifaceted and changing on
a daily basis, we propose a Dynamic Graph Neural Net-
work (DGNN) to capture and represent them. Let G =
{G1, G2, ..., GT } represent DGNN, where Gt = ( Vt, Et, Rt)
is a multi-relational graph snapshot at trading day t and T
is the total number of snapshots. For a stock node vit ∈ V t,
the closing price at a trading day t is denoted as pit. The
ground-truth label of stock vit on trading day t based on the
return between two consecutive trading days is denoted as
yit = pi,t+1−pit
pit
− benchmarkt, in which benchmarkt is
the return of the benchmark index on trading day t.
We formulate the stock prediction as a node regression
task that utilizes DGNN to learn a scoring function,f (G; Θ),
parameterized by Θ. The scoring function is usually opti-
mized by minimizing the loss function as:
L =
X
N
ℓ{Y, f (G; Θ)}, (1)
where N is the set of training samples, andℓ is the loss com-
puted from each sample.
Algorithm Design
In the following sections, we will describe the architecture of
the MDGNN model as depicted in Figure 1, which includes
the Intra-day layer, the Inter-day Temporal Extraction layer,
and the prediction layer.
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
14643


## Page 3

…
(a.1) Multi-relational Graph Construction
…
V
Q
K
ALIBI position
Softmax
stock
embeddings
Bank
Industry
Invisible node
Visible nodeStock
History node
Future node
Sum
Multiply
Dot product
?
Excess
Return
(a.2) Hierarchical Multi-relational
Graph Embedding Layer
<latexit sha1_base64="qVbn7Vb/hXqPfVuNfqqKvrAfpmE=">AAAB73icbVDJSgNBEK2JWxK3qEcvjUHwFGZE1GPQiwcPEcyCyRB6Oj1Jk57F7hoxDPkJLyKKePXkv3jza7SzHDTxQcHjvSqq6nmxFBpt+8vKLCwuLa9kc/nVtfWNzcLWdk1HiWK8yiIZqYZHNZci5FUUKHkjVpwGnuR1r38+8ut3XGkRhdc4iLkb0G4ofMEoGqnRQhFwTS7bhaJdsscg88SZkmI5Fz/dfNx/V9qFz1YnYknAQ2SSat107BjdlCoUTPJhvpVoHlPWp13eNDSkZo2bju8dkn2jdIgfKVMhkrH6eyKlgdaDwDOdAcWenvVG4n9eM0H/1E1FGCfIQzZZ5CeSYERGz5OOUJyhHBhCmRLmVsJ6VFGGJqK8CcGZfXme1A5LznHp6MqkcQYTZGEX9uAAHDiBMlxABarAQMIDPMOLdWs9Wq/W26Q1Y01nduAPrPcfywWTiw==</latexit> 
⇥L
Step 2. Stock → Others
Step 1. Others → Stock
 Step 3. Meta-Path Aggregation
<latexit sha1_base64="PgauOwVwmHD1mYRbLYkfGWrCSmU=">AAAB6HicbZDJSgNBEIZr4hbHLerRS2MQPIUZEfUiBr14TCAbJEPo6dQkbXoWunuEEPIEXjwo4lUfxrsX8W3sLAdN/KHh4/+r6KryE8GVdpxvK7O0vLK6ll23Nza3tndyu3s1FaeSYZXFIpYNnyoUPMKq5lpgI5FIQ19g3e/fjPP6PUrF46iiBwl6Ie1GPOCMamOVK+1c3ik4E5FFcGeQv/qwL5P3L7vUzn22OjFLQ4w0E1Sppusk2htSqTkTOLJbqcKEsj7tYtNgRENU3nAy6IgcGadDgliaF2kycX93DGmo1CD0TWVIdU/NZ2Pzv6yZ6uDCG/IoSTVGbPpRkAqiYzLemnS4RKbFwABlkptZCetRSZk2t7HNEdz5lRehdlJwzwqnZTdfvIapsnAAh3AMLpxDEW6hBFVggPAAT/Bs3VmP1ov1Oi3NWLOeffgj6+0HEn2QHw==</latexit> 
T
<latexit sha1_base64="kcmDIo7ULXQDVDfszEiVXtbd/lo=">AAAB6HicbZBNS8NAEIYn9avGr6pHL8EieCqJiHoRi148tmA/oA1ls520azebsLsRSugv8OJBEa/6Y7x7Ef+N29aDtr6w8PC+M+zMBAlnSrvul5VbWFxaXsmv2mvrG5tbhe2duopTSbFGYx7LZkAUciawppnm2Ewkkijg2AgGV+O8cYdSsVjc6GGCfkR6goWMEm2squgUim7JnciZB+8Hihfv9nny9mlXOoWPdjemaYRCU06Uanluov2MSM0ox5HdThUmhA5ID1sGBYlQ+dlk0JFzYJyuE8bSPKGdifu7IyORUsMoMJUR0X01m43N/7JWqsMzP2MiSTUKOv0oTLmjY2e8tdNlEqnmQwOESmZmdWifSEK1uY1tjuDNrjwP9aOSd1I6rnrF8iVMlYc92IdD8OAUynANFagBBYR7eIQn69Z6sJ6tl2lpzvrp2YU/sl6/ATnlkDk=</latexit> 
n
<latexit sha1_base64="VBWwAgtPyAwQTB/4W3e4QbFDyfI=">AAAB5HicbZC7SgNBFIbPxltcb9HWZjAIVmFXRG3EoI1lBHOBZAmzk7PJmNnZZWZWCCFPYGOh2Ao+jL2N+DZOLoUm/jDw8f/nMOecMBVcG8/7dnJLyyura/l1d2Nza3un4O7WdJIphlWWiEQ1QqpRcIlVw43ARqqQxqHAeti/Huf1B1SaJ/LODFIMYtqVPOKMGmvd+u1C0St5E5FF8GdQvPxwL9L3L7fSLny2OgnLYpSGCap10/dSEwypMpwJHLmtTGNKWZ92sWlR0hh1MJwMOiKH1umQKFH2SUMm7u+OIY21HsShrYyp6en5bGz+lzUzE50HQy7TzKBk04+iTBCTkPHWpMMVMiMGFihT3M5KWI8qyoy9jWuP4M+vvAi145J/Wjoplq9gqjzswwEcgQ9nUIYbqEAVGCA8wjO8OPfOk/M6Lcw5s449+CPn7Qdm4I7V</latexit> 
1
<latexit sha1_base64="t0hkb5Xo8rLZGmoXAJxtYu3meOY=">AAAB6HicbZDJSgNBEIZr4hbHLerRS2MQPIWZIOpFDHrxmIBZIBlCT6cmadOz0N0jhJAn8OJBEa/6MN69iG9jZzlo4g8NH/9fRVeVnwiutON8W5ml5ZXVtey6vbG5tb2T292rqTiVDKssFrFs+FSh4BFWNdcCG4lEGvoC637/epzX71EqHke3epCgF9JuxAPOqDZWpdjO5Z2CMxFZBHcG+csP+yJ5/7LL7dxnqxOzNMRIM0GVarpOor0hlZozgSO7lSpMKOvTLjYNRjRE5Q0ng47IkXE6JIileZEmE/d3x5CGSg1C31SGVPfUfDY2/8uaqQ7OvSGPklRjxKYfBakgOibjrUmHS2RaDAxQJrmZlbAelZRpcxvbHMGdX3kRasWCe1o4qbj50hVMlYUDOIRjcOEMSnADZagCA4QHeIJn6856tF6s12lpxpr17MMfWW8/3uaP/Q==</latexit> 
2
<latexit sha1_base64="PgauOwVwmHD1mYRbLYkfGWrCSmU=">AAAB6HicbZDJSgNBEIZr4hbHLerRS2MQPIUZEfUiBr14TCAbJEPo6dQkbXoWunuEEPIEXjwo4lUfxrsX8W3sLAdN/KHh4/+r6KryE8GVdpxvK7O0vLK6ll23Nza3tndyu3s1FaeSYZXFIpYNnyoUPMKq5lpgI5FIQ19g3e/fjPP6PUrF46iiBwl6Ie1GPOCMamOVK+1c3ik4E5FFcGeQv/qwL5P3L7vUzn22OjFLQ4w0E1Sppusk2htSqTkTOLJbqcKEsj7tYtNgRENU3nAy6IgcGadDgliaF2kycX93DGmo1CD0TWVIdU/NZ2Pzv6yZ6uDCG/IoSTVGbPpRkAqiYzLemnS4RKbFwABlkptZCetRSZk2t7HNEdz5lRehdlJwzwqnZTdfvIapsnAAh3AMLpxDEW6hBFVggPAAT/Bs3VmP1ov1Oi3NWLOeffgj6+0HEn2QHw==</latexit> 
T
<latexit sha1_base64="UPQb/IaubSjMkBHbjUQN3puukK0=">AAAB6HicbZC7SgNBFIbPxltcb1FLm8UgWIVdFbURgzaWCZgLJEuYnZxNxszOLjOzQgh5AhsLRWz1YextxLdxcik08YeBj/8/hznnBAlnSrvut5VZWFxaXsmu2mvrG5tbue2dqopTSbFCYx7LekAUciawopnmWE8kkijgWAt616O8do9SsVjc6n6CfkQ6goWMEm2s8nErl3cL7ljOPHhTyF9+2BfJ+5ddauU+m+2YphEKTTlRquG5ifYHRGpGOQ7tZqowIbRHOtgwKEiEyh+MBx06B8ZpO2EszRPaGbu/OwYkUqofBaYyIrqrZrOR+V/WSHV47g+YSFKNgk4+ClPu6NgZbe20mUSqed8AoZKZWR3aJZJQbW5jmyN4syvPQ/Wo4J0WTspevngFE2VhD/bhEDw4gyLcQAkqQAHhAZ7g2bqzHq0X63VSmrGmPbvwR9bbD+Bqj/4=</latexit> 
3
<latexit sha1_base64="9+b3W2CrFYWK+k8VEEUDdkVcb7w=">AAAB6HicbZDJSgNBEIZr4hbHLerRS2MQPIUZCepFDHrxmIBZIBlCT6cmadOz0N0jhJAn8OJBEa/6MN69iG9jZzlo4g8NH/9fRVeVnwiutON8W5ml5ZXVtey6vbG5tb2T292rqTiVDKssFrFs+FSh4BFWNdcCG4lEGvoC637/epzX71EqHke3epCgF9JuxAPOqDZWpdjO5Z2CMxFZBHcG+csP+yJ5/7LL7dxnqxOzNMRIM0GVarpOor0hlZozgSO7lSpMKOvTLjYNRjRE5Q0ng47IkXE6JIileZEmE/d3x5CGSg1C31SGVPfUfDY2/8uaqQ7OvSGPklRjxKYfBakgOibjrUmHS2RaDAxQJrmZlbAelZRpcxvbHMGdX3kRaicF97RQrLj50hVMlYUDOIRjcOEMSnADZagCA4QHeIJn6856tF6s12lpxpr17MMfWW8/4e6P/w==</latexit> 
4
<latexit sha1_base64="blUzyv9b6wX9shT/fSRwDA4KQMc=">AAAB6HicbZDJSgNBEIZr4hbHLerRy2AQPIUZcbuIQS8eEzALJEPo6dQkbXp6hu4eIYQ8gRcPinjVh/HuRXwbO8tBE39o+Pj/KrqqgoQzpV3328osLC4tr2RX7bX1jc2t3PZOVcWppFihMY9lPSAKORNY0UxzrCcSSRRwrAW961Feu0epWCxudT9BPyIdwUJGiTZW+aSVy7sFdyxnHrwp5C8/7Ivk/csutXKfzXZM0wiFppwo1fDcRPsDIjWjHId2M1WYENojHWwYFCRC5Q/Ggw6dA+O0nTCW5gntjN3fHQMSKdWPAlMZEd1Vs9nI/C9rpDo89wdMJKlGQScfhSl3dOyMtnbaTCLVvG+AUMnMrA7tEkmoNrexzRG82ZXnoXpU8E4Lx2UvX7yCibKwB/twCB6cQRFuoAQVoIDwAE/wbN1Zj9aL9TopzVjTnl34I+vtB+NykAA=</latexit> 
5
<latexit sha1_base64="96na8Xamh4E10eFSoolCzliPs6I=">AAAB6HicbZDJSgNBEIZr4hbHLerRS2MQPIUZkehFDHrxmIBZIBlCT6cmadOz0N0jhJAn8OJBEa/6MN69iG9jZzlo4g8NH/9fRVeVnwiutON8W5ml5ZXVtey6vbG5tb2T292rqTiVDKssFrFs+FSh4BFWNdcCG4lEGvoC637/epzX71EqHke3epCgF9JuxAPOqDZWpdjO5Z2CMxFZBHcG+csP+yJ5/7LL7dxnqxOzNMRIM0GVarpOor0hlZozgSO7lSpMKOvTLjYNRjRE5Q0ng47IkXE6JIileZEmE/d3x5CGSg1C31SGVPfUfDY2/8uaqQ7OvSGPklRjxKYfBakgOibjrUmHS2RaDAxQJrmZlbAelZRpcxvbHMGdX3kRaicFt1g4rbj50hVMlYUDOIRjcOEMSnADZagCA4QHeIJn6856tF6s12lpxpr17MMfWW8/5PaQAQ==</latexit> 
6
(a) Intra-day Graph Snapshot (b) Inter-day Temporal Extraction Layer
<latexit sha1_base64="gBaOuhpXOC68tBWW7k6grNSe52A=">AAAB9HicbVDLSgMxFL1TX7W+qoIbN8EiuCozUtRlqQtdtmAf0A4lk2ba0ExmTDKFMvQ73LhQxKV+hV/gzo3fYqbtQlsPBA7n3Ms9OV7EmdK2/WVlVlbX1jeym7mt7Z3dvfz+QUOFsSS0TkIeypaHFeVM0LpmmtNWJCkOPE6b3vA69ZsjKhULxZ0eR9QNcF8wnxGsjeR2AqwHBPPkZtJ1uvmCXbSnQMvEmZNC+aj2zd4qH9Vu/rPTC0kcUKEJx0q1HTvSboKlZoTTSa4TKxphMsR92jZU4IAqN5mGnqBTo/SQH0rzhEZT9fdGggOlxoFnJtOQatFLxf+8dqz9KzdhIoo1FWR2yI850iFKG0A9JinRfGwIJpKZrIgMsMREm55ypgRn8cvLpHFedC6KpZppowIzZOEYTuAMHLiEMtxCFepA4B4e4AmerZH1aL1Yr7PRjDXfOYQ/sN5/AIiMlac=</latexit> 
G1
<latexit sha1_base64="Xjx83dcNWEQR9h69BWc3XeUuskg=">AAAB9HicbVDLSgMxFL1TX7W+qoIbN8EiuCozRdRlqQtdtmAf0A4lk2ba0ExmTDKFMvQ73LhQxKV+hV/gzo3fYqbtQlsPBA7n3Ms9OV7EmdK2/WVlVlbX1jeym7mt7Z3dvfz+QUOFsSS0TkIeypaHFeVM0LpmmtNWJCkOPE6b3vA69ZsjKhULxZ0eR9QNcF8wnxGsjeR2AqwHBPPkZtItdfMFu2hPgZaJMyeF8lHtm71VPqrd/GenF5I4oEITjpVqO3ak3QRLzQink1wnVjTCZIj7tG2owAFVbjINPUGnRukhP5TmCY2m6u+NBAdKjQPPTKYh1aKXiv957Vj7V27CRBRrKsjskB9zpEOUNoB6TFKi+dgQTCQzWREZYImJNj3lTAnO4peXSaNUdC6K5zXTRgVmyMIxnMAZOHAJZbiFKtSBwD08wBM8WyPr0XqxXmejGWu+cwh/YL3/AIoQlag=</latexit> 
G2
<latexit sha1_base64="y+vV0Dg64Dbf9DSpnb+XpLGiYEs=">AAAB9HicbVDLSgMxFL1TX7W+qoIbN8EiuCozIuqy1IUuW+gL2qFk0kwbmsmMSaZQhn6HGxeKuNSv8AvcufFbzLRdaOuBwOGce7knx4s4U9q2v6zMyura+kZ2M7e1vbO7l98/aKgwloTWSchD2fKwopwJWtdMc9qKJMWBx2nTG96kfnNEpWKhqOlxRN0A9wXzGcHaSG4nwHpAME9uJ91aN1+wi/YUaJk4c1IoHVW/2Vv5o9LNf3Z6IYkDKjThWKm2Y0faTbDUjHA6yXViRSNMhrhP24YKHFDlJtPQE3RqlB7yQ2me0Giq/t5IcKDUOPDMZBpSLXqp+J/XjrV/7SZMRLGmgswO+TFHOkRpA6jHJCWajw3BRDKTFZEBlpho01POlOAsfnmZNM6LzmXxomraKMMMWTiGEzgDB66gBHdQgToQuIcHeIJna2Q9Wi/W62w0Y813DuEPrPcfvZiVyg==</latexit> 
GT
<latexit sha1_base64="X2FM2zpvf+nmo7m9Wk7YGbeutaQ=">AAAB6HicbZC7SgNBFIbPxltcb1FLm8EgWIVdEbURgzaWCZgLJEuYnT1JxsxemJkVwpInsLFQxFYfxt5GfBsniYUm/jDw8f/nMOccPxFcacf5snILi0vLK/lVe219Y3OrsL1TV3EqGdZYLGLZ9KlCwSOsaa4FNhOJNPQFNvzB1Thv3KFUPI5u9DBBL6S9iHc5o9pY1aBTKDolZyIyD+4PFC/e7fPk7dOudAof7SBmaYiRZoIq1XKdRHsZlZozgSO7nSpMKBvQHrYMRjRE5WWTQUfkwDgB6cbSvEiTifu7I6OhUsPQN5Uh1X01m43N/7JWqrtnXsajJNUYselH3VQQHZPx1iTgEpkWQwOUSW5mJaxPJWXa3MY2R3BnV56H+lHJPSkdV91i+RKmysMe7MMhuHAKZbiGCtSAAcI9PMKTdWs9WM/Wy7Q0Z/307MIfWa/fKr2QLw==</latexit> 
d
Figure 1: The overview architecture of the MDGNN Model.
Intra-day Graph Snapshot
In this section, we outline the framework for capturing node
representations from graph snapshots generated on each
trading day. The framework comprises two key components:
the construction of the multi-relation graph and the graph
embedding layer.
Multi-relational Graph Construction The performance of
a single stock is influenced by a wide range of factors be-
yond its individual characteristics. As the stock markets are
complex and multifaceted, a singlet relation is not sufficient
to depict the intricate relations. As such, it is important to
consider the correlations between stocks from comprehen-
sive relations so that a more accurate picture of the overall
performance of stock markets can be depicted.
To tackle the intricacy of stock markets, we integrate rela-
tions from industry, investment banks, and stock pairs to es-
tablish a multi-relational graph. This approach enables us to
reveal these complex connections and offer a deeper under-
standing of the underlying dynamics of the financial system.
(1) Industry Graph: The performance of a company and
its corresponding stock is closely tied to the industry in
which it operates. For instance, as an industry is growing
rapidly, companies in that industry are likely to experience
increased demand for their products or services, which will
lead to higher revenue and profits. As a result, the stock
prices of these companies are likely to increase. Besides, the
products manufactured by a company can either serve as raw
materials for another industry or depend on the raw materi-
als produced by another industry. Therefore, any increase in
the cost of raw materials can result in an increase in the ex-
penses of companies. Additionally, government regulations
and policies toward industries can significantly impact the
associated companies. To be specific, we represent the stock
as S and the industry as I, while the connection between
them is denoted as ESI . This connection contains features
that encode the aforementioned supply, demand, competi-
tion, and regulatory connections to account for the impact
transmission from the industry.
(2) Investment Bank Graph: Investment banks greatly im-
pact stock because they provide a wide range of services
related to stock markets. Investment banks often act as mar-
ket makers for stocks, meaning they provide liquidity to
the market by buying and selling stocks on a regular ba-
sis. In addition, investment banks provide research reports
on stocks regarding the company’s financial performance,
industry trends, and other factors. These relationships allow
investment banks to have an impact on the price of the stock.
We extract the buy, sell, research, and advisory relations
from investment banks to capture the wield significant in-
fluence over stock prices. We denote the investment bank as
B and the connection between that and stock as ESB, which
incorporates the intricate aforementioned relations.
(3) Stock Graph: Stocks have a great impact on other
stocks because of the interconnectedness of the stock mar-
ket and the various factors that can affect stock prices. A
company’s earnings can lead to increased or reduced de-
mand for its stock, as well as other companies in the same
industry or sector. In some cases, companies can be held
by the same owners, in which the co-holding relations of-
fer a means of gauging the correlation among stocks. Addi-
tionally, common shareholders may engage in simultaneous
buying or selling of a company’s stock during a specific pe-
riod of time. Therefore, the performance of stocks can be
positively or negatively correlated with one another. To cap-
ture the interconnected nature of the stock market, we iden-
tify relationships between stocks based on factors such as
sector, ownership, and co-holding relations. These relation-
ships are denoted as ESS .
To create the multiplex relations mentioned earlier, we
start by gathering daily trading data and textual data such
as macroeconomic reports, financial news, financial state-
ments, and research reports from TuShare 1. We then em-
ploy financial lexicons and syntactic methods, as suggested
1https://tushare.pro/
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
14644


## Page 4

by (Wang, Wang, and Li 2020), to build the edges between
pairs of entities. Through intricate data preparation and ex-
traction processes, we construct a multi-relational graph that
integrates stocks, industries, and investment banks as nodes
and multiplex relations as edges.
Hierarchical Multi-relational Graph Embedding Layer
As stated above, we construct a multi-relational graph from
different relationships associated with stocks. This enables
us to capture complex representations of the relationships
between stocks, leading to a more comprehensive under-
standing of stock investment modeling. Concretely, we de-
fine a few meta-paths starting from stock nodes, such
as “Stock-Stock (SS )”, “Stock-Bank-Stock (SBS )”, and
“Stock-Industry-Industry-Stock (SIIS )”. As both nodes
and edges have a distinct impact on stock nodes, we pro-
pose a hierarchical graph embedding layer that can aggre-
gate and propagate information. Besides, edge features are
crucial in graph-based models as they encode essential infor-
mation about the relationships between nodes. For instance,
in the context of stock market prediction, the features that
encode supply, demand, competition, and regulatory con-
nections between an industry and its corresponding stocks
can provide valuable insights into the future trends of stocks.
Concretely, we utilize an attention mechanism when ag-
gregating information from neighborhood nodes, allowing
the model to attend to distinctive attributes of the edges and
the nodes they connect. As demonstrated in (Veli ˇckovi´c
et al. 2018), using multi-head attention in the graph attention
mechanism is advantageous. Hereby, the attention weight of
the k-th head when aggregating the neighbors of target node
vi is conducted as follows:
βij = aT [Whi||Whj||W eij],
αk
ij = exp(LeakyReLU(βij))
P
j′∈Ni
exp(LeakyReLU(βij′ )) , (2)
where Ni denotes the neighborhood nodes of the target node
i, || represents the concatenation operation, and W is the
shared projection matrix. Moreover, we aggregate represen-
tations from multiple heads and use average pooling to up-
date the target node’s representation as follows:
hi = σ

 1
K
KX
k=1
X
j∈Ni
αk
ijWkhj

 , (3)
where Wk is the shared projection matrix and K is the total
number of heads. Consequently, we obtain the stock repre-
sentations from each meta-path. Specifically, we define the
stock representations from the meta-paths “SS ”, “SBS ”,
and “SIIS ” as hi1, hi2, and hi3.
However, combining these representations effectively can
be a challenging task. Attention mechanisms provide a solu-
tion by allowing the model to selectively focus on the most
relevant representations for the target node. By assigning
different attention weights to each representation, the model
can effectively combine and aggregate the information from
multiple meta-paths. This process not only captures the most
critical information but also helps reduce the noise and re-
dundancy in the representations.
Specifically, we design a relation-aware graph module
that aggregates node and relation features from a multi-
relational graph in an adaptive manner as follows:
hvi = σ(
3X
j=1
Softmax(Whij)hij), (4)
where W is a learnable matrix and hvi is the representa-
tion of node vi after incorporating multiple relations among
nodes. By assigning different attention weights to each rep-
resentation, the model can prioritize the most informative
representations, enhancing the model’s ability to capture
important patterns and relationships. Moreover, analyzing
these weights makes it possible to understand the impor-
tance of each relation or meta-path in the final prediction.
This interpretability is crucial for understanding the reason-
ing behind the model’s decision-making process.
To enhance the representations of stock nodes, we stack
multiple hierarchical multi-relational graph embedding lay-
ers. The first layer captures local information, while subse-
quent layers capture increasingly global information. Hence,
as we stack multiple graph layers, nodes that are distant from
the originating node will be impacted. This facilitates the
modeling of the intricate relationships involved in the trans-
mission of stock information. This also enables the model to
learn complex patterns and relationships in the graph, lead-
ing to improved performance. Specifically, we stack L GNN
layers to obtain the representation of each stock node v on a
trading day t, denoted as hvt, using the final GNN layer.
Inter-day Temporal Extraction Layer
Although the node representation is obtained through the
graph embedding layer from each graph snapshot, the se-
mantics of stocks and the relationships between them are
constantly evolving. For instance, every day, securities com-
panies adjust their positions by selling the stocks of a com-
pany purchased the previous day while buying stocks of
companies that have not been purchased. Furthermore, the
features of stocks (e.g., the momentum, volatility, and yield
factors) are also changing due to the impact of market
changes every day. Therefore, it is essential to capture the
dynamic nature of nodes and the evolving relations among
graph snapshots in the temporal order.
To tackle the aforementioned challenge, we have devel-
oped a temporal extraction module that employs the trans-
former structure (Vaswani et al. 2017). This module enables
the extraction of the temporal evolution of graph snapshots’
propagation by taking in the representation of the target
nodes within a time window.
Concretely, let Hv,t−δt:t = {hvt′ |t − δt ≤ t′ ≤ t} repre-
sent the node’s representation, from trading day t and look-
ing back to the preceding δt trading days. Hereby, the win-
dow size δt is a hyperparameter. To facilitate with the struc-
ture, we transform hv,t−δt:t into query Q and key K, and
value V as follows:
Q = WQHv,t−δt:t,
K = WKHv,t−δt:t,
V = WVHv,t−δt:t,
(5)
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
14645


## Page 5

where WQ, WK, and WV are trainable weight matrices of
query, key, and value, respectively.
In addition, the temporal dependency of graph snapshots
is crucial for modeling the dependency in the node’s rep-
resentation. Over time, the historical relationship between
stocks and current price changes will diminish, making stock
prices more susceptible to the influence of recent events.
Hereby, we leverage the relative position method proposed
in ALIBI (Press, Smith, and Lewis 2022) that adds a static,
non-learnable bias to the query-key dot product. It intro-
duces an inductive bias in favor of recent events, as it im-
poses a penalty on attention scores between distant query-
key pairs. Moreover, the penalty increases in proportion to
the distance between a key and a query.
Moreover, we also employ the forward mask to prevent
positions in the input sequence from attending to subsequent
positions during the self-attention mechanism. It’s applied to
the attention mechanism’s softmax operation to mask out the
future positions, ensuring that each position can only attend
to the previous positions.
We calculate the dot product of query and key vectors
to capture information between any node pair via a self-
attention network, in which the multiplicative operation ef-
ficiently captures complex feature interactions. Then we ap-
ply the softmax function to scale the attention weight before
multiplying it with the corresponding value vector.
Z = softmax( QKT
√
d
+ m · P + M)V, (6)
where m is a slope parameter, P is the position bias in-
troduced from ALIBI, and M is the forward mask matrix.
Z combines the significant evolving patterns extracted from
the historical data between time period t − δt and t. zvt de-
notes the representation of stock node v on trading day t.
Prediction Layer
In stock investment prediction, we aim to estimate the prob-
ability ˆyvt that a given stock will yield a positive return on
trading day t based on the stock’s representationzvt as:
ˆyvt = σ(W1zvt + b1). (7)
where W1 and b1 are trainable matrices and bias; σ is the
sigmoid activation function.
Experiments
To validate the efficacy of our method, we conducted exten-
sive experiments using Chinese stock market data.
Experiment Setup
Datasets. First, we construct datasets using the CSI100
and CSI300 indices of China’s stock market with details
in Table 1. Next, we extract a set of 42-dimensional fea-
tures, which includes 25-dimensional market performance
features such as opening price, closing price, change per-
centage, volatility, and turnover rate, 12-dimensional com-
pany valuation features such as P/E ratio, P/B ratio, and
P/S ratio, 4-dimensional company categorical features, and
# stocks # banks # industries # edges
CSI100 100 196 97 18,950,706
CSI300 300 202 191 62,500,988
Table 1: Detailed statistics of the datasets.
1-dimensional institutional consensus expectations feature.
All of these features are normalized prior to analysis.
Backtest. We use the timeframe from 01/01/2020 to
02/31/2023 for backtest. The training cycle is set at half a
year, meaning that we train the model every six months, re-
sulting in a total of seven models in the experimental set
cycle. The training set utilizes data and labels from the pre-
ceding six months, while the validation set employs those
from last month. The model utilizes fixed parameter values
for prediction during the following six months.
Baselines. To show the performance of our proposed model,
we compare MDGNN with SOTA methods. We select the
following models as the baseline for comparison: (1) Tradi-
tional time series modeling methods (MLP, LSTM (Hochre-
iter and Schmidhuber 1997), Transformer (Devlin et al.
2019)). (2) Homogeneous graph methods (GCN (Kipf and
Welling 2017), GAT (Veliˇckovi´c et al. 2018)). (3) Hetero-
geneous graph methods (RGCN (Schlichtkrull et al. 2017),
HAN (Han, Kim, and Enke 2023), HGT (Hu et al. 2020)).
(4) Dynamic graph methods (EvolveGCN (Pareja et al.
2020), HTGNN (Fan et al. 2021)).
Metrics. We utilize Information Coefficient (IC) (Li et al.
2019), Information Ratio (IR), Cumulative Return (CR), and
Precision@K (J¨arvelin and Kek ¨al¨ainen 2000) as evaluation
metrics. IC evaluates the overall ranking performance, and
IR divides the excess return of a portfolio by its tracking
error. CR is the accumulated portfolio return based on the
prediction score. Precision@K evaluates whether the excess
returns of TopK stocks outperform the benchmark index.
Implementation Details. Our experiment is trained with
Nvidia V100 GPU, and all models are built using PyTorch.
The hidden size was set to 128, the number of GNN layers is
2, and the window size is 10. The training and validation sets
are kept consistent across all models. To ensure that all mod-
els receive sufficient training, we train each for 500 epochs
and implement an early stopping strategy.
Experiment Result
The results of our proposed method, as well as the other
baseline models, are presented in Table 2 for CSI100 and
CSI300 datasets. Our model outperforms all other methods
across all metrics. Based on these experimental findings, we
draw the following conclusions:
1) Time series modeling and static graphs: Traditional
time series modeling methods, such as MLP, primarily rely
on the intrinsic node features of the stock, while LSTM/-
Transformer places greater emphasis on temporal features.
However, homogeneous graph-based approaches, such as
GAT and GCN, only consider node features and stock con-
nections. Despite their inferior performance on the CSI100
dataset, these methods outperform Transformer on the larger
CSI300 dataset.
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
14646


## Page 6

Methods CSI 100 CSI 300
IC IR CR Prec@30 IC IR CR Prec@30
MLP 0.0027 0.0282 0.1166 0.4751 0.0039 0.0314 0.1721 0.4958
(2.25e-03) (2.26e-02) (8.10e-03) (8.17e-04) (9.42e-04) (1.53e-02) (1.08e-02) (1.01e-03)
LSTM 0.0040 0.0335 0.1289 0.4808 0.0049 0.0345 0.1859 0.4958
(1.27e-03) (1.31e-02) (1.90e-03) (2.70e-04) (6.84e-04) (1.09e-02) (1.29e-02) (1.99e-03)
Transformer 0.0058 0.0422 0.1383 0.4987 0.0063 0.0442 0.2122 0.5065
(2.50e-03) (1.51e-02) (7.47e-02) (3.22e-03) (1.95e-03) (1.28e-02) (1.14e-01) (6.03e-03)
GAT 0.0031 0.0274 0.1534 0.4812 0.0066 0.0454 0.2653 0.4991
(9.08e-04) (7.63e-03) (2.45e-02) (2.31e-03) (1.50e-03) (2.46e-02) (2.42e-02) (3.00e-04)
GCN 0.0038 0.0305 0.1616 0.4927 0.0075 0.0674 0.2816 0.5055
(1.34e-03) (9.36e-03) (8.64e-03) (2.33e-03) (9.85e-04) (3.80e-02) (2.88e-02) (2.04e-03)
RGCN 0.0104 0.0578 0.1912 0.4985 0.0090 0.0845 0.5159 0.5104
(1.29e-03) (7.47e-03) (2.84e-02) (2.59e-03) (1.69e-03) (1.42e-02) (5.32e-02) (1.85e-03)
HAN 0.0108 0.0525 0.2267 0.4997 0.0086 0.0848 0.3511 0.5112
(4.08e-04) (2.69e-03) (2.48e-02) (3.25e-03) (4.68e-03) (4.53e-02) (5.72e-02) (4.53e-03)
HGT 0.0112 0.0657 0.2384 0.5036 0.0115 0.0874 0.4108 0.4923
(1.35e-03) (7.46e-03) (1.98e-02) (4.72e-03) (2.05e-03) (1.17e-02) (5.65e-02) (6.93e-03)
EvolveGCN 0.0065 0.0538 0.1815 0.4961 0.0080 0.5012 0.4989 0.4830
(3.54e-04) (3.18e-03) (2.81e-02) (2.26e-03) (3.46e-04) (4.69e-03) (6.09e-02) (3.11e-03)
HTGNN 0.0118 0.0724 0.2643 0.5039 0.0192 0.1773 0.4653 0.5126
(3.76e-03) (2.45e-02) (8.23e-02) (3.54e-03) (7.59e-04) (9.94e-03) (7.03e-02) (1.12e-03)
MDGNN 0.0123 0.0746 0.2741 0.5081 0.0322 0.2488 0.9828 0.5232
(2.75e-03) (1.59e-02) (8.11e-02) (3.22e-03) (2.43e-03) (4.19e-03) (1.13e-02) (3.01e-03)
Table 2: Results of methods on public datasets. The last row in each dataset indicates the percentage of improvements gained
by the proposed method w.r.t the best-performed baseline. Prec@k is a shortened form of Precision@k.
2) Heterogeneous and dynamic graphs: The inclusion
of diverse heterogeneous graph information in algorithms,
such as RGCN, HAN, and HGT, has led to notable perfor-
mance enhancements over prior approaches. Additionally,
we compared time series heterogeneous graph-based meth-
ods such as EvolveGCN and HTGNN, which are designed
for temporal and multi-relational graphs, respectively. Our
findings suggest that the incorporation of both temporal
and multi-relational graph information can yield further im-
provements in performance.
3) Our proposed method: Our proposed MDGNN al-
gorithm, leveraging enhanced modules to capture informa-
tion from the distinctive multi-relational graph structure of
stocks, surpasses previous time series heterogeneous graph-
based algorithms on both datasets. Moreover, the perfor-
mance improvement is more pronounced in the CSI300
dataset compared to the CSI100 dataset. This outcome can
be attributed to the inclusion of additional institutional and
industry nodes, which results in a larger training graph and
enables more effective information propagation. These find-
ings provide further evidence of the effectiveness of con-
structing graphs for stock trend prediction.
Ablation Study
Effect of Components.To validate the design choices in our
proposed framework, we perform an ablation experiment by
removing four components individually: edge weight (w/o
edge), meta-path (w/o meta-path), hierarchical aggregation
(w/o aggregation), and temporal extraction layer (w/o tem-
poral). The experiment is performed on the CSI300 dataset,
and the results are presented in Table 3. We observe that the
removal of the meta-path module results in the most signifi-
cant decrease in performance, thereby confirming the effec-
tiveness of the multi-relational graph in our framework.
IC IR CR Prec@30
w/o edge 0.0268 0.2155 0.8950 0.5152
w/o meta-path 0.0216 0.1723 0.7502 0.5076
w/o aggregation 0.0303 0.2392 0.9402 0.5227
w/o temporal 0.0286 0.2226 0.8745 0.5215
MDGNN 0.0322 0.2488 0.9828 0.5232
Table 3: The results of the effect of components.
Effect of Relations. To further confirm the effectiveness of
each relationship in our multi-relational graph, we present
the results in Table 4. Here, SS , SB, SI , and II refer to
the relationships between stocks and stocks, stocks and in-
vestment banks, stocks and industries, and industries and in-
dustries, respectively. The default connection between dif-
ferent node types is bidirectional, and if the required edges
in the meta-path are removed, the corresponding meta-path
will also be removed. With the SB and SI edges, the per-
formance improves to some extent, thereby confirming our
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
14647


## Page 7

(a)
601838.SH
601009.SH
600919.SH000002.SZ
Commercial Bank Services
J.P. Morgan Broking (Hong Kong) Limited
Figure 2: The results of the case study.
basic assumption of constructing a multi-relational graph,
namely that the stock price changes of stocks held by the
same investment bank or belonging to the same industry ex-
hibit a certain degree of consistency. Furthermore, the intro-
duction of the connection between investment banks yields
a more significant effect than the connection between in-
dustries, as the former brings about greater differences in
information when multiple investment banks hold a stock,
whereas it can only belong to one industry.
SS SB SI II IC IR CR Prec@30
✓ - - - 0.0217 0.1727 0.7372 0.5128
✓ ✓ - - 0.0264 0.2092 0.8220 0.5203
✓ - ✓ - 0.0210 0.1632 0.7133 0.5101
✓ - ✓ ✓ 0.0217 0.1802 0.7755 0.5134
✓ ✓ ✓ - 0.0283 0.2300 0.9074 0.5208
✓ ✓ ✓ ✓ 0.0322 0.2488 0.9828 0.5232
Table 4: The results of the effect of relations.
Case Study
A research report on investment bank holdings reveals a ris-
ing credit pulse trend from December 2021 to March 2022,
accompanied by an increase in the proportion of bank hold-
ings by international investment institutions. To analyze this
trend, we focus on Chengdu Bank (601838.SH) and its sub-
graph, which consists of four stock nodes: Chengdu Bank
(601838.SH), Nanjing Bank (601009.SH), Jiangsu Bank
(600919.SH), and Vanke A (000002.SZ). The first three
stocks belong to the commercial banking service industry
and are held by the same institution. The last stock belongs
to the real estate industry and is held by a different institu-
tion, which also holds both Vanke A and Jiangsu Bank.
Figure 2(b) shows the average stock change rates for the
four selected stocks between January 4 and 17, 2022. Tra-
ditional temporal models predict negative change rates for
most bank-related stocks, except for 000002.SZ. However,
the MDGNN model enables the upward trend to propagate
through multiple relation graphs, influencing the change
rates of all bank-related stocks and leading to an increase
in the change rate of 600919.SH. Further analysis of the av-
erage stock change rates of three key industries during this
period is shown in Figure 2(c). The findings indicate that
the utilization of multiple relational graphs has a more pro-
nounced influence on banks and real estate than securities.
Hyperparameter Study
We also design some experiments to check the sensitivity of
hyperparameters. In Figure 3(a), the changes in cumulative
return are depicted across different window sizes. It appears
that increasing the window size improves the effect, but only
up to a certain limit for information capture. Similarly, as the
number of GNN layers increases in Figure 3(b), the effect
also improves gradually, but an excessively high complexity
can lead to a decline in performance.
Figure 3: The results of hyperparameter study.
Conclusion
In this work, we formally define the multifacetedness and
temporal patterns of stocks through empirical analysis for
the first time and propose a novel hierarchical multi-
relational dynamic graph framework for modeling stock in-
vestment prediction. Our approach involves constructing a
multi-relational graph for each trading day and generating
a set of discrete graph snapshots within the specified look-
back window size. In terms of the intra-day graph snapshot,
we design a hierarchical multi-relational graph embedding
layer to first aggregate the neighbor nodes within a specific
meta-path and then adaptively integrate the stock representa-
tion from distinct meta-paths. Furthermore, we incorporate
the transformer structure to aggregate the temporal evolving
patterns of stocks. We demonstrate the effectiveness and ro-
bustness of our proposed framework through extensive ex-
periments. In the future, we would like to study MDGNN
with contrastive learning methods for stock investment pre-
diction and improve performance even further.
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
14648


## Page 8

References
Chen, Q.; and Robert, C. Y . 2021a. Graph-Based Learning
for Stock Movement Prediction with Textual and Relational
Data. In The Journal of Financial Data Science.
Chen, Q.; and Robert, C.-Y . 2021b. Graph-based learning
for stock movement prediction with textual and relational
data. arXiv preprint arXiv:2107.10941.
Chung, J.; Gulcehre, C.; Cho, K.; and Bengio, Y . 2014. Em-
pirical Evaluation of Gated Recurrent Neural Networks on
Sequence Modeling. arXiv:1412.3555.
Devlin, J.; Chang, M.-W.; Lee, K.; and Toutanova, K. 2019.
BERT: Pre-training of Deep Bidirectional Transformers for
Language Understanding. 4171–4186.
Fan, Y .; Ju, M.; Zhang, C.; Zhao, L.; and Ye, Y .
2021. Heterogeneous Temporal Graph Neural Network.
arXiv:2110.13889.
Feng, F.; Chen, H.; He, X.; Ding, J.; Sun, M.; and Chua, T.-S.
2019a. Enhancing Stock Movement Prediction with Adver-
sarial Training. In Proceedings of the Twenty-Eighth Inter-
national Joint Conference on Artificial Intelligence, IJCAI-
19, 5843–5849. International Joint Conferences on Artificial
Intelligence Organization.
Feng, F.; He, X.; Wang, X.; Luo, C.; Liu, Y .; and Chua, T.-
S. 2019b. Temporal relational ranking for stock prediction.
ACM Transactions on Information Systems (TOIS), 37(2):
1–30.
Gu, S.; Kelly, B.; and Xiu, D. 2020. Empirical asset pric-
ing via machine learning. The Review of Financial Studies,
33(5): 2223–2273.
Han, Y .; Kim, J.; and Enke, D. 2023. A machine learning
trading system for the stock market based on N-period Min-
Max labeling using XGBoost. Expert Systems with Applica-
tions, 211: 118581.
Hochreiter, S.; and Schmidhuber, J. 1997. Long Short-Term
Memory. Neural Computation, 9(8): 1735–1780.
Hu, Z.; Dong, Y .; Wang, K.; and Sun, Y . 2020. Het-
erogeneous Graph Transformer. In Proceedings of The
Web Conference 2020, WWW ’20, 2704–2710. New York,
NY , USA: Association for Computing Machinery. ISBN
9781450370233.
Jain, L. C.; and Medsker, L. R. 1999. Recurrent Neural Net-
works: Design and Applications. USA: CRC Press, Inc., 1st
edition. ISBN 0849371813.
J¨arvelin, K.; and Kek¨al¨ainen, J. 2000. IR Evaluation Meth-
ods for Retrieving Highly Relevant Documents. In Pro-
ceedings of the 23rd Annual International ACM SIGIR Con-
ference on Research and Development in Information Re-
trieval, SIGIR ’00, 41–48. New York, NY , USA: Associa-
tion for Computing Machinery. ISBN 1581132263.
Kipf, T. N.; and Welling, M. 2017. Semi-Supervised Clas-
sification with Graph Convolutional Networks. In 5th In-
ternational Conference on Learning Representations, ICLR
2017, Toulon, France, April 24-26, 2017, Conference Track
Proceedings. OpenReview.net.
Li, Z.; Yang, D.; Zhao, L.; Bian, J.; Qin, T.; and Liu, T.-Y .
2019. Individualized Indicator for All: Stock-Wise Techni-
cal Indicator Optimization with Stock Embedding. In Pro-
ceedings of the 25th ACM SIGKDD International Confer-
ence on Knowledge Discovery & Data Mining, KDD ’19,
894–902. New York, NY , USA: Association for Computing
Machinery. ISBN 9781450362016.
Lin, H.; Zhou, D.; Liu, W.; and Bian, J. 2021. Learning Mul-
tiple Stock Trading Patterns with Temporal Routing Adap-
tor and Optimal Transport. In Proceedings of the 27th ACM
SIGKDD Conference on Knowledge Discovery & Data Min-
ing, KDD ’21, 1017–1026. New York, NY , USA: Associa-
tion for Computing Machinery. ISBN 9781450383325.
Nagel, S. 2021. Machine learning in asset pricing, vol-
ume 8. Princeton University Press.
Nelson, D. M.; Pereira, A. C.; and De Oliveira, R. A. 2017.
Stock market’s price movement prediction with LSTM neu-
ral networks. In 2017 International joint conference on neu-
ral networks (IJCNN), 1419–1426. Ieee.
Pareja, A.; Domeniconi, G.; Chen, J.; Ma, T.; Suzumura,
T.; Kanezashi, H.; Kaler, T.; Schardl, T.; and Leiserson,
C. 2020. EvolveGCN: Evolving Graph Convolutional Net-
works for Dynamic Graphs. Proceedings of the AAAI Con-
ference on Artificial Intelligence, 34(04): 5363–5370.
Press, O.; Smith, N. A.; and Lewis, M. 2022. Train Short,
Test Long: Attention with Linear Biases Enables Input
Length Extrapolation. arXiv:2108.12409.
Roy, S. S.; Mittal, D.; Basu, A.; and Abraham, A. 2015.
Stock market forecasting using LASSO linear regression
model. In Afro-European Conference for Industrial Ad-
vancement: Proceedings of the First International Afro-
European Conference for Industrial Advancement AECIA
2014, 371–381. Springer.
Sawhney, R.; Agarwal, S.; Wadhwa, A.; Derr, T.; and Shah,
R. R. 2021. Stock Selection via Spatiotemporal Hypergraph
Attention Network: A Learning to Rank Approach. Pro-
ceedings of the AAAI Conference on Artificial Intelligence ,
35(1): 497–504.
Schlichtkrull, M.; Kipf, T. N.; Bloem, P.; van den Berg, R.;
Titov, I.; and Welling, M. 2017. Modeling Relational Data
with Graph Convolutional Networks. arXiv:1703.06103.
Vaswani, A.; Shazeer, N.; Parmar, N.; Uszkoreit, J.; Jones,
L.; Gomez, A. N.; Kaiser, L. u.; and Polosukhin, I. 2017. At-
tention is All you Need. In Advances in Neural Information
Processing Systems, volume 30. Curran Associates, Inc.
Veliˇckovi´c, P.; Cucurull, G.; Casanova, A.; Romero, A.; Li`o,
P.; and Bengio, Y . 2018. Graph Attention Networks. Inter-
national Conference on Learning Representations.
Wang, H.; Li, S.; Wang, T.; and Zheng, J. 2021a. Hier-
archical Adaptive Temporal-Relational Modeling for Stock
Trend Prediction. In Zhou, Z.-H., ed., Proceedings of the
Thirtieth International Joint Conference on Artificial Intel-
ligence, IJCAI-21, 3691–3698. International Joint Confer-
ences on Artificial Intelligence Organization. Main Track.
Wang, H.; Li, S.; Wang, T.; and Zheng, J. 2021b. Hierarchi-
cal Adaptive Temporal-Relational Modeling for Stock Trend
Prediction. In IJCAI, 3691–3698.
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
14649


## Page 9

Wang, H.; Wang, T.; Li, S.; Zheng, J.; Guan, S.; and Chen,
W. 2022. Adaptive Long-Short Pattern Transformer for
Stock Investment Selection. In Raedt, L. D., ed., Proceed-
ings of the Thirty-First International Joint Conference on
Artificial Intelligence, IJCAI-22, 3970–3977. International
Joint Conferences on Artificial Intelligence Organization.
Main Track.
Wang, H.; Wang, T.; and Li, Y . 2020. Incorporating Expert-
Based Investment Opinion Signals in Stock Prediction: A
Deep Learning Framework. Proceedings of the AAAI Con-
ference on Artificial Intelligence, 34(01): 971–978.
Xu, W.; Liu, W.; Wang, L.; Xia, Y .; Bian, J.; Yin, J.; and Liu,
T.-Y . 2021a. HIST: A Graph-based Framework for Stock
Trend Forecasting via Mining Concept-Oriented Shared In-
formation. arXiv preprint arXiv:2110.13716.
Xu, W.; Liu, W.; Wang, L.; Xia, Y .; Bian, J.; Yin, J.; and Liu,
T.-Y . 2021b. Hist: A graph-based framework for stock trend
forecasting via mining concept-oriented shared information.
arXiv preprint arXiv:2110.13716.
Zhang, L.; Aggarwal, C.; and Qi, G.-J. 2017. Stock Price
Prediction via Discovering Multi-Frequency Trading Pat-
terns. In Proceedings of the 23rd ACM SIGKDD Interna-
tional Conference on Knowledge Discovery and Data Min-
ing, KDD ’17, 2141–2149. New York, NY , USA: Associa-
tion for Computing Machinery. ISBN 9781450348874.
The Thirty-Eighth AAAI Conference on Artiﬁcial Intelligence (AAAI-24)
14650
