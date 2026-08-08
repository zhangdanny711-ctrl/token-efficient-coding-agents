# Batching 指令 ablation 结果（n=12/臂）

日期：2026-08-06
设计：`reports/batching_ablation_design.md`。执行：`experiments/run_batching_ablation.py`，24 个全新 run（control 12 / treatment 12），F1/F3 各 6/臂，**逐 run C/T 交错**同批完成（无 API 漂移窗口），workspace 全部在项目树外，每 run 前污染预检通过。现有 benchmark 文件零改动。
数据归档：`experiments/runs_batching_ablation/`（24 run + 1 smoke）。
质量线：**24/24 PASS**。

## 一句话结论

**按预登记判定规则，batching 判定为"部分支持、效应不足"：turns↓、calls≈、density↑ 三个方向条件全部满足，fragmentation ratio 恰好过显著线（p=0.049），但 turns/density 的效应量太小（p=0.33/0.17），且 token 总量完全无差（p=0.49）——碎片化被指令小幅压低，但远不足以兑现 granularity 分析指出的 60%+ 理论空间。**

## Results — pooled（n=12/臂）

| 指标 | control mean (med) | treatment mean (med) | 方向 | 单侧 perm p |
|---|---:|---:|---|---:|
| **turns** | 11.50 (11.5) | 10.92 (10.0) | ↓ | 0.333 |
| **tool_calls** | 15.67 (15.5) | 16.67 (16.5) | ≈（略↑） | 0.486（双侧） |
| **density (calls/turn)** | 1.42 (1.5) | 1.56 (1.6) | ↑ | 0.166 |
| **fragmentation ratio** | 0.751 | 0.685 | ↓ | **0.049** |
| grand total | 187,313 (195,063) | 189,254 (191,795) | ≈ | 0.490 |
| cache_read | 167,808 | 168,939 | ≈ | 0.466 |
| fresh input | 17,507 | 17,933 | ≈ | 0.645 |
| distinct reads | 8.58 (8.0) | 9.08 (8.0) | ≈（略↑） | — |
| PASS | 12/12 | 12/12 | = | — |

## 预登记判定规则的执行

> Batching is supported only if: turns decrease AND total tool calls stay approximately unchanged AND calls_per_turn increases.

- turns：**方向满足**（11.50→10.92，中位 11.5→10.0），不显著（p=0.33）；
- tool_calls：**满足**（15.67→16.67，双侧 p=0.49，无显著变化）；
- density：**方向满足**（1.42→1.56，中位 1.5→1.6），不显著（p=0.17）；
- fragmentation ratio：0.751→0.685，**p=0.049**，且 treatment 分布右尾被削平（control 最差 0.92/0.94，treatment 封顶 0.76）。

**判定：机制方向一致成立（A/B 分离干净地落在 B 侧——同样的动作打包进更少 turn，而非少做动作），但幅度是"轻推"不是"矫正"。** 按决策规则的字面（只看方向）batching supported；按任何效应量标准 not supported。诚实的表述是:**指令有效但弱**。

## A vs B 路径分离（按要求单列）

| 证据 | 读数 | 指向 |
|---|---|---|
| tool_calls | 15.67→16.67（不降反微升） | **不是 A（少做事）** |
| distinct reads | 8.58→9.08（不降） | 不是 A;也无盲目预取（+0.5 在噪声内，中位持平 8.0） |
| density | 1.42→1.56 | B |
| fragmentation ratio | 0.751→0.685（唯一过线指标） | B |
| turns | −0.58 mean / −1.5 median | B（幅度小） |

**结论：treatment 的全部效应走 B 路径（打包），A 路径（压缩探索）零迹象——这正是设计想要的干预纯度。附带排除了伤害假设 H-harm（reads 未升、PASS 满）。**

