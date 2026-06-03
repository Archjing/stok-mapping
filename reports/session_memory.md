## 2026-06-03 增量归档：解释类 / 研判计划类问答

> 来源 session：`/home/zj/.codex/sessions/2026/06/01/rollout-2026-06-01T18-04-42-019e82a4-8ddf-7f63-9b42-0ba3bf72aa37.jsonl`
> 完整归档规则：命中解释、解读、回答、详解、是非判断、研判、考虑、计划、为什么、是什么、如何、怎么、哪个；以及调研、检索、文献搜索、资料排序、数据源/API/权限/费用评估等主题型研究。
> 其他内容：未命中原文归档规则的会话内容、项目开发文档更新内容已压缩摘要归档。
> 上次已归档时间戳：未找到既有项目 memory 文件，本次新建 `reports/session_memory.md`。

### 👤 User / 用户 - 2026-06-02T13:08:38.630Z
定时任务执行没有

### 🤖 Assistant / 助手 - 2026-06-02T13:09:57.680Z
没有执行。

依据：
- `crontab -l` 里已经有项目入口：`* * * * * bash /home/zj/workspace/stok-mapping/scripts/run_project_scheduler.sh ...`
- 但 `service cron status` 显示：`cron is not running`
- `logs/project_scheduler.log` 是空的
- `logs/scheduler/` 没有运行状态文件
- 当前时间是 `2026-06-02 21:09:33 +0800`，已经过了今天 `07:20` 的日报触发时间

所以问题不是 crontab 没装，而是系统 cron 服务没启动。你手动启动：

```bash
sudo service cron start
```

启动后等 1 分钟，再看：

```bash
tail -n 50 /home/zj/workspace/stok-mapping/logs/project_scheduler.log
```

另外你刚才的 Git 命令写错了，正确格式是：

```bash
git rm --cached -r .claude .codex .agents prompts
```

### 👤 User / 用户 - 2026-06-02T13:10:57.250Z
现在cron服务是开机自启动吗

### 🤖 Assistant / 助手 - 2026-06-02T13:11:21.377Z
看起来是“配置为开机自启动”，但当前没运行。

证据：
- `systemctl is-enabled cron` 返回：`enabled`
- `/etc/rc2.d/S01cron` 等启动链接存在
- 但刚才 `service cron status` 返回：`cron is not running`

这里有个 WSL 常见点：如果 WSL 没有真正启用 systemd，传统“开机自启动”不一定会在每次打开 WSL 时生效。你这边 `sudo service cron start` 失败只是因为当前命令环境不能输入 sudo 密码，不代表服务不能启动。

你可以在自己的终端里直接执行：

```bash
sudo service cron start
service cron status
```

如果想让 WSL 每次启动自动拉起 cron，更稳的是在 `/etc/wsl.conf` 启用 systemd：

```ini
[boot]
systemd=true
```

然后在 Windows 里执行：

```powershell
wsl --shutdown
```

重新打开 WSL 后检查：

```bash
systemctl status cron
```

### 👤 User / 用户 - 2026-06-02T13:15:21.514Z
我现在要补一下今天全天的定时任务，从早报到16:30拉a股数据

### 🤖 Assistant / 助手 - 2026-06-02T13:17:45.108Z
已补跑今天漏掉的关键定时任务。

结果：
- 早报 `daily-brief` 已完成。
- A 股日线历史库已补到 `2026-06-02`。
- 插入 A 股日线数据：`5507` 行。
- 策略 panel cache 已刷新。
- 16:30 的 A 股增量任务再次检查为 `up_to_date`，没有重复插入。

生成产物：
- [phase0_premarket_watchlist_2026-06-03.csv](/home/zj/workspace/stok-mapping/reports/2026-06-03/phase0_premarket_watchlist_2026-06-03.csv)
- [phase0_premarket_report_2026-06-03.html](/home/zj/workspace/stok-mapping/reports/2026-06-03/phase0_premarket_report_2026-06-03.html)
- [phase0_daily_brief_ledger.csv](/home/zj/workspace/stok-mapping/data/simulated_trading/phase0_daily_brief_ledger.csv)

说明：日报的 `brief_date` 是 `2026-06-03`，因为这份报告是基于 `2026-06-02` 收盘数据生成的次日 07:30 盘前简报。当前工作区有这些新产物的本地变更。

### 👤 User / 用户 - 2026-06-02T13:21:25.213Z
日报的观察理由有些写的不对，检查代码逻辑，股票代码是002281的这一行，交易动作是卖出，观察理由是动量分数超过买入阈值，这可能不矛盾但是还是有些别扭的吧，意思是可以立即买回吗？

### 🤖 Assistant / 助手 - 2026-06-02T13:23:40.362Z
你判断是对的，这里确实别扭，而且是代码口径不一致导致的。

原因：
- `交易动作` 用的是连续模拟仓位口径：`sim_trade_action`
- `观察理由` 之前重新用策略信号口径 `_trade_action(row)` 判断
- 所以 `SZ.002281` 出现了“连续模拟要卖出”，但理由却按“策略候选仍满足买入阈值”去写

这不表示“可以立即买回”。更准确的解释是：它在策略信号层仍有一定动量分数，但连续模拟仓位层今天目标权重归零，所以当前动作应解释为卖出/退出，而不是买回提示。

我已修复：
- [export_premarket_watchlist.py](/home/zj/workspace/stok-mapping/scripts/export_premarket_watchlist.py:111) 里 `_trade_reason()` 现在优先使用 `sim_trade_action`
- 已重跑日报

`SZ.002281` 现在变成：
```text
交易动作：关注卖出
策略信号动作：候选观察
观察理由：排名跌出持有前10；已持有0个交易日
```

并检查了全表：`卖出/减仓` 行里已经没有“动量分数超过买入阈值”的观察理由。

### 👤 User / 用户 - 2026-06-02T13:53:29.006Z
告诉我刚才使用的完整命令行

### 🤖 Assistant / 助手 - 2026-06-02T13:53:42.483Z
刚才用于重跑日报的完整命令是：

```bash
./.venv/bin/python -m phase0.cli daily-brief --config config.yaml
```

随后用于抽查 `002281` 和校验卖出理由的命令是：

```bash
./.venv/bin/python - <<'PY'
import pandas as pd
path='reports/2026-06-03/phase0_premarket_watchlist_2026-06-03.csv'
df=pd.read_csv(path, encoding='utf-8-sig')
print(df[df['股票代码'].astype(str).str.contains('002281')].to_string(index=False))
print('\n卖出/减仓且理由含买入阈值行数:', len(df[df['交易动作'].astype(str).str.contains('卖|减仓', regex=True) & df['观察理由'].astype(str).str.contains('买入阈值')]))
PY
```

### 👤 User / 用户 - 2026-06-02T13:54:30.096Z
更新数据的命令行

### 🤖 Assistant / 助手 - 2026-06-02T13:54:38.020Z
更新 A 股日线历史数据的命令是：

```bash
./.venv/bin/python -m phase0.cli update-history --config config.yaml
```

今天补跑时，`daily-brief` 也会先自动执行这个更新步骤：

```bash
./.venv/bin/python -m phase0.cli daily-brief --config config.yaml
```

### 👤 User / 用户 - 2026-06-02T15:10:20.128Z
把每日简报同步发送到远程ECS服务器上的脚本怎么写。（先不改，我一会儿给你网址）

