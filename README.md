# 星润课后复习系统

每次上课后提交课堂总结（文字/文件/音频），AI 自动生成 **8 天填空题复习讲义 PDF** 并记入题库。月底一键生成 **14 天月度综合复习计划 PDF**。

提供 **Web UI**（React + Flask API）和 **命令行**（CLI）两种使用方式。

---

## 快速开始

## Git 协作

当前项目建议长期只保留一个主分支 `master`，功能开发使用临时分支，合并后及时删除。

协作说明见：
[`docs/git-collaboration.md`](docs/git-collaboration.md)

### 方式一：Web UI（推荐）

**macOS** — 双击 `start.command`  
**Windows** — 双击 `start.bat`

启动脚本会自动创建虚拟环境、安装依赖、初始化数据库，并启动后端 `http://127.0.0.1:5001`。

前端默认开发地址为 `http://127.0.0.1:3000`（Vite）。
后端根路径 `/` 会重定向到该前端地址。

**手动启动：**
```bash
# 终端 1：后端
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py

# 终端 2：前端
cd frontend
npm install
npm run dev
```

启动后进入**设置页面**配置 API Key 和服务商（见下方「AI 服务商」）。

生产部署推荐使用环境变量，而不是把敏感配置直接写进 `config.json`。

---

### 方式二：命令行（CLI）

### 1. 初始化（只需做一次）

```bash
python lesson_manager.py setup
```
按提示输入 OpenAI API Key（用于音频转录 + 复习计划生成）。  
API Key 保存在 `config.json`，也可以设置环境变量 `OPENAI_API_KEY`。

### 环境变量部署

推荐在服务器上创建 `.env.runtime`，并通过 `scripts/run_backend.sh` 启动后端。
可参考 `.env.runtime.example`。

常用变量：

```bash
XR_PROVIDER=n1n
N1N_API_KEY=your_n1n_api_key
XR_N1N_BASE_URL=https://api.n1n.ai/v1
XR_N1N_MODEL=gpt-4o

# 可选：admin 登录覆盖
XR_ADMIN_USERNAME=admin
XR_ADMIN_PASSWORD_HASH=<sha256_hex>

# 微信小程序家长上传 bridge
XR_WECHAT_SERVICE_TOKEN=replace_with_shared_bridge_token
```

优先级规则：环境变量 > `config.json`。
`config.json` 仍可用于本地开发和保存登录 token，但生产环境推荐把敏感配置放进环境变量。

服务器发布可直接执行：

```bash
./scripts/deploy_backend.sh
```

如需指定分支：

```bash
./scripts/deploy_backend.sh master-sync
```

这个脚本会自动：
- `git fetch` + `git pull --ff-only`
- 检查并更新 `.venv` 依赖
- 执行 `init_db()`
- 停掉旧的 `app.py` 进程并后台重启
- 对 `http://127.0.0.1:5001/` 做健康检查

部署脚本会自动设置 `XR_OPEN_BROWSER=0`，避免服务器重启时尝试打开本地浏览器。

---

## 微信小程序家长上传 MVP

网站侧在这条链路中承担两件事：

- 作为老师、班级、学生的主数据源
- 作为老师处理 `wechat_mp` 记录的工作台承接层

当前网站已提供：

- 班级邀请码读取/重置
  - `GET /api/classes/<class_id>/invite`
  - `POST /api/classes/<class_id>/invite/reset`
- 微信小程序 bridge 接口
  - `POST /api/wechat/login`
  - `POST /api/wechat/bind-class`
  - `POST /api/wechat/bind-student`
  - `GET /api/wechat/bindings`
  - `POST /api/wechat/wrong-questions`

约束规则：

- 网站里的 `classes / students / users` 是唯一 canonical identity
- 小程序绑定流程必须使用网站返回的学生名单，不允许手填学生名
- 所有 `/api/wechat/*` 请求都必须携带 `X-Wechat-Service-Token`
- 该 token 由网站运行时配置 `XR_WECHAT_SERVICE_TOKEN` 提供，并与 mini backend 的 `WEBSITE_API_TOKEN` 保持一致

### Parent Upload Smoke Test

```text
1. 在网站运行环境配置 XR_WECHAT_SERVICE_TOKEN，并启动 Flask 服务
2. 以 owner/admin 身份登录网站，确认可读取并重置某个班级的邀请码
3. 在 mini backend 配置 WEBSITE_API_BASE_URL 与 WEBSITE_API_TOKEN
4. 在微信开发者工具打开小程序，执行：登录 -> 输入邀请码 -> 选择学生 -> 上传 1 张错题图
5. 回到网站“智能错题”页面，确认出现 source=wechat_mp 的新记录，且班级/学生/老师归属正确
```

---

### 2. 添加一节课

**方式 A：文本文件（推荐）**
```bash
python lesson_manager.py add --file 今天总结.txt --subject 数学 --grade 初二
```

**方式 B：直接粘贴文本**
```bash
python lesson_manager.py add --text "科目：数学\n年级：初二\n本节课主题：..."
```

**方式 C：上传录音文件（自动转录）**
```bash
python lesson_manager.py add --audio 录音.m4a --subject 数学 --grade 初二
```
支持格式：mp3 / m4a / wav / mp4 / ogg / webm / flac

