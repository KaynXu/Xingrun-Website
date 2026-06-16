# Xingrun-Next 重构设计

日期: 2026-06-10
状态: 已与用户确认

## 目标

旧仓库 `Xingrun-Website` 积累了大量僵尸代码、混乱分支和无用数据库表。在桌面新建全新仓库 `xingrun-next`(不带旧 git 历史),按模块搬运并整形保留功能,前端用 Vite + React + Tailwind + shadcn/ui 重建。

## 保留功能

- 错题闭环(小程序上传 / AI 识别 / 练习 PDF / 老师复核 / AI 对话归档)
- 课后复习计划(录音转写 / PDF 生成)
- 班级 / 学生 / 账号 / 机构管理
- 学生端 `/student` 入口
- 咨询(consultations)
- 课程日历(course calendar)
- 课堂反馈(class feedback)
- 积分 / credit 系统
- 雅思相关工作流(docs 工作流文档随迁)

## 砍掉

- 月计划(monthly_plan_jobs 及相关路由/前端)
- 小红书兑换(xhs_open_platform.py、xhs_order_redemptions)
- 疑似僵尸表(class_aliases、user_aliases、wrong_question_mappings、class_history 等)实施时逐表核对生产数据与代码引用,列清单经用户确认后再砍

## 新项目结构

```
xingrun-next/
├── backend/
│   ├── app.py                 # app factory + 注册 blueprint
│   ├── api/                   # 路由层,按领域拆 blueprint
│   │   ├── auth.py            # 账号/机构/注册审批
│   │   ├── classes.py         # 班级/学生
│   │   ├── wrong_questions.py # 错题闭环
│   │   ├── review_plans.py    # 复习计划
│   │   ├── student_portal.py  # 学生端
│   │   ├── consultations.py
│   │   ├── calendar.py
│   │   ├── feedback.py        # 课堂反馈
│   │   └── credits.py
│   ├── services/              # 业务逻辑层(从 lesson_manager.py 拆出)
│   ├── db/                    # schema.sql + 连接 + 迁移
│   ├── ai/                    # prompt / provider / 清洗
│   ├── pdf/                   # pdf_engine
│   └── workers/               # RQ worker(错题上传/擦除)
├── frontend/                  # Vite + React + Tailwind + shadcn/ui
│   └── src/
│       ├── pages/
│       ├── components/ui/
│       └── lib/
├── docs/
└── scripts/                   # deploy / migrate
```

## 数据库

- 后端继续 Flask + SQLite;新 schema 一次性写干净:只含保留功能的表,统一命名,加外键约束
- `scripts/migrate_from_legacy.py`:读旧 `data/xingrun.db` 写新库,输出每表行数对账
- 上线前用生产库副本演练迁移,对账通过才切换

## 迁移策略

搬+整形,不重写业务逻辑。顺序:

1. 账号 / 机构 / 鉴权
2. 班级 / 学生
3. 错题闭环(最复杂,12+ 张表 + worker + AI 链,地基稳后搬)
4. 复习计划
5. 学生端
6. 咨询 / 日历 / 反馈 / 积分

每搬一个模块,把旧 `tests/` 对应测试一起搬过来跑绿,保证行为一致。

## Git 协作规范(新仓库)

- 新 GitHub 仓库,协作者各用独立账号
- `master` 保护:禁直推,只 PR;`develop` 集成;短命 feature 分支
- 旧仓库:删 `backup/` 分支和已合并 `work/` 分支(删前逐个核对未合并提交);旧仓保持可维护状态到新项目上线

## 服务器切换

- 新项目在服务器独立目录 + 独立 PM2 服务(`xingrun-next`)并行部署,旧服务不停
- 验证通过后切 Nginx,旧服务保留观察期后下线

## 执行顺序

① 设计文档落盘 → ② 旧仓库死分支清理 → ③ 新项目骨架 + schema + 迁移脚本 → ④ 按模块搬运(每模块一轮,测试跑绿) → ⑤ 前端 shadcn 重建 → ⑥ 并行部署 + 切换
