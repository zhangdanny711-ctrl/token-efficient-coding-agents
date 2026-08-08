# R1 Ablation 结果（R1-only + R1-removed 四臂）

日期：2026-08-07
预注册：`r1_ablation_design.md`
数据：r1only×12 + r1removed×8（新跑，`experiments/runs_r1_ablation/`）+
baseline×20 / full skill×20（复用主实验池）。60 run 全部 PASS。

## 1. 四臂总表（均值；p 为 permutation 20k 次）

| 指标 | baseline (20) | full (20) | r1only (12) | r1removed (8) |
|---|---:|---:|---:|---:|
| 总 tokens | 184,245 | 149,092 (−19%**) | 171,385 (−7%, p=0.22) | 188,828 (+2.5%, p=0.59) |
| distinct reads | 8.6 | 4.9 (−43%***) | **5.2 (−40%, p=0.0036)** | 8.0 (−7%, p=0.38) |
| long outputs | 3.8 | 2.2 (−42%***) | 2.8 (−28%, p=0.054) | 3.4 (−11%, p=0.33) |
| turns | 11.4 | 9.9 (−13%, p=0.053) | 11.7 (+2%, p=0.61) | 11.4 (−1%, p=0.50) |
| fresh input | 17,191 | 14,068 (−18%*) | 14,625 (−15%, p=0.097) | 17,904 (+4%) |

关键两两检验：r1only vs full——reads p=0.83（无差异）、总量 p=0.12、
turns p=0.060；r1removed vs full——总量 **p=0.022**、reads **p=0.019**
（显著更差）；r1removed vs baseline——全指标无差异。

## 2. 判读

**必要性证实（最干净的结果）：R1-removed ≈ baseline。**只带 R2–R5 的
skill 在所有指标上与不带 skill 无差异，且显著差于 full skill。**没有
R1，整个 skill 等于没装。**R2–R5 单独不产生任何可测效应——包括 turns。

**充分性部分证实：R1-only 完整复现行为效应，但只回收约一半 token 效应。**
- 读取通道 100% 归 R1：r1only reads 5.2 ≈ full 4.9（p=0.83），单条规则
  文本（1.2k chars vs 全文 4.9k）就驱动全部读取纪律。
- token 缺口在 turns 通道：full 把 turns 压到 9.9，r1only（11.7）和
  r1removed（11.4）都没压。分层看 F3 最刺眼：r1only reads −40% 但
  turns 13.3，读取省的钱被 turn 结构成本（~14.8k/turn）吃回，总量
  182k ≈ baseline 180k。F1 上 r1only −15%（161k vs 189k）方向良好。

**turns 之谜——诚实报告三种解释：**
1. **协同效应**：turn 纪律只在全部规则同时在场时涌现（单独都不动，
   合体 −1.5 turn）；
2. **噪声**：full 的 turn 效应本来就边缘（20v20 时 p=0.053），且
   GLM-5.2 turn 方差是全项目最顽固的环境变量（8v8 时已证明爆炸两臂
   共有）；r1only n=12 的 F3 turn 均值被两个长 run 拉高。
3. 注入长度差（full 4.9k vs r1only 1.2k 常驻）方向相反（更长注入
   应该更贵），排除其为 r1only 劣势的解释。
数据无法在 1 和 2 之间裁决（需要 n≥20/臂 的 turn 专项检验）。

## 3. 结论落位（判读矩阵）

落在预注册矩阵第一、二分支之间，偏向第二分支的温和版：

> **R1 是必要且近乎充分的核心**：没有它 skill 无效（必要性，实验级
> 证据）；单独它复现全部行为效应与 F1 侧大部分 token 效应（充分性，
> 部分）。**原归因"效应全部来自 R1"修正为：读取通道效应全部来自
> R1（实验证实），full skill 相对 R1-only 的残余优势（~12%）坐在
> turn 通道上，其来源（规则协同 vs 采样噪声）未决。**

**发布建议随之更新**：不裁剪为单规则。R1-only 会丢掉约一半 token
效应（171k vs 149k）；R2–R5 虽单独无效应，但保留它们无成本（注入
差 ~0.7k/turn 常驻，被 cache 吸收）且可能承载协同。**发布物 = full
skill 不变，R1 标注为 core rule。**

## 4. 与既有证据的一致性

- 回归分解（R²=0.90）说"效应走读取通道"——与 ablation 一致：它测的
  是 full skill 的效应构成，其中读取通道确由 R1 驱动；回归无法看见
  "turns 本身被什么压低"，ablation 补上了这一层。
- F7 的 R4 行为效应（首 Edit 前 turns −30%）与"R2–R5 单独无效"不
  矛盾：F7 测的是 full skill（含 R1 协同），且其效应正是 turn 类。
- 批间漂移检查：r1only F1 均值 161k、r1removed F1 177k，均落在旧批
  baseline/full 的 F1 区间（143k–189k）内；F3 同理。无 >30% 漂移，
  合并有效。

## 5. 局限

1. r1only n=12 / r1removed n=8：等价性判断（r1only ≈ full）power 有限,
   "无差异"读作"未检出差异"；turns 之谜同样受限于 n。
2. 协同 vs 噪声未决——这是本 ablation 留下的唯一开放问题，需要
   turn 专项实验（n≥20/臂）才能收口，性价比低，不建议追。
3. 与主实验共享的所有局限（单模型、单 harness、F1/F3 任务面）。

## 6. 数据

`experiments/runs_r1_ablation/`（12 r1only + 8 r1removed + 1 smoke），
runner `experiments/run_r1_ablation.py`（规则文本运行时从 SKILL.md
逐字抽取，Workflow 节两臂均排除——其步骤内嵌 R3/R4 会污染臂设置）。
