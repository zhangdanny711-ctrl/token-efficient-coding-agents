# Rule 1（先搜后读/最小读取）的 token 贡献分析

日期：2026-08-06
数据：无新实验。Claude Code validation（5 任务 ×2×2）、OpenCode clean 8v8（F1/F3）、batching ablation 24 run。合计 64 个 run，其中 OpenCode 40 个用于回归分解。
方法：读取量直接从轨迹提取（read 工具输出 chars，callID 去重）；跨 run 回归分解 turns 与读取量对总量的独立贡献;两 harness 分别核算。

## TL;DR

**R1 是全项目唯一被两套证据（行为 + 回归）支持的真实 token 杠杆，但它的经济价值完全取决于 harness 成本函数：在 OpenCode/GLM（全价重发）上贡献约 −21k tok/run（≈总量的 11%），方向可靠；在 Claude Code/Sonnet（缓存计价 + baseline 已内化）上贡献为零甚至为负。结论：选项 A 成立但必须加 harness 条件——R1 保留为核心规则，其"token-saving"声明限定于弱纪律 harness。**

## 1. Token attribution（R1 省了什么）

### OpenCode 8v8（skill 的读取效应几乎全部来自 R1——五规则中只有 R1 管读取)

| 量 | baseline | skill | Δ |
|---|---:|---:|---:|
| distinct reads | 8.6 | 5.0 | −3.6（p=0.012） |
| read 输出 chars | 45,734 | 28,790 | **−16,945（−37%）** |
| 全部观察 chars | 50,700 | 34,740 | −15,960（读取占 Δ 的 106%——其他观察略增） |
| fresh input tok | 16,718 | 14,201 | −2,517 |
| cache read tok | 160,968 | 143,200 | −17,768 |
| grand | 179,644 | 159,265 | −20,379 |

链条自洽：**少读的 ~17k chars（≈4.2k tok 直接摄入）通过逐 turn 重发放大**。粗放大器（obs × 剩余turns/2 ≈ ×5.7）给出 ~24k；40-run 回归给出更严谨的数字——

**回归分解（n=40，R²=0.904）**：`grand = 0.902·turns + 0.603·read_chars`（标准化），原始系数 **+1 turn ≈ 14.8k tok，+1k read_chars ≈ 1.22k tok**。按 R1 实际压掉的 16.9k chars 计,**控制 turn 数后 R1 贡献 ≈ −20.7k tok/run（baseline 的 11.5%）**。与 8v8 的原始差（−20.4k）几乎重合——即 OpenCode 上 skill 的全部 token 效应可由 R1 的读取通道解释。

### Claude Code（对照:同一规则、不同经济学）

t2a/t2b 是 CC 侧唯一读取下降的任务（Read 4→2、5→3），但 grand +40k：读取省下的观察量在缓存计价下本来就便宜,而 skill 调用多出的 1 turn（cache read +38k）远超省量。CC 的 R1 台账:**读取通道收益 ≈ 每 turn 观察量的边际缓存价 ≈ 忽略不计；被 skill 机制的 turn 开销直接淹没**。

## 2. Counter-effects（R1 引入了什么成本）

三个候选反效应逐一核查（OpenCode 8v8 + 40-run 回归）：

- **额外 turns？没有。** skill turns 10.4 vs baseline 11.4（还略低）;40 run 上 turns 与 read_chars 相关 r=−0.25——**少读并不以多 turn 为代价**,两维度接近独立（这是 R1 在 OpenCode 上净收益为正的关键:它只动小桶,没碰大桶的坏方向）。
- **额外 cache 重发？没有。** cache read 随读取下降（−17.8k）,因为重发的就是历史观察本身。
- **更长轨迹？没有。** 唯一的正向成本是 AGENTS.md 常驻 ~1k tok/turn ×10 turns ≈ 10k/run 的注入开销——已含在 −20.4k 净差里（即 R1 毛效应 ≈ −30k,注入费 ≈ +10k）。CC 侧则相反:注入机制费 40k,毛效应 ≈ 0,净 −40k。

**反效应结论:R1 本身无内生反效应;所有反效应来自注入机制,且随 harness 剧烈变号。**

## 3. Task-level heterogeneity

