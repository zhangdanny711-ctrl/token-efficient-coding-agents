# OpenCode skill arm 校准：AGENTS.md 注入 vs baseline（F1/F3 ×2）

日期：2026-08-06
范围：仅 F1+F3 skill ×2（共 4 run），未跑 F2–F8，未修改任务/skill/runner。
环境：与 baseline 校准完全一致 —— OpenCode 1.18.14 + `zai-coding-plan/glm-5.2`，同任务同 repo，`--runs-dir /tmp/oc_skill_runs`（项目树外，防 skill 自发现污染），timeout 1200s。
Skill 注入：SKILL.md 正文（去 frontmatter）写入 workspace `AGENTS.md`；prompt 两条件相同。注入已核实（workspace 中 AGENTS.md 存在，轨迹行为符合规则）。
数据：`runs/oc_*_skill_occlean{1,2}`（本批）vs `runs/oc_*_baseline_occlean{1,2}`（上批）。

## Results

8/8 PASS（两条件各 4/4，质量无退化）。

### 主对比表（校准预登记的六个指标）

每格为 [run1, run2]，mean。**n=2/格，方差大，均值仅作方向参考。**

| 指标 | F1 baseline | F1 skill | F3 baseline | F3 skill | pooled baseline | pooled skill | Δ pooled |
|---|---|---|---|---|---:|---:|---:|
| **distinct files read** | [4, 9] 6.5 | [5, 3] 4.0 | [10, 15] 12.5 | [5, 8] 6.5 | 9.5 | 5.2 | **−45%** |
| **fresh input tokens** | [16.1k, 28.9k] 22.5k | [22.9k, 17.1k] 20.0k | [9.1k, 15.5k] 12.3k | [8.5k, 13.9k] 11.2k | 17.4k | 15.6k | −11% |
| **total tokens (grand)** | [136.8k, 199.7k] 168.2k | [245.9k, 129.4k] 187.7k | [173.6k, 160.1k] 166.9k | [115.3k, 211.6k] 163.4k | 167.5k | 175.6k | **+5%（噪声内）** |
| **tool calls** | [11, 15] 13.0 | [13, 7] 10.0 | [15, 20] 17.5 | [13, 19] 16.0 | 15.2 | 13.0 | −15% |
| **long outputs (>4k chars)** | [4, 7] 5.5 | [4, 4] 4.0 | [2, 4] 3.0 | [1, 2] 1.5 | 4.2 | 2.8 | −35% |
| **PASS rate** | 2/2 | 2/2 | 2/2 | 2/2 | 4/4 | 4/4 | 0 |

辅助观察：工具输出总量（观察进入上下文的 chars）——F1 53k/103k → 57k/57k；F3 21k/36k → **17k/25k**。skill 消除了 baseline 的"宽读取尾部"（103k 那种 run 不再出现），F3 中位数也下移。turns：pooled 10.8 → 11.2（基本持平）。重复读取/重复动作两条件恒为 0。

## 分析

### 1. 行为指标全面向好，方向与假设一致（observation）

校准发现的目标浪费——宽读取——被 skill 压缩了：distinct reads −45%（9.5→5.2），且不是均值游戏：**skill 的 4 个 run 里没有一个超过 8 个文件，而 baseline 有 10 和 15 的 run**；F3 baseline 最差 run 枚举了 4 个目录 + 3 个测试文件 + 无关邻居模块，skill 的 F3 轨迹则是 grep LUX-5001 → 定位 rules/numbers → 修——假设驱动而非枚举。long outputs −35%，tool calls −15%，全部方向正确。行为效应在 OpenCode + GLM-5.2 上是真实的，这一点与 Claude Code 校准（baseline 无此浪费、skill 无从改善）形成明确对照。

### 2. 但 total tokens 没有跟着降（observation + 机制解释）

pooled grand total +5%，在 ±37% 的 run 间方差里是噪声。为什么读取减半而总量持平？F1 skill occlean1（245.9k，最贵 run）的逐 turn 分解给出答案：

- 该 run 只读了 5 个文件（行为达标），但走了 **14 turns**（baseline 8–9），修复后跑了 4 次全量 pytest；
- OpenCode 的 cache read 逐 turn 线性累积（2.7k → 25k），**每多 1 turn，此前全部历史再重发一次**——14 turns 的累计 cache read 220.9k，比 8-turn 的 baseline occlean1（118.8k）多出 102k，把省下的读取全部吃掉还有余；
- 同任务的 skill occlean2 只走 7 calls / 8 turns，129.4k——**比两个 baseline run 都便宜**。F3 skill occlean1 同理（115.3k，比 baseline 最好 run 还低 28%）。

