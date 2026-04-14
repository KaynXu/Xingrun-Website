# 生产发布与部署流程

这份文档给未来的 AI 和人工操作者用，目标是把一次标准生产发布收口成固定动作，避免再临场猜分支、猜服务器命令、猜健康检查口径。

## 适用范围

- 当前生产机：`49.234.185.86`
- SSH：`ubuntu@49.234.185.86`
- 生产仓库：`/home/ubuntu/Xingrun-Website`
- PM2 服务：`xingrun`
- 正式发布目标分支：`master`
- 日常开发与集成分支：`develop`

## 先看结论

- 正常发布主路径永远是：`develop -> master -> 部署生产`
- 不要把 `master -> develop` 当成日常 release 流程
- 只有在历史上 `master` 已经混入额外提交、而且明确决定要回灌时，才允许单独处理 `master -> develop`
- 生产机仓库现在已经切到 GitHub SSH over 443；正常情况下直接 `git fetch origin` 即可，不应该再默认走 `bundle`
- 如果服务器 `git fetch origin` 失败，先确认远端 `origin` 仍是 `git@github-xingrun-website:KaynXu/Xingrun-Website.git`，再决定是否切 `git bundle + scp` 兜底

## 推荐闭环

每次正式发布，默认按这 4 步闭环，不要只做中间一段：

1. 先在 `develop` 做 fresh verification，并把通过验证的提交推到 `origin/develop`
2. 再把 `develop` 合到 `master`，并在合并后的 `master` 结果上重跑 verification
3. 部署成功后，再补 `handoff.md` 或相关发布文档的 docs commit，把这次真实发布结果写回仓库
4. 最后把生产机仓库 `HEAD` 轻量同步到最新 `master`，并用一个 temp script 一次性校验本地仓库、`origin/master`、生产机仓库和线上健康状态

如果只做到第 2 步或第 3 步，仓库记录、远端分支和生产机仓库 `HEAD` 很容易出现“功能已上线，但文档或仓库状态没对齐”的半收口状态。

## 发布前检查

在本地仓库根目录执行：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git checkout develop
git status --short --branch
git rev-list --left-right --count origin/master...origin/develop
```

要求：

- 工作区干净
- 本轮待发布改动已经在 `develop`
- 先看清 `master` 和 `develop` 是否已经漂移，再决定是否能直接 release

## 标准发布流程

### 1. 在 `develop` 验证并推送

前端验证：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npm test
npm run build
```

后端如果本地 Python 版本不够，直接用临时 Python 3.13 虚拟环境：

```bash
/opt/homebrew/bin/python3.13 -m venv /tmp/xr-release-py313-venv
/tmp/xr-release-py313-venv/bin/pip install -q --upgrade pip
/tmp/xr-release-py313-venv/bin/pip install -q -r /Users/ark.mini/Desktop/Xingrun-Website/requirements.txt pytest
/tmp/xr-release-py313-venv/bin/python -m pytest \
  /Users/ark.mini/Desktop/Xingrun-Website/tests/test_smart_wrong_questions_api.py \
  /Users/ark.mini/Desktop/Xingrun-Website/tests/test_wechat_parent_upload_api.py \
  /Users/ark.mini/Desktop/Xingrun-Website/tests/test_wechat_parent_upload_data.py -q
```

验证通过后推送：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git checkout develop
git push origin develop
```

### 2. 把 `develop` 合到 `master`

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git checkout master
git pull --ff-only origin master
git merge --no-ff develop -m "Merge branch 'develop'"
```

合并后至少再跑一轮前端验证：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npm test
npm run build
```

然后推送 `master`：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git push origin master
```

## 生产部署

### 方案 A：服务器直接拉最新 `master`

优先用这个方案。先确保 SSH 走密码认证登录服务器，不要卡在错误的公钥顺序上；服务器仓库内部再通过专用 deploy key 走 GitHub SSH over 443：

