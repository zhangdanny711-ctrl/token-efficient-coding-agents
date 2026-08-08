# 实验设计：batching 指令 prompt-ablation（设计文档，未执行）

日期：2026-08-06
状态：仅设计。未运行任何实验，未修改 SKILL.md、任务、runner、analyzer。
前置证据：`opencode_turn_granularity_analysis.md` — 可合并 turn 边界占全部 token 的 61–68%（上界族），碎片化是连续谱、未被任何现有指令约束、采样方差极大（同条件 0.93–2.0 调用/turn）。

## 1. 研究问题与假设

**RQ：交互碎片化是否 prompt 可控？**

- **H1**：批量指令降低 turns、提高调用密度（calls/turn）、降低总 token，PASS 不降。
- **H0**：碎片化是模型采样属性，指令无效（密度分布不变）。
- **H-harm**（需排除的伤害假设）：强行批量导致盲目预取——调用密度上升但 distinct reads 也上升（把"能一起发"理解成"多发"），或 PASS 下降（该看结果再决策的地方没看）。

## 2. 设计

### 2.1 两臂对照（不是三臂）

| 臂 | 注入 |
|---|---|
| **Control** | 当前 OpenCode baseline（无任何注入）——复用现有 8 个 clean run + 补跑至目标 n（交错哨兵校验漂移） |
| **Treatment** | workspace `AGENTS.md` 只含批量指令一段（下文），**不含 Skill v1 任何内容** |

批量指令文本（AGENTS.md 全文，即 treatment 的唯一变量）：

> Before acting, batch related information-gathering actions into the same turn whenever possible. Avoid splitting a single exploration objective across multiple turns when the required information can be collected together.

**为什么不做 baseline / v1 / v1+batching 三臂**：granularity 分析显示 Skill v1 与碎片化维度正交（两臂可合并 turn 数 6.9 vs 7.9，几乎无差）。先用最小两臂回答"prompt 能否触及该维度"这个是/否问题；若能，再做 v1+batching 的组合臂验证可加性——那是第二阶段，避免现在就花 3 臂的样本预算。

### 2.2 注入机制的说明（confound 预防）

Treatment 用与 skill arm 相同的 AGENTS.md 机制注入，但内容只有批量指令。这样"注入机制本身"（AGENTS.md 存在、常驻上下文 ~60 tokens）与 control 形成的差异极小；若担心 AGENTS.md 存在性本身有效应，可在分析时与 skill arm（AGENTS.md 存在但无批量指令）作三角对照——skill arm 的密度与 control 无差异这一已有事实，本身就是"AGENTS.md 存在性不影响密度"的证据。

### 2.3 任务与执行

- 任务：**F1 + F3**（与现有 16 run 同分布；不新建任务）。
- 环境：OpenCode 1.18.14、`zai-coding-plan/glm-5.2`、timeout 1200s、workspace 在项目树外（skill 自发现防护）、run 前 repo 污染检查——全部沿用。
- 执行方式：treatment 与 control 补跑**同日交错**（T,C,T,C…），避免 API 状态漂移成为臂间混杂。

### 2.4 指标（预登记）

主指标（按此顺序做多重比较校正，Holm）：
1. **turns**（main_turns）——单侧 Mann-Whitney，H1 预测下降；
2. **调用密度**（tool_calls / main_turns）——H1 预测上升；这是机制指标，若 turns 降了但密度没升，说明起效路径不是批量（要警惕，见混杂 §4.3）；
3. **fragmentation ratio**——用 granularity 分析的保守口径:可合并相邻 turn 对数 / tool-turns（离线从 transcript 计算，不改 analyzer——分析脚本作为独立文件新增）；
4. **grand total tokens**——单侧 MW。

次指标（不做检验，只报告方向）：distinct files read（**关键伤害监测**：若上升 = 盲目预取）、fresh input、PASS 率（硬性质量线:任一臂 <100% 即触发逐 run 审查）、verify.sh 通过外加轨迹人工抽查 2 run/臂（完成质量:修的是不是目标 bug、有无副作用编辑）。

## 3. 样本量估算

基于 control 侧现有参数（n=8）:turns mean 11.4, sd 3.5;密度 mean 1.38, sd 0.41;grand cv=0.30。

Mann-Whitney 单侧 α=0.05 的近似功效：

| 效应场景 | turns 降至 | Cohen d | n=8/臂 | n=10/臂 | n=12/臂 | n=16/臂 |
|---|---|---|---|---|---|---|
| 强（碎片化大半消除） | ~6.5 | 1.39 | 0.73 | 0.82 | 0.88 | 0.95 |
| 中（波次下限靠近一半） | ~8 | 0.96 | 0.52 | 0.60 | 0.67 | 0.78 |
| 弱 | ~9.5 | 0.54 | 0.26 | 0.30 | 0.34 | 0.42 |