即：**token 总量的主导变量是 turns 数，不是读取宽度**；skill 有效压了读取（每 turn 摄入量），但没有约束 turn 数——而 GLM-5.2 的 turn 数本身方差极大（同条件同任务 8 vs 14）。skill 4 个 run 里最好的两个（129k, 115k）显示了"读取纪律 + 少 turns"同时达成时的收益下限；最差的 run（246k）显示了 turns 失控时读取纪律救不了总量。

### 3. 对照六指标的判定

| 预登记指标 | 结果 | 判定 |
|---|---|---|
| distinct files read | 9.5 → 5.2，无 skill run 超过 baseline 中位 | **改善，且一致** |
| fresh input | −11%，方向对但弱（F1 被 246k run 拉平） | 弱改善 |
| total tokens | +5%，噪声内 | **无改善** |
| tool calls | −15% | 改善 |
| long outputs | −35% | 改善 |
| PASS rate | 4/4 = 4/4 | 持平（必要条件满足） |

### 4. 与 Claude Code 的最终对照（研究叙事的核心数据点）

| | Claude Code + Sonnet | OpenCode + GLM-5.2 |
|---|---|---|
| baseline 有无目标浪费 | 无（零，早停） | 有（宽读取 4/4） |
| skill 行为效应 | 无从发挥（t2a/t2b 有轻微读取减少） | **明确**（reads −45%，long outputs −35%） |
| skill token 效应 | **净负**（+21~42%，固定 +40k/task 调用开销） | **中性**（+5%，AGENTS.md 无调用开销，但 turns 未受控） |
| 剩余瓶颈 | 结构成本（84–94% cache 重发）prompt 不可触 | turn 数方差（同条件 8 vs 14 turns）主导总量 |

"policy 有效性随 harness 而异"得到两个方向的支持：强 harness 上 skill 是纯开销；弱 harness 上 skill 改变行为但收益被它未覆盖的维度（turn 控制）截断。

## 结论与建议（未执行，等指示）

1. **8-run 门槛的判定：行为效应确认，token 效应未确认。** 若研究问题保持"减 token"，当前 skill 在 OpenCode 上是中性的；若按已重构的问题（"policy 行为效应是否随 harness 而异"），F1+F3 已给出干净的阳性对照，**且 n=2 的方差提示任何 token 结论都需要 ≥4 runs/格**。
2. 三个可选方向（按信息量/成本比排序）：
   a. **加 n**：F1+F3 各补 2 run（8 个新 run），把 token 效应从噪声里捞出来或证实为零——最便宜，不改任何东西;
   b. **Skill v1.1 假设**（需修改 skill，未做）：数据指出缺的是 turn 纪律（"合并验证步骤、修复后一次全量测试即收尾"）——R4 现文只说"cheapest first"，没说"不要重复验证"；
   c. 建 F2/F4–F8 前先解决 a 或 b，否则 8 任务只会复制同一个"行为改善、token 持平"模式。
3. 工程注记：本批 4 run 已归档 `runs/`；`/tmp/oc_skill_runs` 已清理；所有 run 用项目树外 workspace（skill 自发现防护）执行，轨迹中无 `skill` 工具调用（污染防护生效）。

## 局限

- n=2/格；F1 skill 两 run 相差 1.9 倍，均值不稳定。所有 Δ% 是方向参考，不是效应量估计。
- skill run 间的 turns 方差（8 vs 14）没有已知协变量可解释（同 prompt 同 repo 同模型），可能就是 GLM-5.2 的采样方差——加 n 是唯一手段。
- AGENTS.md 为常驻注入，与 Claude Code arm 的显式调用协议不同（此前已预登记），跨 harness 只比行为方向，不比绝对量。

---

# 附录（同日补跑）：skill arm 加 n 至 4/任务 —— token effect 复检

补跑 F1+F3 skill ×2（`occlean3/4`，条件与前完全一致，未改 skill/任务）。skill 共 n=8，baseline n=4。8/8 累计 12/12 PASS。

## 合并结果

