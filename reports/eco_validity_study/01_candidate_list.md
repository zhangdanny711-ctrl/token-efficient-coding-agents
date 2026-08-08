# 生态效度 Benchmark — 候选任务清单（用户评审版）

日期:2026-08-07。状态:**待用户评审**——按预注册流程,本清单确认后才开始构建任务。

## 0. 挖矿方法与产出总览

6 个并行挖矿 agent,7 个 pytest 生态纯 Python 库,每个候选都经过**机械验证**
(parent commit + 覆盖 fix commit 的测试 → 必须 FAIL;再覆盖源码 fix → 必须 PASS),
不通过者已丢弃(dateutil 1 个、funcy/toolz 1 个、tinydb 1 个被验证淘汰)。
共 **26 个验证通过的候选**。scratch clone 全部留在 `/tmp/eco_mining/`。

| 库 | 源码 LOC | 布局 | 环境负担 | 验证候选数 |
|---|---|---|---|---|
| boltons | 17,212 | 平铺多模块,零依赖,root 可 import | 无 | 5 |
| more-itertools | 7,187(more.py 5,560)| 平铺,零依赖 | 无 | 6 |
| dateutil | ~7,640 | 平铺(候选年代),需要 install | **重**:py3.12 上需 `-p no:warnings`,依赖 six | 5 |
| tabulate | 2,7–3k 单文件 | 平铺单模块 | 轻:不能装 wcwidth(旧版死循环) | 5 |
| tinydb | 2,249 | 平铺 8 模块 | 轻:pytest.ini 要求 pytest-cov(或 `-o addopts=""`) | 5 |
| toolz | ~3,700 | 平铺 | 旧 parent 有 py3.12 兼容尾巴 | 2 |
| funcy | ~2,380 | 平铺,tests/ 独立目录 | 测试依赖 `whatever` | 3 |

任务格式沿用 F7 模板:workspace = parent commit 源码 + fix commit 的新测试(在
workspace 内可复现失败);verify.sh = 冻结测试对 agent 源码的 holdout;task.md 用
commit message/issue 改写症状描述,两 arm 完全一致。

## 1. 推荐主选(8 个,难度/形态谱系覆盖)

按推荐优先级排序。"泄漏"= 测试名/traceback 对 bug 位置的提示强度(泄漏低 → 探索面大 → 技能作用面大)。

### E1. tinydb — 重开库后文档 ID 跳号(6a84ca9c,2020-05,#314)★跨模块金牌
- 修复:`table.py::_get_next_id` +6/−3;测试在 `test_tinydb.py`,名字不提 table/ID 逻辑。
- 症状:无 traceback,只有计数断言错;需要推理 `_next_id` 缓存跨 reopen 的状态。
- 泄漏 LOW,难度 MEDIUM-HARD。**全清单里最像"真实调试"的任务。**

### E2. tabulate — SEPARATING_LINE 在列填充下失效(af40a322,2022-12,#231)
- 修复:单文件 ~2.7k 行内 `_is_separating_line` +7/−2;行为错(渲染差异),无 traceback。
- 需要理解 padding 为何击穿相等性判断;测试名只泄漏特性名,3k 行单文件内定位靠 grep/细读。
- 泄漏 MEDIUM,难度 MODERATE。**大文件读纪律(R1)的天然靶场。**

### E3. dateutil — `tz.gettz("")` 返回 None(bd69e8e9,2020-04,#925)
- 修复:1,900 行 tz.py 内嵌套闭包里 1 行 truthiness;无 traceback。
- 泄漏:文件级 HIGH 但行级需要真读;难度 MODERATE。
- ⚠️ 环境负担最重(见 §3);若嫌麻烦可降级为备选。

### E4. boltons — OrderedMultiDict.__eq__ 值比较被丢弃(c463d163,2026-06)★跨模块
- 修复:dictutils.py 与 urlutils.py 各 +2/−1(同一类被复制两份);只修一处则 test_urlutils 仍红。
- agent 必须发现 17k LOC 仓库里的跨模块代码复制;静默逻辑错(表达式求值后丢结果)。
- 泄漏 MEDIUM,难度 MEDIUM。**唯一的"修复面本身跨模块"候选。**

