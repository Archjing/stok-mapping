# macOS Tahoe 26 迁移判断原文备忘

不能说“直接无缝迁移”，但**代码、数据、文档主体可以迁移到 macOS Tahoe 26**。需要重建环境和改几处 OS 相关配置。

**可以直接迁移的部分**

- `phase0/` Python 代码主体
- `scripts/` 大部分 shell 脚本
- `config.yaml`
- `data/*.sqlite` 数据库文件
- `reports/`、`docs/`、`refdocs/` 文档与报告
- README、开发计划、任务清单

SQLite 数据库跨平台没问题，当前数据大约：

```text
data    3.9G
reports 90M
```

**不能直接照搬的部分**

- `.venv` 不建议迁移。macOS 上应重新创建虚拟环境。
- WSL 路径需要改：
  ```text
  /mnt/d/ZJ/Dev/brief_today/index.html
  ```
  这在 macOS 不存在。
- cron/systemd 配置不能直接照搬。macOS 没有 Linux systemd，建议改用 `launchd`，或者手动用 cron 也可以，但不如 launchd 原生。
- `service cron status`、`systemctl` 相关命令不能用。
- ECS 同步里的 `rsync` 可以用，但 macOS 自带 rsync 版本较老，建议 Homebrew 安装新版。
- 部分依赖如 `akshare`, `tushare`, `yfinance`, `numpy`, `pandas` 理论支持 macOS，但要在本机重新安装验证。
- `.env`、API token、SSH key、ECS 登录配置需要重新放到 Mac 上。

**推荐迁移步骤**

```bash
git clone <repo>
cd stok-mapping

python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

如果你用 `uv`：

```bash
uv sync
```

然后复制这些运行态资产：

```text
.env
data/
reports/   # 可选，想保留历史报告就复制
```

验证命令：

```bash
./.venv/bin/python -m phase0.cli brief watchlist --skip-update
./.venv/bin/python -m phase0.cli update-history --check-only
./.venv/bin/python -m phase0.cli update-us-market-history --check-only
./.venv/bin/python -m phase0.cli update-hk-market-history --check-only
```

**需要改代码/配置的地方**

最明确的一处是 [phase0/cli.py](/home/zj/workspace/stok-mapping/phase0/cli.py) 里这个硬编码路径：

```python
Path("/mnt/d/ZJ/Dev/brief_today/index.html")
```

迁移到 macOS 前建议改成配置项或环境变量，例如：

```text
BRIEF_LOCAL_MIRROR=/Users/<you>/Dev/brief_today/index.html
```

**结论**

项目主体具备迁移条件，但不是“拷过去马上完全等价运行”。  
最稳妥的判断是：

```text
代码和数据可迁移；
Python 环境、定时任务、路径镜像、密钥和网络代理需要在 macOS 上重建；
迁移后需要跑一轮 check-only 和 watchlist 验收。
```
