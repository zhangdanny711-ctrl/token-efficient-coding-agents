# Skill v1 跨环境对比分析：Claude Code + Sonnet vs OpenCode + GLM-5.2

日期：2026-08-06
性质：基于已有 run 数据的分析，未运行新实验，未修改任何现有文件。
数据来源：
- Claude Code arm：validation v2（5 任务 × 2 条件 × 2 trials，`experiments/runs/t*_v*`、`smoke_*`）+ 校准试点 F1/F3（baseline ×2，`runs/f1_*_p*`、`f3_*_p*`）；分析见 `reports/calibration_analysis.md`。
- OpenCode arm：smoke test ×1 per condition（`runs/oc_smoke_*_oc1`）；见 `reports/opencode_smoke_result.md`。

**样本量警告**：OpenCode 侧目前只有 tasks/smoke 各 1 run。本报告中所有 OpenCode 结论均为 n=1 观察，只能提出假设、不能检验假设。Claude Code 侧为 n=2/条件 × 5 任务 + 4 个校准 baseline，结论较稳。

---

## 1. 实验结果对比

### 1.1 主表

任务成功率：**两个环境、两个条件全部 PASS**（Claude Code 14/14；OpenCode 2/2）。质量维度上没有任何 arm 出现退化。

Claude Code + claude-sonnet-5（validation v2 平均，n=2/格；smoke 为 n=1）：

| task | condition | grand total | fresh input | output | cache read | cache write | tool calls |
|---|---|---:|---:|---:|---:|---:|---:|
| smoke | baseline | 156,097 | 10 | 516 | 154,519 | 1,052 | 4 |
| smoke | skill | 195,557 | 11 | 669 | 180,442 | 14,435 | 5 |
| t1a–t3a 5 任务均值 | baseline | ~178k | ~11 | ~1,000 | ~165k | ~15k | 4–9 |
| t1a–t3a 5 任务均值 | skill | ~230k | ~13 | ~1,100 | ~215k | ~16k | 5–10 |
| F1/F3 校准（baseline only） | baseline | 243k–308k | 14–18 | ~1,550 | 204k–289k | 17k–37k | 6–8 |

OpenCode + GLM-5.2（tasks/smoke，n=1/条件）：

| condition | grand total | fresh input | output | cache read | cache write | tool calls |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 40,833 | 7,385 | 360 | 33,088 | 0 | 6 |
| skill | 55,143 | 3,099 | 332 | 51,712 | 0 | 7 |

**跨 arm 绝对值不可比**（预登记过的告诫，此处再次生效）：模型不同、系统提示不同（Claude Code 每 turn cache 体量 ~15–30k，OpenCode 首 turn 仅 ~7.4k）、缓存计价字段语义不同（Z.ai `cache_write` 恒 0，Claude Code 有显著 write）、skill 注入协议不同（见 §1.4）。有意义的比较只有 **arm 内 skill/baseline 相对差** 和 **行为指标**。

### 1.2 skill 是否改变了 agent 行为？

**是，两个环境都有可观察的行为改变**（observation）：

- Claude Code（validation v2）：t2a Read 4→2、t2b Read 5→3（Rule 1/2 方向的读取减少）；轨迹里出现对规则的显式引用。
- OpenCode（n=1）：baseline 首动作是 `bash ls+find` 宽扫 + 读 3 个文件；skill run 首动作变为两次 `glob` 定向搜索、只读 2 个文件，fresh input 从 7,385 降到 3,099（−58%），assistant 文本 173→96 chars。这是 Rule 1（先搜后读）与 Rule 5（输出纪律）的教科书式执行。

### 1.3 skill 是否降低了 token？

**否，两个环境的 grand total 都上升**（observation）：

| 环境 | baseline → skill | Δ | 相对 |
|---|---|---:|---:|
| Claude Code smoke | 156,097 → 195,557 | +39,460 | +25% |
| Claude Code validation 均值 | ~178k → ~230k | +37k~+80k | +21%~+42% |
| OpenCode smoke | 40,833 → 55,143 | +14,310 | +35% |

