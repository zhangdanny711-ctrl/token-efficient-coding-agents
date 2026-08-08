# 生态效度 Benchmark — 结果报告

日期:2026-08-07。运行:48 runs(6 任务 × 2 arm × 4 runs),全部 PASS(48/48)。
模型 zai-coding-plan/glm-5.2,OpenCode 1.18.14,workspaces /tmp/oc_eco_runs(项目树外),
metrics+transcripts 归档 `experiments/runs_eco_validity/`。
任务清单见 `01_candidate_list.md`;任务目录 `experiments/tasks/eco_*`。

## 0. 设计要点(与既往批次的差异)

- 任务 = **真实 OSS 历史 bug**(tinydb×2、tabulate、boltons、more-itertools、funcy),
  由 fix commit 反转构建:repo = parent commit 快照 + fix commit 的新测试(在 repo 内失败),
  verify.sh = 冻结测试 holdout。**无人工浪费放大器,无作者之手**(task.md 只改写 commit/issue 的症状描述)。
- 预注册预测(memory 2026-08-07):效应从实验室 −19.1% **收缩**到 −5%~−15%。
- 校准 gate:baseline ×2 先行,12/12 PASS,各任务均有可省表面(宽读 2–7 文件、重复读、
  turn 方差),无 F5 式逃逸 → 直接扩容(+2 baseline、+4 skill,B/S 交错防漂移)。
- E2 的 test_textwrapper.py 在 py3.13 下有 2 个与 bug 无关的既有失败(textwrap 行为变化)
  → 构建时从任务 repo 删除该文件(等价于环境修正,不触及目标 bug 的测试)。

## 1. 主结果

**预注册预测被推翻——方向正确但幅度错误:效应不缩反增。**

| 任务 | 库/bug | base 中位 | skill 中位 | Δ% | reads b→s | turns b→s |
|---|---|---|---|---|---|---|
| E1 | tinydb 重开跳号 | 140,667 | 80,374 | **−42.9%** | 4.5→1.0 | 8→6 |
| E2 | tabulate SEPARATING_LINE | 960,826 | 848,743 | −11.7% | 2.0→2.5 | 38→34 |
| E4 | boltons OMD.__eq__ ×2 模块 | 126,485 | 56,340 | **−55.5%** | 2.5→1.0 | 10→6 |
| E5 | tinydb 空库 len() | 110,848 | 70,320 | **−36.6%** | 3.5→1.0 | 8→8 |
| E6 | more-itertools sliced 负 n | 79,643 | 60,331 | **−24.2%** | 2.0→1.5 | 8→6 |
| E7 | funcy autocurry 元数据 | 243,531 | 131,537 | **−46.0%** | 5.5→3.0 | 18→10 |

- **方向一致性 6/6**(每个任务 skill 中位数都低于 baseline)。
- **分层置换检验(任务内 shuffle,统计量 = 各任务中位数 δ 的均值):−36.1%,p = 0.0003**。
- reads:3.5 → 1.8(−49%,p = 0.0001)——与 20v20(−43%)、F7(−50%)完全同带。
- 质量:48/48 PASS,两 arm 无差。

汇总口径说明:pooled 中位 −46.3%;pooled **均值**只 −14.3% 且 p=0.36,原因是 E2 一个任务
贡献了全部长尾(见 §2)——去掉 E2 后 pooled 均值 −44.0% p=0.0003。分层统计量(每任务
等权)是预注册协议的既定主口径,不受单任务票选权重扭曲。

## 2. E2:一个诚实的失效案例(与信息量最大的一个)

E2(tabulate)是唯一效应弱的任务(−11.7%,且两 arm 分布重叠):

- 8 个 run 全部 turn 爆炸(16–53 turns,199k–1.64M tokens),两 arm 无差。
- 行为剖面独特:reads 恒为 2(单文件库,读纪律无空间),但 repeated_reads 8–14、
  bash 10–27 次——成本在**反复 grep/重读同一个 3k 行文件 + 反复跑测试**,不在宽读。
- 这正是 R1 攻击面之外的浪费形态(turn 通道)——与 R1 归因分析的结论
  (r1only 只 −7%,残差在 turn 通道)以及批处理消融的"结构性 per-turn 成本提示词不可控"
  完全互相印证。**大单文件 + 行为型 bug(无 traceback)= 技能盲区**,这是一个
  有预测力的边界刻画,不是噪声。

## 3. 结论

1. **实验室→真实任务,技能效果不衰减**:自建放大器任务 −19.1%(20v20),真实历史 bug
   −36.1%(分层)/每任务中位 −24%~−56%。原怀疑的"author-circularity 抬高效应"不成立——
   反而低估了。机制:真实小库任务的探索面(多文件、README、docs)天然比我们 50 文件
   合成仓库上的 F7 型任务大,R1 的可省表面更大。
2. **收缩预测错在哪**:预注册把"无放大器"等同于"可省浪费少",但真实仓库自带的
   杂物(docs/、CHANGELOG、多模块布局)本身就是放大器。
3. **边界条件**(E2):单大文件 + 行为型 bug → 读通道无空间,浪费全在 turn 通道 →
   技能无效但无害(两 arm 打平,质量不损)。与"无条件启用"结论兼容。
4. 证据链最后一环闭合:**lab-effective → practice-effective**(单模型 GLM-5.2、
   单 harness OpenCode 范围内)。

## 4. 文件与复现

- 任务:`experiments/tasks/eco_{e1_tinydb_nextid,e2_tabulate_sepline,e4_boltons_omdeq,e5_tinydb_emptylen,e6_moreit_sliced,e7_funcy_autocurry}/`
  (repo + task.md + verify.sh;双向验证 buggy=FAIL/fixed=PASS 已确认)。
- 运行:`bash /tmp/oc_eco_runs/run_calibration.sh` / `run_expansion.sh`(已存档于 runs 目录说明)。
- 归档:`experiments/runs_eco_validity/`(48 × metrics.json + transcript.ndjson)。
- 环境注记:tinydb 任务 pytest 需 `-o addopts=""`(或装 pytest-cov,本机已装);
  运行环境不得安装 wcwidth(tabulate 旧版死循环);机器已装 `whatever`(funcy 测试依赖)。
- 备选池:23 个已验证候选(`01_candidate_list.md` §2)可直接扩容。

## 5. 剩余工作

- 把本报告并入 `00_FINAL_REPORT.md`(§3.8 + 修订 §5 限制),然后做 CC+OC 公开报告合并
  (原清单唯一剩项)。
