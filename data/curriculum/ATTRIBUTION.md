# 人教版数学课程知识图谱数据来源

本目录中的 `pep_math_k12_kgraph_d8522c2b.json` 是从以下固定上游文件确定性过滤得到的数据包:

- 项目: `haolpku/K12-KGraph`
- GitHub commit: `8716b6a80850790f509c01286f43e5bfe6858f49`
- Hugging Face dataset: `lhpku20010120/K12-KGraph`
- Dataset revision: `d8522c2b336ee435aa51daa39ca0dd736f56fa53`
- Source file: `K12-KGraph/subject_specific_KG/math.json`
- Source SHA-256: `00ed25179bb4ad096c53b3965fe84a32afa708850de85db5ea4c9e0bacec8f14`
- Data license: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
- Upstream code license: MIT

本项目按非商业用途使用该衍生数据. 该衍生数据继续采用 CC BY-NC-SA 4.0, 不改变 Xingrun 其他代码的许可证.

数据包只保留 Book, Chapter, Section, Concept, Skill 以及任务明确允许的关系和字段. 它不包含 Exercise 节点, 题目正文, 图片, K12-Bench, K12-Train, 模型权重或训练问答.

固定源文件的 README 记录 1475 个 Concept, 但上述固定文件实际包含 1470 个 Concept. Xingrun 的导入器以固定 revision 和 SHA-256 对应文件的实际解析结果为准, 并在任何 revision, hash, schema 或计数不一致时拒绝导入.

完整机器可读来源收据位于 `pep_math_k12_kgraph_d8522c2b.receipt.json`.
