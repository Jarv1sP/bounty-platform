# 搭把手 · 本地悬赏任务平台

独立的本地完整应用：HTML/CSS/JavaScript 界面 + Flask 后端 + SQLite 数据库。
发布任务、认领、提交、退回、验收、讨论和勋章都是真实操作，会保存到数据库。

## 获取与源码运行

[下载本地运行包 v1.0.0](https://github.com/halashaor/bounty-platform/releases/tag/v1.0.0)。运行包包含离线依赖和专门生成的演示数据库。

Git 仓库保留源码、数据库结构和生成脚本，不上传使用中的数据库、账号密钥或设计参考截图。直接从源码运行：

```bash
python -m venv .venv
# Windows: .venv\Scripts\python.exe；macOS/Linux: .venv/bin/python
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py demo
.venv/bin/python run.py
```

上面三条 Python 命令应使用虚拟环境的解释器；`demo` 只用于空数据库，可省略并自行注册账号。

## 解压后启动

### Windows

1. 安装 Python 3.10 或更新版本（若已安装可跳过）。
2. **完整解压 ZIP**，进入 `bounty-platform-local` 文件夹。
3. 双击 `start.bat`。浏览器会打开 `http://127.0.0.1:5080`。
4. 保持命令行窗口开启；关闭窗口或按 Ctrl+C 停止，数据仍保留。

发布包已包含纯 Python 依赖，不需要运行 pip、npm，不需要安装 MySQL，也不需要联网下载网页资源。
没有打包 Python 解释器，因此电脑必须先有 Python。

### macOS / Linux

```bash
cd bounty-platform-local
python3 run.py
# 或：sh start.sh
```

也可以使用 `python run.py --port 5081` 改端口，或加 `--no-browser` 只启动服务。
默认只监听 `127.0.0.1`，不会对局域网或公网开放。没有配置后台常驻或开机自启。

### 给团队一起用

在一台大家都能访问的机器上用 `--host` 指定监听地址，队友用浏览器打开 `http://<这台机器的地址>:5080` 即可：

```bash
python run.py --host 0.0.0.0 --port 5080 --data-dir team-data --no-browser
```

只在可信的团队网络里这样做：能访问这个地址的人都能看到登录页。应用本身走 HTTP；需要放到公网时，请在前面加一层带 HTTPS 的反向代理。
页面上的时间按团队时区显示，默认北京时间（UTC+8）；其他时区用环境变量 `BOUNTY_TZ_OFFSET`（小时数）指定。

## 演示账号和任务

ZIP 内的 `instance/bounty.sqlite3` 是专门新生成的演示数据库，不包含原工作目录的个人账号。

| 用户名 | 密码 | 用途 |
| --- | --- | --- |
| 发布者 | demo12345 | 发布任务、验收或退回（有一个任务等着他验收） |
| 认领人 | demo12345 | 认领、提交；信箱里有两枚新勋章，打开「成就」就会颁奖 |
| 其他成员、陈默、王瑶、周然、林夕 | demo12345 | 团队里的其他同学，用来看推荐、动态、鼓掌和名牌墙 |

预置 24 个算法团队常见的任务（造模拟赛数据、复现论文 baseline、写题解……），分属 5 个项目：
15 个待认领、3 个进行中、2 个待验收、4 个已完成。截止时间按生成时间往后排，加急的两三天内到期。也可直接注册自己的账号。

建议用普通窗口登录“发布者”、无痕窗口登录“认领人”，走一遍：

1. 发布者新建任务，填写说明、交付要求、标签、项目、预计投入、紧急程度和截止时间。
2. 认领人在「发现」里看到「为你挑的」推荐，直接认领，进入详情提交成果。
3. 发布者填写原因退回，认领人修改后再次提交。
4. 发布者选一句夸奖并验收通过；认领人的信箱亮起，打开「成就」播放颁奖，经验和收集册一起涨。

不同账号若使用同一浏览器会话，需要先退出再切换。

## 实现范围

- 独立注册、密码哈希、登录、退出和会话保存。
- **发现**：打开就是「为你挑的」三个任务，每张写明理由（做过的标签和项目、想做的方向、和做过的任务内容相似、能解锁新勋章、急需人手）；可以「换一批」或「不感兴趣」。推荐全部由数据实时算出，不写死任何分类，新项目、新标签会自动加入。
- 标签和项目都可以随手新建；按标签、项目、预计投入（半天内 / 一两天 / 一周左右）、关键词和「只看能拿新勋章的」筛选；每页 12 个任务。
- **我的任务**：按「轮到你 → 等对方 → 没人认领 → 已完成」分组，每行写明最近一条动态。
- 发布者不能认领自己任务；并发认领只允许一人成功。
- 只有认领人可提交；只有发布者可验收或退回，退回必须说明原因；验收时可以选一句夸奖。
- 任务讨论与交付历史持续保留；用户内容按安全文本处理。
- **两条成长线一起涨**：等级按工作量给经验（轻量 10、常规 30、重要 80，加急 +50%），啃硬骨头的人升得快；勋章「点・线・面」× 急不急共 6 种，凑齐一行有庆祝。
- 验收与勋章发放在同一个事务中完成，每个任务只发一次；认领人下次打开「成就」时播放颁奖，按稀有度分档，可跳过。
- 名牌（等级、称号、最多三枚勋章）、团队名牌墙、勋章背面的每一次获得记录、团队动态和鼓掌、每周团队收集包。
- 动效开关、系统减少动态效果支持；音效用 Web Audio 现场合成，默认关闭；关闭 JavaScript 后仍可通过普通页面完成业务流程。

奖励是荣誉勋章，不含金额、积分兑换、支付或结算。
成果支持文字和链接，**不含文件附件上传**。首版不含邮件通知、任务编辑/取消/转派、找回密码和管理员后台。

时间在数据库里按 UTC 保存，界面上按团队时区显示（默认 UTC+8，见上文 `BOUNTY_TZ_OFFSET`）。
截止后禁止新认领，已经认领的任务仍可提交和验收。

## 数据库、备份与全新使用

数据库为 `instance/bounty.sqlite3`；登录密钥首次启动创建于 `instance/secret.key`。
重启应用不会重置用户、任务、讨论或勋章。数据库结构见 `database/schema.sql`。

直接使用全新数据目录（不会改变演示库）：

```bash
python run.py --data-dir my-data
```

初始化空数据库或向空目录导入演示任务：

```bash
python manage.py --data-dir my-data init
python manage.py --data-dir another-demo demo
```

演示导入只允许写入空数据库，避免覆盖已有内容。

一致性备份（服务运行时也可执行，不覆盖同名文件）：

```bash
python manage.py backup backups/bounty-20261014.sqlite3
# 自定义数据目录：
python manage.py --data-dir my-data backup backups/my-data.sqlite3
```

恢复：停止服务，将备份复制为目标数据目录的 `bounty.sqlite3`。务必先保留目标目录旧数据；不建议将备份直接覆盖到仍运行的数据库。
也可以停服务后备份整个数据目录。若 `secret.key` 缺失，用户需重新登录，账号和任务仍在。

## 代码结构

- `run.py` / `start.bat` / `start.sh`：跨平台本地启动入口。
- `app.py`：页面路由、认证和会话，使用服务器端身份校验。
- `bounty/db.py`：表结构、事务与旧版数据迁移。
- `bounty/service.py`：任务归属、状态流转、标签、鼓掌及输入校验。
- `bounty/honors.py`：六种勋章「点・线・面」。
- `bounty/discover.py`：推荐打分、团队动态、我的任务分组等只读查询。
- `bounty/progress.py`：经验和等级、收集册成套、团队收集包。
- `bounty/demo.py`：独立演示数据生成器。
- `templates/`、`static/`：完整界面。`ui.js` 管手感、音效和颁奖；`board.js` 管任务墙翻页和发布页预览。
- `manage.py`：数据库初始化、演示导入和备份。
- `vendor/`：发布包内附的运行依赖及其许可证。
- `tests/`：后端流程、权限、冲突、持久化、推荐、经验和颁奖测试。

没有独立前端构建步骤，不需要额外启动一个前端服务器。
项目不依赖 STARGATE/GPUQ 的代码、数据库、账号、部署或服务。

## 验证与开发

发布包内运行测试：

```bash
python -c "import run,unittest; result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not result.wasSuccessful())"
```

源码目录没有 `vendor/` 时，可执行 `python -m pip install -r requirements.txt` 安装依赖。
可选浏览器测试 `python scripts/check_motion.py` 需要额外安装 `websocket-client` 和 Chromium；与普通使用无关。
验证范围及发布信息见 `RELEASE_NOTES.txt`。Windows 启动脚本已提供，尚未在原生 Windows Python 环境实机执行。
