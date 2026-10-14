# 搭把手 · 本地悬赏任务平台

独立的本地完整应用：HTML/CSS/JavaScript 界面 + Flask 后端 + SQLite 数据库。
发布任务、认领、提交、退回、验收、讨论和勋章都是真实操作，会保存到数据库。

## 获取与源码运行

[下载本地运行包 v1.1.0](https://github.com/halashaor/bounty-platform/releases/tag/v1.1.0)。运行包包含离线依赖和专门生成的演示数据库。

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
默认且仅监听 `127.0.0.1`，不会对局域网或公网开放。没有配置后台常驻或开机自启。

## 演示账号和任务

ZIP 内的 `instance/bounty.sqlite3` 是专门新生成的演示数据库，不包含原工作目录的个人账号。

| 用户名 | 密码 | 用途 |
| --- | --- | --- |
| 发布者 | demo12345 | 发布任务、查看自己的发布、验收或退回 |
| 认领人 | demo12345 | 认领任务、提交成果、查看自己的勋章 |
| 其他成员 | demo12345 | 验证其他成员的权限与讨论 |

预置 24 个可实际操作的任务：16 个待认领、4 个进行中、2 个待验收、2 个已完成。
截止时间按打包时间延后 30 天。也可直接注册自己的账号。

建议用普通窗口登录“发布者”、无痕窗口登录“认领人”，走一遍：

1. 发布者新建任务，填写说明、截止时间、交付要求、任务分量与紧急程度。
2. 认领人在大厅认领，进入详情提交成果。
3. 发布者填写原因退回，认领人修改后再次提交。
4. 发布者验收通过；认领人的“我的勋章”自动出现对应记录。

不同账号若使用同一浏览器会话，需要先退出再切换。

## 实现范围

- 独立注册、密码哈希、登录、退出和会话保存。
- 分类、状态、关键词筛选；我的发布、我的认领。
- 密集委托墙：每区最多 12 张真实任务，图钉和状态印戳；支持区域切换、拖动和键盘左右键。
- 发布者不能认领自己任务；并发认领只允许一人成功。
- 只有认领人可提交；只有发布者可验收或退回，退回必须说明原因。
- 任务讨论与交付历史持续保留；成果链接可点击，用户内容按安全文本处理。
- 我的工作台集中展示进行中的认领、退回原因和待本人验收的交付。
- 团队成果墙仅收录已验收任务，展示最新交付、贡献者、验收人和验收说明 / 感谢。
- 登录成员可为他人已验收成果标记或取消“有帮助”，每人每项最多一个标记；不提供排行榜或奖励积分。
- 任务大厅记录真实的认领、提交和验收动态。
- 验收与勋章发放在同一个事务中完成，每个任务只发一次。
- 个人勋章册、来源记录、首次入册反馈和最多三枚个人展示位。
- 动效开关、系统减少动态效果支持；关闭 JavaScript 后仍可通过普通页面完成业务流程。

奖励是荣誉勋章，不含金额、积分兑换、支付或结算。
成果支持文字和链接，**不含文件附件上传**。首版不含邮件通知、任务编辑/取消/转派、找回密码和管理员后台。

所有时间在界面上明确标注为 **UTC**；UTC+8 的当地时间减 8 小时即为 UTC。
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
- `bounty/service.py`：任务归属、状态流转及输入校验。
- `bounty/honors.py`：六种任务勋章。
- `bounty/community.py`：个人工作台、团队成果和有帮助反馈。
- `bounty/demo.py`：独立演示数据生成器。
- `templates/`、`static/`：完整界面；`board.js` 只移动已由服务端生成的任务墙。
- `manage.py`：数据库初始化、演示导入和备份。
- `vendor/`：发布包内附的运行依赖及其许可证。
- `tests/`：后端流程、权限、冲突、持久化测试。

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

## v1.1.0 学生团队版

新增“论文阅读、算法复现、实验分析、工程支持、分享整理”分类，保留旧分类和数据。演示任务改为算法团队常见工作，并包含“定位复现差异”等交付示例。成果墙展示验收结论，不会把未验收的实验或未证实的效果当成成果。

我的发布 / 我的认领仍可从工作台进入。验收说明可写具体贡献与感谢，直接保留在团队成果和个人勋章来源中。“有帮助”仅作同伴反馈，支持取消，提交成功后才播放反馈动画。

首次启动自动创建 appreciations 表，不修改既有用户、任务、交付和勋章。服务端测试新增工作台归属、退回重交提示、成果展示边界、感谢与交付转义、反馈权限及持久化、分页校验；浏览器已实测反馈提交/取消、刷新保留及贡献者不能给自己反馈。
