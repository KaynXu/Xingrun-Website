# 自有服务器部署说明

这个项目当前实际跑在自有服务器上，不走微信云托管。

## 当前正式环境

- 服务器：`49.234.185.86`
- 公网域名：`https://xingrun.online`
- SSH：`ssh ubuntu@49.234.185.86`
- 后端目录：`/home/ubuntu/xingrun-backend-repo/backend`
- PM2 进程：`xingrun-bridge`
- 服务端口：`3001`

## 小程序当前配置

当前小程序应直连自有服务器：

- [miniprogram/app.js](/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/app.js)
  - `serverUrl = https://xingrun.online`

## 服务器部署步骤

1. SSH 登录服务器。
2. 进入后端目录：`cd /home/ubuntu/xingrun-backend-repo/backend`
3. 同步代码后执行：`npm run build`
4. 重启服务：`pm2 restart xingrun-bridge`

## 部署后验证

先在服务器本机执行：

- `curl http://127.0.0.1:3001/healthz`

预期返回：

- `{"ok":true,"service":"xingrun-parent-wechat-bridge",...}`

如果要检查家长链路，继续验证：

- `POST /wechat/parent/login`
- `GET /wechat/parent/bindings?openId=test-openid`
- `POST /wechat/parent/bind-class`
- `POST /wechat/parent/bind-student`
- `POST /wechat/parent/wrong-questions`
- `POST /wechat/parent/wrong-question-boxes`

## 当前已确认的问题

`2026-04-09` 起当前正式服务器已切到“家长绑定 -> 家长首页 -> 上传错题”链路，旧聊天式 `/rooms`、`/wechat/config` 等接口已从 bridge 中删除；上传页当前也已包含 `AI 框选` 能力，走 `POST /wechat/parent/wrong-question-boxes`。