**建议:n=12/臂（F1、F3 各 6）**。理由：
- 若指令真能压碎片化，从依赖结构看效应不会是弱档（正常密度 run 就在同分布里，指令只需把分布右移），中—强档在 n=12 有 67–88% 功效；
- control 已有 8 run 可复用 → 新跑 4 control（哨兵兼补样）+ 12 treatment = **16 个新 run**，按 F1/F3 均值 ~170k tokens/run 估计约 2.7M tokens 预算;
- 若 n=12 出零效应，弱效应未被排除，但"值得写进 skill 的效应量"（至少中档）已被排除——这就是决策需要的信息。
- turns 若如 H1 下降，密度（d 未知但同源）与 fragmentation ratio 大概率同向;grand total 在 cv=0.30 下 n=12 只对大效应敏感，预登记为方向性指标，不以它判决。

## 4. 混杂因素与对策

**4.1 API/模型漂移（最大风险）**：treatment 全是新 run，control 8 个是旧 run。对策:补 4 个 control 与 treatment 同日交错跑;新旧 control 先做同臂对比（MW 双侧），若中位差 >30% 则弃用旧 run、当日重跑全部 control（预算翻倍是可接受的坏情形）。

**4.2 AGENTS.md 存在性效应**：treatment 的注入载体本身可能改变行为（不是指令内容起效）。对策:上文三角对照——skill arm（同载体、无批量指令）密度与 control 无差是既有证据;若结果可疑再加"AGENTS.md 装无关内容"的安慰剂臂（不预先跑）。

**4.3 效应路径混淆**：指令可能通过"少做事"而非"合并做事"降 turns——表现为 calls 总数下降、密度不升、reads 下降。这与批量假设不同（批量 = calls 不变,turns 变少）。对策：密度与 calls 总数一起报告;预登记判别式——**批量生效 = turns↓ 且 calls≈ 且密度↑**;"少做事"路径若出现,是另一个（也有价值的）发现,但不支持 H1。

**4.4 任务异质性**：F1（宽代码库探索）与 F3（日志/数据侦查）的碎片化形态不同。对策:分任务分层报告主指标;样本平均分配（6+6）;不做任务间合并检验（只报 pooled 方向）。

**4.5 天花板效应**：control 分布里已有高密度 run（2.0 calls/turn）。若某次采样 control 恰好偏高密度，臂间差被压缩——这是随机化要吃的噪声,n=12 的功效表已含此项（sd 取自含高密度 run 的样本）。

**4.6 质量渠道**：批量预取可能让模型带着更多上下文做编辑,PASS 不降但修复质量变化（如顺手改别处）。对策:verify.sh 之外,人工抽查每臂 2 个 run 的 edit diff。

## 5. 预登记的结果解释矩阵

| 结果 | 结论 |
|---|---|
| turns↓ 密度↑ calls≈ reads≈ PASS 8/8 | **碎片化 prompt 可控**——收益上限全场最大的维度被打开;下一步把批量指令并入 Skill v1.1 做组合臂 |
| turns↓ 密度≈ calls↓ reads↓ | 指令通过压缩探索起效（与 R1 同路径）,批量假设不支持;碎片化维度仍未被触及 |
| 全指标 ≈ | 中档以上效应被排除 → 碎片化主要是采样/模型属性,prompt 不可达;转向 harness 侧结论（成本函数 × 行为的乘积论）,Skill v1 保持原样 |
| reads↑ 或 PASS<8/8 | 批量指令有害（盲目预取/过早行动）→ 记录为"粒度指令的安全边界",拒绝该干预 |

四个分支都可写进最终报告,无浪费分支。

## 6. 执行清单（批准后）

1. 新增 `run_opencode_experiment.py` 的调用方式**不改文件**:treatment 不能用 `--condition skill`（那会注入 SKILL.md）。两个选项,批准时二选一:
   a. 新增独立小 runner `run_batching_ablation.py`（复制 runner、AGENTS.md 内容换成批量指令,~30 行差异）——不动现有文件,推荐;
   b. 给现有 runner 加 `--agents-md <path>` 参数——更通用但修改了 runner,违背"不改 benchmark 文件"约束。
2. fragmentation ratio 计算脚本独立新增（复用 granularity 分析代码）。
3. 跑序:C,T,C,T…同日完成;先 4 个 control 哨兵。
4. 中止线:任何 run 超 timeout、或前 4 个 treatment PASS<3 → 停,报告后再议。

——设计完。等待批准执行,或对样本量/臂结构/指令文本的修改意见。
