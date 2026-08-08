# OpenCode + GLM-5.2 校准试点：F1 deep-chain / F3 long-log（baseline only）

日期：2026-08-06
范围：仅校准，未跑 skill arm，未开始 F2/F4–F8，未修改 skill 与任务设计。
环境：OpenCode 1.18.14 + `zai-coding-plan/glm-5.2`，`run_opencode_experiment.py`（`opencode run --format json --auto --dir <workspace>`），timeout 1200s。
有效数据：`runs/oc_*_occlean{1,2}`（4 runs）。

## 0. 先说两件校准前发现的事

### 0.1 Repo 审计：发现并清除污染

- `f1_deep_chain/repo`、`f3_long_log/repo`、`smoke/repo` 内均残留 `__pycache__`/`.pytest_cache`（共 100+ 文件），全部清除；`repos/alpha_storefront`、`repos/beta_etlkit` 本身干净。
- 冻结初始态核查：diff 任务 repo vs 干净源 repo，差异恰好等于注入 bug（F1：`serializers.py` 的 `int(float(amount)*100)` 精度 bug + 两个测试文件的任务态差异；F3：`numbers.py` `parse_decimal` 丢失 `.replace(",", "")`）。无 agent 修改残留。
- 临时副本上确认 buggy 态：F1 fail 3/122（预期 3）、F3 fail 3/122（含 `test_line_totals`），两任务 `verify.sh` 对 buggy 态均返回 FAIL。**只修复了污染，未动任务设计。**

### 0.2 第一批 4 个 run 全部作废：OpenCode 自动发现了被测 skill

第一批 run（`runs/oc_*_baseline_oc{1,2}`，已就地标记 `CONTAMINATED.md`）的 F3 轨迹里出现了 `skill` 工具调用，输出正是我们的 token-efficient-coding SKILL.md 全文。原因：**OpenCode 1.18.x 会自动发现 `.claude/skills/<name>/SKILL.md` 并作为 skill 工具暴露**（二进制内置行为，含 `~/.claude/skills` 与项目级路径）；workspace 位于项目树内（`experiments/runs/...`），OpenCode 沿目录向上发现了项目级 `.claude/skills/token-efficient-coding`。baseline 被被测干预物污染，且 F3 的两个 run 中 agent 主动调用了它。

修复：改用 `--runs-dir /tmp/oc_cal_runs`（项目树外）重跑 4 个 run，确认轨迹中无 skill 工具调用，结果拷回 `runs/oc_*_occlean*` 存档。**这对后续所有 OpenCode 实验是硬约束：workspace 必须放在项目树外，否则 baseline/skill 操纵失效。**（对 Claude Code arm 无影响——其 skill 发现只在 workspace 自身的 `.claude/skills/`。）

## Results

4/4 PASS。对照组：同任务 Claude Code + Sonnet baseline（`f1_*_p*`、`f3_*_p*`）。

### F1 deep-chain（storefront，56 文件；bug 在 persistence/serializers 三层调用链底部）

| run | verify | grand total | fresh input | output | cache read | cache write | tool calls | Reads (distinct) | long outputs | repeated reads/actions | turns | 首 Edit 前 turns | 测试序列 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| occlean1 | PASS | 136,794 | 16,139 | 1,871 | 118,784 | 0 | 11 | 4 (4) | 4 | 0 / 0 | 8 | 4 | full×3 |
| occlean2 | PASS | 199,668 | 28,910 | 1,926 | 168,832 | 0 | 15 | 9 (9) | 7 | 0 / 0 | 9 | 5 | full×3 |
| *CC p1* | *PASS* | *243,358* | *14* | *1,485* | *204,541* | *37,318* | *6* | *2 (2)* | *1* | *0 / 0* | *7* | — | — |
| *CC p2* | *PASS* | *282,209* | *14* | *1,645* | *253,555* | *26,995* | *6* | *2 (2)* | *3* | *0 / 0* | *7* | — | — |

### F3 long-log（etlkit；诱饵 = 25k-char 运行日志，bug 在 utils/numbers.py）

