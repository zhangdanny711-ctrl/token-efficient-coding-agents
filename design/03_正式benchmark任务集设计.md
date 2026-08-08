# 正式 Benchmark 任务集设计

日期：2026-08-06
前置：02 号文件（Skill v1 五规则版，不再讨论）、experiments/results_summary.md（validation v2）
约束：沿用现有 pipeline（task.md + repo/ + verify.sh），不改 runner/analyzer。

## 1. 设计原则：从 validation 结论反推

Validation 给出的定量边界是本设计的出发点：

1. **固定开销 ≈ +40k tokens/任务**（Skill 调用多一个 turn × 全上下文 cache 重读 + SKILL.md 注入）。
   → 每个正式任务的 baseline 可去除浪费目标 **≥ 80k tokens（≥ 2× 开销）**，
   否则任务无判别力。反推 baseline 总量应落在 **300k–800k** 区间
   （validation 任务只有 150k–200k，几乎没有 slack）。
2. **浪费必须是结构性诱导的，不是指望模型犯错**。validation 证明
   claude-sonnet-5 在小而干净的任务上近乎最优。正式任务必须让
   "不守纪律的默认行为"客观上昂贵：文件大到整读很贵、输出长到不截取很贵、
   探索宽到不委托很贵、陷阱真到不停下很贵。
3. **每条规则至少有 2 个任务能让其 headline 指标产生非零方差**。
   validation 里 R2/R3 指标全程为 0，等于没测。
4. **保留小任务作为对照锚点**，用于在正式批次内重新估计固定开销项
   （而不是沿用 validation 的 +39k 假设）。

## 2. 浪费放大器（任务的构造材料）

每个任务由基础仓库 + 若干放大器组合而成：

| 放大器 | 机制 | 针对规则 | analyzer 现有指标 |
|---|---|---|---|
| **大文件**（400–900 行 × 多个） | 整文件 Read 单次即 5–10k tokens，且随历史每 turn 重复携带 | R1 | reads_with_offset_or_limit、单次工具结果均值 |
| **宽探索面**（症状离病因 ≥3 模块，错误信息指向错误位置） | 主上下文探索读取永久驻留 | R2 | Task calls、subagent tokens、主上下文斜率 |
| **长输出命令**（pytest 全量 >10k 字符、运行脚本 dump 20k 字符日志） | 不 tail/grep 就把整段日志收进上下文 | R1/R4 | long_outputs (>4k chars)、全量套件运行次数 |
| **循环诱饵**（同签名二层 bug、死代码红鲱鱼） | 无新证据的重复尝试 | R3 | repeated_identical_actions、同错误签名最长链 |
| **规模错配**（大仓库里的小修复） | 规划/探索投入不随任务难度缩放 | R4 | 首次 Edit 前 token/turns |
| **机械宽改动**（跨 10+ 文件的一致性修改） | Write 整写、复述未改代码、逐文件长汇报 | R5 | Write-on-existing、output tokens |

## 3. 基础仓库：2 个冻结的合成项目

02 号文件建议"真实项目注入缺陷"，但真实中型 Python 项目普遍带第三方依赖
（verify.sh 需离线 `python3 -m pytest` 自足运行），且无法精确控制文件尺寸
和日志体量。改为 **2 个手工构建的合成项目**，一次授权，多任务复用：

### Repo Alpha —— `storefront`（分层业务后端）
- ~35 个 src 文件 + ~15 个测试文件，~7k LOC，纯 stdlib。
- 分层：`api/ → services/ → domain/ → persistence/ → utils/`，跨层调用链长。
- 刻意包含 4–6 个 **500–900 行的大模块**（如 `services/orders.py`、
  `persistence/serializers.py`），使"整读一个文件"单次成本 5–10k tokens。
- 测试套件 ~200 用例，全量运行输出 >10k 字符（含大量 DeprecationWarning
  与 verbose fixture 日志）；每个模块有对应的窄测试文件可单独运行。
- 用途：深链 bug、跨模块 feature、大仓库小修复、机械宽改动。

