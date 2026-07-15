# 生产发布与部署流程

这份文档定义 Xingrun Website 的标准生产发布流程. 生产进程只由 PM2 管理, 不使用 `nohup`, PID 文件或手工后台运行 Python.

## 适用范围

- 生产机: `49.234.185.86`
- SSH: `ubuntu@49.234.185.86`
- 仓库: `/home/ubuntu/Xingrun-Website`
- Python: `3.12.x`
- Web process: `xingrun`
- 课堂点评记忆 worker: `xingrun-class-commentary-memory-worker`
- 发布分支: `master`
- 集成分支: `develop`

服务器密码, API key 和 Qdrant key 从批准的 secret store 获取. 不把它们写进仓库, 发布文档或命令历史.

## 发布原则

- 正常路径是 `develop -> master -> production`.
- `master`合并由人工确认, 不自动执行.
- 本地和生产都使用 Python 3.12. 不再用 Python 3.13 临时环境代替发布验证.
- `scripts/deploy_backend.sh`是 Web 和课堂点评记忆 worker 的唯一生产进程发布入口.
- 脚本始终创建或重启 Web. Flag 开启时才创建或使用 `pm2 restart --update-env`重启 memory worker; flag 关闭时停止已存在的 worker.
- Memory worker 的 `kill_timeout`不得低于 `330000ms`, 保证 300 秒任务有正常退出窗口.

## 1. 发布前验证

在本地仓库根目录确认工作区和分支关系:

```bash
git checkout develop
git fetch origin
git status --short --branch
git rev-list --left-right --count origin/develop...develop
git rev-list --left-right --count origin/master...origin/develop
```

要求:

- 工作区干净.
- 本地 `develop`与 `origin/develop`同步.
- 本轮改动已经提交到 `develop`.
- 已看清 `master`和`develop`的差异.

用 Python 3.12 创建临时验证环境:

```bash
PYTHON_312="${XR_PYTHON_BIN:-python3.12}"
"$PYTHON_312" -m venv /tmp/xr-release-py312-venv
/tmp/xr-release-py312-venv/bin/python -m pip install -q --upgrade pip
/tmp/xr-release-py312-venv/bin/python -m pip install -q -r requirements.txt pytest
/tmp/xr-release-py312-venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

验证通过后推送 `develop`:

```bash
git push origin develop
```

## 2. 人工合并到 master

只有人工确认后才执行:

```bash
git checkout master
git pull --ff-only origin master
git merge --no-ff develop -m "Merge branch 'develop'"
```

在合并后的 `master`重新运行与发布风险相称的测试, 至少包括后端定向测试, 前端测试, 前端 build 和 `git diff --check`. 全部通过后:

```bash
git push origin master
```

## 3. 生产配置门槛

`XR_CLASS_COMMENTARY_MEMORY_ENABLED=0`是合法的 migration-first 模式, 可以先上线 schema 和 Web. 只有 flag 设置为 `1`时, 生产 `.env.runtime`才必须包含有效的 Redis, Mem0, Qdrant 和 embedding 配置. 关键项:

```bash
XR_CLASS_COMMENTARY_MEMORY_ENABLED=1
XR_REDIS_URL=redis://127.0.0.1:6379/0
XR_CLASS_COMMENTARY_MEMORY_QUEUE=class_commentary_memory
XR_CLASS_COMMENTARY_MEMORY_EXTRACTION_TIMEOUT=300
XR_CLASS_COMMENTARY_MEMORY_OPERATION_TIMEOUT=120
XR_CLASS_COMMENTARY_MEMORY_RECONCILE_INTERVAL=600
XR_MEM0_VECTOR_PROVIDER=qdrant
XR_MEM0_QDRANT_URL=...
XR_MEM0_QDRANT_API_KEY=...
XR_MEM0_COLLECTION_NAME=xingrun_class_commentary_memory
XR_MEM0_EMBEDDER_PROVIDER=...
XR_MEM0_EMBEDDER_MODEL=...
XR_MEM0_EMBEDDING_DIMS=...
```

部署脚本会 fail-fast 检查 Python 3.12 和 worker kill timeout. Flag 关闭时停止已存在的 memory worker并跳过 memory capability gate; flag 开启但配置或 capability 不健康时发布失败, 不把`确认并学习`暴露成可用能力.

## 4. 生产部署

### 方案 A: 服务器直接拉取 master

优先使用这条路径:

```bash
ssh ubuntu@49.234.185.86
cd /home/ubuntu/Xingrun-Website
git remote get-url origin
git fetch origin
git checkout master
git pull --ff-only origin master
npm --prefix frontend run build
XR_SKIP_GIT_SYNC=1 XR_PYTHON_BIN=python3.12 ./scripts/deploy_backend.sh master
```

预期 `origin`为:

```text
git@github-xingrun-website:KaynXu/Xingrun-Website.git
```

服务器的 `~/.ssh/config`使用:

```sshconfig
Host github-xingrun-website
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/id_xingrun_website_deploy
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
```

### 方案 B: GitHub 拉取失败时使用 bundle

服务器出现 GitHub 网络错误时, 不无限重试. 在本地创建 bundle:

```bash
git checkout master
bundle_path="/tmp/xr-master-$(git rev-parse --short HEAD).bundle"
git bundle create "$bundle_path" master
scp "$bundle_path" ubuntu@49.234.185.86:/tmp/
```

然后在生产机执行:

```bash
cd /home/ubuntu/Xingrun-Website
bundle_path=/tmp/xr-master.bundle
```

把上面的 `bundle_path`改成实际上传文件名, 再执行:

```bash
git fetch "$bundle_path" master:refs/heads/deploy-master
git checkout master
git merge --ff-only deploy-master
git branch -D deploy-master
npm --prefix frontend run build
XR_SKIP_GIT_SYNC=1 XR_PYTHON_BIN=python3.12 ./scripts/deploy_backend.sh master
rm -f "$bundle_path"
```

本地 bundle 在传输和部署确认后删除.

## 5. 部署脚本做了什么

`scripts/deploy_backend.sh`按顺序执行:

1. 加载 `.env.runtime`并检查 Python 3.12.
2. 检查 `kill_timeout >= 330000ms`.
3. 可选拉取指定分支. 已在外部完成同步时使用 `XR_SKIP_GIT_SYNC=1`.
4. 安装 Python 依赖并运行 `init_db()`.
5. 读取 memory feature flag.
6. 始终创建或重启 `xingrun`. Flag 开启时创建或重启 memory worker; flag 关闭时停止已存在的 worker.
7. 始终检查 Web 是 `online`. Flag 开启时再检查 worker 是 `online`并确认 kill timeout; flag 关闭时确认已存在的 worker 是 `stopped`.
8. 检查 Web 根路由返回精确的 HTTP `302`.
9. Flag 开启时运行 Mem0/Qdrant add, get, search, delete 和中文检索 smoke.
10. Flag 开启时检查 Redis ping 和目标 RQ queue 的 worker count >= 1.
11. Flag 开启时检查 ScheduledJobRegistry 中只有一个下一时间桶 `cc-memory-reconcile-*`任务.
12. Flag 开启且已有投影记录时, 抽查 SQLite `memory_record_id`和 Mem0 `memory_id`可以双向定位. 首次空库会明确输出 `no_projected_records`.
13. 全部检查通过后执行 `pm2 save`.

Capability API 需要老师登录态, 所以发布脚本不伪造业务账号. 它直接复用 API 和 worker 使用的 runtime config 与 healthcheck 实现.

## 6. 人工复核

脚本成功后再执行一次只读复核:

```bash
cd /home/ubuntu/Xingrun-Website
set -a
source .env.runtime
set +a

