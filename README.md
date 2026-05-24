# Xingrun-Website

星润教学管理系统（前后端同仓）：
- 后端：Flask API（默认 `127.0.0.1:5001`）
- 前端：React + Vite（默认 `127.0.0.1:3000`）
- 数据：SQLite（默认 `data/xingrun.db`）

## 1. 功能概览

- 账号与组织体系：注册申请、机构审批、角色权限（super_owner / owner / admin / teacher）
- 复习计划：创建、查询、下载 PDF、统计
- 班级管理：班级/学生维护、邀请码、教师绑定
- 班级反馈：任务创建、标签配置、草稿与确认流
- 智能错题：错题提交流与映射管理（含微信家长侧上传链路）
- 积分系统：机构余额、AI 调用记账、账本与成员用量查询

## 2. 项目结构

```text
Xingrun-Website/
├── app.py                         # Flask API 入口
├── lesson_manager.py              # SQLite 数据层
├── ai_processor.py                # AI 处理
├── credit_manager.py              # 积分账本
├── config_runtime.py              # 运行时配置加载（config + env）
├── requirements.txt               # 后端依赖
├── frontend/                      # React + Vite 前端
├── tests/                         # 后端测试
├── scripts/                       # 启动/部署脚本
├── docs/                          # 规范、runbook、计划
└── data/                          # 运行时数据（db/pdf/upload）
```

## 3. 本地启动（推荐）

### 3.1 后端

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
./scripts/run_backend.sh
```

说明：
- `scripts/run_backend.sh` 会读取 `.env.runtime`（如果存在）
- 这个脚本只启动后端 API，不启动前端
- 服务启动后默认监听 `127.0.0.1:5001`
- `5001` 是后端/API 地址；本地开发时不要把它当成页面入口
- 为避免“后端起了但前端没起”的假启动，脚本默认不会自动打开浏览器

### 3.2 前端

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npm install
npm run dev
```

说明：
- 前端默认 `3000` 端口
- 前端需要单独启动
- 3000 才是开发态页面入口
- 后端根路由 `/` 会重定向到 `XR_BROWSER_URL`（默认 `http://127.0.0.1:3000`），所以只有前端已启动时打开 `5001` 才有意义

### 3.3 后端快捷启动（macOS）

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
./start.command
```

说明：
- `start.command` 仅启动后端，并会打印前端启动提示
- 它不会帮你启动前端，也不会自动打开浏览器到错误入口

### 3.4 后端快捷启动（Windows）

```bat
cd /d C:\path\to\Xingrun-Website
start.bat
```

说明：
- `start.bat` 与 `start.command` 一样，仅启动后端
- 本地开发时请另开终端运行前端，再访问 `http://127.0.0.1:3000`

## 4. 运行配置

配置来源按覆盖优先级：
1. 代码默认值（`config_runtime.py`）
2. 本地运行时文件 `config.json`（不入库）
3. 环境变量（优先级最高）

推荐把线上和本机密钥放进 `.env.runtime` 或系统环境变量；仓库里的
`.env.runtime.example` 只保留占位值。不要把真实 API key 写进 Git 跟踪文件。

常用环境变量：
- `XR_DB_PATH`
- `XR_PROVIDER`
- `DEEPSEEK_API_KEY`
- `XR_DEEPSEEK_MODEL`
- `OPENAI_API_KEY`
- `MIMO_API_KEY`
- `DASHSCOPE_API_KEY`
- `XR_QWEN_BASE_URL`
- `XR_BROWSER_URL`
- `XR_OPEN_BROWSER`
- `XR_WRONG_QUESTION_SERVICE_URL`
- `XR_WRONG_QUESTION_SERVICE_TOKEN`

说明：
- 默认数据库真相源固定为 `data/xingrun.db`
- 只有显式设置 `XR_DB_PATH` 或 `config.json` 里的 `db_path` 时，才会改用其他 SQLite 文件

## 5. 测试与构建

### 5.1 后端测试

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

### 5.2 前端检查与测试

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
```

## 6. 部署（当前约定）

生产服务器信息见：`AGENTS.md`。

常用脚本：

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
./scripts/deploy_backend.sh master
```

可选指定分支：

```bash
./scripts/deploy_backend.sh develop
```

说明：
- 脚本会执行：拉取分支 -> 安装依赖 -> 初始化数据库 -> 重启后端 -> 健康检查
- 默认健康检查地址：`http://127.0.0.1:5001/`

## 7. Git 协作建议（适配你当前 master + develop）

你目前是：`master` 主线 + `develop` 集成线 + feature 分支。

建议用一条简单阈值规则，避免频繁“合并来合并去”：
- 小改动（文档、1~2 文件、低风险）：直接在 `develop` 提交
- 中大改动（功能、接口、数据库、多人并行）：从 `develop` 切 feature 分支
- 发布时再把 `develop` 合并到 `master`

这样可以在保留稳定发布节奏的前提下，减少微任务的分支成本。
