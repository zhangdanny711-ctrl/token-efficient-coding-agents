# Literature Review

## Scope

The project began with a scoping review of 44 papers and technical reports on coding-agent cost, context selection, early termination, adaptive planning, repository-level code generation, prompt compression, and agent skills. Eighteen sources were read as core evidence; the remainder supplied methods, boundary cases, or evaluation context.

The review searched arXiv, ACL Anthology, OpenReview, official conference pages, and author project pages. It used backward and forward citation chaining and does not claim to be exhaustive.

## Evidence that shaped the intervention

| Finding | Evidence | Design implication |
|---|---|---|
| File reads and accumulated observations dominate many coding-agent trajectories | [How Do AI Agents Spend Your Money?](https://arxiv.org/abs/2604.22750), [SWE-Pruner](https://arxiv.org/abs/2601.16746) | Search before reading; inspect task-relevant ranges; constrain long output |
| More tokens and longer trajectories do not guarantee success | [SWE-agent](https://arxiv.org/abs/2405.15793), [EET](https://arxiv.org/abs/2601.05777) | Track progress and stop paths that produce no new evidence |
| Task-relevant, structure-preserving pruning can reduce token use without reducing quality | [SWE-Pruner](https://arxiv.org/abs/2601.16746), [RepoCoder](https://arxiv.org/abs/2303.12570), [CoCoGen](https://aclanthology.org/2024.findings-acl.138/) | Prefer narrow retrieval over generic text compression |
| Static decomposition can increase cost through cascaded retries | [Runtime-Structured Task Decomposition](https://arxiv.org/abs/2605.15425) | Delegate or decompose only when the search space warrants the overhead |
| Planning is most valuable when triggered by failure or complexity | [PaT](https://aclanthology.org/2026.acl-long.1703/), [Reason-Code](https://aclanthology.org/2026.acl-industry.30/) | Use direct execution for local tasks and escalate planning adaptively |
| Skills improve average task quality but have heterogeneous token effects across harnesses | [SkillsBench](https://arxiv.org/abs/2602.12670) | Count skill injection overhead and evaluate each harness separately |
| Skill packages themselves can become context-heavy | [SkillReducer](https://arxiv.org/abs/2603.29919) | Keep the always-loaded policy concise and progressively disclose optional material |
| Real-world skill retrieval is sensitive to relevance and refinement quality | [How Well Do Agentic Skills Work in the Wild](https://arxiv.org/abs/2604.04323) | Release one narrowly scoped skill rather than a broad skill library |

## Core reading list

1. [How Do AI Agents Spend Your Money?](https://arxiv.org/abs/2604.22750)
2. [Tokenomics](https://arxiv.org/abs/2601.14470)
3. [EET](https://arxiv.org/abs/2601.05777)
4. [SWE-Pruner](https://arxiv.org/abs/2601.16746)
5. [Runtime-Structured Task Decomposition](https://arxiv.org/abs/2605.15425)
6. [PaT](https://aclanthology.org/2026.acl-long.1703/)
7. [Reason-Code](https://aclanthology.org/2026.acl-industry.30/)
8. [SWE-agent](https://arxiv.org/abs/2405.15793)
9. [Agentless](https://arxiv.org/abs/2407.01489)
10. [PatchPilot](https://arxiv.org/abs/2502.02747)
11. [RepoCoder](https://arxiv.org/abs/2303.12570)
12. [CoCoGen](https://aclanthology.org/2024.findings-acl.138/)
13. [HULA](https://arxiv.org/abs/2411.12924)
14. [What Makes a GitHub Issue Ready for Copilot?](https://arxiv.org/abs/2512.21426)
15. [Ambig-SWE](https://arxiv.org/abs/2502.13069)
16. [SkillsBench](https://arxiv.org/abs/2602.12670)
17. [SkillReducer](https://arxiv.org/abs/2603.29919)
18. [How Well Do Agentic Skills Work in the Wild](https://arxiv.org/abs/2604.04323)

## Mapping evidence to the five rules

### Rule 1: minimal context acquisition

This is the most directly supported rule. SWE-Pruner reports that line-level, task-aware pruning can reduce tokens while preserving code structure, and several repository-level systems show that targeted retrieval outperforms dumping a full codebase into context. The rule translates this evidence into search-before-read, bounded reads, no unchanged re-reads, and constrained command output.

### Rule 2: delegated exploration

Multi-agent and decomposition studies show mixed cost results. Delegation can reduce the main agent's context, but communication and duplicated exploration can erase the gain. The rule therefore activates only for genuinely wide questions and asks for a conclusion rather than file dumps.

### Rule 3: progress-aware stopping

Early-termination evidence shows that unsuccessful trajectories often consume large budgets without proportional success gains. The rule uses observable progress—new errors, eliminated hypotheses, newly passing tests—rather than a fixed turn cap.

### Rule 4: adaptive effort

Planning and expensive verification should be conditional. Local tasks use locate–fix–verify directly; failures, cross-module changes, public APIs, or migration risk trigger explicit planning and wider tests.

### Rule 5: output discipline

Agent output and tool observations become future input. Targeted edits, short progress messages, and concise final reports reduce context growth without changing the implemented solution.

## Research gap

Prior work demonstrates that token waste exists and that middleware can prune context, but it does not establish that a user-authored prompt policy will deliver the same savings in a modern coding harness. SkillsBench further shows that skill effects vary across model–harness combinations. This project therefore focuses on a narrower empirical question: how much waste is reachable from a portable prompt-level policy, and under what baseline conditions does policy overhead exceed the waste it removes?

## Evaluation caution

Many coding-agent studies rely on public SWE-bench variants whose tasks, patches, and tests have been widely exposed. An OpenAI audit also documents contamination and test-quality concerns: [Why SWE-bench Verified no longer measures frontier coding capabilities](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/).

This project does not use leaderboard scores as evidence of general model capability. It relies on within-task treatment comparisons, mechanically reconstructed historical bugs, fixed verification, and explicit reporting of contaminated runs.
