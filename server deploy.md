# Server 1 简表

> 当前公网生产机就是这台：`49.234.185.86`
> 默认部署目标按这台机器处理，除非明确说明要发别的环境。

## 服务器 1

- **IP**: `49.234.185.86`
- **SSH**: `ssh ubuntu@49.234.185.86`
- **密码**: `***REMOVED-ROTATED-SSH-PASSWORD***`
- **仓库路径**: `/home/ubuntu/Xingrun-Website`
- **后端 PM2**: `xingrun`

## 日常发布

优先使用根目录下的脚本：

```bash
./deploy.sh "feat: your change" Xingrun-Summary/app.py Xingrun-Summary/frontend/src/App.tsx
```

如果这次代码已经提前 commit 过了，只想推送并部署：

```bash
./deploy.sh --skip-commit
```

## 脚本默认行为

- 默认服务器：`ubuntu@49.234.185.86`
- 默认远端仓库：`/home/ubuntu/Xingrun-Website`
- 默认重启 PM2：`xingrun`
- 前端仍会执行 `npm --prefix frontend run build`

## 脚本失效时的手动兜底

```bash
ssh ubuntu@49.234.185.86
cd /home/ubuntu/Xingrun-Website
git pull origin master
npm --prefix frontend run build
pm2 restart xingrun
pm2 status
```

## 备注

- `deploy.sh` 在工作区根目录，本地默认进入 `Xingrun-Summary`
- 线上服务器默认仓库路径是 `/home/ubuntu/Xingrun-Website`
- 如果未来再引入 staging 或备用机，必须在文档里明确标注用途，不能覆盖这份生产机说明
