# Token Efficient Coding Skill v1 设计方案

日期：2026-08-06
平台：Claude Code（headless `claude -p`，transcript JSONL 为唯一数据源）
状态：设计稿，SKILL.md 未生成

## 0. 设计前提（Claude Code 机制）

- Skill 位于 `.claude/skills/token-efficient-coding/SKILL.md`，实验中通过 prompt 显式指名调用以消除触发方差；
- Transcript JSONL（`~/.claude/projects/<proj>/<session>.jsonl`）逐条记录 `usage`
  （input / cache_read / cache_creation / output tokens）与全部工具调用参数，全部指标由此计算，无需插桩；
- 依赖工具：Grep/Glob（搜索）、Read offset/limit（局部读取）、Edit（局部修改）、Task/Explore subagent（上下文隔离）。

## 1. 设计原则

1. 只收录 SKILL.md 能软约束、且行为可在 transcript 中自动观测的规则——每条规则必须对应可计算指标；
2. v1 只有单个 SKILL.md（<150 行），不带 references/scripts，保持因果归因干净；渐进披露留给 v2；
3. 三大浪费源（冗余上下文 / 无进展循环 / 非自适应分配）各 2–3 条，共 7 条规则。

## 2. 规则表

| # | 规则 | 浪费源 | 证据 | 关键验证指标 |
|---|---|---|---|---|
| R1 | 层级定位：先 Grep/Glob，后带 limit 的局部 Read；禁整目录读取 | 冗余上下文 | Agentless、SWE-Pruner（读取占 67–76%） | search-before-read 率；每次 Read 平均 token；全文件读取次数 |
| R2 | 未变化文件不重读，引用既有结论 | 冗余上下文 | How Agents Spend（高成本失败↔重复查看） | 重复读取率（未 Edit 文件的重复 Read / 总 Read） |
| R3 | ≥3 文件的探索委托 subagent，只回收结论 | 冗余上下文 | 调研遗漏项；上下文防火墙机制（非任务分解） | subagent 次数与 token（计入总账）；主上下文 fresh input 每轮斜率 |
| R4 | 工具输出过滤：单测优先、日志 tail/grep 截取 | 冗余上下文 | SWE-agent 简洁反馈原则 | 单次 Bash 结果平均/最大 token；全量测试套件运行次数 |
| R5 | 进展账本：连续 2 轮无新增证据→停止当前路径，换定位或问人 | 无进展循环 | EET 弱版本（原文均降 ~30% 输入 token，质量损失 0.2pp） | 无进展轮数（工具调用集合相似+错误哈希相同）；失败任务总 token；同错误签名最长链 |
| R6 | 条件式规划：简单任务直接尝试+便宜验证，失败/跨模块才升级规划 | 非自适应分配 | PaT、Reason-Code | 首次 Edit 前轮数与 token（按难度分层）；首改即过验收比例（防抢跑） |
| R7 | 输出纪律：Edit 局部修改、不复述未改代码、结论式汇报 | 输出侧（调研薄弱项） | 输出单价最高；Agentless 小 diff | 总 output token；Write 覆盖已有文件次数；Edit 字符量/文件长度比 |

每条规则在 SKILL.md 中附豁免条件（如安全改动可扩大读取），防 Goodhart 式机械遵守损害质量。

## 3. SKILL.md 行数分配（目标 <150）

frontmatter ~5 / 总原则 ~10 / 核心状态机 ~25 / 7 条规则各 8–12 行 ~85 / 停止与升级条件 ~15。

状态机：理解验收 → 低成本定位 → 最小读取 → 局部修改 → 针对性验证
（通过→按需回归→结束；失败有新证据→定向补充；无进展→换路/问人；缺意图→集中问一次）。

## 4. 实验方案

### 4.1 对照

- Baseline：无 skill 目录；Skill：含 skill 目录 + prompt 末尾一句显式调用；其余（模型版本、权限 allowlist、仓库 commit、任务卡）完全一致；
- Skill 文本注入开销计入 Skill 组总 token（SkillsBench 教训）；
- 附带小实验：5 次不指名调用，报告自动触发率；
- 运行：`claude -p "$(cat task.md)" --output-format stream-json`，每 run 独立新会话。

### 4.2 任务集（10 题 × 2 条件 × 3 runs = 60 runs）

冻结 commit 的中小型真实仓库 + 人工注入缺陷（不用 SWE-bench 公开题，避免污染）：

- T1 简单 bug fix ×4：单文件、报错明确（验证 R1/R4/R6；预期省得少但不翻车）；
- T2 中等 ×4：跨 2–3 文件需定位（验证 R1/R2/R3；预期主要收益区）；
- T3 探索/易绕路 ×2：误导性报错或需理解结构（验证 R3/R5；预期方差最大）。

每题：统一任务卡（目标/现状/验收/范围）+ holdout 验收测试（agent 不可见，事后由 harness 执行）+ 回归测试。

### 4.3 指标

- 主指标：成功率约束下的端到端 token（fresh input / cache read / cache write / output 分列）；
- 次级：工具调用数、轮数、美元、挂钟时间；
- 规则级行为指标 12 项（见规则表）——回答"哪条规则起作用、哪条没被遵守"；
- 统计：按任务配对差值 + Wilcoxon 符号秩；配对散点图；不报跨任务均值（同任务运行间成本可差 2×）。

### 4.4 Trajectory 分析（analyze_trajectory.py）

1. 每 run 摘要：token 四项、按工具分的调用计数、重复读取率、无进展轮数、首次 Edit 位置、通过与否；
2. 规则遵守度：12 项指标 + 按轮次分桶的违反率（检验 skill 遵循度随轨迹变长衰减）；
3. 定性案例：2–3 个分叉最大任务的工具调用时序并排图。

### 4.5 预期与风险预案

- 最可能形态：T2/T3 有收益、T1 持平或因 skill 开销略亏 → 按难度分层报告，本身即合格发现；
- 某规则遵守率 <50% → 进 v2 措辞修订清单，非方向失败；
- 质量下降 → 定位到具体规则（最可能 R1 读取不足或 R6 抢跑），补豁免条件。

## 5. 待确认决策

1. 实验模型（建议 claude-sonnet-5，60 runs 成本可控）；
2. 任务仓库来源（建议 2–3 个几千行级 Python 开源项目冻结 commit 注入缺陷；或用户自选仓库）。