```bash
export SSHPASS='***REMOVED-ROTATED-SSH-PASSWORD***'
sshpass -e ssh -tt \
  -o PubkeyAuthentication=no \
  -o PreferredAuthentications=password,keyboard-interactive \
  -o StrictHostKeyChecking=accept-new \
ubuntu@49.234.185.86 '
set -euo pipefail
cd /home/ubuntu/Xingrun-Website
git remote get-url origin
git fetch origin
git checkout master
git pull --ff-only origin master
npm --prefix frontend run build
pm2 restart xingrun
pm2 status xingrun | sed -n "1,20p"
curl -sS -D - -o /dev/null http://127.0.0.1:5001/ | sed -n "1,10p"
'
```

当前生产机修复后的关键状态应当是：

```bash
cd /home/ubuntu/Xingrun-Website
git remote get-url origin
```

输出应为：

```text
git@github-xingrun-website:KaynXu/Xingrun-Website.git
```

对应服务器上的 `~/.ssh/config` 使用专用 alias：

```sshconfig
Host github-xingrun-website
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/id_xingrun_website_deploy
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
```

### 方案 B：服务器拉 GitHub 失败时，走 `bundle` 兜底

如果看到这些错误，不要继续硬等：

- `Couldn't connect to server`
- `GnuTLS recv error (-110)`
- `TLS connection was non-properly terminated`

直接在本地执行：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
bundle_path="/tmp/xr-master-$(git rev-parse --short HEAD).bundle"
git bundle create "$bundle_path" master

export SSHPASS='***REMOVED-ROTATED-SSH-PASSWORD***'
sshpass -e scp \
  -o PubkeyAuthentication=no \
  -o PreferredAuthentications=password,keyboard-interactive \
  -o StrictHostKeyChecking=accept-new \
  "$bundle_path" ubuntu@49.234.185.86:/tmp/

sshpass -e ssh -tt \
  -o PubkeyAuthentication=no \
  -o PreferredAuthentications=password,keyboard-interactive \
  -o StrictHostKeyChecking=accept-new \
  ubuntu@49.234.185.86 '
set -euo pipefail
cd /home/ubuntu/Xingrun-Website
bundle_path=/tmp/'"$(basename "$bundle_path")"'
git fetch "$bundle_path" master:refs/heads/deploy-master
git checkout master
git merge --ff-only deploy-master
git branch -D deploy-master
npm --prefix frontend run build
pm2 restart xingrun
pm2 status xingrun | sed -n "1,20p"
sleep 8
curl -sS -D - -o /dev/null http://127.0.0.1:5001/ | sed -n "1,10p"
rm -f "$bundle_path"
'

rm -f "$bundle_path"
```

## 健康检查怎么判断算成功

当前服务根路由 `/` 的正常行为通常不是 `200`，而是：

```text
HTTP/1.1 302 FOUND
Location: http://127.0.0.1:3000
```

所以：

- `pm2 status xingrun` 显示 `online`
- `curl http://127.0.0.1:5001/` 返回 `302 FOUND`

就可以视为服务正常恢复。

如果刚 `pm2 restart xingrun` 后第一下 `curl` 失败，不要立刻判定部署失败，先 `sleep 8` 再打一次。

## 发布后收尾

发布完成后再做这几步：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git checkout develop
git status --short --branch
git log --oneline -3 --decorate
```

- 更新根目录 `handoff.md`
- 记录这次是否走了正常发布还是 `bundle` 兜底
- 如果文档本身有更新，单独提交 docs commit
- 如果这次补了发布 docs commit，记得把生产机仓库也再 `git pull --ff-only origin master` 一次，只同步仓库头，不必重复重启服务
- 不要把运行时垃圾文件留在工作区，比如 `__pycache__/`、`tests/__pycache__/`、`data/xingrun.db`

## 给下一位 AI 的硬规则

- 先读 `AGENTS.md` 和 `handoff.md`
- 小改动默认在 `develop`
- 生产发布只按 `develop -> master -> 部署`
- 不要把 `master -> develop` 当默认步骤
- proof 必须通过临时脚本执行，并把完整输出贴回对话
- 如果服务器连 GitHub 抖动，直接切 `bundle` 方案，不要无限重试
