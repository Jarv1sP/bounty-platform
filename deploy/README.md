# 云端部署

用 Docker Compose 把应用跑在一台服务器上，前面用 Caddy（或其他反向代理）提供 HTTPS。整个团队共用一个空间，注册需要团队邀请码。

## 构建镜像

在本地下载 wheel，再在有 Docker 的机器上构建。镜像只用官方基础镜像、离线 wheel 安装和 COPY，不编译源码。

```bash
python -m pip download --only-binary=:all: --platform manylinux2014_x86_64 \
  --python-version 312 --implementation cp --abi cp312 \
  -r requirements-cloud.txt -d wheels
docker build --network=none -t bounty-platform:VERSION .
```

## 安装

先装好 Docker Compose，准备好域名、DNS 和反向代理。以下以 `/opt/bounty-platform` 为安装目录：

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
BOUNTY_PROXY_NETWORK=caddy
```

- 邀请码用 `python -c 'import secrets; print(secrets.token_urlsafe(24))'` 生成，不要用上面的占位值。
- `BOUNTY_PROXY_NETWORK` 填反向代理所在的 Docker 网络名，应用和代理要在同一个网络里。

创建管理员并启动：

```bash
cd /opt/bounty-platform
docker compose run --rm web python manage.py create-user 管理员用户名 --admin
docker compose up -d --wait
```

在反向代理里加一个站点，反代 `bounty-platform:8080`（Caddy 可以参考 `Caddyfile.snippet`），校验后热加载。应用要求 HTTPS；不要为了测试关掉 Secure cookie，也不要把 8080 直接映射到公网。

启动后检查：`/healthz`、用邀请码注册、登录、发布 / 认领 / 验收，以及重启后数据还在。

正式入口 `wsgi:create_cloud_app()` 要求设置 `BOUNTY_DOMAIN` 和至少 16 个字符的随机 `BOUNTY_INVITE_CODE`。HTTPS cookie 使用独立的名字；只信任一层反向代理的转发头。登录和注册按来源 IP 限流：每分钟最多 30 次、每小时约 300 次，计数存在应用自己的 SQLite 里。

## 日常维护

```bash
cd /opt/bounty-platform
docker compose ps
docker compose logs --tail=100 web
docker compose restart web
docker compose exec web python manage.py admin 用户名
# 在交互终端里输入新密码，不要把密码写进命令参数
docker compose exec web python manage.py reset-password 用户名
```

公开页面不显示演示账号。忘记密码时由管理员核对身份后用上面的命令重置，没有邮件找回。如果需要让所有人重新登录（比如密钥泄露），先停应用，备份并更换 `data/secret.key` 后再启动。

更新版本：构建新镜像，改 `.env` 里的 `BOUNTY_IMAGE`，再 `docker compose up -d --wait`。数据库结构在启动时自动升级。

## 备份与恢复

把 `backup.py` 和两个 systemd 文件装到安装目录和 `/etc/systemd/system/` 后启用定时器。`bounty-backup.timer` 每天 UTC 04:15 左右运行一次：用 SQLite 在线备份，保留最近 30 份，同时复制会话密钥，每次都检查完整性。备份在 `/opt/bounty-platform/backups`，仅 root 可读。这是同机备份，机器整体损坏时不能代替异地副本。

```bash
sudo systemctl status bounty-backup.timer
sudo systemctl start bounty-backup.service
sudo journalctl -u bounty-backup.service -n 20
```

恢复：先 `docker compose stop web`，把现有 `data` 整个目录挪到别处留作回退，再从选定的备份建一个新的 `data`，放回数据库和密钥，所有者设为 `10001:10001`、目录权限 0700。不要把备份覆盖到正在运行的 SQLite 上，也不要把旧的 WAL/SHM 文件混进来。检查数据库完整性后 `docker compose up -d --wait`。

回退版本只需把 `.env` 里的镜像标签改回去；涉及数据库结构降级时，同时恢复对应时间的备份。
