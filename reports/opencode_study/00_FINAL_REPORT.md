# Token-Efficient Coding Skill 在 OpenCode + GLM-5.2 上的有效性研究
## —— 最终综合报告

日期：2026-08-06（主体），2026-08-07 增补 F5/F7 外部效度研究（§3.7）、R1 ablation（§3.8）、生态效度 benchmark（§3.9）、难度带质量压力测试（§3.10）
研究者：与 Claude Code (Fable 5) 协作完成
数据规模：OpenCode 206 个 run（40 主实验 + 24 batching ablation + 28 F5/F7/F4 外部效度 + 21 R1 ablation + 48 生态效度 + 48 难度带 + smoke），全部 PASS；另引用 Claude Code 侧既有 20 run 作跨 harness 对照。
定位声明：本研究刻意定位于**单模型（GLM-5.2，中等性能开源模型）+ 单 harness（OpenCode）**——这正是文献中 token 浪费证据的采样区间，也是 token-efficient policy 的目标场景。跨模型复制经评估后主动放弃（见 §5）。

---

## 1. 背景与研究问题

前序工作（`../calibration_analysis.md`）在 Claude Code + Sonnet 上得到干净的**负结果**：五规则 token-efficient skill（Skill v1）无法减少 token——baseline 已内化全部目标纪律（零宽读取、零循环、自动截断长输出），skill 的调用开销（+40k/task）没有可回收的浪费来抵偿，且 84–94% 的 token 是缓存重发的结构成本，prompt 规则不可触及。

由此产生本 session 的研究问题：**同一个 skill，在默认纪律更弱的 agent harness（OpenCode + GLM-5.2）上是否有效？** 即把问题从"skill 是否省 token"重构为"**token-efficient policy 的有效性是否随 harness 而异**"。

## 2. 主结果（一表版）

**F1/F3 两任务、20 vs 20 run、单侧 permutation 检验：**

| 指标 | baseline (n=20) | Skill v1 (n=20) | Δ | p |
|---|---:|---:|---:|---:|
| **总 tokens** | 184,245 | 149,092 | **−19.1%**（中位 −30.5%） | **0.0094** |
| distinct files read | 8.6 | 4.9 | −43% | 0.00014 |
| long outputs (>4k chars) | 3.8 | 2.2 | −42% | 0.00068 |
| fresh input tokens | 17,191 | 14,068 | −18% | 0.032 |
| turns | 11.4 | 9.9 | −13% | 0.053 |
| 任务通过率 | 20/20 | 20/20 | 质量零损 | — |

**结论：Skill v1 在 OpenCode + GLM-5.2 上显著降低 token 消耗约五分之一，质量无损。** 与 Claude Code 的净负结果（+21~42%）并置，核心论点成立：**规则本身跨 harness 有效，规则的经济性是 harness 属性**——policy 的价值取决于 (a) baseline 有没有留下可回收浪费、(b) harness 对历史重发怎么计价。

## 3. 研究过程与各阶段结论

### 3.1 基础设施迁移（`opencode_migration_findings.md`, `opencode_smoke_result.md`）

新建 `run_opencode_experiment.py` + `analyze_opencode_trajectory.py`（输出 schema 与 Claude Code 管线一致，旧管线零改动）。Skill 注入采用 workspace `AGENTS.md`（OpenCode 官方机制，prompt 两臂相同——与 Claude Code 的显式调用协议不同，已预登记）。三个工程要点：
1. `opencode run` 必须带 `--dir <workspace>`，否则 agent 逃出工作区；
2. **OpenCode 沿目录树自动发现 `.claude/skills/`** ——所有 workspace 必须放在项目树外（第一批校准 run 因此污染作废,教训已固化进 runner 默认值）；
3. Z.ai 端点上报 cache read（Bedrock GLM 不报）、`cache_write` 恒 0、订阅制 `cost=0`。