### 🤖 Assistant / 助手 - 2026-06-02T15:10:33.272Z
可以先按这个思路写，等你给 ECS 地址后再落地到脚本。

推荐用 `rsync` over SSH，同步本地固定入口目录：

```bash
rsync -avz --delete \
  /home/zj/workspace/stok-mapping/reports/brief_today/ \
  USER@ECS_HOST:/path/to/brief_today/
```

如果只同步单个 HTML：

```bash
scp \
  /home/zj/workspace/stok-mapping/reports/brief_today/index.html \
  USER@ECS_HOST:/path/to/brief_today/index.html
```

更适合做成脚本的版本大概是：

```bash
#!/usr/bin/env bash
set -euo pipefail

LOCAL_DIR="/home/zj/workspace/stok-mapping/reports/brief_today/"
REMOTE="USER@ECS_HOST"
REMOTE_DIR="/path/to/brief_today/"

rsync -avz --delete "${LOCAL_DIR}" "${REMOTE}:${REMOTE_DIR}"
```

之后可以挂在 `daily-brief` 之后执行，或者作为 scheduler 里的独立任务。等你给我 ECS 的 host、用户名、目标目录、是否用密钥登录，我再帮你写成项目脚本。

### 👤 User / 用户 - 2026-06-02T15:18:46.715Z
REMOTE="root@39.105.102.5" 有密码,REMOTE_DIR="/brief/"

### 🤖 Assistant / 助手 - 2026-06-02T15:19:09.080Z
可以。先不改项目代码的话，手动同步命令如下。

同步整个 `brief_today/` 目录到 ECS 的 `/brief/`：

```bash
rsync -avz --delete \
  /home/zj/workspace/stok-mapping/reports/brief_today/ \
  root@39.105.102.5:/brief/
```

如果只传 `index.html`：

```bash
scp \
  /home/zj/workspace/stok-mapping/reports/brief_today/index.html \
  root@39.105.102.5:/brief/index.html
```

因为你现在是密码登录，运行后会提示输入 root 密码。不要把密码写进脚本。后续如果要放进定时任务，建议先给 ECS 配 SSH key，否则 cron 里没法交互输入密码。

### 👤 User / 用户 - 2026-06-02T15:19:55.043Z
好rsync

### 🤖 Assistant / 助手 - 2026-06-02T15:20:04.265Z
用这条：

```bash
rsync -avz --delete \
  /home/zj/workspace/stok-mapping/reports/brief_today/ \
  root@39.105.102.5:/brief/
```

含义：
- 本地同步源：`reports/brief_today/`
- 远端目标：`root@39.105.102.5:/brief/`
- `--delete`：远端 `/brief/` 中本地已不存在的文件也会删除，保持完全一致
- 第一次运行会要求输入 root 密码

如果只是想覆盖上传，不删除远端其他文件，可以去掉 `--delete`：

```bash
rsync -avz \
  /home/zj/workspace/stok-mapping/reports/brief_today/ \
  root@39.105.102.5:/brief/
```

### 👤 User / 用户 - 2026-06-02T15:19:55.043Z
登录需要输入passphrase

### 🤖 Assistant / 助手 - 2026-06-02T15:26:18.826Z
这说明你不是单纯“密码登录”，而是本机 SSH 私钥设置了 passphrase。`rsync` 通过 SSH 连接时会先要求解锁私钥。

手动同步时直接输入 passphrase 即可：

```bash
rsync -avz --delete \
  /home/zj/workspace/stok-mapping/reports/brief_today/ \
  root@39.105.102.5:/brief/
```

如果后面要放进定时任务，不能依赖交互输入 passphrase。推荐做法是先启动 `ssh-agent` 并添加私钥：

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa
```

如果你的私钥不是 `id_rsa`，换成实际路径，例如：

```bash
ssh-add ~/.ssh/id_ed25519
```

之后同一个 shell 会话里再跑 `rsync` 就不会重复问 passphrase。  
但 cron 定时任务仍然通常拿不到这个 agent，后续要自动化同步，最好专门配置一把用于该任务的部署 key，或者给 cron 显式传 `SSH_AUTH_SOCK`。

### 👤 User / 用户 - 2026-06-02T15:26:10.741Z
我想配置简单点取消passphrase

### 🤖 Assistant / 助手 - 2026-06-02T15:26:29.883Z
可以，把现有 SSH 私钥的 passphrase 清空即可。常见命令：

```bash
ssh-keygen -p -f ~/.ssh/id_rsa
```

如果你用的是 ed25519：

```bash
ssh-keygen -p -f ~/.ssh/id_ed25519
```

流程中它会问：
- `Enter old passphrase:` 输入当前 passphrase
- `Enter new passphrase:` 直接回车
- `Enter same passphrase again:` 再直接回车

之后 `rsync` 就不会再要求输入 passphrase：

```bash
rsync -avz --delete \
  /home/zj/workspace/stok-mapping/reports/brief_today/ \
  root@39.105.102.5:/brief/
