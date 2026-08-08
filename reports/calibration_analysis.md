# Calibration Analysis: 为什么 F1/F3 中 skill 没有 token reduction 空间

日期：2026-08-06
数据来源：validation v2（5 任务 × 2 条件，`experiments/results_summary.md`）、
校准试点 F1/F3（baseline ×2，`experiments/runs/f1_*_p*`、`f3_*_p*`）。
环境：Claude Code headless（`claude -p`）+ `claude-sonnet-5`，fresh session per trial。

**一句话结论**：F1/F3 没有出现 skill 可回收的浪费，不是因为放大器不存在，
而是因为 baseline（harness + model 的默认行为）已经实现了 Skill v1 五条规则
所要求的几乎全部纪律；剩余 token 消耗的 84–94% 是"高效轨迹本身的逐轮上下文
重发"，这属于 harness/定价层的结构成本，用户级 skill 无法触及。

---

## 1. 全部实验结果汇总

### 1.1 主表（14 runs）

"input tokens" 指非缓存 fresh input（Claude Code 计费口径下该字段极小，
真正的输入体量在 cache read/write，见 §1.2）。

| task | condition | success | total tokens | input tokens | output tokens | tool calls |
|------|-----------|---------|-------------:|-------------:|--------------:|-----------:|
| t1a_daterange | baseline | PASS | 156,117 | 10 | 654 | 4 |
| t1a_daterange | skill | PASS | 195,351 | 11 | 664 | 5 |
| t1b_slugify | baseline | PASS | 156,553 | 10 | 524 | 4 |
| t1b_slugify | skill | PASS | 196,487 | 11 | 709 | 5 |
| t2a_ledger | baseline | PASS | 192,064 | 12 | 829 | 8 |
| t2a_ledger | skill | PASS | 232,053 | 13 | 1,011 | 7 |
| t2b_eventbus | baseline | PASS | 200,489 | 12 | 1,943 | 9 |
| t2b_eventbus | skill | PASS | 237,842 | 13 | 1,621 | 8 |
| t3a_pipeline | baseline | PASS | 191,487 | 12 | 949 | 5 |
| t3a_pipeline | skill | PASS | 271,590 | 15 | 1,429 | 8 |
| f1_deep_chain (p1) | baseline | PASS | 243,358 | 14 | 1,485 | 6 |
| f1_deep_chain (p2) | baseline | PASS | 282,209 | 14 | 1,645 | 6 |
| f3_long_log (p1) | baseline | PASS | 308,178 | 18 | 1,570 | 8 |
| f3_long_log (p2) | baseline | PASS | 270,898 | 16 | 1,531 | 7 |

F1/F3 没有 skill 条件的 run：按 design/03 §6 的预登记方案，校准试点只跑
baseline ×2，先检查"通过线"（baseline ≥300k 且目标浪费 ≥1 次）再决定是否
授权 skill arm 与其余任务。通过线未达标（见 §2），skill arm 依规未启动。

### 1.2 Token 构成分解（为什么 "input tokens" 一列没有信息量）

| run | cache read | cache write | cache read / total |
|---|---:|---:|---:|
| t1a baseline | 142,776 | 12,677 | 91.5% |
| t3a skill | 253,455 | 16,691 | 93.3% |
| f1 p1 | 204,541 | 37,318 | 84.0% |
| f1 p2 | 253,555 | 26,995 | 89.8% |
| f3 p1 | 288,987 | 17,603 | 93.8% |
| f3 p2 | 252,429 | 16,922 | 93.2% |

所有 run 的 grand total 中 84–94% 是 cache read——即"整段历史每 turn 原样
重发（以缓存价）"。这不是行为浪费，而是多轮 agent 的结构成本：它随
**turn 数 × 当时上下文长度** 增长。skill 能影响的只有 turn 数和每 turn 收进
来的 observation 体量；而 baseline 的 turn 数已经在 6–9、observation 已经
被主动裁剪（§2），所以没有下降空间，反而 Skill 调用本身多一个 turn，
造成 validation 中稳定的 +37–40k（t3a 因多 2 turns 达 +80k）。