即：**skill 改变了行为方向（正确方向），但被结构性开销反噬**。两个环境中被压低的量（fresh input、读取数、文本量）都是小桶；被推高的量（turn 数 → cache re-read）是大桶。

### 1.4 overhead 来自哪里？——两个环境的开销机制不同

| | Claude Code | OpenCode |
|---|---|---|
| 注入机制 | `.claude/skills/` + prompt 显式点名 | workspace `AGENTS.md`，无提示词差异 |
| 开销形态 | **一次性大额**：+1 个"读 SKILL.md"turn ≈ +40k（整段历史以缓存价重发一轮） | **持续小额**：~1k tokens 常驻上下文 × 每 turn 重发；本次另 +1 turn（+18.6k cache read） |
| 本次实测 Δ | +39k（smoke） | +14.3k（smoke，n=1） |

OpenCode 的 +1 turn 需要拆开（observation）：skill run 的第 7 个 tool call 是 `pytest` 失败后带 `PYTHONPATH=.` 重试——这是环境毛刺引起的 evidence-driven 重试，与 skill 无因果。剔除该 turn 的话两条轨迹 turn 数相同，Δ 会明显小于 14.3k。**hypothesis**：OpenCode 的 AGENTS.md 注入开销结构上低于 Claude Code 的 skill-invocation 开销（无额外 turn、无 40k 级重发），单 turn 边际成本 ~1k × turns。这在正式 runs 中可以直接检验（比较两条件 turn 数相同的 run 对）。

---

## 2. 为什么两个环境中 skill 都没有明显收益？

先把两种解释分开：

- **解释 A（"skill 没有效果"）**：规则没有被执行，行为无变化 → §1.2 已证伪。skill 在两个环境里都真实改变了行为。
- **解释 B（"baseline 太强，marginal benefit 不足"）**：规则被执行了，但 baseline 已经把可回收浪费吃掉了大半，剩余空间 < 固定开销。

现有证据支持解释 B，且两个环境的支持强度不同：

### 2.1 baseline 是否已具备 token-efficient 行为？

- **Claude Code：是，且非常强**（calibration_analysis.md 的核心发现）。F1 只读 2 个文件、用 grep 跨越三层调用链；F3 从未运行 25k-char 日志命令、每条命令自带 tail 截断。search_before_read_rate 全部 1.0，repeated_reads 全部 0。五条规则中 R1/R4/R5 的行为在 baseline 里已是默认值。
- **OpenCode + GLM-5.2：部分具备，纪律弱一档**（n=1 observation）。baseline 也是先搜索（sbr=1.0，`find` 计为搜索），但首动作是 `ls -la && find` 宽扫而非定向 grep，且读了 3 个文件（含测试 + 实现 + 第三个文件），Claude Code smoke baseline 只读 1 个。fresh input 7,385 vs skill 的 3,099 说明 baseline 每 turn 收进了更多 observation。**hypothesis**：GLM-5.2/OpenCode 的 baseline 纪律低于 Sonnet/Claude Code，留有真实可回收空间——这正是 smoke 中 skill 能把 fresh input 压掉 58% 的原因。

### 2.2 固定开销 vs 可回收浪费

Claude Code：开销 ≈ +40k/task，校准显示目标浪费 ≈ 0 → 比值 8:1 净负（已定论）。
OpenCode：开销 ≈ 每 turn ~1k + 可能的额外 turn；可回收量未知（smoke 任务本身只有 ~40k 总量，没有浪费放大器）。**当前无法判定**，需要在放大器任务上测。

### 2.3 任务规模是否不足？

是（两个环境同理，observation）：smoke/validation 任务 4–10 个 tool calls 就完成，trajectories 里没有 R2（≥3 文件探索）和 R3（无进展循环）的触发条件。Claude Code 侧专门为此造了 F1–F8 放大器任务，但校准显示即使放大器也没在 *Claude Code baseline* 上诱发浪费。**关键未知**：同样的放大器任务在 OpenCode baseline 上是否诱发浪费——这是决定 OpenCode benchmark 是否值得跑的核心问题，且一次校准（F1/F3 baseline ×2）就能回答。

### 2.4 task design 是否没有触发规则？