| run | verify | grand total | fresh input | output | cache read | cache write | tool calls | Reads (distinct) | long outputs | repeated reads/actions | turns | 首 Edit 前 turns | 测试序列 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| occlean1 | PASS | 173,561 | 9,071 | 1,226 | 163,264 | 0 | 15 | 10 (10) | 2 | 0 / 0 | 16 | 12 | full×2 |
| occlean2 | PASS | 160,143 | 15,531 | 3,236 | 141,376 | 0 | 20 | 15 (15) | 4 | 0 / 0 | 10 | 6 | full×2 |
| *CC p1* | *PASS* | *308,178* | *18* | *1,570* | *288,987* | *17,603* | *8* | *2 (2)* | *0* | *0 / 0* | *9* | — | — |
| *CC p2* | *PASS* | *270,898* | *16* | *1,531* | *252,429* | *16,922* | *7* | *2 (2)* | *0* | *0 / 0* | *8* | — | — |

注意口径：跨 CLI 的绝对 token 不可比（模型/系统提示/缓存计价语义都不同；OpenCode `cache_write` 恒 0、`output` 含 reasoning）。可比的是**行为指标**（读取数、long outputs、重复动作、turns）。

## Waste behavior analysis

### 1. 四类目标浪费是否出现？

**大范围读取——出现，两任务皆有，是主要浪费形态。**
- F1 occlean2 读了 9 个文件（102.8k chars 工具输出），其中 `test_api.py`（16.4k）、`test_repositories.py`、`test_carts_service.py`、`conftest.py` 四个测试文件与定位 bug 无必要——失败信息已给出精确断言差；对照 occlean1 只读 4 个文件、Claude Code 只读 2 个。整文件读取无一次使用 offset/limit（`serializers.py` 24.7k chars、`repositories.py` 18k chars 全量拉入）。
- F3 两个 run 分别读 10/15 个文件。occlean2 的 15 个 Read 里有 4 个是目录列举、3 个测试文件、`text.py`（与 bug 无关的邻居模块）；相比之下 Claude Code baseline 只读 2 个文件。**F3 的 sbr（先搜后读率）only 0.0–0.5**，即多数首读没有搜索先导——枚举式浏览而非假设驱动定位。
- 量化（proxy）：F1 两 run 工具输出 53k vs 103k chars，波动 ×1.9 完全由读取宽度驱动；宽读 run 的 grand total 高 46%（137k→200k）。**可回收量级估算**（hypothesis，按 run 间差分）：F1 ~60k tokens、F3 的枚举/测试文件读取 ~10–20k tokens。

**重复读取——未出现。** 8/8 指标为零（repeated_reads=0, repeated_identical_actions=0），与 Claude Code 相同。

**长日志污染——未出现，但诱饵同样未被踩中。** 两个 F3 run 都没有运行 25k-char 的 `etlkit run` 全量日志命令；occlean1 甚至全程没跑它，occlean2 只在修复后跑了一次且自带 `| tail` 截断。**这与 Claude Code 校准的发现一致：F3 的 task.md 提供了 pytest 捷径，诱饵对两个 harness 都没有生效**——不能据此得出"GLM-5.2 抗长日志污染"的结论（inducement 失败 ≠ 行为良好）。
- 但注意 long_outputs 计数 2–7（阈值 4k chars）全部来自**整文件 Read**，不是命令输出——长输出问题在 OpenCode 上换了形态出现（读取侧而非执行侧）。

**Debug loop——未出现。** max_identical_error_repeats=1（8/8），无同错误重试。所有 run 一次 Edit 即修对。唯一的低效重复是 F1 修复后连跑 3 次全量 pytest（Claude Code 跑 1 次）——属于过度验证而非 loop。

### 2. 哪些 Skill v1 规则被自然遵守？

- **R3（进展/止损）**：完全遵守。无循环、无同错重试、一次修对。
- **R1 的"先搜"半条**（仅 F1）：sbr=1.0，先 find/pytest 再读。
- **R5 的编辑纪律**：全部用单次定向 Edit，无整文件重写。

