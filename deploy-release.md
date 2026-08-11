# Xingrun 生产发布

这份文件是唯一的生产发布说明. 生产进程统一由 PM2 管理, 不使用 `nohup`, PID 文件或手工后台启动.

## 固定约定

- 生产机: `ubuntu@49.234.185.86`
- 仓库: `/home/ubuntu/Xingrun-Website`
- 集成分支: `develop`
- 发布分支: `master`
- Python: `3.12.x`
- Web 进程: `xingrun`
- Memory worker: `xingrun-class-commentary-memory-worker`
- 唯一部署入口: `scripts/deploy_backend.sh`

密码和 API key 只放 secret store 或生产机 `.env.runtime`. 不写入 Git, 文档或命令历史.

## 发布流程

在本地确认改动和分支关系, 完成与改动风险相称的测试:

```bash
git checkout develop
git fetch origin
git status --short --branch
git rev-list --left-right --count origin/develop...develop
git rev-list --left-right --count origin/master...origin/develop
git diff --check
```

提交并推送 `develop`, 然后合并到 `master`:

```bash
git push origin develop
git checkout master
git pull --ff-only origin master
git merge --no-ff develop -m "Merge branch 'develop'"
git push origin master
```

在生产机发布 `master`:

```bash
ssh ubuntu@49.234.185.86
cd /home/ubuntu/Xingrun-Website
git fetch origin
git checkout master
git pull --ff-only origin master
npm --prefix frontend run build
XR_SKIP_GIT_SYNC=1 XR_PYTHON_BIN=python3.12 ./scripts/deploy_backend.sh master
```

若发布包含新的固定课程包, Web/worker 健康后再执行显式课程导入. 不得在启动脚本中联网拉取或自动激活. 先确认 `.env.runtime` 解析出的 `XR_DB_PATH` 实际绝对路径和 active super owner id, 对该 SQLite 做在线备份和完整性检查, 然后按 `README.md` 的 `apply -> review -> activate -> verify` 顺序执行. 最后运行:

```bash
.venv/bin/python scripts/rebuild_class_commentary_semantica_graph.py --confirm
```

重建验收必须同时看到固定课程包的 2237 个基础节点、4007 条基础关系, 以及现有可信 learning event. 课程数据采用 CC BY-NC-SA 4.0, 只允许在已确认的非商业用途边界内发布.

生产机 `origin` 应为 `git@github-xingrun-website:KaynXu/Xingrun-Website.git`. 如果 GitHub 暂时不可达, 使用一次性 `git bundle` 传输 `master`, 只做 fast-forward, 发布成功后删除 bundle.

## 为什么保留部署脚本

`scripts/deploy_backend.sh` 负责不可省略的确定性步骤:

- 校验 Python 3.12 和必要命令.
- 安装后端依赖并初始化数据库.
- 创建或重启 PM2 Web 进程.
- 当 `XR_CLASS_COMMENTARY_MEMORY_ENABLED` 或 `XR_CLASS_COMMENTARY_GRAPH_ENABLED` 任一开启时启动共享 worker; 两者都关闭时停止它.
- 检查 Web `online` 和根路由 HTTP `302`.
- Memory 开启时检查 worker, Redis/RQ, Mem0/Qdrant 和 reconciliation job.
- Graph 开启时确认 Explorer 关闭, graph store 为持久绝对路径, 从 SQLite rebuild 后的节点/关系/hash 完整一致, Redis/RQ 健康且 graph reconciliation 已排期.
- 全部通过后执行 `pm2 save`.

模型可以辅助诊断, 但不能替代这些可重复的状态变更和健康门槛. `scripts/ralph/` 中的历史 proof 脚本不属于发布入口.

## 配置和验收

`XR_CLASS_COMMENTARY_MEMORY_ENABLED=0` 是合法的 migration-first 模式. 设置为 `1` 时, `.env.runtime` 必须提供有效的 Redis, Mem0, Qdrant 和 embedding 配置.

发布脚本成功后做一次只读复核:

```bash
cd /home/ubuntu/Xingrun-Website
pm2 status xingrun xingrun-class-commentary-memory-worker
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/
```

成功标准:

- Web 为 `online`, HTTP 为 `302`.
- Memory 开启时 worker 为 `online`, 相关 capability 检查全部通过.
- Graph 开启时 worker 为 `online`, Explorer 为关闭, Semantica rebuild 与 SQLite canonical counts 一致.
- Memory 和 Graph 都关闭时已有 worker 为 `stopped`.

失败时只查看必要日志, 不输出 `.env.runtime`, `pm2 env` 或完整 memory 内容:

```bash
pm2 logs xingrun --lines 80 --nostream
pm2 logs xingrun-class-commentary-memory-worker --lines 80 --nostream
```

## 回滚

- 代码问题使用 `git revert`, 再按 `develop -> master` 发布. 不改写共享历史.
- Memory 依赖故障时将 `XR_CLASS_COMMENTARY_MEMORY_ENABLED=0`, 重新运行标准部署脚本.
- 不自动执行数据库 down migration, 不删除 generation, revision, memory, evidence 或 operation 数据.
