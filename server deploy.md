# Server 1 简表

> 当前公网生产机就是这台：`49.234.185.86`
> 默认部署目标按这台机器处理，除非明确说明要发别的环境。
> 完整生产发布步骤不要只看这份简表，统一以 `docs/deploy-release.md` 为准。

## 服务器 1

- **IP**: `49.234.185.86`
- **SSH**: `ssh ubuntu@49.234.185.86`
- **密码**: `***REMOVED-ROTATED-SSH-PASSWORD***`
- **仓库路径**: `/home/ubuntu/Xingrun-Website`
- **后端 PM2**: `xingrun`

## 日常发布

当前仓库没有根目录 `deploy.sh`，实际可用脚本是：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
./scripts/deploy_backend.sh master
```

如果只是把 `develop` 推到远端，不等于已经发生产。生产正式发布仍然是：

`develop -> master -> 生产部署`

完整步骤见 `docs/deploy-release.md`。

如果只是同步 `develop` 远端：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git push origin develop
```

然后登录生产机并执行：

```bash
cd /home/ubuntu/Xingrun-Website
git fetch origin
git checkout develop
git pull --ff-only origin develop
npm --prefix frontend run build
pm2 restart xingrun
pm2 status xingrun
curl -fsS http://127.0.0.1:5001/
```

## 脚本默认行为

- `./scripts/deploy_backend.sh <branch>` 运行在服务器仓库内。
- 脚本会执行：拉取分支 -> 安装后端依赖 -> 初始化数据库 -> 重启后端 -> 健康检查。
- 这个脚本只管后端，不会替代前端构建；前端仍需单独执行 `npm --prefix frontend run build`。

## SSH 登录兜底

如果普通 `ssh ubuntu@49.234.185.86` 一直失败，但已确认密码可用，优先强制走密码认证：

```bash
export SSHPASS='***REMOVED-ROTATED-SSH-PASSWORD***'
sshpass -e ssh -tt \
	-o PubkeyAuthentication=no \
	-o PreferredAuthentications=password,keyboard-interactive \
	-o StrictHostKeyChecking=accept-new \
	ubuntu@49.234.185.86
```

这次实测就是靠这组参数恢复了服务器登录。根因不是仓库或 PM2，而是默认 SSH 认证顺序没有正确落到密码登录。

## 手动发布兜底

```bash
export SSHPASS='***REMOVED-ROTATED-SSH-PASSWORD***'
sshpass -e ssh -tt \
	-o PubkeyAuthentication=no \
	-o PreferredAuthentications=password,keyboard-interactive \
	-o StrictHostKeyChecking=accept-new \
	ubuntu@49.234.185.86 '
set -euo pipefail
cd /home/ubuntu/Xingrun-Website
git fetch origin
git checkout develop
git pull --ff-only origin develop
npm --prefix frontend run build
pm2 restart xingrun
pm2 status xingrun | sed -n "1,20p"
curl -fsS http://127.0.0.1:5001/ | head -c 200 && echo
'
```

## 备注

- 线上服务器默认仓库路径是 `/home/ubuntu/Xingrun-Website`
- 当前生产发布目标分支是 `master`，开发集成分支是 `develop`
- 如果未来再引入 staging 或备用机，必须在文档里明确标注用途，不能覆盖这份生产机说明