| | baseline (n=4) | skill (n=8) |
|---|---:|---:|
| grand total mean | 167,542 (sd 26k) | 159,265 (sd 52k) |
| grand total **median** | 166,852 | **128,498** |
| range | 137k–200k | 115k–246k |
| distinct reads mean | 9.5 | 5.0 |
| fresh input mean | 17,413 | 14,201 |
| tool calls mean | 15.2 | 12.8 |
| long outputs mean | 4.2 | 2.2 |
| P(skill run < baseline run) | — | 0.62 |

新 4 个 run 里 3 个落在 116k–128k 低位，1 个（F3 occlean4，12 turns）202k。

## Token effect 的判定：存在，但是条件性的（双峰）

skill 的 8 个 run 按 turns 干净地分成两簇：

| 簇 | runs | grand total | vs baseline mean |
|---|---|---|---|
| turns ≤ 10（5/8） | 129k, 126k, 116k, 115k, 128k | **mean 122,891** | **−27%** |
| turns > 10（3/8） | 246k, 212k, 202k | mean 219,888 | +31% |

- 全部 12 个 clean run 上 turns 与 grand total 的相关 r=0.717；两条件的**每 turn 成本**几乎相同（baseline 16.5k vs skill 15.2k/turn）——证实总量 ≈ turn 数 × 结构常数，skill 压的是读取（行为指标全面改善且在 n=8 下保持：reads 9.5→5.0），turn 数不受 prompt 规则控制。
- 解释（hypothesis→现在有 8 点支撑）：**当 GLM-5.2 采样出正常长度的轨迹（≤10 turns，8 个 skill run 中 5 个）时，skill 带来实打实的 −27%；当它采样出长轨迹（3/8）时，行为纪律救不了结构性重发**。均值 −5% 是这两簇的加权假象，中位数 −23% 更接近典型情形。
- 用统计语言：token effect 方向为负（省），中位效应约 −23%，但分布重尾右偏，n=8 尚不足以给出稳健区间；行为效应（reads −47%）则在所有 8 个 run 上一致。

## 更新后的结论

1. **Token effect：确认存在（条件性）**——中位 −23%，由读取纪律驱动；上界被 turn 数采样方差截断。"skill 在弱 harness 上净中性"的前一版结论修正为"**净正（典型情形），重尾风险来自 turn 失控**"。
2. Skill v1.1 的假设进一步聚焦：只需补 turn 纪律（修复后一次全量验证收尾、合并侦查命令），5/8 的低簇会变成 8/8——这是当前数据指出的最大单一杠杆（每消除一个长轨迹 run 省约 90k）。
3. F2/F4–F8 建造决策现在有依据：行为效应稳定 + token 效应中位数为负 → 扩任务集能回答"该效应是否泛化"，值得建；但建议先做 v1.1（改动一条规则文本）再全量跑，避免 8 任务 × 重尾方差需要过大的 n。

---

# 附录 2（同日）：baseline 补至 n=8 —— 公平 8v8 对比与长轨迹归因

补跑 baseline F1+F3 ×2（`occlean3/4`，一切与前批一致，未改 skill/任务/runner/analyzer）。两臂各 n=8，16/16 PASS。

## 8v8 主表

| | baseline (n=8) | skill (n=8) | perm p (one-sided) |
|---|---:|---:|---:|
| grand total mean | 179,644 (sd 54k) | 159,265 (sd 52k) | — |
| grand total median | 173,714 | 128,498 | p=0.221 |
| range | 98k–276k | 115k–246k | |
| **distinct reads** mean/med | 8.6 / 8.5 | 5.0 / 5.0 | **p=0.012** |
| **long outputs** mean | 3.9 | 2.2 | **p=0.036** |
| tool calls mean | 14.6 | 12.8 | p=0.109 |
| fresh input mean | 16,717 | 14,201 | p=0.191 |
| turns mean/med | 11.4 / 10.5 | 10.4 / 9.5 | p=0.260 |
| turns>10 比例 | **4/8** | 3/8 | 无差异 |
| PASS | 8/8 | 8/8 | |

新 baseline run 揭示了此前 n=4 低估的方差：97.9k–275.9k（×2.8），其中 275.9k 的 run 走了 15 turns、修复后跑了 4 轮测试——**与 skill arm 的长轨迹形态完全相同**。

## 长轨迹归因：是 baseline 固有方差，不是 skill 特异

三条独立证据，方向一致：