```

注意：清空 passphrase 后，私钥文件本身就变得更敏感。至少确认权限是：

```bash
chmod 600 ~/.ssh/id_rsa
# 或
chmod 600 ~/.ssh/id_ed25519
```

### 👤 User / 用户 - 2026-06-02T16:36:49.705Z
现在的定时任务时用什么方式配置的，带我回顾一下

### 🤖 Assistant / 助手 - 2026-06-02T16:37:52.780Z
现在的定时任务是“一个系统 cron 入口 + 项目内部调度脚本”的方式。

**1. 系统 cron 只做一件事**
当前 `crontab -l` 是：

```cron
# stok-mapping project scheduler start
* * * * * bash /home/zj/workspace/stok-mapping/scripts/run_project_scheduler.sh >> /home/zj/workspace/stok-mapping/logs/project_scheduler.log 2>&1
# stok-mapping project scheduler end
```

也就是系统 cron 每分钟调用一次：

```bash
scripts/run_project_scheduler.sh
```

当前 cron 服务状态是：

```text
cron is running
```

**2. 具体任务由项目脚本判断**
真正的时间表写在：

```text
scripts/run_project_scheduler.sh
```

当前任务是：

```text
周一 03:30：update-financials
交易日 07:20：daily-brief
交易日 16:20：update-hk-market-history
交易日 16:30：update-history
交易日 17:10：update-us-market-history
```

对应命令：

```bash
./.venv/bin/python -m phase0.cli update-financials --config config.yaml
./.venv/bin/python -m phase0.cli daily-brief --config config.yaml
./.venv/bin/python -m phase0.cli update-hk-market-history --config config.yaml
./.venv/bin/python -m phase0.cli update-history --config config.yaml
./.venv/bin/python -m phase0.cli update-us-market-history --config config.yaml
```

**3. 去重和锁**
脚本用两个机制避免重复跑：

```text
logs/scheduler/<task>.last
logs/scheduler/locks/<task>.lock
```

逻辑是：
- 只有当前时间精确等于配置时间，比如 `07:20`，才触发。
- 同一个任务当天如果已有 `.last` 记录，就不再跑。
- 如果 lock 目录存在，说明任务正在跑，会跳过。

**4. 环境变量**
脚本会自动加载项目根目录的 `.env`：

```bash
source "${PROJECT_ROOT}/.env"
```

所以 Tushare、FRED、Tiingo、ECS 同步相关环境变量都可以从 `.env` 进来。

任务时间也可以通过环境变量覆盖，例如：

```bash
DAILY_BRIEF_TIME=07:20
A_SHARE_HISTORY_TIME=16:30
US_MARKET_HISTORY_TIME=17:10
HK_MARKET_HISTORY_TIME=16:20
FINANCIAL_FACTORS_TIME=03:30
```

**5. 当前风险点**
现在 `logs/project_scheduler.log` 和任务日志是空的，`logs/scheduler/` 里也还没有 `.last` 文件。这说明 cron 服务现在虽然是 running，但从上次启动到目前还没撞上任何任务触发分钟，或者刚启动不久。到下一个配置时间点后再看日志才有证据。

### 👤 User / 用户 - 2026-06-02T16:39:12.081Z
这个cron定时任务时什么时候创建启动的？

### 🤖 Assistant / 助手 - 2026-06-02T16:40:17.383Z
能确认的时间线是：

- **项目调度脚本创建时间**：`2026-06-02 06:05:32 +0800`  
  文件：`scripts/run_project_scheduler.sh`

- **cron 安装脚本创建/修改时间**：`2026-06-02 06:05:34 +0800`  
  文件：`scripts/install_dev_cron.sh`

- **项目 scheduler 日志文件首次出现时间**：`2026-06-02 06:07:01 +0800`  
  文件：`logs/project_scheduler.log`

- **代码提交时间**：`2026-06-02 06:16:33 +0800`  
  提交：`4521ab9 ops task: add cron ,keep step`

所以可以判断：**这个项目 cron 定时任务是在 2026-06-02 早上 06:05-06:07 左右创建/安装的，随后在 06:16 提交进 Git。**

但要区分两件事：

1. **任务配置创建时间**：大约 `2026-06-02 06:05-06:07`
2. **cron 服务是否一直运行**：不是一直稳定运行。昨天 `2026-06-02 21:09` 我们检查时，`cron is not running`。现在它是 running。

当前 crontab 入口是：

```cron
* * * * * bash /home/zj/workspace/stok-mapping/scripts/run_project_scheduler.sh >> /home/zj/workspace/stok-mapping/logs/project_scheduler.log 2>&1
```

cron 本身没有可靠记录“这条 crontab 具体哪一秒安装”的元数据，所以以上是根据脚本时间戳、日志文件时间戳和 Git 提交记录推断出的最准确结论。

### 👤 User / 用户 - 2026-06-02T16:41:15.569Z
那么解决这个风险让系统能够在服务保持拉起这个服务

### 🤖 Assistant / 助手 - 2026-06-02T16:42:52.968Z
当前风险点是：`/etc/wsl.conf` 已经写了 `systemd=true`，但当前 WSL 实际 PID 1 还是 `/init`，说明这个配置还没有通过重启 WSL 生效。

现在状态：

```text
/etc/wsl.conf:
[boot]
 systemd=true

