# R1-only Ablation 设计（预注册）

日期：2026-08-07
状态：执行前预注册

## 1. 动机与时机

"skill 的 token 效应全部来自 R1"是本项目的中心论点，目前证据为强推断
（回归分解 −20.7k vs 实测 −20.4k 吻合 + 其余规则逐一排除 + F7 第三任务
方向一致）。此前评估认为在 F1/F3 上 ablation 结果预定而跳过；现在补做的
理由：(a) 归因已成中心论点，值得实验级证据；(b) 若证实 R1-only 足够，
发布物可裁剪为单规则（注入更短）。

## 2. 臂设置

| 臂 | 注入 | n | 来源 |
|---|---|---:|---|
| baseline | 无 | 20 | 复用主实验池 |
| full skill | SKILL.md 全文（去 frontmatter） | 20 | 复用主实验 skill 臂 |
| **R1-only** | 导语 + Rule 1 原文 | 12（F1×6, F3×6） | 新跑 |
| R1-removed（可选） | 导语 + Rule 2–5 原文 | 8（F1×4, F3×4） | 视 R1-only 结果决定 |

R1-only 文本构成：SKILL.md 的标题、开头导语（"least context you need…"
段）+ Rule 1 全节，**逐字照抄不改写**（避免表述漂移混淆）。Workflow
一节不带——其第 5 步内嵌 R3（"if no new evidence, change approach"）、
第 4 步内嵌 R4（"cheapest relevant verification"），带上即污染。
R1-removed = 同一导语 + Rule 2–5 原文（去 Rule 1 与 Workflow）。

协议其余全同主实验：runner sibling 模式（`run_r1_ablation.py`，现有
文件零改动）、GLM-5.2 (Z.ai)、workspace AGENTS.md 注入、运行目录
`/tmp/oc_r1_ablation_runs`（项目树外）、analyzer 同 schema。

## 3. 预注册预测

1. R1-only vs baseline：总量显著下降，幅度与 full skill 相当（−15%~−25%）；
   reads −40% 上下；单侧 permutation p<0.05。
2. R1-only vs full skill：无显著差异。**注意 power 限制**：n=12 vs 20
   只能给出"未检出差异 + 描述性接近"，不是严格等价性证明——此局限
   预先声明。
3. R1-removed vs baseline（若跑）：全指标持平。

## 4. 判读矩阵（四分支全可发表）

| 结果 | 结论 |
|---|---|
| R1-only ≈ full skill | 归因证实；skill 可裁剪为单规则发布 |
| R1-only 显著弱于 full | 其余规则有协同贡献，归因需修正（新发现） |
| R1-only 强于 full | 其余规则是拖累（注入费/干扰），同样有信息 |
| R1-only ≈ baseline | 归因链有大问题，全面重查 |

## 5. 已知混淆与处理

- **注入长度差**：R1-only 文本约为全文 1/4，AGENTS.md 常驻开销更小。
  若 R1-only 总量略优于 full，需区分"规则效应"与"注入更短"。处理：
  效应对比以行为指标（reads、long_outputs）为主，token 为辅；注入
  体量差单独报告。
- **批间漂移**：新 run 与复用池不同日。处理：主对比（R1-only vs
  baseline/full）跨批,沿用 20v20 时验证过的批间一致性方法——报告
  新批内 F1/F3 分层均值,与旧批同任务分层比对；若中位漂移 >30% 则
  全部重跑（与 batching ablation 同阈值）。
- **主指标**：grand_total（单侧 permutation, 20k 次）；行为指标
  distinct_files_read、long_outputs、fresh input（同主实验预登记集）。

## 6. 执行顺序

1. 建 `run_r1_ablation.py`（含 r1only/r1removed 两臂）；
2. smoke ×1（F1, r1only）：确认 AGENTS.md 内容正确、无 skill 工具
   自发现污染、指标齐全；
3. 正式 12 run（F1×6, F3×6, r1only）；
4. 三臂分析 + 判读矩阵落位；R1-removed 是否跑视结果决定；
5. 结果写入 `r1_ablation_results.md`，更新 00_FINAL_REPORT。
