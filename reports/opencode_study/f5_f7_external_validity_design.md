# F5/F7 外部效度实验设计（预注册）

日期：2026-08-07
状态：任务已建成，校准前预注册

## 1. 动机

20v20 主结果（`00_FINAL_REPORT.md`）确认 Skill v1 在 OpenCode + GLM-5.2 上
−19.1% (p=0.0094)，但外部效度只有 F1/F3 两个 R1 靶向任务，且归因分析表明
效应全部走 R1 读取通道。本实验回答两个问题：

- **Q1（前置）**：OpenCode baseline 在 R3/R4 靶向任务上有没有可回收浪费？
  F1/F3 校准显示 baseline 零循环零重读，但那两个任务不诱发循环——需要
  专门设陷阱的任务来测。
- **Q2**：full Skill v1 在非 R1 场景是帮忙、中性、还是净负
  （R1 的"先搜后读"在 typo 级修复上可能是纯开销）？

R1-only ablation 被有意跳过：在 F1/F3 上其余四规则无作用机制，ablation
结果几乎预定（见 2026-08-07 讨论）；降级为发表前置项。

## 2. 任务

### F7 大仓库小修复（R4 靶向）

- 仓库：alpha_storefront（54 文件，8.4k 行），干净版全绿。
- 注入：`storefront/utils/text.py` `slugify()` 的 `strip("-")` → `lstrip("-")`。
- 失败签名：2 个失败测试，`test_utils.py::test_slugify_*`，assertion diff
  直接显示 `'hello-' != 'hello'`；task.md 点名症状与函数级行为。
- 陷阱：仓库规模（54 文件）与修复规模（1 字符）错配。测 baseline 是否
  因仓库大而先全面探索。
- 判别指标：**首次 Edit 前的 turns / tokens / distinct files read**。

### F5 二层 bug（R3 靶向）

- 仓库：beta_etlkit（35 文件），干净版全绿。
- 注入（两处同型缺陷，绕过 `parse_decimal` 的逗号容忍）：
  1. `etlkit/rules.py` `rule_type` decimal 分支 → `float(str(value).strip().lstrip("$"))`
  2. `etlkit/ops.py` `op_cast` decimal 分支 → 同上
- 陷阱机制（已实测）：修掉第 1 处后重跑同一命令，loaded 仍 61、LUX 仍
  全被拒、错误消息**一字不差**（`could not convert string to float: '1,204.50'`），
  仅发作阶段 validate→transform（日志中 `rejected by type` vs
  `rejected by op cast`）。不细读日志会判为"没修好"而循环改第 1 处。
- 公平性：两处缺陷都在 repo 内、grep `float(` 可同时定位；细读日志可
  明确区分两层。无 harness 侧陷阱。
- 判别指标：**同错误签名最长链、repeated_identical_actions、修复第 1 处
  后到识别第 2 处之间的 turns/tokens**。
- 陷阱强度预案（蓝图 §8）：当前为"强"档（同消息不同阶段）。若校准发现
  两臂全挂，弱档 = 把第 2 处的消息改得更可分辨；若零方差（人人直达
  grep 全修），记录为任务失效。

### 验证（两任务均三遍检查通过）

broken 版 FAIL / 正确修复版 PASS / 篡改 tests 无效（verify.sh 冻结测试
holdout，沿用 F1/F3 模板）；`__pycache__`/`.pyc` 清零。

## 3. 协议

沿用 20v20 主实验协议，全部不变：runner `run_opencode_experiment.py`、
GLM-5.2 (Z.ai)、workspace 在项目树外、skill 注入 = workspace `AGENTS.md`
（两臂 prompt 相同）、analyzer schema 不变。

## 4. 决策关卡（预注册）

**校准**：baseline × 4 runs/任务（共 8）。

- **F7 关卡**：baseline 首次 Edit 前 reads 中位数 ≥4 文件 或 首 Edit 前
  tokens 占总量 ≥40% → 有 R4 浪费，继续 skill 臂；否则记录
  "OpenCode 在规模错配下无过度探索"为负结果，F7 不扩样。
- **F5 关卡**：baseline ≥2/4 runs 出现"入坑"（修第 1 处后 ≥2 次无进展
  重试/重复编辑同一文件）→ 有 R3 浪费，继续；0–1/4 入坑 → 记录
  "GLM-5.2 能自发区分两层"为负结果，不扩样。
- 两臂均 FAIL ≥2/4 → 陷阱过强，启用弱档重校准（仅 F5 预期可能触发）。

**扩样**（过关卡后）：skill 臂 4 runs 校准行为，然后两臂各补到 8–10
（F5 入坑行为二值方差大，按蓝图必要时加到每臂 10+）。检验：单侧
permutation，主指标 = 总 tokens；机制指标按上表预登记。

## 5. 预测（登记在先）

- F7：baseline 中度过度探索（读 4–8 文件——F1 校准显示 OpenCode 有枚举
  式浏览习惯，失败测试点名文件可能压制它）；skill 若有效走 reads 通道，
  幅度小于 F1（可省面小）；skill 最坏情形 = 注入费 + 多余"先搜"，净负。
- F5：不确定性真正所在。GLM-5.2 在 F1/F3 无循环行为，但那里没有循环
  诱饵；此处二值入坑。若 baseline 入坑率 ≥50%，skill 的 R3（"新证据"
  识别）第一次有作用对象。
- 任一"无浪费"负结果都直接写入外部效度结论：skill 的适用面 = R1 场景，
  其余规则在 OpenCode 上无对象。

## 6. 文件

- `experiments/tasks/f7_bigrepo_smallfix/`（task.md / verify.sh / repo）
- `experiments/tasks/f5_two_layer/`（同上）
- 数据将写入 `experiments/runs_f5f7/`
