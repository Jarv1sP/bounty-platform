# 云端运行

此目录为独立悬赏平台的部署配置，不使用 STARGATE/GPUQ 的账号、数据库、节点、执行桥或镜像。

## 本次实例

**管理员交接：此实例已经安装，不必重装。** 先在阿里云 DNS 为 `j4rv1s.xyz` 新增 A 记录 `bounty → 47.99.144.195`，确认解析生效，再检查 HTTPS 证书与登录。Caddy 的 bounty 站点块已热加载。初始登录资料在下述 root 私有文件中，不要复制进工单或 Git。

- 地址：`https://bounty.j4rv1s.xyz`，DNS A 记录须指向 `47.99.144.195`。
- 主机：现有 VPS；管理路径 `/opt/bounty-platform`。
- Compose 项目及容器：`bounty-platform`。不发布宿主机端口。
- 仅复用现有 Caddy 的 `amax-console-net` 反向代理网络和公网 443。
- 独立数据：`/opt/bounty-platform/data/bounty.sqlite3` 和 `secret.key`。
- 使用 Python 3.12、Gunicorn 单 worker / 2 threads；内存上限 256 MiB、CPU 上限 0.5 核。
- 正式数据库初始只有一个管理员 `halashaor`，没有演示账号或任务。
- 初始密码及团队邀请码：服务器 `/opt/bounty-platform/bootstrap.json`，仅 root 可读，禁止提交 Git。
- `.env` 存镜像标签、域名、邀请码和数据目录，权限 0600。
- 当前仍为一个团队共享空间；邀请码仅发给本团队成员，不是多租户 SaaS。

## 镜像

在本地下载 wheel；在有 Docker 的构建机执行 Dockerfile。云端这次仅使用官方基础镜像、离线 wheel 安装与 COPY，没有源码编译。

```bash
python -m pip download --only-binary=:all: --platform manylinux2014_x86_64 \
  --python-version 312 --implementation cp --abi cp312 \
  -r requirements-cloud.txt -d wheels
docker build --network=none -t bounty-platform:VERSION .
```

## 在另一台机器全新安装

现有实例不要执行本节。新机器先安装 Docker Compose，并准备独立域名、DNS 和 Caddy。完成上面的镜像构建后：

```bash
sudo install -d -m 700 /opt/bounty-platform
sudo install -d -m 700 -o 10001 -g 10001 /opt/bounty-platform/data
sudo cp deploy/compose.yml /opt/bounty-platform/compose.yml
```

在该目录新建权限为 0600 的 `.env`：

```dotenv
BOUNTY_IMAGE=bounty-platform:VERSION
BOUNTY_DOMAIN=your-domain.example
BOUNTY_DATA_DIR=/data
BOUNTY_INVITE_CODE=REPLACE_WITH_RANDOM_VALUE_AT_LEAST_16_CHARACTERS
```

用 `python -c 'import secrets; print(secrets.token_urlsafe(24))'` 生成邀请码，在可信终端保存；不要使用上述占位值。将 Compose 中外部网络 `amax-console-net` 改为你自己的 Caddy 网络，并确保 Caddy 和应用都在该网络内。然后创建管理员并启动：

```bash
cd /opt/bounty-platform
docker compose run --rm web python manage.py create-user 管理员用户名 --admin
docker compose up -d --wait
```

添加对应域名的 Caddy 站点，反代 `bounty-platform:8080`，校验后热加载。应用要求 HTTPS；不要为了测试关闭 Secure cookie 或直接公开 8080。需要每日备份时将本目录的 `backup.py` 和两个 systemd 文件安装到文中路径并启用定时器。服务启动后检查 `/healthz`、注册邀请码、登录、发布/认领/验收及重启后的数据持久性。

正式入口 `wsgi:create_cloud_app()` 要求设置 `BOUNTY_DOMAIN` 和至少 16 字符的随机 `BOUNTY_INVITE_CODE`。HTTPS cookie 使用独立名称；只信任一层 Caddy 转发头。登录和注册按来源 IP 每分钟最多 30 次、滚动窗口最多约 300 次/小时，计数存自己的 SQLite。不要把 8080 直接映射到公网。

## 日常维护

```bash
cd /opt/bounty-platform
docker compose ps
docker compose logs --tail=100 web
docker compose restart web
# 仅重启此应用；无需重启 amax-console、headscale 或 caddy。
docker compose exec web python manage.py admin 用户名
# 在交互终端中安全输入新密码，不把密码写进命令参数。
docker compose exec web python manage.py reset-password 用户名
```

公开页面不显示本地演示账号。忘记密码目前由运维核对身份后使用上述命令处理，没有邮件找回功能。若因泄露需撤销全部现有会话，先停本应用，备份并轮换自己的 `data/secret.key` 后再启动。

## 备份与恢复

`bounty-backup.timer` 每日 UTC 04:15 附近运行 `backup.py`。使用 SQLite 在线备份，保留最近 30 份，并复制会话密钥；每次检查完整性。备份在 `/opt/bounty-platform/backups`，仅 root 可读。当前为同机备份，主机整体损坏时不能替代异地副本。

```bash
sudo systemctl status bounty-backup.timer
sudo systemctl start bounty-backup.service
sudo journalctl -u bounty-backup.service -n 20
```

恢复时先 `docker compose stop web`，把现有 `data` 整目录移至独立回退目录，再从选定备份建立新的 `data`，恢复数据库和密钥并设置所有者 `10001:10001`、目录权限 0700。禁止把备份覆盖到仍运行的 SQLite 上，也不要将旧 WAL/SHM 文件混入恢复后的目录。检查数据库完整性后 `docker compose up -d --wait`。

## Caddy 与回退

仅向 `/opt/headscale/caddy/Caddyfile` 增加 `Caddyfile.snippet` 的新站点块。变更前保存现有文件，校验候选配置，确认当前文件没有被其他部署修改，再写入并执行：

```bash
docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

本次原配置存 `/opt/bounty-platform/Caddyfile.before`；后续回退应只移除新增的 bounty 站点块，不能用旧备份覆盖其他人后来的路由改动。回退应用只改本项目 `.env` 的镜像标签；涉及数据库结构降级时同时使用匹配的备份。

## 上线前验证记录

- 官方 Python 3.12 镜像内，256 MiB / 0.5 CPU 限额下 40 项测试通过。
- 浏览器任务闭环、方向推荐、勋章、积木保存及名牌、18 个桌面/手机页面检查通过。
- 云端 Gunicorn 实际管理员登录和 9 个业务页面返回 200。
- 初始备份在临时目录恢复，完整性、外键和账号/任务数量检查通过。
- Caddy 热加载前后 GPUQ 首页均返回 200；原平台容器未重建。
- 本机 Python 3.10/3.13 曾出现模板编译阶段崩溃，原因未明；官方生产镜像测试未复现，不把本机重试成功视为根因修复。
- 公网 DNS、证书和公网登录最终状态以实际验收结果为准，容器健康不等于公网已上线。

修复内容：同类勋章入口按具体勋章筛选且排除自己/过期任务；鼓掌通知显示所有待查看任务；讨论不再覆盖退回状态和原因。

品牌新名称尚未确认，保留原名，未将讨论中的候选名字写入正式界面。