### 3.2 Baseline 校准（`opencode_calibration_f1_f3.md`）

与 Claude Code 相反，**OpenCode baseline 存在真实浪费**：4/4 run 宽读取（4–15 文件 vs CC 的 2 个，枚举式浏览，零精读），run 间方差 ±37%。无重复读取、无 debug loop（R3 类浪费为零）。→ 按预登记关卡判定继续（Decision A）。

### 3.3 Skill arm 与样本量之路（`opencode_skill_calibration_f1_f3.md` 附录 1–3）

8v8 时行为效应即显著（reads p=0.012）但总量 p=0.221;中途一次重要自我纠错——"skill run 双峰"的初判被 baseline n=8 推翻（**turn 爆炸是环境采样方差，两臂共有**，baseline 爆炸率反而更高）。最终 skill 补至 n=20（新批均值比旧批更低，无漂移），baseline 池并入 batching ablation 的 12 个协议相同的 control run → **20v20 过线（p=0.0094）**。

### 3.4 Turn 级与粒度分析（`opencode_turn_level_analysis.md`, `opencode_turn_granularity_analysis.md`）

对 16 个 clean run 的逐 turn 重建发现浪费的真正形态：**碎片化（de-batching）**——爆炸轨迹不是多做事（调用只多 23%）而是把同样的事切碎（turns 多 62%，85% tool-turn 单调用）。信息依赖图分析显示 **61–68% 的全部 token 坐在"理论可合并"的 turn 边界上**，且正常轨迹也背着 56%——碎片化是连续谱，Skill v1 完全未触及该维度。

### 3.5 Batching 指令 ablation（`batching_ablation_design.md`, `batching_ablation_results.md`）

针对碎片化的单指令对照实验（n=24，本项目唯一的单指令实验）：**机制证实、经济失败**——效应纯走"打包"路径（fragmentation ratio 0.75→0.69, p=0.049;calls 不变）但幅度太小，token 总量持平（p=0.49）。分层:F1 上消除爆炸尾部,F3 上失效。→ 不并入 skill。**剩余碎片化是模型逐步解码的生成习惯，一句提醒够不到。**

### 3.6 规则级归因（`rule1_token_contribution_analysis.md`）

（注：本节为 2026-08-06 状态；§3.7 的 F7 结果提供第三任务独立支持，§3.8 的 ablation 将归因升级为实验级并做出一处修正。）

40-run 回归（R²=0.90）:`总量 ≈ 0.9·turns + 0.6·read_chars`,+1 turn ≈ 14.8k tok,+1k 读取 chars ≈ 1.22k tok,两维度近独立。**skill 的全部 token 效应可由 R1（先搜后读/少读）的读取通道解释**（回归折算 −20.7k vs 臂间实测 −20.4k,吻合）;R2 在 OpenCode 不可执行（无子代理）,R3/R4 无空间,R5 杯水车薪。R1 无内生反效应（少读不多 turn）。**注意：这是强推断而非实验结论**——R1-only ablation 未做。

### 3.7 F5/F7/F4 外部效度研究（2026-08-07，`f5_f7_external_validity_design.md` / `f5_f7_results.md`）

主实验的外部效度缺口（2 任务、全 R1 靶向）由新任务补上（R1-only ablation 被有意跳过——在 F1/F3 上其余规则无作用机制，ablation 结果预定，降级为发表前置项）：