部分成立，但要与 §2.3 区分：F1 的失败测试名泄露了 bug 位置、F3 的 task.md 提供了绕过长日志的 pytest 捷径（calibration_analysis.md 的 verifiability-vs-inducement 冲突）。这些设计缺陷对任何 agent 都会削弱诱发力。若 OpenCode 校准也零浪费，需先排除"任务给了逃生门"这一混杂，再归因于"baseline 太强"。

**小结**：Claude Code 侧的结论是"baseline 太强 + 结构成本占 84–94%，prompt 级规则无从下手"。OpenCode 侧目前只能说"行为可被改变、开销机制更便宜、baseline 疑似更松"——三者都指向值得测，但都未检验。

---

## 3. Rule-level transfer analysis

| Rule | Claude Code 支持/触发 | OpenCode 支持/触发 | harness 依赖 | 需要改 skill 吗 |
|---|---|---|---|---|
| R1 最小上下文获取 | 支持（Grep/Glob/Read offset+limit）；baseline 已自发执行，skill 无增量 | 支持（grep/glob/read 同能力）；**skill 触发了行为改变**（glob-first、少读 1 文件、fresh input −58%） | 低——两边工具等价 | 文字级：无需。工具名大小写不同但模型能对应 |
| R2 探索委托 | 支持（Task/Explore subagent）；**从未触发**（任务太小，全部 Task=0） | **机制不同**：无 Claude Code 式 Task 工具语义；OpenCode 有自己的 agent/subagent 体系，但 (a) 未在轨迹中出现，(b) 流中无 `parent_tool_use_id` 类归因字段，**子代理 token 无法单独核算**（analyzer 的 `tokens.subagent` 恒 0） | **高——本条规则依赖特定 harness 能力** | **是**。两个选择：改写为 OpenCode 的委托原语（若其 task/agent 机制在 run 模式可用且可观测），或在 OpenCode arm 显式移除 R2 并预登记为 4 规则版。保留一条不可执行的规则会引入无法测量的 dead instruction |
| R3 进展账本/止损 | 模型级行为，harness 无关；**从未触发**（无循环诱饵任务跑过 skill arm） | 同为模型级；未触发。smoke skill run 的 pytest→PYTHONPATH 重试是 evidence-driven（新错误、新假设），符合 R3 精神但非触发 | 无 | 否 |
| R4 自适应投入 | 模型级；baseline 已默认 locate→fix→verify 直行，无增量 | 模型级；baseline 同样直行（6 calls 完成）。**未知**：GLM-5.2 在大任务上是否会过度规划——Claude Code 侧此规则无空间的结论不能外推 | 无 | 否 |
| R5 输出纪律 | 支持（Edit 工具、文本量可测）；baseline 已简洁（117–692 chars） | 支持（edit 工具）；skill run 文本 173→96 chars，方向正确但基数已小 | 低 | 否 |

**核心迁移结论**：五条规则中四条（R1/R3/R4/R5）是模型级或双方等价工具级的，文字不改即可跨 agent 使用；**R2 是唯一硬绑定 harness 能力的规则**，且在 OpenCode 下既不可同法执行也不可测量（无子代理归因）。Skill v1 若要作为"跨 agent policy"发布，R2 必须重写为能力探测式（"若你的环境提供委托/子代理机制则……否则跳过"）或按 harness 出变体，并在实验设计里把 R2 从 OpenCode arm 的预登记指标中剔除。

另一个测量层差异需要预登记：OpenCode 的 `output_tokens` 含折叠的 reasoning tokens、`cache_write` 恒 0、订阅制下 `cost=0` —— R5 的 output 指标和任何美元口径指标在两 arm 间不同义。

---

## 4. 研究含义

### 4.1 研究问题是否应该重构？

支持重构（基于两组 observation 的合取）：

- 原问题"token-efficient skill 是否减少 token"在 Claude Code 上已有干净的负结果，且负因是 **baseline 内化 + 结构成本占绝对多数**，不是 skill 写得差。
- 同一份 skill 在 OpenCode 上产生了 Claude Code 上看不到的行为增量（baseline 有松弛可收）。同一 policy、不同 harness、不同边际效果——这本身就是比"skill 有没有用"更有信息量的现象。

