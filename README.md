# Token-Efficient Coding Agents: A Cross-Harness Effectiveness Study

> Token-Efficient Coding Skill：一项跨 Harness 的有效性研究
>
> A personal research project by **Enze Zhang**: pre-registered, controlled experiments (226 valid runs) measuring how much of a multi-turn coding agent's token spend a prompt-level efficiency policy can actually recover — and why the answer flips sign across harnesses. The deployable artifact is [`.claude/skills/token-efficient-coding/SKILL.md`](.claude/skills/token-efficient-coding/SKILL.md).

**一句话结论：同一份 5 规则的 token 效率 skill，在 Claude Code + Sonnet 上净负（baseline 已内置全部纪律，注入开销无浪费可抵），在 OpenCode + GLM-5.2 上净省 19%（实验室任务）到 36%（真实开源 bug），未观察到质量损失。Token 浪费不是 agent 的普遍属性，而是“模型习惯 × harness 成本结构”的乘积——policy 的价值随环境符号翻转。**

日期：2026-08-06 至 2026-08-07 | 数据：226 个有效实验 run（Claude Code 20 + OpenCode 206），全部通过冻结验证 | 方法：预注册校准关卡 + 配对对照 + 置换检验 + 规则级 ablation + 质量压力测试

## TL;DR (English)

**Question.** How much of a multi-turn coding agent's token spend is removable waste — and can a prompt-level efficiency policy (a 5-rule `SKILL.md`: minimal-context reads, exploration delegation, no-progress stopping, adaptive verification, output discipline) actually recover it, without touching the model or the harness?

**Answer: it depends on the environment, to the point of sign reversal.**

- **Claude Code + claude-sonnet-5: cleanly net-negative.** The baseline already ships every discipline the skill prescribes (zero redundant reads, self-truncated outputs, hypothesis-driven grep). 84–94% of tokens are per-turn cache replay — structurally unreachable from the prompt layer. The skill's ~40k/task injection overhead buys nothing; stopped early per pre-registered rules.
- **OpenCode + GLM-5.2: significantly net-positive.** Lab tasks: **−19.1%** total tokens (20v20, p=0.0094). Six real historical bugs mined from open-source libraries (tinydb, tabulate, boltons, more-itertools, funcy): **−36.1%** (stratified permutation test, p=0.0003), direction consistent 6/6. Hardest-tier tasks: **−38.8%** (p=0.01). Quality: **226/226 valid runs passed their frozen verification**, with no observed pass-rate loss between arms.
- **Attribution (4-arm ablation).** One rule does the work: R1 minimal-context reads. Removing it makes the skill indistinguishable from baseline; alone it reproduces the full read reduction.
- **Quality stress test.** An inverted calibration gate (baseline *must* fail) could not be reached: three rounds of escalating information deprivation left baseline at 36/36 pass, with reads flat and all compensation flowing through extra turns — evidence that quality robustness lives in the turns channel, orthogonal to the reads channel the skill compresses. A direct skill-arm check (12/12 pass, reads unchanged) refuted the "less reading starves hard bugs" concern.