PID 1:
init(Ubuntu-24. /init
```

**推荐修复方式**
在 Windows PowerShell 里执行：

```powershell
wsl --shutdown
```

然后重新打开 WSL，检查：

```bash
ps -p 1 -o comm,args
systemctl status cron
```

如果 systemd 生效，再执行一次：

```bash
sudo systemctl enable --now cron
```

之后 cron 会随 WSL 启动自动拉起；如果 cron 异常退出，也由 systemd 管理。

**如果 systemd 仍未生效**
可以用 WSL boot command 兜底，让每次 WSL 启动时强制启动 cron：

```bash
sudo tee /etc/wsl.conf >/dev/null <<'EOF'
[network]
generateResolvConf = false

[boot]
systemd=true
command="service cron start"
EOF
```

然后 Windows PowerShell：

```powershell
wsl --shutdown
```

重新打开 WSL 后验证：

```bash
service cron status
crontab -l
```

当前项目 crontab 已经装好，不需要重装。要解决的是 WSL 启动时 cron 服务本身被拉起。

## 其他会话内容压缩摘要

- 文档与远端追踪：用户要求将 `refdocs/PROJECT_ARCHITECTURE_OVERVIEW.md`、`refdocs/STRATEGY_DEVELOPMENT_GUIDELINES.md`、`refdocs/strategy_explanations/INDEX.md` 移动到 `docs/`，并更新 README。仓库中未找到 `refdocs/WEB_RESEARCH_REPORT_WORKFLOW.md`，因此只清理了 README 中的坏链接。后续又要求远端仓库不再追踪 `refdocs docs logs tasks`，曾提交 `8a059c0 stop tracking local docs and task folders`。随后用户手动执行 `git add -A` 又将 `docs/`、`logs/`、`refdocs/`、`tasks/` 重新加入并提交 `57560f3 ..`，最终 `git push` 成功，当前远端 main 到 `57560f3`。
- Logo 资产：根据用户要求从当前 SVG 重新渲染 PNG，修正中间最小公式位置，先向 logo 中心移动，再向左移到 `x=430`，同步更新 `assets/brand/stok-mapping-logo.svg`、`assets/brand/stok-mapping-wordmark.svg` 和对应 PNG。使用本地 Chromium/Playwright 内嵌 SVG 渲染；第一次 `<img src=file://...>` 生成空图，第二次内嵌 SVG 成功。
- 日报补跑与代码修复：执行 `./.venv/bin/python -m phase0.cli daily-brief --config config.yaml` 补跑，A 股历史库更新至 `2026-06-02`，插入 `5507` 行。随后执行 `./.venv/bin/python -m phase0.cli update-history --config config.yaml`，状态为 `up_to_date`。修复 `scripts/export_premarket_watchlist.py` 中观察理由口径，使 `_trade_reason()` 优先使用 `sim_trade_action`。
- README 更新：在 README 靠开头新增 `常用补跑 / 维护命令` 段落，记录 `daily-brief`、`premarket`、`update-history`、`update-us-market-history`、`update-hk-market-history`、`update-financials`、`build-universe`、`run` 等命令。
- 固定日报入口：在 `phase0/cli.py` 的 `daily-brief` 流程中复制生成的 HTML 到 `reports/brief_today/index.html`，后又扩展复制到 `/mnt/d/ZJ/Dev/brief_today/index.html`。验证命令为 `./.venv/bin/python -m phase0.cli daily-brief --config config.yaml --skip-update`，两份 `index.html` 与原始归档简报一致。
- ECS 同步：先讨论独立脚本 `scripts/sync_brief_to_ecs.sh`，默认 `root@39.105.102.5:/brief/`，首次验证时远端缺 `rsync` 报错。随后用户要求不要独立脚本，改为直接写到每日简报生成程序。最终在 `phase0/cli.py` 内新增带注释的 `_sync_daily_brief_to_ecs()`，执行 `rsync -avz --delete reports/brief_today/ root@39.105.102.5:/brief/`。验证成功，远端 `/brief/index.html` 创建并同步。
- cron/systemd：用户手动检查后，`service cron status` 显示 systemd 已生效，`cron.service` active running since `2026-06-03 00:43:58 CST`，并在 `00:44:01` 执行用户 crontab：`bash /home/zj/workspace/stok-mapping/scripts/run_project_scheduler.sh >> .../logs/project_scheduler.log 2>&1`。`crontab -l` 保持一个项目入口。
- Git 操作：用户提交 `0602 catchup` 后 push 被拒，因远端有新提交；后续 `git pull --rebase`、`git push` 成功。之后又提交 `68482f5 .`，push 被拒，执行 `git pull --rebase` 后 `git push` 到 `1ef935d`。最后用户把 `docs/logs/refdocs/tasks` 重新 `git add -A` 并提交 `57560f3 ..`，push 成功，`git status` 显示 clean。

## 2026-06-03 增量归档：调研、术语解释、模拟账户与 watchlist 架构调整

> 来源 session：
> - `/home/zj/.codex/sessions/2026/06/03/rollout-2026-06-03T10-01-08-019e8b36-8b55-7113-a02b-94686aa8e487.jsonl`
> - 当前 API 会话（本地 JSONL 未完整覆盖，按当前对话原文与已落地文件增量归档）
> 完整归档规则：命中解释、解读、回答、详解、是非判断、研判、考虑、计划、为什么、是什么、如何、怎么、哪个；以及调研、检索、文献搜索、资料排序、数据源/API/权限/费用评估等主题型研究。
> 其他内容：未命中原文归档规则的会话内容、项目开发文档更新内容已压缩摘要归档。
> 上次已归档时间戳：`reports/session_memory.md` 上一节末尾为 2026-06-02 cron/systemd 与 Git 操作摘要；本次追加 2026-06-03 调研、术语解释、账户账本和命令路由变更。

### 👤 User / 用户 - 2026-06-03T02:01:41.612Z
web search，个人股市投资者研究量化投资策略，模拟盈利，实盘亏损的讯息

### 🤖 Assistant / 助手 - 2026-06-03T02:02:21.827Z
我搜到的公开资料里，确实有不少“回测/模拟盘盈利，实盘亏损”的个人量化投资者案例和分析。重点如下：

**典型案例**
- 博客园「玖菜量化笔记」有一篇个人复盘：作者 2025 年初开始研究量化，2.5 万起步，后续加仓，最终总亏损 19,538 元，比例 -20.75%；其中量化实盘亏损 11,359 元，比例 -10.17%。作者提到早期通过调参数跑出漂亮回测曲线，但实盘遇到代码 bug、涨跌停无法成交、网络/持仓状态不同步、风格剧变和人工干预等问题。来源：[用2万起步量化投资1年，亏了多少，学到了什么？](https://www.cnblogs.com/jiucaiquant/p/19902261)
- 宽客在线有一篇较老但典型的文章：举例称有人把 demo 策略参数优化后，回测收益从 10% 提到 40%，实盘投入 10 万后遇到样本外行情，2 个月亏 20%，后来亏到 50%。来源：[回测很好，为什么实盘却不靠谱？](https://www.quantinfo.com/Article/View/296.html)
- BigQuant 的资料也提到高频/短线策略常见落差：某短线高频策略历史回测“亏损率近乎为零”，实盘首日因行情延迟、数据同步偏差导致多笔订单偏离预期，当日收益较回测预期下滑近 40%。来源：[高频策略落地关键](https://bigquant.com/wiki/doc/5dw14N7xQT)

**高频出现的原因**
- 过拟合：策略“背诵”历史数据，参数越调越漂亮，但样本外失效。学术资料也把 backtesting overfitting 作为量化策略评估中的重要问题。来源：[arXiv 1905.05023](https://arxiv.org/abs/1905.05023)
- 未来函数/信息泄露：回测不小心用了当时实际不可得的信息，比如事后知道某行业/股票强，再倒推策略。
- 成本低估：手续费、印花税、滑点、冲击成本、买卖价差没有真实计入。BigQuant 回测指南特别提醒，很多新手只设手续费，忽略滑点和冲击成本，导致实盘大幅亏损。来源：[BigQuant 量化回测指南](https://bigquant.com/wiki/doc/Z0tjAS5sWx)
- 成交假设不现实：回测默认按开盘价/收盘价成交，实盘可能买不到、卖不出，尤其是小盘股、低流动性股票、涨跌停、停牌、A 股 T+1。
- 模拟盘/Paper trading 太干净：模拟成交通常没有真实排队、盘口冲击、延迟、撤单失败、部分成交等问题。
- 心理和人工干预：模拟盈利时容易高估承受力，实盘连续亏损后停策略、手动平仓、加减仓，破坏原策略统计特征。

**给个人投资者的实用判断**
- 只看“年化收益”和“胜率”不够，要看样本外、滚动回测、不同市场阶段、最大回撤、换手率、单笔期望、成本敏感性。
- 回测里要故意加重成本：滑点、冲击成本、无法成交、T+1、涨跌停、停牌。
- 模拟盘盈利不能直接等同于可实盘盈利，尤其是高换手、低单笔利润、小盘股策略。
- 实盘先小资金、长时间跟踪，记录每笔“理论成交 vs 实际成交”的偏差，再决定是否放大资金。

一句话总结：公开资料的共同结论是，个人量化最常见的问题不是“不会写策略”，而是把回测/模拟当成了盈利证明。更严谨地说，回测最多只是“值得继续验证”的信号，不是实盘收益承诺。

### 👤 User / 用户 - 2026-06-03T02:04:36.799Z
再搜索一遍，这次多找几个案例，并分析原因

### 🤖 Assistant / 助手 - 2026-06-03T02:05:28.470Z
我又搜了一轮，结论更明确：这类信息很多，但“可审计的实盘账户流水级案例”少，大多数是个人博客、平台文章、社区复盘和研究论文。下面按可信度和信息量整理。

**新增案例**

1. **个人量化 2 万起步，最终亏损约 20.75%**
作者称 2025 年初开始量化投资，初始 2.5 万，后续加仓，最终总亏损 19,538 元，比例 -20.75%；其中量化实盘亏损 11,359 元，比例 -10.17%。  
原因包括：回测调参过度、代码 bug、涨跌停无法成交、网络/持仓状态不同步、风格剧变、人工干预。  
来源：[用2万起步量化投资1年，亏了多少，学到了什么？](https://www.cnblogs.com/jiucaiquant/p/19902261)

2. **Demo 策略回测 40%，实盘 2 个月亏 20%，后续亏到 50%**
宽客在线举例：复制 demo 策略后优化参数，回测收益从 10% 提到 40%，投入 10 万实盘后，遇到严监管、去杠杆、大股东减持等样本外事件，2 个月亏 20%，随后因拒绝止损继续亏到 50%。  
来源：[回测很好，为什么实盘却不靠谱？](https://www.quantinfo.com/Article/View/296.html)

3. **AI/LSTM 选股：回测年化 21%，模拟/实盘阶段亏 12.3%**
一篇 AI 量化复盘写到，LSTM 模型训练集准确率 68%，回测年化 21%、最大回撤 -16%、夏普 1.35；2024 年 10 月 8 日开始跑实盘/模拟，到 11 月底亏 12.3%。  
作者归因：过拟合、A 股市场风格变化、特征工程中使用了当日收盘后才知道的数据，形成 lookahead bias。  
来源：[我用AI量化策略模拟盘3个月亏损18.7%的完整复盘](https://www.cnblogs.com/pcdoctor/p/19916020)

4. **AI 情绪分析择时：文本理解有效，但金融语义迁移失败**
同一篇复盘还提到 AI 情绪分析择时案例：模型能处理文本，但对金融语义、市场预期、反身性理解不足，导致信号在真实行情中失效。  
来源同上：[cnblogs AI 量化复盘](https://www.cnblogs.com/pcdoctor/p/19916020)

5. **高频/短线策略：回测几乎不亏，实盘首日收益低于预期约 40%**
BigQuant 资料提到，短线高频策略历史回测“亏损率近乎为零”，但实盘首日因行情延迟、数据同步偏差，多笔订单偏离预期，当日收益较回测预期下滑近 40%。  
来源：[高频策略落地关键](https://bigquant.com/wiki/doc/5dw14N7xQT)

6. **FX 策略：三个月模拟实盘后发现回测规则不可执行**
SSRN 上有一篇独立研究，作者审计一个外汇 session breakout 策略。三个月 MetaTrader 5 demo live-paper-trading 后发现，原回测里的 trailing stop 规则在真实 MT5 条件下不可执行，因为止损修改会被平台拒绝。  
这不是实盘亏钱案例，但很典型：回测盈利逻辑在真实交易系统里根本无法按同样规则执行。  
来源：[What Survived Live Reconciliation](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5805443)

7. **期货隔夜策略：回测未计入跳空滑点，5 周损失 2.5%**
Pomegra 的 paper trading 教材举例：一个期货策略回测持仓隔夜，但模拟/前向测试中 5 周遇到三次跳空，仅隔夜 gap slippage 就造成账户 -2.5% 损失，而原回测没有计入。  
来源：[Why Paper Trade Before Going Live](https://pomegra.io/learn/library/track-e-trading-risk/active-trading/chapter-11-forward-testing-paper-trading/why-paper-trade-before-live)

8. **社区案例：回测盈利，实盘接近打平，加入 spread filter 后才改善**
Reddit r/algotrading 有交易者复盘：策略回测盈利，但实盘几乎只能打平；问题在于点差、部分成交、低流动性时段的尾部滑点，2-3 次事件就吃掉数月利润。  
这是社区个案，不如论文可靠，但非常贴近个人投资者。  
来源：[What broke first when I moved from backtesting to live](https://www.reddit.com/r/algotrading/comments/1ssh4lq/what_broke_first_when_i_moved_from_backtesting_to/)

**原因归纳**

第一类是**回测本身造假式乐观**：未来函数、幸存者偏差、复权/非复权处理错误、交易周期错位、NA 值处理错误、指标计算时间点错误。很多策略不是“实盘失效”，而是回测时已经错了。

第二类是**过拟合和数据挖掘**：参数越调越漂亮，本质是在记忆历史噪声。Quantpedia 对样本内/样本外策略分析指出，样本外夏普衰减 1/3 到 1/2 是合理预期；McLean & Pontiff 的 Journal of Finance 论文也显示，因子收益在样本外和发表后会明显衰减。  
来源：[Quantpedia](https://quantpedia.com/in-sample-vs-out-of-sample-analysis-of-trading-strategies/)、[McLean & Pontiff 2016](https://ideas.repec.org/a/bla/jfinan/v71y2016i1p5-32.html)

第三类是**交易成本低估**：手续费只是最小一块，真正杀伤高换手策略的是滑点、买卖价差、冲击成本、部分成交、撤单失败。尤其是日内、高频、网格、做市、低单笔利润策略，成本稍微高一点就从正期望变负期望。

第四类是**成交假设不现实**：回测里“开盘价买入”“收盘价卖出”很干净，实盘有涨跌停、停牌、T+1、盘口深度、排队、延迟、低流动性、限价单不成交、市价单滑点。

第五类是**市场状态变化**：训练期有效的风格，实盘期可能切换。比如小盘转大盘、成长转价值、高波动转低波动、牛市转震荡。策略如果只靠历史统计相关性，而没有经济逻辑或风控约束，很容易样本外坍塌。

第六类是**模拟盘心理不等于实盘心理**：模拟盘亏损不痛，实盘亏损会导致提前停策略、手动止损、加仓摊平、错过信号、临时改参数。很多策略不是机械系统亏，而是人和系统混在一起后亏。

**实用判断**

个人投资者看到一个“回测盈利”策略，至少要打这几个折扣：

- 回测年化先打 5 折，再看是否仍有吸引力。
- 成本加倍、滑点加倍后仍盈利，才值得继续看。
- 参数轻微变化后收益不崩，才可能不是过拟合。
- 样本外、滚动回测、前向模拟都过关，才考虑小资金实盘。
- 小资金实盘重点不是赚钱，而是记录“理论成交 vs 实际成交”的偏差。
- 如果策略利润主要来自高换手、低流动性、小盘股、尾盘/开盘瞬间成交，实盘落差风险最高。

一句话：个人量化最常见的亏损路径是“回测找到幻觉，模拟盘放大信心，实盘支付学费”。真正要验证的不是回测曲线有多漂亮，而是策略在脏数据、真实成本、不可成交、风格切换和人性压力下还能不能活。

### 👤 User / 用户 - 2026-06-03T02:09:39.702Z
怎么规避脏数据

### 🤖 Assistant / 助手 - 2026-06-03T02:10:01.403Z
规避脏数据的核心不是“找到一个完美数据源”，而是建立一套**数据验收、交叉校验、异常处理、回测防污染**流程。

**1. 不直接信任原始数据**

每次入库前做基础校验：

- 日期是否缺失、重复、乱序
- OHLC 是否合理：`low <= open/close <= high`
- 成交量/成交额是否为负、异常为 0
- 涨跌幅是否超过交易所限制
- 停牌日是否错误出现成交
- 除权除息日前后价格是否连续
- 股票代码、名称、上市/退市状态是否正确

A 股尤其要注意：复权价格、涨跌停、停牌、退市、ST、代码变更、合并重组。

**2. 多数据源交叉验证**

不要只用一个源。至少分层：

- 主数据源：例如 Tushare、AkShare、券商接口、交易所数据
- 对照源：东方财富、同花顺、Yahoo、聚宽、BigQuant 等
- 关键字段交叉：收盘价、成交量、复权因子、上市状态、财报日期

如果两个源不一致，不要自动取平均。应该标记为 `suspect`，人工或规则确认。

**3. 给数据打质量标签**

不要只存“干净数据”，还要存质量状态：

```text
raw        原始抓取
validated 通过规则校验
suspect   存疑，需要复核
patched   已修正
excluded  回测中排除
```

回测时只允许使用 `validated` 或经过说明的 `patched` 数据。

**4. 保留原始数据，不覆盖**

永远保留 raw 表。修正数据写到 normalized/clean 表，并记录来源：

```text
symbol
trade_date
field
old_value
new_value
source
reason
patched_at
```

这样以后发现问题，可以追溯是哪条规则改坏了数据。

**5. 防止未来函数污染**

这是量化里最隐蔽的“脏数据”。

尤其注意：

- 财报数据不能用公告日之前的数据
- 指数成分股不能用今天的成分回测过去
- ST、退市、行业分类不能用事后状态回填历史
- 复权因子要确认是否会引入未来分红送股信息
- 因子计算必须只用 `t` 日收盘前可得的数据
- 交易信号生成日和实际成交日要错开

原则：回测某一天时，只能看到那一天真实可获得的信息。

**6. 对异常值做“隔离”，不要粗暴删除**

比如某只股票一天涨跌 30%，可能是：

- 数据错误
- 除权除息
- 新股/北交所/科创板特殊规则
- 停复牌
- 真实极端行情

正确做法是先标记异常，再结合事件表判断。不能简单 winsorize 或删除，否则可能把真实风险抹掉。

**7. 回测前做数据体检报告**

每次跑策略前输出一份检查：

- 股票数量
- 交易日数量
- 缺失率
- 异常 OHLC 数量
- 停牌冲突数量
- 复权跳变数量
- 极端收益数量
- 被排除样本数量
- 数据源版本号

没有体检报告的回测，结果可信度很低。

**8. 用小策略做数据验尸**

跑几个“数据探针”策略：

- 全市场等权买入
- 指数成分等权买入
- 昨日涨停股统计
- 停牌股成交检查
- 财报公告日后买入检查
- 复权前后收益连续性检查

这些策略不为赚钱，而是用来发现数据怪异。

**最实用的规避清单**

你可以把回测数据门槛定成：

- 原始数据可追溯
- 至少一个对照源
- OHLC/成交量自动校验
- 停牌、涨跌停、上市退市状态完整
- 财报/公告类数据按公告日生效
- 指数成分、行业分类按历史版本生效
- 复权逻辑清楚
- 异常值有标记，不静默删除
- 回测输出数据质量报告

一句话：脏数据无法完全消灭，只能通过“保留原始、规则验收、交叉验证、异常标记、时间点约束”把它的伤害控制住。

### 👤 User / 用户 - 2026-06-03T02:49:38.465Z
OHLCV是什么

### 🤖 Assistant / 助手 - 2026-06-03T02:49:46.181Z
OHLCV 是股票/交易数据里最基础的一组行情字段：

- `O` = Open，开盘价
- `H` = High，最高价
- `L` = Low，最低价
- `C` = Close，收盘价
- `V` = Volume，成交量

一根 K 线基本就是一组 OHLCV。

例如某股票某天：

```text
Open   10.00
High   10.80
Low     9.90
Close  10.50
Volume 1,200,000
```

意思是：当天 10.00 开盘，最高涨到 10.80，最低到 9.90，最后 10.50 收盘，成交量 120 万股。

在量化里，OHLCV 用来计算均线、涨跌幅、波动率、成交量变化、突破信号、回测买卖价格等。常见的数据质量检查就是：

```text
Low <= Open <= High
Low <= Close <= High
Volume >= 0
```

A 股里还经常配合成交额、涨跌停价格、复权因子、停牌状态一起看。

### 👤 User / 用户 - 当前 API 会话
好，检查代码实现与此逻辑是否偏差，如有，改正。

### 🤖 Assistant / 助手 - 当前 API 会话
已检查并改正，当前实现已对齐你刚才确认的逻辑。

核心调整：

- `watchlist` 现在明确是“计划/观察层”，不再把当天观察池直接当成已成交账单。
- 模拟交易账单只记录“本地日线库已有对应 OHLCV 的交易日”。
- 当前本地 A 股日线最新是 `2026-06-02`，所以今天 `2026-06-03` 的 watchlist 仍生成，但正式账单只确认到 `2026-06-02`。
- 原先 SQLite 里错误写入的 `2026-06-03` 模拟成交记录已通过重建删除。
- `next_open` 已改为“执行日开盘价”，不是“信号日/报告日开盘价”。
- 持仓估值按执行日收盘价计算。
- 交易执行已纳入：100 股整数手、现金约束、佣金、印花税、滑点、涨跌停/停牌基础检查、最大成交参与率。

已验证：

- `py_compile` 通过。
- `./.venv/bin/python -m phase0.cli brief daily --skip-update` 运行成功。
- 当前 watchlist 输出仍是：
  - `reports/2026-06-03/phase0_watchlist_report_2026-06-03.html`
  - `reports/watchlist_today/index.html`
- 当前正式模拟账单输出为：
  - `reports/2026-06-02/simulated_account_bill_2026-06-02.html`

页面里的账户快照现在也会提示：当前观察池尚未确认成交，展示最近一个已确认模拟账单日。

### 👤 User / 用户 - 当前 API 会话
模拟账单在明天的watchlist页面里，会变成两行吗

### 🤖 Assistant / 助手 - 当前 API 会话
不会在 `watchlist` 页面里变成“两天两行”的账户快照。

按当前实现：

- `watchlist` 页面里的“模拟账户快照”只显示 **最近一个已确认账单日的一行汇总**。
- 明天如果本地日线库已经有 `2026-06-03` 的 OHLCV，系统会确认 `2026-06-03` 的模拟执行结果。
- 到时页面快照会从 `2026-06-02` 切换成 `2026-06-03`，仍然是一行。
- 底层 SQLite 里会保留多天记录，例如 `2026-06-02`、`2026-06-03` 两条日资产记录。
- 独立的模拟交易账单 HTML 会显示某一天的成交明细，可能有多行交易，但那是当日买卖明细，不是 watchlist 页面上的多日汇总。

也就是说：**数据库会有连续多日记录，watchlist 页面默认只展示最新确认日。**

### 👤 User / 用户 - 当前 API 会话
再给我看一下当前完整项目命令路由

### 🤖 Assistant / 助手 - 当前 API 会话
当前项目命令路由如下，按“建议主入口”和“兼容/专项入口”区分。

**主入口**
```bash
./.venv/bin/python -m phase0.cli brief daily
```
当前日报主入口。现在完整日报还没单独重写，实际复用 `brief watchlist`：先更新 A 股日线，再生成观察池页面、模拟账户快照、账单，并同步 `reports/watchlist_today/index.html` 到 ECS。

```bash
./.venv/bin/python -m phase0.cli brief watchlist
```
阶段试用观察池入口。和 `brief daily` 当前执行路径一致。

```bash
./.venv/bin/python -m phase0.cli brief premarket
```
只导出原始盘前观察池，不先更新 A 股历史库。

```bash
./.venv/bin/python -m phase0.cli brief account-bill
./.venv/bin/python -m phase0.cli brief account-bill --date 2026-06-02
```
从 SQLite 导出模拟交易账单 HTML。无日期时默认最新确认账单日。

**数据更新**
```bash
./.venv/bin/python -m phase0.cli update-history
```
更新 A 股本地日线历史库。

```bash
./.venv/bin/python -m phase0.cli update-us-market-history
./.venv/bin/python -m phase0.cli update-hk-market-history
```
更新美股/港股日线历史库。都支持 `--check-only`。

```bash
./.venv/bin/python -m phase0.cli update-financials
```
更新 A 股季度财务因子。支持 `--periods`。

**研究与验证**
```bash
./.venv/bin/python -m phase0.cli run
./.venv/bin/python -m phase0.cli cost-sensitivity
./.venv/bin/python -m phase0.cli bill
./.venv/bin/python -m phase0.cli market-regime
./.venv/bin/python -m phase0.cli oos-report
./.venv/bin/python -m phase0.cli execution-gate
./.venv/bin/python -m phase0.cli financial-pti
./.venv/bin/python -m phase0.cli build-universe
```

**导入/重建**
```bash
./.venv/bin/python -m phase0.cli import-history
./.venv/bin/python -m phase0.cli import-index-history
```

**兼容旧入口**
```bash
./.venv/bin/python -m phase0.cli daily-brief
./.venv/bin/python -m phase0.cli premarket
./.venv/bin/python -m phase0.cli brief daily-brief
```
这些还能用，但建议以后统一用 `brief ...` 层级入口。

**脚本层入口**
```bash
bash scripts/run_project_scheduler.sh
```
统一调度器。cron 每分钟调用它，内部按时间触发：

- `07:20`：`brief watchlist`
- `16:20`：`update-hk-market-history`
- `16:30`：`update-history`
- `17:10`：`update-us-market-history`
- 周一 `03:30`：`update-financials`

```bash
bash scripts/run_daily_brief_pipeline.sh
```
手动/兼容脚本，现在内部调用 `brief watchlist`。

### 👤 User / 用户 - 当前 API 会话
现在展开simulated_accounts.sqlite内容给我看

### 🤖 Assistant / 助手 - 当前 API 会话
当前 `data/simulated_trading/simulated_accounts.sqlite` 内容如下。

**表结构**
共有 4 张表：

- `simulated_accounts`：模拟账户配置
- `account_daily_assets`：每日账户资产快照
- `account_trades`：每日模拟成交明细
- `account_positions`：每日持仓快照

**行数**
```text
simulated_accounts     1
account_daily_assets   1
account_trades         4
account_positions      4
```

**模拟账户**
```text
account_id: default
name: 默认模拟账户
initial_cash: 1,000,000.00
enabled: 1
execution_price_mode: next_open
max_participation_rate: 0.05
lot_size: 100
updated_at: 2026-06-03 03:03:12
```

**每日资产快照**
```text
账单日: 2026-06-02
起始日: 2026-06-02
总资产: 1,003,587.26
股票资产: 158,524.00
现金资产: 845,063.26
当日收益额: 3,587.26
当日收益率: 0.3587%
目标仓位: 15.80%
成交金额: 154,518.00
成交股数: 11,500
成交价口径: next_open
最大成交参与率: 0.05
```

**成交明细**
```text
2026-06-02 09:30  买入  SH.603986  兆易创新  100股    1手    价格471.00   金额47,100.00  成本127.64
2026-06-02 09:30  买入  SH.688012  DR中微公  100股    1手    价格278.46   金额27,846.00  成本75.46
2026-06-02 09:30  买入  SZ.000725  京东方Ａ  11200股  112手  价格5.31     金额59,472.00  成本161.17
2026-06-02 09:30  买入  SZ.002281  光迅科技  100股    1手    价格201.00   金额20,100.00  成本54.47
```

**持仓快照**
```text
2026-06-02  SH.603986  兆易创新  100股    1手    收盘价474.69  市值47,469.00
2026-06-02  SH.688012  DR中微公  100股    1手    收盘价282.80  市值28,280.00
2026-06-02  SZ.000725  京东方Ａ  11200股  112手  收盘价5.47    市值61,264.00
2026-06-02  SZ.002281  光迅科技  100股    1手    收盘价215.11  市值21,511.00
```

当前库里只有 `2026-06-02` 一个已确认账单日；`2026-06-03` 观察池还没有被写成正式成交账单。

### 👤 User / 用户 - 当前 API 会话
下次我说，“查看账单”,或“查看某某账户账单”时，你执行相同展示对应数据表内容的操作。

### 🤖 Assistant / 助手 - 当前 API 会话
收到。后续你说：

- “查看账单”
- “查看模拟账单”
- “查看某某账户账单”
- “展开账户账单”

我就默认读取：

```text
data/simulated_trading/simulated_accounts.sqlite
```

并展示对应账户的：

- 表结构与行数
- `simulated_accounts`
- `account_daily_assets`
- `account_trades`
- `account_positions`

如果没有指定账户，就默认查看 `default / 默认模拟账户`。如果指定了账户名，我会按 `account_id` 或账户名称匹配后展示。

### 👤 User / 用户 - 当前 API 会话
聊天记录里，关于账户设计的内容，记录下来，方便后期回查

### 🤖 Assistant / 助手 - 当前 API 会话
已记录到账户设计备忘文档：

[refdocs/simulated_account_design_and_bill_query_note.md](/home/zj/workspace/stok-mapping/refdocs/simulated_account_design_and_bill_query_note.md)

里面整理了：

- 模拟账户定位
- `watchlist` 与正式账单的边界
- 执行价格和时间口径
- A 股整手、现金、佣金、滑点等交易约束
- SQLite 账本结构
- 当前已确认账单状态
- 后续你说“查看账单”时的默认查询约定
- 后续待增强项

没有覆盖原来的账户分类备忘，原文件仍保留在：

[refdocs/simulated_account_classification_note.md](/home/zj/workspace/stok-mapping/refdocs/simulated_account_classification_note.md)

## 其他会话内容压缩摘要

- 2026-06-03 调研类问答已单独原文归档到 `refdocs/retail_quant_backtest_live_loss_web_search_2026-06-03.md`。第一次检索保存“个人量化回测/模拟盈利、实盘亏损”的案例与原因；第二次检索追加更多案例，包括个人 2 万起步亏损、demo 策略回测 40% 实盘亏损、AI/LSTM 选股亏损、AI 情绪择时失效、高频回测落差、FX 策略执行规则不可行、期货隔夜跳空滑点、Reddit 社区案例等。记忆中保留了助手原文、来源链接、原因归纳和实用判断。
- 2026-06-03 概念解释“怎么规避脏数据”已原文归档到 `refdocs/dirty_data_avoidance_for_quant_2026-06-03.md`。核心内容包括：不直接信任原始数据、多数据源交叉验证、数据质量标签、保留 raw 表、防未来函数污染、异常值隔离、回测前数据体检报告和数据探针策略。
- 当前 watchlist 与模拟账户账单边界已落地：`watchlist` 是计划层/观察层；正式模拟账单只记录本地日线库已有对应执行日 OHLCV 的已确认日期；当前 `2026-06-03` watchlist 不再写成正式成交账单，正式账单仅确认至 `2026-06-02`。
- `phase0/accounts.py` 新增模拟账户模块，支持 `SimulatedAccountConfig`、账户配置读取、执行价格口径、A 股 100 股整手、现金约束、佣金、印花税、滑点、涨跌停/停牌基础检查、最大成交参与率、本地 OHLCV 读取、SQLite 表写入、最近账户快照读取和 HTML 账单导出。
- `scripts/export_premarket_watchlist.py` 接入模拟账户账本和账户快照。watchlist 页面新增“模拟账户快照”，只显示最近一个已确认账单日；如果当前观察池尚未确认成交，页面提示“当前观察池尚未确认成交，显示最近已确认账单”。页面术语中将 `next_open` 翻译为“执行日开盘价”，`close` 为“执行日收盘价”，`conservative` 为“执行日开盘保守价”。
- `phase0/cli.py` 命令路由已整理：推荐主入口为 `brief daily`、`brief watchlist`、`brief premarket`、`brief account-bill`；旧 `daily-brief`、`premarket`、`brief daily-brief` 仅作兼容。`brief daily` 当前仍复用 `brief watchlist` 代码，未来需独立重写正式 daily brief 产物。
- 7:20 调度任务路径变化已处理：`scripts/run_project_scheduler.sh` 中 `daily_brief` 任务从旧兼容入口切换为 `phase0.cli brief watchlist --config config.yaml`；`scripts/run_daily_brief_pipeline.sh` 也改为调用 `brief watchlist`。
- watchlist 固定输出路径更新为 `reports/watchlist_today/index.html`，仍复制一份到 `/mnt/d/ZJ/Dev/brief_today/index.html`。ECS 同步函数 `_sync_watchlist_to_ecs()` 直接从 `reports/watchlist_today/` rsync 到 `root@39.105.102.5:/brief/`，由环境变量 `BRIEF_SYNC_REMOTE` 和 `BRIEF_SYNC_REMOTE_DIR` 覆盖。
- 已手动执行同步到远端 ECS：`rsync -avz --delete /home/zj/workspace/stok-mapping/reports/watchlist_today/ root@39.105.102.5:/brief/`，返回成功，远端 `/brief/index.html` 已更新。
- README 已核对当前 CLI 路由并更新：新增 `CLI 路由总览`，区分推荐入口、兼容入口、数据更新、研究验证、导入/维护和脚本层入口；更新 7:20 调度说明为 `brief watchlist`，输出 `reports/watchlist_today/index.html` 并同步 ECS。
- `DEVELOPMENT_PLAN.md` 已更新最后修订为 `2026-06-03`，同步 `brief/watchlist` 路由、模拟账户账本与调度链路状态；当前最高优先级中勾选“强化 07:30 阶段试用观察池自动生成链路”“完成 brief 命令路由整理”“接入模拟账户 SQLite 主账本与最近确认账单快照展示”，保留“正式 daily brief 从 watchlist 兼容实现中拆出”“交易日历判断”“运行窗口/失败重试”等未完成项。
- `tasks/WEEKLY_EXECUTION_CHECKLIST.md` 新增 `W2.12.0 已完成基线`，勾选统一调度器、7:20 入口切换、`reports/watchlist_today/index.html`、ECS 同步、`brief` 命令路由、模拟账户 SQLite 主账本、watchlist 与正式模拟账单边界；保留 `W2.12.1` 交易日判断和 `W2.12.2` 失败重试为未完成；新增 `W2.12.3 正式日报产物后续拆分`。
- `tasks/ops/SCHEDULER_PIPELINE_TASKS.md` 已同步勾选：`07:20` 任务切到 `phase0.cli brief watchlist`、固定生成 `reports/watchlist_today/index.html`、内置 ECS rsync、兼容脚本调用 `brief watchlist`、`brief` 命令路由整理。`T6.1.2.3.4` 改为将 `brief watchlist` / `brief daily` 与 A 股下一个盘前检查日绑定。
- 验证命令：`./.venv/bin/python -m py_compile phase0/accounts.py phase0/cli.py scripts/export_premarket_watchlist.py` 通过；`./.venv/bin/python -m phase0.cli brief --help` 显示 `daily,daily-brief,watchlist,premarket,account-bill` 子命令；`bash -n scripts/run_project_scheduler.sh`、`bash -n scripts/run_daily_brief_pipeline.sh` 通过。
- Git 提交与推送已完成：提交 `e2735ca Add watchlist account ledger pipeline`，已推送到 `origin/main`。提交包含 `phase0/accounts.py`、`phase0/cli.py`、`scripts/export_premarket_watchlist.py`、调度脚本、`config.yaml`、`README.md`、`DEVELOPMENT_PLAN.md`、周任务清单、调度任务清单、`refdocs/simulated_account_classification_note.md` 和 `refdocs/simulated_account_design_and_bill_query_note.md`。未提交本地运行产物：`logs/`、`data/simulated_trading/*.sqlite`、生成的 `reports/...html`、其他个人备忘文档。

## 2026-06-03 增量归档：账户账单口径与 premarket 运行

> 来源 session：当前 API 会话
> 完整归档规则：命中“为什么”“是什么”等解释类问答。
> 其他内容：用户本地执行命令与输出已按运行摘要归档。
> 上次已归档时间戳：当前 API 会话上一节已归档到 `e2735ca Add watchlist account ledger pipeline` 推送完成。

### 👤 User / 用户 - 当前 API 会话
观察池页面的模拟账户快照，和模拟账单里的账户数据为什么不一致？

### 🤖 Assistant / 助手 - 当前 API 会话
原因是你看到的“模拟账单”很可能是这个旧文件：

```text
reports/2026-06-03/simulated_account_bill_2026-06-03.html
```

它是之前修正逻辑前生成的静态旧产物，里面有 `2026-06-03` 的模拟成交数据。但当前正式 SQLite 账本里已经没有 `2026-06-03` 账单，只有 `2026-06-02`。

当前真实账本状态是：

```text
data/simulated_trading/simulated_accounts.sqlite
```

只有：

```text
账单日: 2026-06-02
总资产: 1,003,587.26
股票资产: 158,524.00
现金资产: 845,063.26
成交金额: 154,518.00
成交股数: 11,500
```

这和观察池页面的“模拟账户快照”一致，也和当前有效账单：

```text
reports/2026-06-02/simulated_account_bill_2026-06-02.html
```

一致。

所以结论是：

- `watchlist` 页面没有错。
- `2026-06-02` 模拟账单没有错。
- 不一致来自旧的 `reports/2026-06-03/simulated_account_bill_2026-06-03.html` 静态文件残留。
- 当前逻辑已经不会再把尚未确认 OHLCV 的 `2026-06-03` 写成正式账单。

这个旧文件应该视为过期报告，后续可以清理掉，避免误看。

### 👤 User / 用户 - 当前 API 会话
`./.venv/bin/python -m phase0.cli brief account-bill` 是用什么数据导出的账单

### 🤖 Assistant / 助手 - 当前 API 会话
`./.venv/bin/python -m phase0.cli brief account-bill` 是从这个 SQLite 主账本导出的：

```text
data/simulated_trading/simulated_accounts.sqlite
```

具体读取逻辑是：

- 先读取 `config.yaml` 里的模拟账户配置：
  ```yaml
  accounts:
    simulated:
      - account_id: default
        database_path: data/simulated_trading/simulated_accounts.sqlite
  ```

- 如果你没有传 `--date`，程序会查：
  ```sql
  SELECT MAX(brief_date)
  FROM account_daily_assets
  WHERE account_id = 'default'
  ```

- 当前最大账单日是：
  ```text
  2026-06-02
  ```

- 然后从同一个 SQLite 里读取这几张表导出 HTML：
  ```text
  simulated_accounts
  account_daily_assets
  account_trades
  account_positions
  ```

所以它不是根据 `reports/2026-06-03/*.html` 旧文件导出的，也不是重新用 watchlist CSV 临时算出来的；它是从当前正式账户账本 SQLite 导出的。

这也是为什么你刚才命令输出的是：

```text
Date: 2026-06-02
Account bill: reports/2026-06-02/simulated_account_bill_2026-06-02.html
```

## 其他会话内容压缩摘要

- 用户本地执行 `./.venv/bin/python -m phase0.cli brief account-bill`，命令成功，输出 `Account: default`、`Date: 2026-06-02`、账单文件 `/home/zj/workspace/stok-mapping/reports/2026-06-02/simulated_account_bill_2026-06-02.html`。该命令从 `data/simulated_trading/simulated_accounts.sqlite` 的 `account_daily_assets` 最大 `brief_date` 自动选择账单日期。
- 用户本地执行 `./.venv/bin/python -m phase0.cli brief premarket`，命令成功，输出 `panel_cache=hit path=/home/zj/workspace/stok-mapping/reports/cache/low_turnover_panel.pkl`，生成原始 premarket 观察池：`/home/zj/workspace/stok-mapping/reports/phase0_premarket_watchlist.csv`，生成原始报告：`/home/zj/workspace/stok-mapping/reports/phase0_premarket_report.html`，`Rows: 28`，`Signal date: 2026-06-02`，`Check time: 2026-06-03 07:30`。
- 注意：`brief premarket` 是原始盘前观察池导出入口，不走 `brief watchlist` 的日期目录归档、`reports/watchlist_today/index.html` 固定入口和 ECS 同步链路。日常阶段试用观察池仍优先使用 `brief daily` 或 `brief watchlist`。