### E5. tinydb — 空库 len() 崩溃(1cc77cbc,2020-04,#307)★跨模块金牌
- 修复:table.py `__len__` +3;测试在 test_tinydb.py,泄漏 LOW(有 traceback 但要跨 db→table 委托链)。
- 难度 EASY-MEDIUM。做谱系下端、又不像 F7 那样测试直接点名文件。

### E6. more-itertools — sliced() 负 n 静默截断(958990e2,2026-07)
- 修复:more.py(5,560 行)+3;静默错误输出而非崩溃。
- 泄漏 HIGH(类-函数命名约定),但 5.5k 行单文件内导航是真实成本;难度 EASY-MEDIUM。

### E7. funcy — autocurry 丢失函数元数据(60910f8e,2022-04,PR#117)
- 修复:funcs.py +2/−1(@wraps 放置在递归闭包里不显然);无 traceback(`__doc__` is None)。
- tests/ 独立目录 → 泄漏 MEDIUM-LOW;难度 MEDIUM。小库对照(2.4k LOC,探索面小)。

### E8. tabulate — maxcolwidths 下 bool 字符串崩溃(d29909b4,2025-03,#305)
- 修复:+1/−7;有 traceback 但"正确修法 = 删掉类型重建机制"与浅补丁(特判 bool)不同。
- 泄漏 MEDIUM,难度 EASY-MODERATE。⚠️ workspace 禁装 wcwidth(旧 parent 的 #399 死循环)。

**谱系检查**:难度 1×MEDIUM-HARD / 3×MEDIUM / 2×EASY-MEDIUM / 2×EASY侧;症状 5 无 traceback vs 3 有;
仓库大小 17k/7.6k/5.5k/3k/2.2k/2.4k;跨模块 3 个;库不重复超过 2 次。

## 2. 备选池(候补/替换用,已验证)

| id | 库 | commit | 内容 | 难度 | 备注 |
|---|---|---|---|---|---|
| B1 | dateutil | 34906dc | isoparse 分隔符一致性,+9/−5 状态机 | MODERATE | 565 个既有测试的回归压力,修复本身最有含金量 |
| B2 | toolz | 5a7e078c | partition_all 假 __len__,哨兵切片 | MED-HARD | 2025 commit,parent 全绿 |
| B3 | boltons | 8a2a93d8 | ParsedException 截断 traceback IndexError,2 hunk | MEDIUM | 单 guard 浅修可能过新测试,需检查 verify 是否足够判别 |
| B4 | more-itertools | be5793a5 | gray_product/partial_product 迭代器×repeat 别名 | MEDIUM | 双函数同型修复 |
| B5 | tinydb | 770486ff | Query.test 不可哈希参数 | MEDIUM | 多个可行修复点,verify 接受单文件修 |
| B6 | boltons | 766b5547 | bytes2human 1024 边界 | EASY-MED | 静默错值,1.3k 行模块 |
| B7 | funcy | a96b449e | cache.invalidate 幂等 | EASY | 地板任务/校准用 |
| B8 | dateutil | 79d2e486 | parse("0-100") TypeError | EASY | 泄漏 MEDIUM |
| B9 | tabulate | 20c6370d | 空数据+maxcolwidths 崩溃,两处修 | EASY | 与 B10 是四年后的孪生 bug,二选一 |
| B10 | tabulate | 87a9a4e0 | 空表+maxheadercolwidths | TRIVIAL | 2026-03 commit |
| B11 | more-itertools | cca32949 | last() 的 `__reversed__ = None` 哨兵 | EASY-MED | hasattr→getattr 惯用法 |
| B12 | more-itertools | f51a53bf | interleave_evenly([]) IndexError | EASY | |
| B13 | dateutil | 424a438b | T24:00 日期翻转语义 | MODERATE | 2018,多 hunk |
| B14 | funcy | 6c111987 | throttle(timedelta) 未绑定方法 | EASY | |
| B15 | more-itertools | edb3346f | numeric_range 空 reversed | EASY-MED | |
| B16 | boltons | ead236e2 | backoff_iter factor=1.0 除零 | EASY-MED | |
| B17 | more-itertools | cf186b5d | product_index 迭代器 len | EASY | |
| B18 | toolz | a69f8a5c | accumulate 空序列 PEP479 | EASY-MED | parent 有 5 个 py3.12 无关失败,verify 需限 scope |
| B19 | tinydb | dcf0a013 | LRUCache falsy 值 | EASY | 与 B20 同一函数,二选一 |
| B20 | tinydb | 781fb6ca | LRUCache 更新不写值 | EASY | |
| B21 | boltons | c1c25da3 | Bits 长度 off-by-one | EASY | |
| B22 | tabulate | 92cb7096 | intfmt 字符串数字崩溃 | EASY | |
| B23 | dateutil | 5cf3e3cb | parse_isodate 错误消息 bytes repr | TRIVIAL | |

## 3. 环境与协议注意事项(建任务前要定的)

1. **dateutil 特殊性**:py3.12+ 上 import 即触发 DeprecationWarning,而 setup.cfg 把它升级为 error →
   所有 pytest 都要 `-p no:warnings`;还需要 six。选它就要接受 workspace 预装依赖 + verify.sh 加参数,
   或者干脆从主选降级(E3→B1 也一样受影响)。**建议:主选保留 E3 但准备好一键替换为 B4/B2。**
2. **tabulate**:运行环境**不装 wcwidth**即可,零成本。
3. **tinydb**:pytest.ini 有 `--cov` addopts → 系统装一个 pytest-cov(或 verify/说明里统一 `-o addopts=""`)。
4. **测试内注释/文档字符串**可能引用 issue 号(如 more-itertools B11 链到 #1001)——构建时保持原样
   (自然任务的一部分)还是剥离?**建议保持原样**,GLM 若真能利用 issue 号也是生态效度的一部分。
5. **2026 年 commit**(boltons 全部、more-itertools 前两个、B10)大概率在 GLM-5.2 训练截止之后 →
   污染风险最低;2020–2022 的候选可能在训练集里,但污染对两 arm 对称(既有结论)。
6. 运行协议不变:baseline 校准(×2/任务)→ 浪费 gate → 双 arm 扩容;workspace 在 /tmp(项目树外)。
   预注册预测不变:效应收缩到 −5%~−15%。

## 4. 廉价补充:alpha/beta 仓库上的非 bugfix 任务(已踩点)

- **F2 特性添加**(alpha):"含税价显示策略"。踩点确认:`PriceBreakdown.as_dict()`(pricing.py)、
  `order_summary` handler、reports.py 的 decimal-string 约定都在,接口被 9+ 模块引用而实改 3 处的
  结构成立。需要写 holdout 测试(新特性无既有测试)——这是与 bugfix 任务的关键差异,verify.sh
  要新写冻结验收测试。
- **F8 机械重构**(alpha):Money 旧 API 迁移。踩点:`add/sub/mul/percent` 源内调用点约 33 处、
  跨 6 文件;设计里"废弃旧签名 → 新签名"的机械变换可行,verify = 冻结测试 + grep 断言旧调用清零。
  ⚠️ tests/ 也大量用旧 API——若旧 API 彻底删除,冻结测试本身会失败,所以变换须保持向后兼容
  (旧方法保留为废弃 wrapper),或 verify 用改写后的冻结测试(引入作者之手)。**倾向前者。**

## 5. 建议的评审决定点

1. 主选 8 个(E1–E8)是否认可?特别是 dateutil(E3)要不要为环境负担让位给 B1/B2?
2. 规模:8 个真实 bug + F2 + F8 = 10 任务 × 2 arm × 4 runs ≈ 80 runs(~12–16M tokens,
   与 20v20 一批相当)?还是先 6 任务起步?
3. F2/F8 是否要做(F2 的 holdout 测试要新写,作者之手最重;F8 次之)?
4. 测试内 issue 引用保持原样的决定是否同意?