- **F5 二层 bug（R3 靶向）：关卡未通过，0/4 入坑——R3 无对象。**两处同型缺陷（validate/transform 阶段各一，修完第一处后同一命令报一字不差的错误）设计为循环诱饵，但 GLM-5.2 的修复习惯是"先全局定位、一次修完"——grep 时两处缺陷共同暴露，陷阱预设的"修一处→重跑→误判"路径从未被走过。按预注册不扩样。这把 F1/F3 的"零循环"观察升级为更强的结论：**不是任务缺诱饵，而是诱饵在这种行为模式下不可达**。计划外观察：F5 baseline 重度宽读（13–25 文件、265k–517k），R1 浪费普遍性证据扩至第 4 个任务。
- **F7 大仓库小修复（R4 靶向）：关卡过线（首 Edit 前 token 占比中位 51%），10v10，20/20 PASS。**行为效应确认——reads −50% (p=0.044)、首 Edit 前 turns −30% (p=0.003)，方向与主实验一致；**token 效应 −5.9% 不显著 (p=0.245)**——可省面太小（baseline 仅 ~66k），~4k 毛效应被 ±12k 方差淹没，与 §3.6 回归模型"效应 ∝ 可省读取量"的预测定量吻合。
- **"skill 在小任务上净负"的预注册担忧被否证**：AGENTS.md 注入在 OpenCode 上边际成本 ≈0（进 system prompt 被 cache 吸收），无 Claude Code 式机制费。

- **F4 验证分级（R4 验证半条，同日追加）：关卡未通过——诱饵被模型习惯绕过。**放大器（pytest -v，全量 36.8k 字符 vs 窄测试 ~1k）没能生效：baseline 4/4 的 8 次 pytest 调用**全部自带 `| tail -N` 截断**（最大收取 2.8k = 全量的 7.6%），2/4 还主动加 `-q`。R4 想省的验证成本已被 GLM-5.2 的自截断习惯抹平——与 F5 的"全局定位习惯击败循环陷阱"同构。

**外部效度结论（更新后）：skill 的适用面 = 存在可省读取量的任务；适用面之外它安分（不帮忙也不碍事）→ 在 OpenCode 上可无条件启用，无需按任务类型开关。**规则级记分板终版：R1 主力（三任务方向一致）、R4 探索半条行为生效但分红小（F7）/验证半条无对象（F4）、R2 不可执行（无子代理）、R3 无对象（F5）、R5 杯水车薪。贯穿 F4/F5 的元发现：**GLM-5.2 自带两项纪律（全局定位、输出自截断），它们不省宽读，但让循环类和验证成本类浪费在源头上不存在**——skill 的可作用面由"模型习惯留下的缺口"决定，而 GLM-5.2 的缺口恰好只有读取宽度。

### 3.8 R1 Ablation（2026-08-07，`r1_ablation_design.md` / `r1_ablation_results.md`）

四臂设计（baseline×20 / full×20 复用，r1only×12 / r1removed×8 新跑，60 run 全 PASS），把归因从强推断升级为实验证据，并做出一处重要修正：

- **必要性（实验证实）**：R1-removed（只带 R2–R5）≈ baseline（全指标无差异），显著差于 full（总量 p=0.022）。**没有 R1，skill 等于没装。**
- **充分性（部分证实）**：R1-only 完整复现读取效应（reads 5.2 vs full 4.9，p=0.83；vs baseline −40%，p=0.0036），但总量只到 −7%（vs full 的 −19%）——**缺口在 turns 通道**：full 压 turns 至 9.9，r1only（11.7）与 r1removed（11.4）都没压。单条规则都不产生 turn 纪律，只有合体时出现（协同 vs 采样噪声未决，n 不足以裁决）。
- **归因修正**："效应全部来自 R1" → **"读取通道效应全部来自 R1（实验级）；full 相对 R1-only 的残余 ~12% 坐在 turn 通道，来源未决"**。
- **发布决策**：不裁剪为单规则——R1-only 丢一半 token 效应，而保留 R2–R5 注入成本 ≈0。发布物 = full skill，R1 标注 core rule。

### 3.9 生态效度 Benchmark：真实 OSS 历史 bug（2026-08-07，`../eco_validity_study/01_candidate_list.md` / `02_results.md`）