### Repo Beta —— `etlkit`（批处理数据管道 CLI）
- ~25 个文件，~4k LOC，纯 stdlib，附带 sample 数据文件。
- 核心特征：`python -m etlkit run samples/...` 一次运行输出 **~20k 字符**
  的逐阶段日志（这是真实管道的常态，不是人为噪音），关键错误行埋在中部。
- 阶段化架构（extract → validate → transform → load），阶段间通过 dict
  契约传数据，适合注入"上游产出缺字段、下游报错"类深链缺陷。
- 用途：长日志调试、二层 bug 循环诱饵。

同仓库多任务的相关性风险：各 trial 是独立 fresh session，无状态泄漏；
任务间的统计相关性在分析时按仓库分组报告即可。收益（授权成本减半、
仓库特征跨任务恒定、便于归因）明显大于代价。

## 4. 任务清单（10 任务 = 2 对照 + 8 正式）

### 对照组（直接复用 validation 任务，零授权成本）

| ID | 复用 | 作用 |
|---|---|---|
| C1 | t1a_daterange | 固定开销锚点：可去除浪费 ≈ 0，skill−baseline 差值即当批固定开销的直接估计 |
| C2 | t1b_slugify | 同上，双锚点降低单点噪声 |

### 正式组（8 个新任务）

| ID | 仓库 | 类型 | 放大器组合 | 主要暴露 | 判别指标（analyzer 现成） |
|---|---|---|---|---|---|
| F1 深链 bug | Alpha | bug fix | 宽探索面 + 大文件。症状：API 层返回错误金额；病因：`persistence/serializers.py` 的精度丢失，中间隔 3 层；traceback 尾部停在 `services/`，指向错误位置 | R1/R2：baseline 预期沿调用链整读 4–6 个大文件（~40–60k）；skill 应搜索定位或委托 | 读取文件数、reads_with_offset_or_limit、Task calls |
| F2 跨切面 feature | Alpha | feature | 宽探索面。新增"价格含税/不含税显示策略"：接口被 9 个模块引用，实际只需改 3 处 + 1 个新函数；找齐调用点是典型 ≥3 文件探索 | R2：是否委托 subagent 收集调用点、只回收结论 | Task calls、subagent tokens、主上下文 turns |
| F3 长日志调试 | Beta | bug fix | 长输出命令。task.md 给出复现命令（20k 字符日志）；关键 ValueError 在日志中部，末尾是无关的清理阶段警告 | R1 日志过滤：baseline 若整段收日志，一次 5k tokens 且随 turn 重复携带 | long_outputs、单次工具结果均值 |
| F4 验证分级 | Alpha | bug fix | 长输出命令 + 窄测试可用。1 个明确 bug；全量 pytest 输出 >10k 字符，对应窄测试文件 0.3k | R4 单测优先：全量套件运行次数、每次验证的 observation 体量 | 全量套件次数（_classify_test_cmd 已支持）、long_outputs |
| F5 二层 bug | Beta | bug fix | 循环诱饵。修复表层 bug 后，同一条命令报**同型异因**的第二个错（相同异常类、相似消息、不同阶段）；不细读会当作"没修好"而反复改第一处 | R3：能否识别"新证据"而非无进展循环 | repeated_identical_actions、同错误签名最长链、失败任务总 token |
| F6 红鲱鱼 | Alpha | bug fix | 循环诱饵。存在一个看似控制该行为的 config 项 + 误导注释，实为死代码；真实病因在别处。改 config 无效 → 是否停止换路 | R3 停止规则 + R1（validation 中 t1b 证明模型能抗单个误导注释，本任务把误导做成"可操作但无效"） | 无进展轮数、repeated_identical_actions |
| F7 大仓库小修复 | Alpha | bug fix | 规模错配。typo 级 bug，失败测试直接点名文件与行为；仓库却有 50 文件。测试规划/探索是否过度 | R4 自适应：baseline 可能因仓库大而先全面探索；skill "先试"应直达 | 首次 Edit 前 turns/tokens、读取文件数 |
| F8 机械宽改动 | Alpha | refactor | 机械宽改动。废弃 `utils.money` 旧 API，全仓 12 处调用点迁移到新签名（变换机械、可 grep 定位） | R5 输出纪律 + R2：Edit 局部改 vs Write 整写；逐文件长汇报 vs 结论式 | Write-on-existing、output tokens、Edit/Write 比 |