**Practical takeaway.** On weak-discipline harnesses (OpenCode/GLM-class — the same regime where the literature's waste evidence was measured), install the skill and leave it always-on: it saves most where tasks are most expensive and does no harm off-target. On strong harnesses (Claude Code-class), skip it — the waste it targets has already been engineered away, and injection costs real money. Before deploying anywhere new: spend two calibration runs checking whether the baseline actually leaves recoverable waste.

**Method highlights.** Pre-registered calibration gates before every arm expansion; two early-stops executed as registered; anti-cheating holdout verification (frozen test suites, two-way verified buggy=FAIL/fixed=PASS); a control-arm contamination incident (OpenCode auto-discovering `.claude/skills/` up the directory tree) caught, documented, and re-run; rule-level attribution upgraded from regression (R²=0.90) to experimental ablation. Full navigation in §7; the detailed technical report is `reports/opencode_study/00_FINAL_REPORT.md`.

---

## 1. 研究问题

多轮 coding agent 的 token 消耗中有多少是可去除的浪费?文献(SWE-Pruner、How Agents Spend Your Money 等)在 Mini-SWE-Agent/OpenHands/ChatDev 上给出的答案是"很多"——读取占总量 67–76%、重复查看与失败拖长显著推高成本。本项目问的是一个更工程化的问题:

> **把效率纪律写成一份用户级 skill(prompt 层规则,不改模型不改 harness),能不能兑现这些浪费?**

Skill v1 = 5 条规则:R1 最小上下文获取(先搜后局部读、长输出截取)、R2 探索委托、R3 无进展停止、R4 自适应投入(先试后规划、窄验证优先)、R5 输出纪律。设计文档:`design/02_skill_v1_五规则版.md`。

## 2. 主结果

### 2.1 Claude Code + claude-sonnet-5:干净的负结果

14 个 run(5 验证任务 + 2 个校准任务 ×2)的一致图景(`reports/calibration_analysis.md`):

- baseline **零可回收浪费**:重复读取 0、循环 0、每条测试命令自发 `| tail`、688 行大文件用 offset/limit 只取 40–100 行、探索是假设驱动的 grep 而非枚举。五条规则要求的纪律,baseline 出厂即有。
- token 的 84–94% 是逐轮上下文缓存重发——**结构成本,prompt 规则原则上不可触及**。
- skill 注入自带 +40k/任务固定开销(多一个调用 turn × 全上下文重读),开销/可回收 ≈ 8:1,**净效应稳定为负(+37~80k)**。按预注册 early-stop 规则提前止损。

### 2.2 OpenCode + GLM-5.2:显著正效应(20v20 主实验)

同一份 skill,弱默认纪律的环境(`reports/opencode_study/00_FINAL_REPORT.md`):

| 指标 | baseline | skill | Δ | p(单侧置换) |
|---|---:|---:|---:|---:|
| 总 tokens | 184,245 | 149,092 | **−19.1%**(中位 −30.5%) | **0.0094** |
| 读取文件数 | 8.6 | 4.9 | −43% | 0.00014 |
| 长输出次数 | 3.8 | 2.2 | −42% | 0.00068 |
| 通过率 | 20/20 | 20/20 | 质量零损 | — |

### 2.3 生态效度:真实开源历史 bug 上效应更大

自建任务有 author-circularity 风险(任务作者 = skill 作者)。终局检验:从 5 个真实 Python 库(tinydb/tabulate/boltons/more-itertools/funcy)挖出 6 个**真实历史 bug**(fix commit 反转,parent 快照 + 修复 commit 的测试,双向机械验证),无任何人工放大器,48 run(`reports/eco_validity_study/02_results.md`):

- **6/6 任务方向一致**,各任务中位 δ = −11.7% ~ −55.5%;
- **分层置换检验 −36.1%,p=0.0003**;reads −49%(与实验室 −43% 同带,同一机制);
- **48/48 全部修复成功**,两臂质量无差;
- 预注册预测(效应收缩到 −5~−15%)**被反向推翻**:真实仓库自带的 docs/多模块杂物本身就是天然探索面,比合成放大器更大。

### 2.4 机制:效应从哪来,边界在哪

- **规则级归因(四臂 ablation,60 run)**:R1 是唯一主力——去掉 R1 后 skill ≈ 没装(p=0.022 差于完整版);R1 单独可复现全部读取效应,但只拿到 −7% 总量(完整版 −19%),残余坐在 turn 通道,无单条规则可压。发布物 = 完整 skill,R1 标注核心。
- **浪费的真实形态是碎片化**:61–68% 的 token 坐在"理论可合并"的 turn 边界上(信息依赖图重建);但单指令 batching ablation 证明这是模型逐步解码的生成习惯,提示层够不到(ratio p=0.049 而 token 持平)。
- **GLM-5.2 自带两项纪律**(全局定位、输出自截断)使循环诱饵(F5)和验证成本诱饵(F4)在源头上不可达——skill 的可作用面 = 模型习惯留下的缺口,GLM-5.2 的缺口恰好是读取宽度。
- **边界案例(E2/tabulate)**:单个 3k 行文件 + 无 traceback 的行为型 bug → 读通道无空间,浪费全在反复 grep/重读/跑测试的 turn 通道,skill 无效但无害(两臂打平,质量不损)。
- **小任务不亏**(F7,10v10):AGENTS.md 注入在 OpenCode 上边际成本 ≈0,skill 在没有可省面的任务上安分 → **可无条件启用,无需按任务开关**。

### 2.5 质量压力测试:"少读"不以通过率为代价

"skill 让 agent 少读 → 难 bug 信息饥饿 → 质量损失"是 R1 的天然质疑。主动攻击(`reports/difficulty_band_study/`):取备选池最难的 3 个真实 bug(含一个手工合成的单文件双缺陷任务),**倒置校准关卡**——要求 baseline 出现失败(目标通过率 50–80%)才算任务够难。三轮递进信息剥夺(有失败测试 → 只有复现代码 → 纯散文症状 + 隐藏验收测试),baseline **36/36 全 PASS**,目标难度带不可达(合并失败率 95% 上界 ≈8%)。

关键机制数据:信息剥夺使 token 成本 ×2.8–4.2、turns 11→32,**而读取宽度全程平坦(2–3.5 个文件)**——GLM-5.2 靠 turn 预算弹性(自建复现测试迭代)补偿信息缺失,从不靠宽读。**质量鲁棒性坐在 turns 通道(昂贵),与 skill 压的 reads 通道(廉价)正交——"少读"没有质量代价是结构性的,不是运气。**

追加 skill arm 直接检验("会不会 baseline 全过恰因它没少读?"):最难档同条件 12 run,**skill 12/12 PASS**,reads 与 baseline 持平(无可省空间时不砍读)——尾部风险直接排除,双臂合并 48/48。意外收获:skill 在最难档 **token −38.8%(分层中位,p=0.01)**,节省全部来自压住 baseline 的 turn 膨胀(如 toolz 任务 698k→285k)——高难任务上 skill 不但无质量代价,反而是成本膨胀的解药(探索性发现,n=4/格)。

## 3. 核心图景:prompt 干预的可达面

| 维度 | prompt 可控性 | 证据 |
|---|---|---|
| **内容**(读什么进上下文) | **可控** | reads −43~−50%(4 组独立实验同带);总量 −19%/−36% |
| **粒度**(分几个 turn 做) | 弱可控、无经济效果 | batching ablation:ratio p=0.049,token 持平 |
| **结构**(每 turn 历史重发) | 不可控 | CC 84–94% 缓存重发 / OC 全价重发,均为定价层属性 |

**跨 harness 的符号翻转是本项目的中心发现**:同一 skill 在 CC 净负(−40k 注入费买不到毛效应)、在 OC 净正(−35k~−70k 毛效应,注入费 ≈0)。文献的浪费证据(弱 scaffold)与 OC 端一致;CC 代表"浪费已被 harness 解决"的一端——SWE-agent ACI 原则、observation 截断这些文献中的"待部署缓解措施",在 Claude Code 里是出厂配置。

**实践建议**:部署 token 效率 policy 前,先花 2 个 run 校准 baseline 有没有可回收浪费(宽读、重复读、无截断长输出)。有 → skill 值得装且可常开;没有 → 省下注入费,浪费主体在你碰不到的定价层。

## 4. 方法论要点(负结果为什么可信,正结果为什么不虚)

1. **预注册 + 校准关卡**:每个任务先跑 baseline ×2,确认目标浪费存在且无逃逸通道,才授权 skill arm;两次 early-stop(CC 主实验、F5/F4 诱饵失效)都按预注册规则执行。
2. **防作弊验证**:verify.sh 用冻结测试套件在临时目录对 agent 源码做 holdout,测试篡改无效;任务仓库出货前双向验证(buggy=FAIL/fixed=PASS)。
3. **对照污染防御**:OpenCode 自动发现项目树内 `.claude/skills/`——第一批校准 run 因此作废重跑;此后所有 workspace 在项目树外。
4. **统计口径诚实**:生态效度批的 pooled 均值(−14.3%,p=0.36)被单任务长尾拖平,报告以预注册的分层每任务等权口径(−36.1%,p=0.0003)为主,两个口径都呈现。
5. **归因分层**:"观察到差异" → "回归解释"(R²=0.90) → "实验级 ablation"(四臂),逐级升级,每级标注推断强度。

## 5. 局限

- **单模型单 harness 的正结果**:GLM-5.2 + OpenCode(刻意定位——这是文献浪费证据的采样区间);CC 侧只有负结果。"碎片化是否 GLM 特有"未测。
- **任务形态全部是 bug 修复**;特性添加/重构类未测。质量结论已做压力测试(§2.5)但仍是弱上界:真实单-commit bug 任务族内 baseline 失败率 95% 上界 ≈8%;多文件架构级缺陷等更难形态超出可挖掘范围,未测。
- R3(停止规则)、R4 验证半条在 GLM-5.2 上**无对象**(模型习惯使诱饵不可达),其价值在其他模型上未知;R2(委托)在 OpenCode 物理不可测(无子代理)。
- OpenCode 度量:output 含 reasoning、cache_write 恒 0、订阅制 cost=0——跨 harness 只比行为指标与相对量。

## 6. 复现核心结果

复现已经归档的核心统计结果不需要模型 API、OpenCode 或 Claude Code，只需要 Python 3 标准库：

```bash
python3 experiments/reproduce_key_results.py
```

脚本会审计 230 份 `metrics.json`，排除 4 个明确标记的污染 run，确认 226/226 个有效 run 通过冻结验证，并重新计算 20v20 主实验与 6 个真实开源 bug 的分层结果。置换检验使用固定随机种子的 Monte Carlo 估计，因此 p 值末位可能与报告略有浮动；效应量由原始数据确定。

如果需要重新运行一个 OpenCode + GLM-5.2 trial（而不是复算归档结果），请将 workspace 放在项目目录之外，避免 OpenCode 向上发现本仓库的 skill：

```bash
python3 experiments/run_opencode_experiment.py \
  --task experiments/tasks/<task> \
  --condition skill \
  --run-id <id> \
  --runs-dir /tmp/token-efficient-runs
```

## 7. 仓库导航

| 路径 | 内容 |
|---|---|
| `design/` | Skill 设计(5 规则版)与 benchmark 任务集设计 |
| `reports/calibration_analysis.md` | Claude Code 侧完整分析(负结果) |
| `reports/opencode_study/00_FINAL_REPORT.md` | OpenCode 侧最终报告(主实验+全部 ablation,含文件索引) |
| `reports/eco_validity_study/` | 生态效度:候选挖掘(26 个验证候选)与结果(48 run) |
| `reports/difficulty_band_study/` | 质量压力测试:倒置关卡三轮加难 + skill 直接检验,48 run 全 PASS |
| `experiments/reproduce_key_results.py` | 从归档 metrics 一键复现 226-run 审计与两项 headline 结果 |
| `experiments/` | 双 harness 运行管线、任务集(`tasks/`)、全部 run 归档(`runs*/`,含每个 run 的 transcript 与 metrics;agent 工作副本 workspace 不入库) |
| `literature/` | 44 篇文献 scoping review(18 篇核心) |
