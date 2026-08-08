# 难度带质量权衡实验 — 预注册设计

日期:2026-08-07。状态:**预注册,校准 gate 前冻结**。

## 1. 动机

生态效度批次(`reports/eco_validity_study/02_results.md`)48/48 全 PASS——天花板效应使该批次
**无法检测**技能导致的质量损失。机制风险真实存在:R1"少读"可能让需要多文件上下文的难 bug
信息饥饿 → baseline 能修、skill 修不了。本实验把任务难度推进到 baseline 有真实失败率的区间,
直接测量两 arm 的 pass-rate 差。

## 2. 任务(3 个,来自 alternates 池最难档,均已两向机械验证)

| id | 库 | 源 commit | 内容 | 池内评级 |
|---|---|---|---|---|
| H1 | toolz (~3.7k LOC) | 5a7e078c (2025-10) | `partition_all` 假 `__len__` → 需在哨兵切片逻辑里推导 off-by-one 检测并 raise LookupError;正确修复非显然(`prev[end-1] is no_pad or prev[end] is not no_pad`) | B2, MED-HARD |
| H2 | boltons (~17k LOC) | 8a2a93d8 (2026-05) | `ParsedException.from_string` 截断 traceback IndexError;**2-hunk 修复**——已手工验证单 guard 浅修(只改 while 条件)仍 FAIL,第二处 `line_no+1` 越界必须同时修 | B3, MEDIUM |
| H3 | dateutil (~7.6k LOC) | **合成**:B1 34906dc (分隔符一致性状态机 +9/−5) + B13 424a438b (T24:00 翻转,3 处修) | 单文件 isoparser.py 内两个独立 bug,6 个测试失败;B1 需重写 `_parse_isotime` 分隔符处理且不破坏 559 个既有回归测试 | B1 MODERATE + B13 MODERATE 合成 |

构建方式:parent snapshot + fix-commit 测试(H3 = B1-parent 快照 + 手工回注 B13 bug +
34906dc 的测试文件,买回两 bug 同存;两向验证 6 failed → 0 failed)。环境:py3.13 系统解释器,
hypothesis+freezegun 本次已装(dateutil 全套需要),wcwidth 保持缺席;H1 verify 需带 tlz shim;
H3 删除 test/property/(hypothesis 版本兼容噪声)与 test_internals.py(py3.13 既有失败,与
bug 无关);H1 删除 test_package.py(pip metadata 既有失败)。

## 3. 协议

- Runner:`run_opencode_experiment.py` 不改,模型 zai-coding-plan/glm-5.2,workspace 在
  /tmp/oc_hard_runs(项目树外,防 .claude/skills 自动发现)。
- **校准 gate(倒置)**:每任务 baseline ×4。**要求出现失败**——4/4 全 PASS = 任务太容易,
  换/合成更难的;0/4 全 FAIL = 太难,同样换。目标带:两 arm 合并 pass-rate 落在 50–80%。
- 主批:过 gate 的任务扩容到 **8–10 runs/arm/task**(校准 runs 计入 baseline arm),
  两 arm 交错执行(抗 API 漂移)。总量 ≈ 3 任务 × 2 arm × 8–10 ≈ 48–60 runs。
- PASS 判定:verify.sh(冻结测试 holdout)exit 0,与此前所有批次一致。

## 4. 预注册终点与解释矩阵

**主终点**:per-task pass-rate 差(skill − baseline),Fisher 精确检验;pooled 用
Mantel-Haenszel 分层。**副终点**:token 总量(仅在 PASS 子集内比较 + 全样本各报一次)、
失败 run 的 token 消耗(假经济检查:失败 run 烧掉的 token 是纯损失)。