配对差值（skill − baseline，validation v2）：
t1a **+39,234**；t1b **+39,934**；t2a **+39,989**；t2b **+37,353**；t3a **+80,103**。
质量两 arm 均 10/10 PASS，无质量差可交换。

---

## 2. Baseline 为什么没有出现预期浪费：逐项轨迹证据

以下每一项引用具体 run 的工具调用序列（transcript.jsonl 提取）。

### 2.1 Excessive file reading —— 未出现（这是 F1 的主放大器）

F1 的设计预期是"沿 api→services→persistence 调用链整读 4–6 个大文件
（~40–60k tokens）"。实际两个 run 都只读了 **2 个文件**，且路径完全同构：

```
f1 p1:  find *.py → Read money.py (158 行, 6,669 chars)
        → grep -rn "float|from_decimal_string|Decimal(" storefront/
        → Read serializers.py [offset=1 limit=100]   ← 688 行大文件只读了 100 行
        → Edit → pytest | tail -20
f1 p2:  同构；serializers.py 用 [offset=55 limit=40] 只读 40 行（1,367 chars）
```

两个关键细节：
- **大文件放大器被 offset/limit 拆弹**。`serializers.py` 有 688 行（整读约
  7–8k tokens），但 p1 只取前 100 行、p2 grep 到行号后只取 40 行。
  `reads_with_offset_or_limit` = 1/1（占该 run Read 调用的 50%）。
- **3 层调用链被一次 grep 跨过**。p1 的推理文本显示假设驱动的定位：先猜
  `money.py`（读后排除），grep float/Decimal 模式直接命中
  `serializers.py:86` 的 `int(float(rec["amount"]) * 100)`。调用链从未被逐层
  走过。

对照组唯一一次真正的多余读取在 validation：t2a baseline 读了 4 个文件，
其中 `models.py`、`test_ledger.py` 与修复无关；skill arm 同任务只读 2 个。
这是全部 14 个 run 中 skill 规则唯一可见的正向效果，量级约 2–3 次读取
（几 k tokens），比固定开销小一个数量级。

### 2.2 Repeated reads —— 全程为 0

14 个 run 的 `repeated_reads` 全部为 0。没有任何一个文件被读第二次。

### 2.3 Long command outputs —— F3 的主放大器完全未触发；F1 有偶发但小

**F3（关键证据）**：任务提供了 20k+ 字符日志的复现命令
（`python3 -m etlkit run samples/...`，实测 25,405 chars，关键 WARNING 在
中部第 97 行/共 252 行）。两个 run 的 Bash 调用全列表：

```
f3 p1:  find | sort (869c) → pytest | tail -80 (3,199c)
        → grep LUX-5001 samples/orders_july.csv (515c)
        → grep -rn parse_decimal (1,330c) → pytest | tail -20 (179c)
f3 p2:  同构，少一次 grep
```

**agent 从头到尾没有运行那条日志命令**——task.md 同时给出了
`pytest tests/ -q` 作为复现（3 failures），agent 直接选了更窄的证据源，
且每条 pytest 都自带 `| tail -N`。`long_outputs` = 0/0。25k 字符的放大器
建在那里，但 baseline 绕开了它。

**F1 需要如实修正**：p2 的 `long_outputs` = 3，其中一次
`grep -rn "float|...|amount" storefront/` 没加 `| head`，收进 **17,959 chars**
（约 4.5k tokens）——这是 4 个 pilot run 中唯一一次真正的 R1 违规。但它
(a) 单次、未重复，(b) 量级 ~5k tokens，远小于 +40k 的 skill 固定开销，
(c) 预登记通过线针对的是"整读 ≥3 个大文件"，未达成。p1 的 1 次 long output
是整读 `money.py`（6,669 chars，158 行的小文件，Skill 规则本身豁免
<100 行、这里也仅略超）。

### 2.4 Debugging loops —— 未出现

全部 run：`repeated_identical_actions` = 0，`max_identical_error_repeats` ≤ 1，
每个 run 恰好 **1 次 Edit、一次通过**。F1/F3 的 `test_sequence` 是
`[full]` 或 `[full, full]`（后者 = 修复前复现 + 修复后确认，属必要验证而非
循环）。R3（停止规则）在 14 个 run 中从未获得触发条件。

