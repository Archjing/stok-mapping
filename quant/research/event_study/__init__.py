"""Event-study research engine for the AI corpus.

纯函数事件研究核心：市场模型 → 异常收益/累计异常收益 → 截面显著性检验。

定位（研究情报 + 解释层）：量化"某政策/公告对个股或板块的冲击多大"。
不接入主 ranker，不把 CAR 当交易信号；结果只作为后续事件因子进入
admission 之前的假设依据。
"""