1. **爆炸率**：baseline 4/8 vs skill 3/8——baseline 反而更高。turn 失控与 skill 无关联（n=16 下无任何检验能区分）。
2. **每 turn 成本**：baseline 16.1k vs skill 15.2k——两臂结构成本相同，turn 爆炸对两臂的伤害是同一常数。
3. **turns↔grand 相关在合并 16 run 上升到 r=0.814**——turn 数是两臂共同的总量主导变量，属于 GLM-5.2（+此 harness）的采样属性。

**结论（数据支持）**：附录 1 中"skill 双峰"的读法不成立——双峰是 *环境* 的，两臂都双峰。skill 既不引起也不预防 turn 爆炸。

## 分层对比（描述性，事后分析，供机制理解，不作检验用）

| turns 层 | baseline | skill | Δ |
|---|---|---|---:|
| ≤10（正常轨迹） | 148,632 (n=4) | 122,891 (n=5) | **−17%** |
| >10（爆炸轨迹） | 210,656 (n=4) | 219,888 (n=3) | +4% |

在 turn 数相近的正常轨迹内，skill 的读取纪律转化为 −17% 总量；在爆炸轨迹内无差异（重发成本淹没读取节省）。与"skill 控制每 turn 摄入、不控制 turn 数"的机制完全一致。

## 8v8 后的证据等级更新

- **数据支持**：reads −42%（p=0.012）、long outputs −44%（p=0.036）、质量不降（16/16）、turn 爆炸为环境固有方差（4/8 vs 3/8）、总量由 turns 主导（r=0.814）。
- **方向一致但未过线**：grand total（median −26%，p=0.221）——重尾下 n=8/臂检验力不足；观察到的中位差如为真，需要约 n≥15/臂才可靠越过 0.05（粗略功效估算）。
- **不再成立**：附录 1 的"token effect 存在（条件性）"表述过强——正确表述为"**正常轨迹层内 −17%（描述性）；全样本中位 −26% 但 p=0.221**"。
- v1.1 的动机重新评估：turn 爆炸既然是两臂共有的环境属性，**给 skill 加 turn 规则的预期收益同样适用于说明它对 baseline 也可能有效**——若做 ablation，它检验的不是"修 skill 的缺陷"而是"prompt 规则能否压制采样性 turn 爆炸"。（按指示，此处不提出修改方案。）

---

# 附录 3（同日）：skill 补至 n=20，20v20 终检验 —— token 效应过显著线

skill arm 补跑 F1/F3 各 ×6（occlean5–10，协议不变），12/12 PASS。baseline 池 = 8 个 clean baseline + 12 个 batching-ablation control（协议同为无注入 baseline；两批均值 179.6k / 187.3k，差 4%，合并合法）。**两臂各 n=20，40/40 PASS。**

## 20v20 主结果（单侧 permutation，100k 次）

| 指标 | baseline (n=20) | skill (n=20) | Δ | p |
|---|---:|---:|---:|---:|
| **grand total** | 184,245（中位 187,298） | 149,092（中位 130,106） | **−19.1%** | **0.0094** |
| distinct reads | 8.6 | 4.9 | −43.0% | 0.00014 |
| long outputs | 3.8 | 2.2 | −42.1% | 0.00068 |
| fresh input | 17,191 | 14,068 | −18.2% | 0.032 |
| turns | 11.4 | 9.9 | −13.1% | 0.053 |
| PASS | 20/20 | 20/20 | — | — |

批次一致性：skill 旧批 (n=8) 159.3k vs 新批 (n=12) 142.3k——新批更低，无向上漂移。turn 爆炸率 skill 6/20 vs baseline 11/20——n=20 下 skill 侧爆炸也更少（此前 8v8 的 3/8 vs 4/8 同方向但更弱）。

## 结论修订（最终版）

**Skill v1 在 OpenCode + GLM-5.2 的 F1/F3 上显著降低 token 总量:−19.1%（均值）/−30.5%（中位），p=0.0094。** 此前"observed but not statistically confirmed"（附录 2）升级为 confirmed。行为通道（reads −43%, p<0.001）与总量通道现在都有统计支持,且质量零损（40/40 PASS）。机制归因（R1 读取通道解释绝大部分效应,见 `rule1_token_contribution_analysis.md`）保持为强推断——R1-only ablation 仍未做,是唯一遗留的归因缺口。外部效度仍限 F1/F3（两个 R1 靶向任务）。