执行后自动：
- 调用 AI 生成 8 天填空题复习讲义
- 存入题库（SQLite 数据库）
- 输出 PDF 到 `data/pdfs/` 并自动打开

---

### 3. 课堂总结推荐格式

系统可以识别结构化格式（也支持自由格式，AI 会自动解析）：

```
科目：数学
年级：初二
本节课主题：二次函数图像与性质
课堂总结：
  本节讲了二次函数 y=ax²+bx+c 的开口方向、对称轴、顶点……
学生薄弱点（如果有）：
  顶点坐标公式记错，忘记讨论 a 的正负
```

---

### 4. 查看课程列表

```bash
python lesson_manager.py list              # 全部
python lesson_manager.py list --month 2026-03  # 某月
```

---

### 5. 生成月度综合复习 PDF

```bash
python lesson_manager.py monthly --month 2026-03
```
系统会把当月全部课程聚合，AI 生成 14 天月度复习计划 PDF。

---

### 5.1 使用新版课后复习计划模板

项目内已同步新版模板工作区到 `review_plan_templates/`，用于生成“第 1 / 2 / 7 / 14 / 30 天”的课后复习计划 PDF。

常用命令：

```bash
python review_plan_templates/generate_review_pdfs.py
```

指定某个课程包生成：

```bash
python review_plan_templates/generate_review_pdfs.py default review_plan_templates/lesson_pack_vector_workflow.py
```

如需旧双语版：

```bash
python review_plan_templates/generate_review_pdfs.py hybrid review_plan_templates/lesson_pack_vector_workflow.py
```

说明：
- 网页和 CLI 的单课 PDF 现在统一走 `review_plan_templates/single_lesson_pdf.py`
- 模板脚本、课程包和工作流文档位于 `review_plan_templates/`
- `review_plan_templates/generate_review_pdfs.py` 仍可独立生成同款版式 PDF
- 生成的 PDF 默认输出到 `review_plan_templates/pdf_output/`
- 输出目录已加入 `.gitignore`，不会把新生成的 PDF 自动纳入版本管理
- `pdf_engine.py` 仅保留月度 / 非单课 PDF 逻辑

---

### 6. 题库操作

```bash
python lesson_manager.py quiz                      # 全部题库（隐藏答案）
python lesson_manager.py quiz --month 2026-03      # 某月题库
python lesson_manager.py quiz --id 3               # 某节课题库
python lesson_manager.py quiz --show-answers       # 显示答案
```

---

### 7. 其他命令

```bash
python lesson_manager.py show --id 3    # 查看某节课详情
python lesson_manager.py open --id 3    # 重新打开某节课 PDF
```

---

## AI 服务商

支持三种服务商，在 Web UI 设置页、`config.json` 或环境变量中切换：

| 服务商 | 说明 |
|--------|------|
| OpenAI | 默认，使用 GPT-4o 生成计划 + Whisper 语音转文字 |
| DeepSeek | 兼容 OpenAI SDK |
| MiMo | 自定义端点 |

---

## REST API

后端提供 REST API（CORS 已放行 `localhost:3000`、`localhost:5173`、`localhost:8080`），供当前仓库内 `frontend/` 调用：

| 端点 | 方法 |
|------|------|
| `/api/stats` | GET |
| `/api/classes` | GET, POST |
| `/api/classes/<id>` | GET, PUT, DELETE |
| `/api/review-plans` | GET, POST |
| `/api/review-plans/<id>` | GET, DELETE |
| `/api/quiz` | GET |
| `/api/monthly` | GET |
| `/api/monthly/generate` | POST |
| `/api/settings` | GET, POST |

---

## 文件结构

```
Xingrun-Website/
├── app.py                      ← Flask 主应用，所有路由
├── lesson_manager.py           ← 数据库层 + CLI 入口
├── ai_processor.py             ← AI 调用（计划生成、语音转写）
├── pdf_engine.py               ← PDF 生成（课时单、月度、周报）
├── frontend/                   ← Vite + React 前端
├── review_plan_templates/      ← 新版课后复习计划模板、课包与工作流文档
├── config.json                 ← 本地配置与登录 token（生产环境建议使用环境变量覆盖）
├── .env.runtime.example        ← 生产环境变量示例
├── config_runtime.py           ← 运行时配置加载（环境变量优先）
├── scripts/                    ← 部署与后端运行脚本
├── tests/                      ← 后端回归测试
├── requirements.txt
├── start.command               ← macOS 一键启动
├── start.bat                   ← Windows 一键启动
└── data/
    ├── lessons.db              ← SQLite 数据库（课程 + 题库）
    ├── pdfs/                   ← 生成的 PDF 文件
    └── uploads/                ← 音频临时文件（处理后自动删除）
```

---

## 注意事项

- 需要有效的 **OpenAI API Key** 才能使用 AI 功能（音频转录 + 计划生成）
- 单次添加课程约消耗 GPT-4o 3000~5000 tokens（约 $0.01～$0.02）
- 月度复习约消耗 5000~10000 tokens（多课程聚合）
- 数据全部本地存储，不上传到任何服务器
- 生产部署建议不要把真实 API Key 提交进 git；优先使用 `.env.runtime`