至此所有正结果都来自**自建**任务（任务作者 = skill 作者，author-circularity 风险），且清一色 bug 修复。生态效度研究用真实开源库的历史 bug 直接检验：从 7 个 pytest 生态纯 Python 库挖出 26 个机械验证过的 fix commit（parent+新测试=FAIL → 叠加官方修复=PASS），选 6 个反转成任务（tinydb×2、tabulate、boltons、more-itertools、funcy；难度谱系 easy→medium-hard，5/6 无 traceback 或低定位泄漏），**无人工浪费放大器**。校准关卡 12/12 通过后扩至 6 任务 × 2 臂 × 4 run = 48 run。

**预注册预测被反向推翻**：预测效应收缩至 −5%~−15%（"无放大器 → 可省浪费少"），实测**效应变大**——

| 指标 | 结果 | p |
|---|---|---|
| 分层置换检验（任务内 shuffle，主口径） | **−36.1%** | **0.0003** |
| 方向一致性 | 6/6 任务 skill 中位更低 | — |
| 各任务中位 δ | −11.7% ~ −55.5% | — |
| reads | 3.5 → 1.8（−49%） | 0.0001 |
| 通过率 | 48/48 | 质量零损 |

预测错误的机制：真实仓库自带的探索面（docs/、CHANGELOG、多模块布局）本身就是天然放大器，宽读空间 ≥ 自建合成仓库。reads 效应（−49%）与主实验（−43%）、F7（−50%）完全同带——同一机制，不是新效应。

**E2（tabulate）= 有预测力的边界案例**：唯一弱效应任务（−11.7%，分布重叠）。单个 3k 行文件 + 行为型 bug（无 traceback）→ 读通道无空间（reads 恒 2），两臂全部 turn 爆炸（16–53 turns，浪费在反复 grep/重读/跑测试的 turn 通道）——与 §3.8"full 的残余效应坐在 turn 通道、无单规则可压"精确互证。技能在此类任务上无效但无害，与"无条件启用"结论兼容。

统计口径注记：pooled 均值 −14.3%（p=0.36）被 E2 一个任务的长尾拖平（去 E2 后 −44%，p=0.0003）；分层每任务等权统计量是预注册主口径。

**证据链就此闭合：lab-effective（−19.1%，自建任务）→ practice-effective（−36.1%，真实任务），GLM-5.2 + OpenCode 范围内。**

### 3.10 难度带质量压力测试（2026-08-07，`../difficulty_band_study/00_design.md` / `01_results.md`）

针对 §5.1a 的天花板限制发起的主动攻击：从备选池取 3 个最难候选（toolz partition_all 哨兵切片、boltons tbutils 2-hunk、dateutil 合成双 bug），设计**倒置校准 gate**——baseline 必须出现失败（目标 pass 带 50–80%）才扩容双臂,以直接检测"skill 少读 → 质量损失"。

**结果：目标难度带不可达。** 三轮递进信息剥夺（v1 红测试锚点 → v2 移除失败测试只留复现代码 → v3 纯散文症状），baseline **36/36 全 PASS**（合并失败率 95% 上界 ≈8%）。关键数据：token 成本随信息剥夺 ×2.8–4.2（v3 中位 644k–1387k/run），turns 同步膨胀（11→32），**而 distinct reads 全程平坦（2–3.5）**——GLM-5.2 用 turn 预算弹性（自建复现测试→迭代）补偿信息缺失，从不用宽读补偿。机制含义：**质量鲁棒性由 turns 通道（昂贵）支撑，与 R1 压的 reads 通道（廉价）正交——这是"skill 无质量代价"的机制性解释**，与 §3.8 通道分解、§3.9 E2 边界案例三方互证。