pm2 status xingrun xingrun-class-commentary-memory-worker
curl -sS -D - -o /dev/null http://127.0.0.1:5001/ | sed -n '1,10p'
.venv/bin/rq info \
  --url "${XR_REDIS_URL:-redis://127.0.0.1:6379/0}" \
  "${XR_CLASS_COMMENTARY_MEMORY_QUEUE:-class_commentary_memory}"
```

成功口径:

- `xingrun`是 `online`.
- 根路由是 `HTTP/1.1 302 FOUND`.
- Flag 为 `1`时, `xingrun-class-commentary-memory-worker`是 `online`, RQ 目标 queue 至少显示 1 个 worker, 部署脚本输出 `memory=ready`, `redis=ready`和 1 个 reconciliation job ID.
- Flag 为 `0`时, 已存在的 memory worker 是 `stopped`, memory capability gate 明确显示 skipped.

如果失败, 使用不泄露环境变量的命令看日志:

```bash
pm2 logs xingrun --lines 80 --nostream
pm2 logs xingrun-class-commentary-memory-worker --lines 80 --nostream
```

不要输出 `pm2 env`, `.env.runtime`或完整 memory 内容到共享记录.

## 7. 回滚

### 代码回滚

首选在本地对问题提交创建 `git revert`反向提交, 经过 `develop -> master`人工 release 后重新执行标准部署. 不使用 `git reset --hard`改写共享历史.

数据库 migration 是前向兼容的. 代码回滚时不自动 down migration, 不删除 generation, revision, memory record, evidence 或 operation 数据.

### 紧急关闭学习能力

如果 Mem0, Qdrant 或 Redis 故障影响发布, 先关闭用户能力:

```bash
cd /home/ubuntu/Xingrun-Website
# 在 .env.runtime 中把 XR_CLASS_COMMENTARY_MEMORY_ENABLED 改为 0
XR_SKIP_GIT_SYNC=1 XR_PYTHON_BIN=python3.12 ./scripts/deploy_backend.sh master
```

该动作只停止新的学习和检索, 不删除 SQLite 或 Mem0 数据. Web 继续按 `online + 302`验收, memory worker 按 `stopped`验收.

修复依赖或配置后:

1. 把 `XR_CLASS_COMMENTARY_MEMORY_ENABLED`恢复为 `1`.
2. 重新运行 `XR_SKIP_GIT_SYNC=1 XR_PYTHON_BIN=python3.12 ./scripts/deploy_backend.sh master`.
3. 只有全部自动检查和人工复核通过后才结束回滚事件.

## 8. 发布后收尾

- 记录生产 `HEAD`, 两个 PM2 process 状态, HTTP 状态和 capability probe 结果.
- 更新 `handoff.md`中的完成项, 遗留问题和下一步.
- 删除本地和服务器的临时 bundle.
- 不提交 `.env.runtime`, `data/*.db`, `__pycache__/`, proof 输出或一次性健康探针产物.
- 如果本轮只同步了后续 docs commit, 可以仅 `git pull --ff-only origin master`, 不需要重复重启服务.