**为什么 token 没省（重要机制细节）**:turns mean 只降 0.58,而 treatment 的 calls 略多、常驻 AGENTS.md 每 turn 多 ~60 tok,两相抵消,grand total 持平（187k vs 189k）。turn 边界成本 ≈16k/turn,要在总量上可见需要 turns 降 ≥2——目前中位数降了 1.5,均值只降 0.58,被 F3 的两个 treatment 爆炸 run（14/18 turns）拖住。

## Stratified

**F1（代码库探索型）——效应形态最好**：

| | C | T |
|---|---|---|
| turns | [7,9,9,12,13,13] mean 10.5 | [8,9,9,10,10,10] mean 9.3 |
| calls | 14.5 | 14.2 |
| density | 1.41 | 1.52 |
| grand | 196,149 | 188,280 |

T 的 turns 分布被**压缩**（全部 ≤10,control 有 12/13/13）——指令在 F1 上消除了爆炸尾部。calls 持平,教科书式 B 路径。

**F3（日志/数据侦查型）——效应失效**：

| | C | T |
|---|---|---|
| turns | mean 12.5 | mean 12.5（含 18-turn 爆炸） |
| calls | 16.8 | **19.2（+14%）** |
| density | 1.43 | 1.60 |
| grand | 178,477 | 190,228 |

T 在 F3 上密度升了但 calls 也涨了:模型把"batch"理解成"每 turn 多发",却没有减少 turn 总数——多打包的调用部分是额外侦查（reads 10.0→11.5）。碎片化 ratio 仍降（0.747→0.689）,但被 calls 膨胀抵消。**任务异质性明确:batching 指令对结构化代码探索（F1）有形态改善,对开放式数据侦查（F3）无效甚至轻微反效。**

## 结论与含义

1. **碎片化部分 prompt 可控**：fragmentation ratio 是唯一过线指标（p=0.049）,且路径分离干净（纯 B）。但可控幅度（−9% ratio, −5% turns）与理论空间（60%+）差一个数量级——**granularity 分析的"可合并"大多不是一句指令能兑现的,剩余碎片化是模型的深层生成习惯（逐步决策倾向）,不是缺提醒**。
2. **token 总量不受影响**（p=0.49）——按设计的解释矩阵,落在"turns↓密度↑calls≈但幅度不足"与"全指标≈"之间:机制存在,经济效果为零。**不建议把该指令并入 Skill v1.1**——60 tok/turn 的常驻成本换不来可测的 token 节省;它买到的只有轨迹形态的整洁。
3. 对研究叙事的贡献恰好补上最后一块:**五规则 skill 管得住"读什么"（reads −42%,已证）,管不住"分几步读"（本实验,弱效应）,更管不住 harness 的每步结构成本（84–94% cache 重发/全价重发）。prompt 干预的可达面被完整地画出来了**:内容维度可控、粒度维度弱可控、结构维度不可控。
4. F1/F3 的分层差异提示:若未来仍想追粒度,方向不是改指令文本,而是**任务类型选择性**（只对结构化探索任务注入）或 harness 侧（如 OpenCode 支持 parallel tool calls 的显式 API 约束）——均超出当前 prompt-only 范围。

## 与预算的对账

24 run 合计 ~4.5M tokens(设计估算 2.7M 偏低,因两臂均值都高于旧 baseline——同日新采样整体偏贵,交错设计正确地中和了该漂移,这也验证了哨兵机制的必要性:旧 8 个 control run 的 mean 179.6k vs 本批 control 187.3k,漂移 +4%,在容忍线内)。

## 局限

- n=12/臂对 turns/density 的小效应（d≈0.3–0.5）功效只有 ~30–40%——"效应存在但更小"未被排除;被排除的是设计预登记的中-强效应。
- fragmentation ratio 的 p=0.049 是边缘显著,且该指标与设计主指标高度相关,Holm 校正下不存活;将其解读为"方向证据"而非"确证"。
- 指令文本只测了一种表述;更强的措辞（如给出打包示例、数值目标"≤6 turns"）可能有更大效应——但那是新实验。