### 3. 哪些规则未被遵守（= skill 的潜在作用空间）？

- **R1 的"少读/精读"半条——系统性违反**：读取宽度 4–15 文件（CC：2），零 offset/limit 使用，读了明确不必要的测试/邻居文件；F3 的 sbr 低至 0.0。
- **R4（投入匹配）——部分违反**：F1 修复后 full suite ×3；F3 occlean1 首 Edit 前 12 turns（CC 全程才 8–9 turns）。测试序列全是 full，从不先跑窄测试。
- **R2（委托探索）——未触发也不可触发**（无子代理机制），与设计预期一致。
- R5 的文本纪律无从评判（输出本来不长）。

### 4. 与 Claude Code 校准的关键对照

| 维度 | Claude Code + Sonnet | OpenCode + GLM-5.2 |
|---|---|---|
| 目标浪费出现次数 | 0（这是早停原因） | **每个 run 都有**（宽读取；F1 occlean2 与 occlean1 差 63k tokens 全是读取差异） |
| 读取纪律 | 2 文件、grep 桥接调用链 | 4–15 文件、枚举式浏览、无精读 |
| run 间方差 | 小（同任务 ±16%） | 大（F1 ±37%），纪律不稳定本身就是浪费来源 |
| 结构成本占比 | cache read 84–94% | cache read 87–94%（同样主导，但这里 fresh input 也有 9k–29k 的实质体量） |

## Decision

**A：继续 OpenCode benchmark（进入 skill arm），有条件。**

预登记通过线的对照检查（design/03 §6 移植）：
- "baseline ≥300k"：**未达**（137k–200k）——但该线是按 Claude Code 的 token 口径定的（其 cache_write 计费、系统提示更大），跨 CLI 直接套用不合理；改按行为线判断。
- "目标浪费 ≥1 次/run"：**达标，4/4**（宽读取 + 过度验证），且 run 间差分给出的可回收量（F1 ~60k）与每 turn ~1k 的 AGENTS.md 开销相比，量级余地充足（smoke 实测 skill 开销 +14k 且含毛刺 turn）。

与 Claude Code 校准形成干净对比：同一批任务，一个 harness 零浪费早停，另一个 harness 4/4 出现 R1/R4 违反——这正是"policy 有效性随 harness 而异"重构问题所需要的第二个数据点。

**条件/下一步（按序）：**
1. skill arm 只跑 F1+F3 ×2（8 run 决策，仍不是 full benchmark）：检验 AGENTS.md 注入能否把读取宽度压向 CC 水平（预登记指标：distinct_files_read、fresh input、grand total、PASS 率不降）。
2. R2 在 OpenCode arm 预登记为不可测（无子代理归因），从评分中剔除。
3. 所有后续 run 必须 `--runs-dir` 指到项目树外（§0.2 的 skill 自发现污染），建议把该防护直接写进 runner 默认值。
4. F2/F4–F8 是否建造，等 F1+F3 的 skill arm 结果再定——若 skill 连最明确的宽读取都压不动，建更多放大器任务没有意义。

**不选 B 的理由**：B 的前提（"baseline 已接近最优"）被 4/4 的宽读取证据直接否定。GLM-5.2 baseline 在 R3（止损）上接近最优，但在 R1 读取纪律上留有 CC 对照下 2–7 倍的宽度、几十 k tokens 的可回收空间。

## 附：本次数据的局限

- n=2/任务，run 间方差大（F1 ±37%），skill arm 对比需要至少 ×2 并报告区间而非点估计。
- F3 长日志诱饵对两个 harness 都未生效（task.md 捷径），"长输出污染"维度在当前任务集上不可测；若重构问题要覆盖该维度，需修任务（校准分析里已记录的 verifiability-vs-inducement 冲突），本次未动。
- OpenCode `output_tokens` 含 reasoning、`cache_write` 恒 0：与 CC 的 token 口径差异已在 analyzer 文档注明，所有跨 arm 表格只比行为指标。