按预注册终止规则，正式对比不扩容；应用户质疑（"baseline 全过会不会正因为它没少读"）追加 skill arm sanity check ×12（v3 最难档同条件）：**skill 12/12 PASS，reads 与 baseline 持平（2–3.5，无可省空间时不强行砍读）——"少读致难任务失败"的尾部风险被直接排除，质量上界升级为双臂 48/48**。意外收获：skill 在最难档 token 分层中位 **−38.8%（p=0.0102）**，且节省全部来自 turns 通道（20→13.5 / 20.5→15.5 / 32→25.5）——高难条件下 baseline 的 turn 膨胀存在 prompt 可压缩部分，为 §3.8 遗留的"turn 残余是协同还是噪声"提供了首个方向性证据（探索性，n=4/格）。质量-token 权衡如存在，触发面在更难的任务形态（多文件架构级缺陷、无回归套件保护）。

## 4. 核心图景：prompt 干预的可达面

| 维度 | prompt 可控性 | 证据 |
|---|---|---|
| **内容**（读什么进上下文） | **可控** | reads −43%, p=0.00014；总量 −19%, p=0.0094 |
| **粒度**（分几个 turn 做） | 弱可控、无经济效果 | batching ablation: ratio p=0.049 但 token 持平 |
| **结构**（每 turn 历史重发成本） | 不可控 | 两 harness 的 84–94% / 全价重发均为定价层属性 |

跨 harness 维度：同一 skill 在 CC 净负（−40k 机制费买不到任何毛效应）、在 OC 净正（−35k 毛效应减 ~10k 注入费）。**浪费 = 模型行为 × harness 成本函数的乘积**;文献中的 token 浪费证据（Mini-SWE-Agent/OpenHands 等弱 scaffold）与我们的 OC 结果一致,CC 代表的强 scaffold 端是浪费问题"已被 harness 解决"的一端。

## 5. 局限（诚实清单，生态效度研究后更新）

1. ~~外部效度 = 2 个任务~~ → **已扩至 11 任务**（自建 F1/F3/F4/F5/F7 + 真实 OSS bug ×6，§3.9）。~~author-circularity~~ → 已由真实任务否证。剩余：F5 的 R3 负结果是"诱饵不可达"而非"规则无效"——运行时才可见的二层 bug（状态依赖类）未测，需要超出当前框架的任务设计；R5 靶向任务（F8）未建；**任务形态仍全部是 bug 修复**——特性添加/重构类任务（原 F2/F8）经评审裁剪（工程成本 vs 边际证据），"skill 在非 bugfix 任务上的效果"未测。
1a. ~~生态效度批的质量结论受天花板限制~~ → **已主动压力测试**（§3.10）：三轮信息剥夺仍 36/36 PASS，50–80% pass 带在该任务族不可达；质量结论升级为"合并失败率 95% 上界 ≈8% + 机制性解释（质量靠 turns 通道支撑,与 skill 压的 reads 通道正交）"。剩余空白：更难任务形态（多文件架构级缺陷）超出可挖掘的真实单-commit bug 范围，未测。
2. ~~归因是强推断~~ → **已升级为实验级**（§3.8 四臂 ablation）：R1 必要性坐实、读取通道充分性坐实；遗留的唯一开放点 = full 相对 R1-only 的 turn 通道残余（~12%）是规则协同还是采样噪声（需 n≥20/臂 turn 专项，性价比低，不追）。
3. **单模型（GLM-5.2）单 harness（OpenCode 1.18.14）**——这是定位而非缺陷（见开头定位声明）：GLM-5.2 代表文献浪费证据的模型区间，结论 scope 明确为"中等性能模型 + 弱 scaffold harness"。跨模型对照（GPT-5.5 / Bedrock gpt-oss）经评估后放弃：机器无 GPT-5.5 访问，且项目目标不含"强模型是否也宽读"这一问题。"碎片化是否 GLM 特有"保持未测。
4. baseline 池的 12 个 run 来自 batching ablation 的 control 臂（协议相同、均值差 4%）,合并是事后决定——已通过批间一致性检验,但非预登记。
5. F3 的长日志诱饵两个 harness 都未踩中（task.md 提供 pytest 捷径）,"长输出污染"维度实际不可测。
6. OpenCode 度量口径:output_tokens 含 reasoning、cache_write 恒 0、cost=0——跨 harness 只比行为指标和相对量。
7. F7 的 token 检验 power 不足（效应 ~4k vs sd ~12k）："不显著"应读作"效应量级 ≲ 方差",不是"无效应"。