| 结果 | 解释 | 行动 |
|---|---|---|
| pass-rate 无差 + tokens 仍显著更低 | 技能在难任务上也不牺牲质量 | 升级主张:"−36% 且难度带内质量无损" |
| **skill 败得更多** | R1 信息饥饿实锤 | 主张改写为"−X% token 以 Y% pass 为代价";补失败 run token 浪费分析 |
| skill 败得更少 | 聚焦收益(少读→少分心) | 作为次要正向发现报告 |
| 两 arm 都全 PASS(gate 漏判) | 天花板未破 | 该任务从主分析剔除,只报 token |

**功效说明(诚实)**:n=8–10/arm 的 Fisher 检验只能探测很大的 pass-rate 差
(如 9/10 vs 4/10);中小差异检测不足。本实验定位为"排除大质量损失 + 方向估计",
不是精确效应量估计。预注册预测:**无大差异**(F7/eco 系列中 skill arm 从未出现
baseline 能过而 skill 挂掉的模式),但这正是需要检验的。

## 4a. 修订 v2(2026-08-07,校准 gate 触发,预注册允许的分支)

**v1 gate 结果:12/12 baseline 全 PASS——三个任务全部太容易**(H3 烧到 383k–777k tokens
但两 bug 都修掉;GLM-5.2 有失败测试锚点时,即使状态机重写也能靠迭代通过)。按预注册
"all-pass → 换/合成更难" 分支,升级为 **v2:去掉失败测试锚点**:

- workspace 内测试改为 **parent 版本**(H1/H2:buggy 状态下全绿;H3:只有 defect 1 的
  5 个失败可见,defect 2 仅 xfail 标记)。
- verify.sh 的 holdout 改为 **fix-commit 版测试**(`holdout/` 目录,workspace 中不存在)。
- task.md 给出**行为规格 + 复现片段**(说明验收测试是隐藏的、workspace 测试通过≠完成),
  两 arm 完全一致。
- 难度机制:从"迭代修红测试"变为"按规格实现 + 不破坏回归"——agent 无法用红测试
  确认修对,必须从规格推导正确行为(H1 的 LookupError 判据、H2 的第二处越界、
  H3 的 defect 2 无锚点)。
- v1 校准 runs 归档至 runs 目录 `v1_cal/` 子目录,不计入任何 arm(协议变更)。
- v2 两向验证:3/3 buggy=FAIL、fixed=PASS;倒置 gate 重新跑 baseline ×4/任务。

## 4b. 修订 v3(2026-08-07,v2 gate 再次 all-pass 触发)

**v2 gate 结果:12/12 baseline 全 PASS**(H1 263k–681k;H2 204k–518k;H3 521k–985k)。
诊断:v2 task.md 的"复现片段"= 可执行 oracle,agent 直接把它变成本地测试迭代到绿。
**v3:去掉复现片段**,症状只用散文描述(用户报告口吻),保留"验收测试是隐藏的"通告;
H1 保留 LookupError 要求(holdout 判定精确异常类型,不给会变成猜谜)。两 arm 仍完全一致。
v2 校准 runs 归档 `v2_cal/`。**预算约束(新增)**:v3 gate 若仍 all-pass,不再继续加难度——
终止判定为"该任务族(可挖掘单-commit 真实 bug + 全回归套件)内,GLM-5.2/OpenCode baseline
处于质量天花板,50–80% 目标带不可达",此时以 v3 12 校准 runs + 已有 48 eco runs 为证据,
写"质量损失上界只能弱约束"的诚实结论,主批不扩容。

## 5. 泄漏/难度自评

- H1:task.md 必须说明"应 raise LookupError"(verify 测试要求精确异常类型,不说明会把
  验收变成猜谜)。难度在哨兵切片的正确判据,不在定位。泄漏 HIGH、修复难度 HARD。
- H2:测试名 `test_parsed_exc_truncated` 泄漏场景;难度在发现第二处越界(浅修过不了
  frozen test,已验证)。
- H3:6 个失败测试都指向 isoparser.py;难度在状态机重写的回归压力(559 个邻近测试)+
  双 bug 需都修。task.md 明说两个缺陷(症状层面),不给修法。