### 2.5 Excessive planning —— 未出现

`turns_before_first_edit`：F1 均为 4、F3 为 5–6（其中含复现测试），与仓库
规模无关——validation 的 5–8 文件小仓库是 2–3，56 文件的 Alpha 也只是 4。
没有 plan mode、没有 TODO 列表、没有前置全仓浏览；assistant 全程文本输出
505–1,645 chars（f3 p1 仅 505）。规模错配诱导的"先全面探索"没有发生：
f1 p1 的第一条命令 `find . -name "*.py" | grep -v test | head -5` 甚至
自带 `head -5`。

### 2.6 Unnecessary edits —— 未出现

全部 run：`Write` on existing files = 0，每 run 恰好 1 次 `Edit`（局部
string replacement），改动即最小修复（F1：一行 float 转换改
`Money.from_decimal_string`；F3：`parse_decimal` 补 `.replace(",", "")`）。
无复述未改代码、无逐文件汇报。

### 2.7 小结：五规则的"违规余量"实测

| Skill 规则 | 预期浪费 | F1/F3 baseline 实测 | 可回收量 |
|---|---|---|---:|
| R1 最小读取/过滤输出 | 整读大文件、收长日志 | offset/limit 主动使用；自发 `\| tail`；1 次 18k grep 疏漏 | ~5k |
| R2 委托探索 | 主上下文宽探索 | 探索 = 1 次 find + 1–2 次 grep，无可委托面 | 0 |
| R3 停止规则 | 无进展循环 | 全部一次修复通过 | 0 |
| R4 自适应规划/验证 | 过度规划、全量重跑 | 首编辑前 4–6 turns；pytest 全部自截断 | ≈0 |
| R5 输出纪律 | 长汇报、整写文件 | 输出 0.5–1.6k chars；0 次 Write | 0 |

合计可回收 ≈5k tokens/run，对比 skill 固定开销 ≈40k：**期望净效应约 −35k，
方向在实验前就已注定**。这正是 validation 结论（"固定开销 > 可去除浪费"）
在 2–3 倍规模任务上的复现。

---

## 3. 是不是 Claude Code + Sonnet 组合本身已经 token-efficient？

### 3.1 本实验内的直接证据

上面 §2 的行为不是任务侥幸，而是跨 14 个 run、两个仓库、三档规模的稳定
模式：search-before-read rate 恒为 1.0；管道级 `| tail` 出现在**每一条**
测试命令上（baseline 无任何提示的情况下）；offset/limit 精确到 grep 命中的
行号邻域。这些恰好是 SKILL.md Rule 1/4 的原文要求——baseline 的行为像是
"已经内置了这份 skill"。

两个来源无法从本实验区分但都存在：
- **Harness 层**：Claude Code 的系统提示与工具设计本身鼓励 Grep/Glob 定位、
  Read 支持 offset/limit、工具结果有截断机制，且全上下文走 prompt cache。
- **模型层**：claude-sonnet-5 显然在 agentic 轨迹上训练过——自发
  `2>&1 | tail -N`、假设驱动 grep、"succeed fast" 的单次修复，这些是
  策略性行为而非工具被动特性。

### 3.2 对照 literature：浪费证据都测在什么 setup 上

关键事实：**文献中最强的浪费定量证据全部来自非 Claude Code 的 scaffold**
（详见 `literature/02/04/05`）：

| 浪费模式 | 文献证据 | 测量 setup | 与本实验的对照 |
|---|---|---|---|
| 读取占 token 67.5–76.1% | SWE-Pruner (2601.16746) | **Mini-SWE-Agent / OpenHands**，多为整文件读取 | 本实验读取被 offset/limit + grep 压到 2 文件/run |
| 重复查看/修改同一文件与高成本显著相关；"失败拖得久" | How Agents Spend (2604.22750)；SWE-agent (2405.15793) | **OpenHands**（2026，frontier 模型）；**SWE-agent + GPT-4 Turbo**（2024） | repeated_reads=0；无失败轨迹 |
| 通信税/整段代码重传 | Tokenomics (2601.14470) | **ChatDev + GPT-5 Reasoning**（角色扮演多 agent） | 单 agent，不适用 |
| 静态分解重试成本 +80.5% | Runtime-Structured (2605.15425) | 受控 workload，模拟失败 | 无分解、无重试 |