覆盖检查（原则 3）：R1←F1/F3/F4；R2←F1/F2/F8；R3←F5/F6；R4←F4/F7；R5←F8（+全任务 output 通道）。每规则 ≥2 任务。

### 陷阱公平性红线（防止复制 v1 事故）

- 所有陷阱必须**在 repo 内、可被正确推理解开**：F5 的第二个错误在细读日志后可明确区分；F6 的死代码可通过追调用链证实。禁止 harness 侧陷阱（stale 缓存、环境差异）。
- task.md 描述在两 arm 完全一致，且不撒谎——可以省略（不说病因在哪），不可误导（不说病因在 config）。误导只允许存在于 repo 内容本身（注释、错误消息措辞），与真实代码库的误导来源同构。
- 授权 checklist：`find repo -name '__pycache__' -o -name '*.pyc'` 必须为空；verify.sh 沿用现有模板（diff 保护 tests/ + 全量 pytest，`-x '__pycache__' -x '*.pyc'`）；F8 的 verify 额外 grep 断言旧 API 调用点清零。

## 5. 实验与统计设计

沿用 01 §4 框架，参数落定：

- **规模**：10 任务 × 2 条件 × 3 runs = 60 trials（模型 claude-sonnet-5，与 validation 可比）。
- **主分析**：按任务配对差值（skill − baseline，run 间取均值），报告
  总 tokens、总 cost（两种口径都报——validation 已证明 cache 定价使两者结论可能相反）。
- **开销校正**：用 C1/C2 估计当批固定开销 δ̂，正式任务报告
  "净效应 = 配对差 − δ̂"，这是 skill 是否 pay off 的 headline 数字。
- **机制分析**：每任务预先登记 1–2 个判别指标（上表最后一列）。
  结论按"指标动了且 token 降了 / 指标动了但被开销吃掉 / 指标没动"三分归因，
  避免只看总量。
- **失败也是数据**：若某任务两 arm 均 FAIL 或均满分且零浪费，标记任务失效，
  不进主分析（但报告）。

## 6. 校准试点（先做，防止全量授权打水漂)

授权全部 8 个正式任务前，先只建 **F1（Alpha 深链）+ F3（Beta 长日志）**
各跑 baseline × 2：

- 通过线：baseline 总 tokens ≥ 300k，且目标浪费行为至少出现 1 次
  （F1 整读 ≥3 个大文件 / F3 收下 ≥1 次 long_output）。
- 若 baseline 在这种规模下依然纪律良好 → skill 假说在该模型上基本可判负，
  以 2 个任务的成本提前止损；写入报告即为有效结论。
- 通过后再完成其余 6 个任务的授权（两个基础仓库此时已建好，边际成本低）。

## 7. 授权顺序

1. 建 Repo Alpha（先写干净版 + 全绿测试套件，再派生任务时注入缺陷）；
2. 建 Repo Beta（同上，重点调校日志体量到 ~20k 字符）;
3. F1、F3 + 校准试点（§6）；
4. 其余 F2/F4–F8 派生（每个 = 复制干净仓库 + 注入缺陷/删除 feature + 写 task.md + verify.sh + 跑 3 遍 verify 确认干净版通过、缺陷版失败）；
5. C1/C2 目录直接从 validation 任务复制。

## 8. 遗留决策

- F5/F6 的陷阱强度只能靠试运行标定：太弱→R3 仍零方差；太强→两 arm 均 FAIL。
  预案：各准备强/弱两档缺陷注入 patch，按校准结果选择。
- 3 runs/cell 对 ±80k 级效应量的检验力足够（validation 单 run 方差目测 <10k），
  但 F5/F6 这类"是否入坑"的二值行为方差大，必要时对这两个任务加到 5 runs。