| 任务 | 读取形态 | R1 效应 |
|---|---|---|
| OC F1（深链代码探索,大文件 7–25k chars） | baseline 读 6.8 文件 65.9k chars | skill −22.4k chars、grand −23.2k。**单文件贵 → 每少读一个文件都值钱** |
| OC F3（日志/数据侦查,小文件 0.2–4.4k） | baseline 读 10.5 文件但仅 25.6k chars | skill 读数减半（10.5→5.8）但 chars 只省 11.5k;grand −17.6k 更多来自 turns −1.8。**文件小 → R1 的"少读几个"不值钱,值钱的是它顺带避免的枚举式 turn** |
| CC t2a/t2b（中型代码任务） | Read 4–5→2–3 | 读取通道 ≈0（缓存价）,净负（机制费） |
| CC t1a/t3a（小任务） | baseline 已只读 1–2 文件 | 无空间,t3a skill 反而多读多 turn |
| batching ablation（无 R1 注入的 24 run） | control/treatment reads 8.6/9.1 | 佐证:没有 R1 时读取宽度回到 baseline 水平——8v8 的读取压缩确系 R1 所为,不是环境漂移 |

**异质性规律：R1 的价值 ∝ 单位读取的 chars × harness 重发价格。** 大文件 + 全价重发（OC F1）是最优场景;小文件任务里 R1 主要是行为整形（防枚举浏览）;缓存深折扣 harness（CC）里读取通道无经济意义。

## 4. Research decision：A / B / C

**推荐:A（保留为核心规则）,但重写其声明为条件式;拒绝 B 的降级和 C 的移除。**

- **反对 C（移除）**：R1 是 64 个 run 里唯一同时满足 (i) 行为效应显著（p=0.012）、(ii) 有独立回归通道（+1k chars ≈ 1.2k tok, 控制 turns 后 −20.7k/run）、(iii) 无内生反效应、(iv) 质量零损（PASS 全保）的规则。项目里没有"更高杠杆的维度"可聚焦——粒度维度已被 batching ablation 证明弱可控无经济效果,结构维度不可控。移除 R1 等于放弃唯一坐实的杠杆。
- **反对 B（降级为安全/生产力规则）**：B 的前提是"R1 不省 token"——这只在 Claude Code 上成立。OpenCode 上 −11%/run 是回归支持的真实节省,且 GLM 类"弱纪律 + 全价重发"配置正是 token 效率问题实际存在的地方（CC 上问题本来就不存在）。在问题存在的域内,R1 是省 token 的;把它降级是让 CC 的特例否决了普适域的证据。
- **A 的必要修正**：R1 的文档必须写明作用域——"**R1 的 token 收益依赖两个条件:(1) baseline 缺读取纪律（可用 5-run 校准检出）,(2) harness 对历史重发计全价或高价。二者都不满足时（如 Claude Code + Sonnet）,R1 无害但注入机制的固定开销会使 skill 整体净负——此时不应部署 skill 而非修改 R1**"。这同时是最终报告的核心论点:规则本身跨 harness 有效,规则的*经济性*是 harness 属性。

### 决策依据一览

| 判据 | OpenCode/GLM | Claude Code/Sonnet |
|---|---|---|
| R1 行为可注入 | ✅ p=0.012 | ✅（t2a/t2b）但 baseline 已基本内化 |
| R1 token 通道 | ✅ −20.7k/run（11.5%）,回归独立 | ❌ ≈0（缓存价） |
| 反效应 | 注入费 ~10k/run,净 −20k | 注入费 ~40k/run,净 −40k |
| 结论 | **核心规则,名副其实** | 无害规则,skill 整体不应部署 |

## 局限

- 回归是观察性的（40 run 非随机分配 read_chars）,系数解释为"关联分解"而非因果;但 8v8 的臂间随机对比给了因果锚点,二者数值吻合（−20.4k vs −20.7k）。
- chars→tokens 用 ~4:1 粗折算,仅用于叙述;所有结论性数字来自 token 字段本身。
- CC 侧读取通道"≈0"基于缓存计价的报账口径;若以 API 原价计,CC 的读取节省也有正值——但那不是用户支付的价格。
- F3 的 R1 效应与 turn 效应部分共线（枚举式浏览既多读也多 turn）,分层里 −17.6k 中读取通道占比按回归系数折 ~40%,其余经 turn 通道——R1 在 F3 的贡献有一部分是"防枚举"的间接产物,归因边界在报告正文已标注。