文献里被这些论文当作"待部署缓解措施"的机制——observation 折叠、简洁工具
反馈、输出截断、guardrails（SWE-agent ACI 原则；`literature/03` 的 L2
"需要 Harness 支持配置"清单）——在 Claude Code 里已经是出厂配置。也就是说
**Skill v1 五条规则针对的浪费清单，很大程度上是从"较弱 scaffold 的实测浪费"
推导出来的，而目标环境已经吸收了其中大部分**。

两条重要的反向证据，防止过度声明：
1. How Agents Spend 明确指出**即使有缓存，累计输入仍主导总成本**——本实验
   的 84–94% cache read 占比正是这个现象。现代 harness 解决的是"行为浪费"
   （多余读取、循环），**没有解决"结构重发"**——后者只能靠减 turn 数、
   context editing/压缩或定价，全部在用户级 skill 的作用范围之外。
2. SkillsBench (2602.12670) 在 18 个 model–harness 组合（含 Claude Code）上
   发现 skill 对 **token 的影响方向本就不定（有升有降）**，且 ad-hoc
   自写 skill 在 3 个 harness 上**差于无 skill baseline**。我们的负结果与
   该文献分布一致，不是异常值。

### 3.3 哪些浪费模式可以认为"已被现代组合解决"

基于本实验 + 文献 setup 对照的判断（限定 Claude Code + claude-sonnet-5）：

- **已解决（本实验 0 出现）**：整文件盲读、重复读取、无截断收取测试/构建
  输出、无进展重试循环、整写文件式编辑、与任务规模无关的固定重规划。
- **偶发残留（小量级）**：未加 `head` 的宽 grep（f1 p2 一次 ~5k）；略超
  阈值的小文件整读。合计 <5% 总量。
- **未解决、但 skill 也无法解决**：逐轮全上下文重发（84–94% 的成本主体）。
- **本实验无法判定**：真正宽探索面（≥10 文件收集类任务，F2/F8 未建）、
  强循环诱饵下的行为（F5/F6 未建）。这些留作 open question，但见 §4——
  即使建了，判别力也存疑。

---

## 4. Benchmark design 分析：任务不够难，还是 baseline 太强？

两者都有成分，但**主因是 baseline 太强，且二者在此环境下互相锁死**。
需要分开陈述：

### 4.1 "任务不够难"的成分：两个可指认的设计缺陷

1. **失败测试名泄露病因位置（F1）**。F1 的 5 个 failures 分布在
   `test_api.py` 和 `test_serializers.py`——后者的文件名直接把 3 层调用链
   压缩成了一次 pytest 输出。设计意图"traceback 尾部停在 services/、指向
   错误位置"没有实现：宽探索放大器被测试套件自身短路。
2. **给了绕过长日志的复现捷径（F3）**。task.md 写了
   "`python3 -m pytest tests/ -q` reproduces the problem (3 failures)"，
   agent 于是完全没碰 25k 字符的日志命令。放大器建成了，但任务卡给了一条
   更便宜的旁路。

这两个缺陷有共同根源：**可验证性与可诱导性冲突**。holdout verify 需要
确定性测试套件；而测试套件（名字、失败消息、断言文本）本身就是最高效的
定位信号。只要 task.md 承诺 "all tests pass" 是验收标准，理性的 agent
就会先跑测试——测试一跑，大部分探索放大器就失效。

### 4.2 "baseline 太强"的成分：即使修掉上述缺陷，纪律本身仍在

区分的关键证据是：**即使在放大器实际接触到 agent 的地方，纪律依然生效**。
- f1 两个 run 都真实打开了 688 行的大文件——但用 offset/limit 只取了
  100/40 行。这与"没遇到大文件"不同：遇到了，没浪费。
