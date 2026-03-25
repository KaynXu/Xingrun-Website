# 复习计划管理系统

每次上课后，把录音或课堂总结发给系统，自动生成 8 天填空题复习讲义 PDF，并记入题库。月底可一键生成月度综合复习计划。

---

## 快速开始

### 1. 初始化（只需做一次）

```bash
python lesson_manager.py setup
```
按提示输入 OpenAI API Key（用于音频转录 + 复习计划生成）。  
API Key 保存在 `config.json`，也可以设置环境变量 `OPENAI_API_KEY`。

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

## 文件结构

```
复习计划/
├── lesson_manager.py           ← 主入口 CLI
├── ai_processor.py             ← AI 处理（转录 + 计划生成）
├── pdf_engine.py               ← PDF 生成引擎
├── config.json                 ← API Key 配置
├── data/
│   ├── lessons.db              ← SQLite 数据库（课程 + 题库）
│   └── pdfs/                   ← 生成的 PDF 文件
└── .venv/                      ← Python 虚拟环境
```

---

## 注意事项

- 需要有效的 **OpenAI API Key** 才能使用 AI 功能（音频转录 + 计划生成）
- 单次添加课程约消耗 GPT-4o 3000~5000 tokens（约 $0.01～$0.02）
- 月度复习约消耗 5000~10000 tokens（多课程聚合）
- 数据全部本地存储，不上传到任何服务器
