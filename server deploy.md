# Server 1 简表

> 当前公网生产机是 `49.234.185.86`. 默认部署目标按这台机器处理, 除非明确指定其他环境.
> 完整流程以 `docs/deploy-release.md` 为准.

## 生产信息

- IP: `49.234.185.86`
- SSH: `ssh ubuntu@49.234.185.86`
- SSH 凭据: 从批准的 secret store 获取, 不写入仓库
- 仓库: `/home/ubuntu/Xingrun-Website`
- Python: `3.12.x`
- PM2 Web: `xingrun`
- PM2 课堂点评记忆 worker: `xingrun-class-commentary-memory-worker`
- 正式发布分支: `master`
- 开发集成分支: `develop`

## 日常发布

先由人工确认 `develop -> master`, 再登录生产机执行:

```bash
cd /home/ubuntu/Xingrun-Website
git fetch origin
git checkout master
git pull --ff-only origin master
npm --prefix frontend run build
XR_SKIP_GIT_SYNC=1 XR_PYTHON_BIN=python3.12 ./scripts/deploy_backend.sh master
```

`scripts/deploy_backend.sh`是后端和课堂点评记忆 worker 的唯一生产启动入口. 它会:

- fail-fast 检查 Python 3.12 和 worker `kill_timeout >= 330000ms`.
- 安装依赖并执行数据库初始化.
- 始终创建或重启 `xingrun`. Flag 开启时才创建或使用 `pm2 restart --update-env`重启 memory worker; flag 关闭时停止已存在的 worker.
- 执行 `pm2 save`.
- 始终检查 Web PM2 和 `302`. Flag 开启时再检查 worker, Redis/RQ, Mem0/Qdrant 中文写入检索, reconciliation 排期和已有 SQLite-Mem0 映射.

脚本不构建前端, 所以前端 build 必须在脚本前完成. 不再使用 `nohup`, PID 文件或手工启动 `app.py`作为生产兜底.

## 发布前配置

`XR_CLASS_COMMENTARY_MEMORY_ENABLED=0`是合法的 migration-first 发布模式, 此时可以先上线 schema 和 Web. 只有设置为 `1`时, `.env.runtime`才必须正确配置以下 memory 依赖:

```bash
XR_CLASS_COMMENTARY_MEMORY_ENABLED=1
XR_REDIS_URL=redis://127.0.0.1:6379/0
XR_CLASS_COMMENTARY_MEMORY_QUEUE=class_commentary_memory
XR_MEM0_VECTOR_PROVIDER=qdrant
XR_MEM0_QDRANT_URL=...
XR_MEM0_QDRANT_API_KEY=...
XR_MEM0_COLLECTION_NAME=xingrun_class_commentary_memory
XR_MEM0_EMBEDDER_PROVIDER=...
XR_MEM0_EMBEDDER_MODEL=...
XR_MEM0_EMBEDDER_API_KEY=...
XR_MEM0_EMBEDDER_BASE_URL=...
XR_MEM0_EMBEDDING_DIMS=...
```

API key 和服务器密码只放 secret store 或服务器 `.env.runtime`, 不写入 Git 或命令历史.

## 快速检查

```bash
cd /home/ubuntu/Xingrun-Website
set -a
source .env.runtime
set +a
pm2 status xingrun xingrun-class-commentary-memory-worker
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/
.venv/bin/rq info \
  --url "${XR_REDIS_URL:-redis://127.0.0.1:6379/0}" \
  "${XR_CLASS_COMMENTARY_MEMORY_QUEUE:-class_commentary_memory}"
```

成功口径: Web 始终是 `online`且 HTTP 状态是 `302`. Flag 为 `1`时 memory worker 也必须是 `online`, RQ 目标队列至少有 1 个 worker; flag 为 `0`时已存在的 memory worker 必须是 `stopped`.

## 回滚

- 首选: 在 Git 中创建反向提交, 按 `develop -> master`重新发布, 不改写共享历史.
- 紧急关闭学习能力: 在服务器把 `XR_CLASS_COMMENTARY_MEMORY_ENABLED=0`, 再运行标准部署脚本. 脚本会重启 Web, 停止已存在的 memory worker并执行 `pm2 save`. 这只关闭新学习和检索, 不删除 SQLite revision 或 Mem0 memory.
- 数据库 schema 使用前向兼容策略. 不自动执行 down migration, 不删除 revision, operation 或 evidence 表.
- 恢复前先修正配置或代码, 重新打开 flag, 然后再次运行标准部署脚本. 脚本全部健康检查通过后才算恢复完成.

## GitHub 拉取异常

生产机 `origin`应为:

```text
git@github-xingrun-website:KaynXu/Xingrun-Website.git
```

它通过服务器 `~/.ssh/config`中的 `github-xingrun-website` alias 连接 `ssh.github.com:443`. 如果直接拉取失败, 使用 `docs/deploy-release.md`中的 bundle 兜底, 不在仓库保存 SSH 密码.
