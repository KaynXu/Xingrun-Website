# Git 协作约定

这份说明只服务当前项目，目标很简单：主线保持清楚，分支不堆积，谁来接手都能马上看懂。

## 默认规则

- 远端长期只保留一个主分支：`master`
- 开发新功能、修 bug、做较大改动时，先从 `master` 临时切一个功能分支
- 功能分支命名尽量直接，例如：`feature/consultation-batch`、`fix/login-copy`
- 完成后先合并回 `master`，再删除本地和远端功能分支
- 不要长期保留 `feature/*`、`backup/*`、`copilot/*` 之类的远端分支

## 推荐流程

### 1. 开始开发前

```bash
git checkout master
git pull --ff-only origin master
git checkout -b feature/your-task-name
```

### 2. 开发过程中

- 只在自己的功能分支上提交
- 尽量一个任务对应一个分支
- 分支还没合并前，不直接往 `master` 上写新的功能提交

### 3. 完成后

```bash
git checkout master
git pull --ff-only origin master
git merge --no-ff feature/your-task-name
git push origin master
git branch -d feature/your-task-name
git push origin --delete feature/your-task-name
```

## 什么时候需要开分支

- 要开发一个新功能
- 要修一个明确的问题
- 要做一批相关联的文案或 UI 修改
- 这次改动可能需要回退、审查或单独测试

## 什么时候可以不单独开分支

- 只有你一个人在仓库里快速做一个极小改动
- 而且你确定这次改动马上就会直接合进 `master`

即便如此，长期看还是推荐开临时分支，后续更不容易乱。

## 对这个项目的特别约定

- `master` 是唯一主线
- 合并完成的功能分支要及时删除
- 如果本地有未提交改动，先处理或暂存，再执行 `pull`、`rebase`、`merge`
- 本地运行数据例如 `data/lessons.db` 不要随手混进正常代码提交

## 一句话版本

先从 `master` 开临时分支，做完合回 `master`，推送后把功能分支删掉，仓库里长期只留一个主分支。