重构后的问题 **"token-efficient policies 的有效性是否随 coding agent/harness 而异"** 有三个优点：(1) 它把已有的负结果从"失败"变为一个数据点（强 harness 端）；(2) 它可检验——OpenCode arm 就是第二个数据点；(3) 它与文献对齐：token 浪费证据均来自 Mini-SWE-Agent/OpenHands/ChatDev 等弱 scaffold（calibration_analysis.md §4），我们的贡献可以是"浪费与其可回收性是 harness 属性，而非 LLM agent 的普遍属性"。

### 4.2 如果 agent 已内置类似优化，skill 的价值在哪里？

Hypothesis（不是本数据能证明的）：此时 skill 的价值不在 token delta，而在：
- **可移植性/保险**：同一 policy 在换模型、换 harness、模型退化（长上下文后期纪律衰减)时提供下限保障；
- **显性化**：把隐性 harness 行为变成可审计的规则（工程价值而非实验效应）；
- 但在强 harness 上它是**纯成本**（+40k/task），"没有坏处"并不成立——这点 Claude Code 数据已经证明。

### 4.3 如果弱 harness 存在更多浪费，skill 是否更有价值？

这是当前最值得检验的 hypothesis，且 smoke 给了方向性支持（fresh input −58%）但同时暴露了约束：**skill 收益的上限受"开销所在的桶"限制**。OpenCode 下开销桶（每 turn ~1k 常驻 + cache 重发）与收益桶（observation 减量 → 后续每 turn 少重发）是同一个桶，不像 Claude Code 那样收益桶几乎是空的。若 GLM-5.2 baseline 在放大器任务上真的乱读乱试，1k/turn 的保费对上几十 k 的可回收浪费，净收益为正是可能的——这正是校准要回答的。

---

## 5. 下一步实验建议

按优先级：

1. **先跑 OpenCode 校准，不要直接跑正式 benchmark**（复用 Claude Code 侧验证过的早停协议）：F1 + F3 baseline ×2 on OpenCode + GLM-5.2，预登记通过线（建议：出现 ≥1 次目标浪费行为——重复读、未截断长输出、宽扫≥3 文件——且估算可回收量 ≥ 2× 每任务 skill 开销）。4 个 run 即可决定整个 arm 的去留，成本极低。**跑之前必须完成全部冻结任务 repo 的污染审计**（smoke repo 已发现并修复一次污染；F1/F3 repo 未复查）。
2. **task design 微调（若校准前有余力）**：修复已知的两个逃生门（F1 失败测试名泄露位置、F3 的 pytest 捷径），否则"零浪费"结果无法在"baseline 强"与"任务放水"之间归因。这属于修任务缺陷，不是为 OpenCode 定制。
3. **Skill v1 出 OpenCode 变体，只动 R2**：改写或移除探索委托规则并预登记该差异；其余四条保持逐字一致，否则跨 arm 的 rule-level 比较失效。
4. **把 agent/harness 正式提升为实验变量**：设计从"1 harness × 2 条件"变为"2 harness × 2 条件"的 2×2；主对比是 arm 内 skill 效应，跨 arm 只比较相对量（Δ%/行为指标），绝对 token 不比。预登记两 arm 的度量不等价处：`output_tokens` 含 reasoning、`cache_write=0`、`cost=0`、无 subagent 归因。
5. **OpenCode skill 条件补一个协议对齐检查**：当前 OpenCode arm 无"显式点名 skill"的 prompt 行（AGENTS.md 常驻），与 Claude Code arm 的显式调用不同。建议保持现状（AGENTS.md 是 OpenCode 官方机制，改 prompt 反而引入第二个变量），但在报告里恒定标注该协议差异。
6. **样本量**：OpenCode 侧任何行为结论目前都建立在 n=1 上；校准阶段就应 ×2，正式阶段沿用现有 per-task ×2 设计。

**如果校准显示 OpenCode baseline 也零浪费**：研究以"跨 harness 的双负结果 + baseline 内化是行业趋势"收尾，仍是干净的可发表叙事；不建议再追第三个 harness，边际信息量递减。