- f3 两个 run 的每条命令（包括第一次复现）都自带 `| tail`。这不是因为
  日志可绕过，而是无条件习惯——它对任何长输出源都会生效。
- 探索是假设驱动的（先猜 money.py，grep 验证），不是穷举式的。就算测试名
  不泄露，一次 `grep -rn "amount"` 也会命中 serializers.py（f1 p2 的 grep
  实际就返回了它）。

所以修复 4.1 的缺陷（去掉 pytest 捷径、让测试名不指向病因）预计只会增加
1–2 次 grep 和一次日志过滤读取（agent 大概率 `grep ERROR log` 而不是整读
25k）——量级仍是几 k，远够不到 40k 开销线。

### 4.3 判定与含义

**判定：baseline 强是主因**——它的纪律在被放大器实际接触时依然成立；
任务缺陷只是让这一点显现得更快、更干净。继续加难任务（去掉测试复现、
症状只在日志里、跨 10 文件收集类）在逻辑上可行，但存在方法论上限：

> 当"能让 baseline 浪费"成为任务的设计目标时，benchmark 测的就不再是
> "skill 在真实任务分布上的收益"，而是"我们能否构造出击败默认纪律的
> corner case"。即使构造成功，其结论也无法外推。

这就是 design/03 §6 预登记 early-stop 的原意，本次触发是按规则执行。

---

## 5. Revised conclusion

### 问题："Can user-level skill reduce token usage?"

实验支持的回答分三层：

**（1）user-level skill 能改变行为——这被证实了。**
validation v2 中 skill arm 在 t2a/t2b 上确实减少了文件读取（4→2、5→3），
方向与规则预测一致。skill 不是被忽略的死文本。

**（2）但在本环境中，行为改变没有可兑换的 token 空间。**
Claude Code + claude-sonnet-5 的 baseline 在 150k–310k 规模的单因 bug 修复
任务上，可回收浪费实测 ≈0–5k tokens/run（14 个 run 的一致结果），而 skill
的结构性固定开销 ≈+40k（Skill 调用多一个 turn × 全上下文缓存重读 + SKILL.md
注入）。**开销/收益 ≈ 8:1，净效应必然为负**。token 总量的 84–94% 是逐轮
上下文重发，这部分不由行为决定，skill 原则上不可触及。

**（3）结论的适用边界（这不是"skill failed"的普遍声明）。**
文献对照表明浪费高度依赖 setup：同类浪费在 Mini-SWE-Agent/OpenHands/
ChatDev 上真实存在且量大（读取占 67–76%、失败拖长、通信税）。因此正确的
表述是：

> **在 harness 与模型已经内置强 token 纪律的环境（Claude Code +
> claude-sonnet-5）中，提示层的效率规则是冗余的：它能规范的行为已经是
> 默认行为，它不能触及的成本（逐轮重发）才是成本主体，而它自身的调用
> 开销使净效应稳定为负（token 口径 +37–80k/任务；美元口径因缓存定价
> 减轻至 +$0.01–0.04，但符号不变）。skill 若要 pay off，需要以下至少
> 一项：更弱的 harness/模型、真实存在宽探索或循环的任务类别、或把规则
> 从"每任务注入的提示"降为"零边际成本的 harness 默认值"。**

这个负结果与 SkillsBench 的大样本发现（skill 的 token 效应在 Claude Code
上方向不定、ad-hoc skill 常为净负）互相印证，且是通过预登记通过线提前
止损得出的——它是本项目方法论有效性的证据，而非失败。

### 若继续，值得做的（按信息价值排序）

1. **换弱环境复测**（同一 skill、同一任务、较弱模型或最小 scaffold）：
   直接检验 §3 的归因——若弱环境下 skill 转正，"环境已内置纪律"的解释成立。
2. **harness 级验证**：把 R1/R4 写进系统配置（如 output 截断阈值、默认
   tail），以零 per-task 开销测同样的规则——分离"规则价值"与"注入成本"。
3. F2/F8（宽收集类）作为最后一个未测象限，但预期判别力低（§4.3）。