## 6. 遗留工作（生态效度研究后更新）

1. ~~R1-only ablation~~ → **已完成**（§3.8，含 R1-removed 反向臂）；
2. ~~建 F4/F5/F6/F7~~ → **F4/F5/F7 已完成**（§3.7）；F6（红鲱鱼,R3）预期与 F5 同命运（全局定位习惯使静态陷阱不可达）,不再建造；F2/F8 靶向 R2,在 OpenCode 上物理不可测（无子代理）,不建造;
3. ~~跨模型复制~~ → 主动放弃,项目定位单模型（见 §5.3）;
4. ~~生态效度~~ → **已完成**（§3.9，48 run，−36.1% p=0.0003）；备选池尚有 23 个已验证候选可随时扩容；
5. **Claude Code 侧最终报告合并**（本报告 + `../calibration_analysis.md` 收束成对外发布版）——唯一剩余项。

## 7. 文件索引

本目录（`reports/opencode_study/`）:

| 文件 | 内容 |
|---|---|
| `00_FINAL_REPORT.md` | 本报告 |
| `opencode_migration_findings.md` | 基础设施迁移与信号验证 |
| `opencode_smoke_result.md` | 管线 smoke test（两臂 ×1） |
| `opencode_vs_claudecode_smoke_analysis.md` | 早期跨 harness 对比与研究问题重构 |
| `opencode_calibration_f1_f3.md` | baseline 校准（含 skill 自发现污染事故与修复） |
| `opencode_skill_calibration_f1_f3.md` | 主实验:skill arm,附录 1–3 至 20v20 终检验 |
| `opencode_turn_level_analysis.md` | turn 分段与浪费四分类 |
| `opencode_turn_granularity_analysis.md` | 信息依赖图与碎片化定量 |
| `batching_ablation_design.md` / `_results.md` | 单指令 ablation 设计与结果（n=24） |
| `rule1_token_contribution_analysis.md` | R1 归因回归分析 |
| `f5_f7_external_validity_design.md` / `f5_f7_results.md` | F5/F7/F4 外部效度研究预注册与结果（n=28, 2026-08-07） |
| `r1_ablation_design.md` / `r1_ablation_results.md` | R1 四臂 ablation 预注册与结果（n=20 新跑, 2026-08-07） |
| `../eco_validity_study/01_candidate_list.md` / `02_results.md` | 生态效度 benchmark：真实 OSS bug 挖掘（26 候选）与结果（48 run, 2026-08-07） |
| `../difficulty_band_study/00_design.md` / `01_results.md` | 难度带质量压力测试：倒置 gate 三轮加难 + skill sanity check,48 run 全 PASS（2026-08-07） |

数据:`experiments/runs/`（40 主实验 run + 早期 smoke/作废 run 留档）、`experiments/runs_batching_ablation/`（25 run）、`experiments/runs_f5f7/`（28 run 含 F4）、`experiments/runs_r1_ablation/`（21 run）、`experiments/runs_eco_validity/`（48 run）、`experiments/runs_difficulty_band/`（48 run：v1_cal/v2_cal/v3 baseline+skill）。任务:`experiments/tasks/f5_two_layer/`、`experiments/tasks/f7_bigrepo_smallfix/`（2026-08-07 新建）、`experiments/tasks/eco_*/`（6 个真实 OSS bug 任务，2026-08-07）、`experiments/tasks/hard_*/`（3 个难度带任务,含 holdout/ 隐藏测试,2026-08-07）。代码:`experiments/run_opencode_experiment.py`、`analyze_opencode_trajectory.py`、`run_batching_ablation.py`（Claude Code 原管线零改动）。
