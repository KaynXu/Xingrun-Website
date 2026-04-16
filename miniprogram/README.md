# Xingrun Parent Upload

当前仓库只保留家长上传错题链路：

- 小程序：
  - 家长绑定孩子
  - 家长首页查看已绑定孩子
  - 上传错题图片
  - 多图框题、统一提交
- 后端 bridge：
  - `/wechat/parent/login`
  - `/wechat/parent/bind-class`
  - `/wechat/parent/bind-student`
  - `/wechat/parent/bindings`
  - `/wechat/parent/wrong-questions`

## 当前目录

```text
miniprogram/
├── backend/
├── miniprogram/
├── handoff.md
└── CLOUD_HOSTING_SETUP.md
```

## 小程序入口

- 默认入口会根据本地绑定状态在：
  - `pages/parent-bind/index`
  - `pages/parent-home/index`
 之间跳转
- 家长上传页支持：
  - 多图追加
  - 每张图多个题框
  - 统一提交所有确认后的错题

## 正式服务器

- `49.234.185.86`
- 公网域名：`https://xingrun.online`
- bridge 服务端口：`3001`
- bridge 目录：`/home/ubuntu/xingrun-backend-repo/backend`
- 网站目录：`/home/ubuntu/Xingrun-Website`

## 本地验证

```bash
cd backend
node parent-only-scope.test.cjs
node --import tsx --test src/parent-wechat-bridge.test.ts
npm run build

cd ../miniprogram
node parent-only-scope.test.js
node pages/parent-upload/model.test.js
node utils/parentApi.test.js
```
