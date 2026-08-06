# TASK merge & TRX port — bilingual speaker notes / 中英对照演讲词

*Companion to `2026-06-30-merge-trx-beamer.tex` (15 slides). For each slide: a short bilingual
explanation of what it shows, then a natural spoken speaker script in English and Chinese.*

*本文件配合 `2026-06-30-merge-trx-beamer.tex`(15 页)使用。每页给出:该页展示内容的中英简要说明,
再给出自然口语的英文与中文演讲词。中英内容对照,可任选一种语言讲述。*

Last updated 2026-06-30. Deck tip `e7789b92`; delivered P0 baseline `d1f7f9e7` (CI green, 736 passed).

---

## Slide 1 · Title page — Merging upstream bpsi into a modernized TASK fork and consolidating trx->tr

**Explanation / 说明**

- **EN** — The title slide: an engineering report on merging Kyoto's upstream bpsi line into the modernized kyoshimi TASK fork (P0, delivered) and porting trx's fusion physics into tr (P1, in progress).
- **中** — 标题页:一份工程报告,内容是把京都大学上游 bpsi 主线合并进现代化的 kyoshimi TASK 分支(P0,已交付),并把 trx 的聚变物理移植进 tr(P1,进行中)。

**Speaker script / 演讲词**

> **English.** Good afternoon everyone. Today I'll walk you through an engineering effort on the TASK plasma-transport stack that had two parts: first, merging the upstream Kyoto development line, which we call bpsi, into our modernized fork, and second, consolidating the older transport module trx back into the main tr module. The first part, the merge and baseline, is already delivered with green CI; the fusion port is currently in progress. I'll focus as much on the lessons learned as on the result.

> **中文.** 各位下午好。今天我要向大家介绍在 TASK 等离子体输运代码上做的一项工程工作,它分为两部分:第一,把京都大学的上游开发主线——我们称为 bpsi——合并进我们现代化的分支;第二,把较旧的输运模块 trx 整合回主 tr 模块。第一部分,也就是合并和基线,已经交付并且 CI 全绿;聚变物理的移植目前还在进行中。我会把重点既放在结果上,也放在其中学到的经验教训上。

---

## Slide 2 · Outline

**Explanation / 说明**

- **EN** — The table of contents, listing the talk's sections: Background, Motivation, P0 the merge, Validation, the tot_ht6m case study, P1 TRX-to-tr, and finally Results and roadmap.
- **中** — 目录页,列出报告各章节:背景、动机、P0 合并、验证、tot_ht6m 案例研究、P1 TRX 到 tr,以及最后的成果与路线图。

**Speaker script / 演讲词**

> **English.** Here's the roadmap for the talk. I'll start with the background — three git lines that had drifted apart — and the motivation for unifying them. Then P0, the actual merge and how we got CI green for the first time, including a case study on the tot_ht6m equilibrium solver. Finally P1, the fusion physics port from trx into tr, and where the whole modernization effort is headed.

> **中文.** 这是本次报告的大纲。我会先讲背景——三条已经彼此分叉的 git 主线——以及统一它们的动机。然后是 P0,也就是实际的合并过程,以及我们如何第一次让 CI 变绿,其中包括一个关于 tot_ht6m 平衡求解器的案例研究。最后是 P1,把聚变物理从 trx 移植进 tr,以及整个现代化工作的未来方向。

---

## Slide 3 · Background: three git lines that had drifted apart

**Explanation / 说明**

- **EN** — Introduces TASK as a Fortran tokamak transport stack and the three git lines that had diverged: bpsi (Kyoto main dev, the base), kyoshimi-develop (the Phase-L modernization fork), and ats-fukuyama (a stale 2023 GitHub backup); it also defines Phase-L and states the goal of one reliable baseline.
- **中** — 介绍 TASK 是一套 Fortran 托卡马克输运代码,以及三条已分叉的 git 主线:bpsi(京都主开发线,作为合并基底)、kyoshimi-develop(Phase-L 现代化分支)、ats-fukuyama(2023 年的过时 GitHub 备份);同时给出 Phase-L 的定义和“一个可靠基线”的目标。

**Speaker script / 演讲词**

> **English.** TASK is a Fortran tokamak transport stack — equilibrium, transport, Fokker-Planck, wave modules, and a tot orchestrator. Over time three git lines had drifted apart. bpsi is the Kyoto main development line, carrying the latest physics and bug-fixes, so it's our merge base. kyoshimi-develop is a fork of bpsi at commit 8eed6fc2 that carries what we call the Phase-L modernization — F90-ification, per-module C-ABI shared libraries with Python wrappers and MCP servers, and splitting trcomm into six sub-modules. The third line, ats-fukuyama, is just a stale 2023 GitHub backup, read-only. Our goal was to unify the GitHub-hosted fork line (kyoshimi-develop) and the Kyoto bpsi line into a single, CI-validated baseline that different developers can safely branch from, and then make tr the one canonical transport module.

> **中文.** TASK 是一套 Fortran 托卡马克输运代码——包括平衡、输运、Fokker-Planck、波模块,以及一个 tot 协调器。随着时间推移,三条 git 主线彼此分叉了。bpsi 是京都的主开发线,承载着最新的物理和 bug 修复,所以它是我们的合并基底。kyoshimi-develop 是在提交 8eed6fc2 处从 bpsi 分出来的一个分支,承载着我们所说的 Phase-L 现代化——F90 化、每个模块的 C-ABI 共享库加上 Python 封装和 MCP 服务器,以及把 trcomm 拆成六个子模块。第三条线 ats-fukuyama,只是一个 2023 年的过时 GitHub 备份,只读。我们的目标是把 GitHub 上的 fork 线(kyoshimi-develop)和京都的 bpsi 线统一成一个经过 CI 验证的单一基线,让不同的开发者可以安全地从中分支,然后把 tr 打造成唯一权威的输运模块。

---

## Slide 4 · Why: converge two diverged lines into one reliable baseline

**Explanation / 说明**

- **EN** — A diagram of the unification: the GitHub-hosted Phase-L fork kyoshimi-develop (forked from the stale ats-fukuyama backup) and the latest Kyoto bpsi line feed into merge commit 0254aa91 plus fixes, producing the unified CI-green baseline (736 tests passing) that developers A and B branch from for new features.
- **中** — 统一过程的示意图:GitHub 上的 Phase-L 分支 kyoshimi-develop(由过时的 ats-fukuyama 备份 fork 而来)与最新的京都 bpsi 线汇入合并提交 0254aa91 加上修复,生成统一的、CI 全绿的基线(736 个测试通过),开发者 A 和 B 由此分支去做新功能。

**Speaker script / 演讲词**

> **English.** This diagram captures why we did the merge. On the left we have the two source lines that actually merge: the GitHub-hosted Phase-L fork kyoshimi-develop — which itself forked from the now-stale ats-fukuyama backup — and the latest Kyoto development line bpsi. Both flow into the merge commit 0254aa91, plus a series of fixes, and out the other side comes a single unified baseline on kyoshimi-develop, with CI green and 736 tests passing. The point is that developer A, developer B, and anyone adding new features can all branch cleanly from this one baseline. Without it, every developer would have to re-reconcile divergent trees each time they wanted to merge or build something new — which is exactly the situation we wanted to eliminate.

> **中文.** 这张图说明了我们为什么要做这次合并。左边是真正参与合并的两条源头线:GitHub 上的 Phase-L 分支 kyoshimi-develop——它本身是从如今已过时的 ats-fukuyama 备份 fork 出来的——和最新的京都开发线 bpsi。两者都汇入合并提交 0254aa91,再加上一系列修复,另一端就产出了 kyoshimi-develop 上一个统一的基线,CI 全绿,736 个测试通过。关键在于,开发者 A、开发者 B,以及任何要加新功能的人,都可以干净地从这一个基线分支出去。如果没有它,每个开发者每次想合并或做新东西时,都得重新去调和这些分叉的代码树——而这正是我们想要消除的局面。

---

## Slide 5 · P0: base selection and topology

**Explanation / 说明**

- **EN** — This slide justifies picking bpsi/develop as the single merge base (ats-fukuyama is a stale, superseded backup) and lays out the merge topology: the fork at 8eed6fc2, bpsi advancing +23 commits to fa9dd493, the Phase-L tip 58f1fe2e, and the merge 0254aa91 that grafts bpsi INTO the fork, delivered CI-green at d1f7f9e7.
- **中** — 本页说明为什么选择 bpsi/develop 作为唯一的合并基底(ats-fukuyama 是已被取代的陈旧备份),并给出合并拓扑:分叉点 8eed6fc2、bpsi 前进 23 个提交到 fa9dd493、Phase-L 分支尖端 58f1fe2e,以及把 bpsi 合并进分叉的合并提交 0254aa91,最终在 d1f7f9e7 交付并通过 CI。

**Speaker script / 演讲词**

> **English.** The first thing I had to settle was: what exactly are we merging into what? An audit showed that this is not a symmetric three-way merge. The GitHub line, ats-fukuyama, is 119 commits behind and its so-called unique commits are just superseded backups, so I discarded it as a base. The real base is bpsi/develop, the Kyoto main-dev line, which carries the latest physics and bug-fixes. So the topology is: we fork from bpsi at 8eed6fc2 back in December; bpsi then moves ahead by twenty-three commits to fa9dd493, while our Phase-L modernization moves to 58f1fe2e. The merge commit 0254aa91 takes the fork as its first parent and the bpsi base as its second — in other words, I merged bpsi INTO the fork, not the other way around, so the modernized structure stays primary. And the guiding principle for every single conflict was the same: keep the kyoshimi modernization, but graft in the bpsi intent — the bug-fixes and the eq and tr q-solver refinement.

> **中文.** 我首先要确定的是:到底是把什么合并进什么。一次审计表明,这并不是一个对称的三方合并。GitHub 那条线 ats-fukuyama 落后了 119 个提交,它所谓的独有提交其实只是被取代的备份,所以我把它排除在基底之外。真正的基底是 bpsi/develop,也就是京都的主开发线,它带着最新的物理和 bug 修复。所以拓扑是这样的:我们在去年十二月从 bpsi 的 8eed6fc2 分叉出来;之后 bpsi 前进了二十三个提交到 fa9dd493,而我们的 Phase-L 现代化则前进到 58f1fe2e。合并提交 0254aa91 以分叉作为第一父提交、以 bpsi 基底作为第二父提交——换句话说,我是把 bpsi 合并进分叉,而不是反过来,这样现代化的结构仍然是主体。而每一个冲突的解决原则都一样:保留 kyoshimi 的现代化,但嫁接进 bpsi 的意图——也就是那些 bug 修复,以及 eq 和 tr 的 q 求解器改进。

---

## Slide 6 · P0: the 10 conflict resolutions

**Explanation / 说明**

- **EN** — This slide is the ledger of how the merge was resolved: ten files (git flagged nine conflicts), each with its resolution strategy — grafting bpsi's eq-solver refinements into the free-form Phase-L code, taking-ours on the trcomm 6-module split, taking-theirs where bpsi fixed a double-free, and a three-way blend on the wrx ray-power file.
- **中** — 本页是合并解决方案的清单:十个文件(git 标出九处冲突),逐一给出解决策略——把 bpsi 的 eq 求解器改进嫁接进自由格式的 Phase-L 代码、在 trcomm 六模块拆分上采用我们的版本、在 bpsi 修了重复释放的地方采用他们的版本,以及在 wrx 射线功率文件上做三方融合。

**Speaker script / 演讲词**

> **English.** Here is the actual conflict ledger — ten files touched, of which git flagged nine as true conflicts. Rather than walk every row, let me point at the pattern. The eq files at the top all follow the same move: bpsi's fixed-form edits get grafted into our free-form F90 — that's where the flux-surface grid goes from 200 to 400 points, and where the EQLOOP adaptive under-relaxation comes in. For trcomm we took ours, because our version is the six-module split, and we added an idempotent DEALLOCATE. Where bpsi genuinely fixed something — a double-free in trmain, a SAVE-workspace fix in txcalv — we took theirs. And the one genuinely three-way case is wrcalpwr: I had to keep our headless out-of-bounds clamp AND graft in bpsi's dx change at the same time. So it's not one rule applied blindly — it's the same intent, keep-modernization-graft-bpsi, expressed differently per file.

> **中文.** 这是真正的冲突清单——一共动了十个文件,其中 git 标出九处真正的冲突。我不逐行念,而是指出规律。最上面那几个 eq 文件都遵循同一个动作:把 bpsi 的固定格式改动嫁接进我们的自由格式 F90——通量面网格就是在这里从 200 点提到 400 点,EQLOOP 的自适应欠松弛也是在这里引入的。对于 trcomm 我们采用自己的版本,因为我们的版本是六模块拆分,并且我们加了一个幂等的 DEALLOCATE。而在 bpsi 确实修好了东西的地方——trmain 里的重复释放、txcalv 里的 SAVE 工作区修复——我们就采用他们的。真正的三方情形只有一个,就是 wrcalpwr:我必须同时保留我们的无头越界钳制,又嫁接进 bpsi 的 dx 改动。所以这不是盲目套用一条规则,而是同一个意图——保留现代化、嫁接 bpsi——在每个文件里以不同方式体现。

---

## Slide 7 · Getting CI to green: issues surfaced class by class

**Explanation / 说明**

- **EN** — This slide shows that this repo's CI had never once been green — the build never even reached pytest — and walks the fix-by-fix table where problems surfaced in distinct classes (auto-merge artifacts, a divide-by-zero, the make.header repo-name bug, a link-time plcomm/pl_view clash, env gaps, and the three equivalence baselines), ending at 736 passed, 1 pre-existing xfail, CI green on 3.11 and 3.13.
- **中** — 本页说明这个仓库的 CI 从来没有一次通过过——构建甚至从没跑到 pytest——并逐一走过修复表:问题分门别类地浮现(自动合并的残留、除零、make.header 仓库名 bug、链接期的 plcomm/pl_view 冲突、环境缺口,以及三条等价性基线),最终 736 项通过、1 项既有 xfail,在 3.11 和 3.13 上 CI 通过。

**Speaker script / 演讲词**

> **English.** Now, an uncomfortable starting fact: this repo's CI had never been green — not even on the pure base. The build never once reached the pytest stage, so there was no safety net at all before this work. The fixes came not all at once but class by class, and each class taught us something. The first two were auto-merge artifacts — an eq fixed-form leak and a lost wrx clamp. Then a divide-by-zero on wrx dx, a dropped USE, a non-idempotent dealloc. Then a genuinely surprising one — make.header failed simply because the repo wasn't named 'task'. The subtlest class was the plcomm one: bpsi had added a bare PT to plcomm_parm that clashed with ti and wm, and a pl_view module move that broke fp only at LINK time, not compile time. After the latent env gaps — missing numpy, mcp-servers off the PYTHONPATH — and the three equivalence baselines, we finally landed it: 736 passed, one pre-existing xfail, green on both Python 3.11 and 3.13. That was delivered by fast-forwarding myfork's kyoshimi-develop to d1f7f9e7.

> **中文.** 接下来是一个让人不太舒服的起点事实:这个仓库的 CI 从来没绿过——连纯基底都没绿过。构建从没跑到 pytest 阶段,所以在这项工作之前根本没有任何安全网。修复不是一次到位,而是一类一类浮现的,每一类都给了我们启发。前两个是自动合并的残留——一处 eq 固定格式泄漏和一处丢失的 wrx 钳制。然后是 wrx dx 上的除零、一处漏掉的 USE、一处非幂等的释放。再然后是一个真正出人意料的:make.header 失败,仅仅因为仓库名不叫 'task'。最微妙的一类是 plcomm:bpsi 往 plcomm_parm 里加了一个裸的 PT,和 ti、wm 冲突;还有一个 pl_view 的模块搬迁,只在链接期、而非编译期,把 fp 弄坏了。在处理完那些潜藏的环境缺口——缺 numpy、mcp 服务器不在 PYTHONPATH 上——以及三条等价性基线之后,我们终于把它落地了:736 项通过、1 项既有 xfail,在 Python 3.11 和 3.13 上都绿。这是通过把 myfork 的 kyoshimi-develop 快进到 d1f7f9e7 交付的。

---

## Slide 8 · The 1e-10 equivalence baselines

**Explanation / 说明**

- **EN** — This slide separates the three drifted equivalence baselines into two distinct causes — wrx_demo and wrx_iter01 are pure compiler-version FP reordering (gf8.5, gf13.2, gf15 all differ but stay within ~1e-9), while tot_ht6m_short is a real ~1e-4 physics shift — and states the lesson plus the env-gated capture mechanism that regenerates the baselines on the exact CI compiler.
- **中** — 本页把三条漂移的等价性基线分成两种截然不同的成因——wrx_demo 和 wrx_iter01 是纯粹的编译器版本浮点重排(gf8.5、gf13.2、gf15 各不相同但都在约 1e-9 以内),而 tot_ht6m_short 是一个真实的约 1e-4 物理偏移——并给出教训,以及在确切的 CI 编译器上重新生成基线的环境门控捕获机制。

**Speaker script / 演讲词**

> **English.** The last class of failures were the equivalence baselines, and this is where I want to be precise, because two of them and the third are not the same kind of problem. wrx_demo and wrx_iter01 drifted purely because of the compiler version — the same source, floating-point reassociated differently under gfortran 8.5 versus 13.2 versus 15, all staying within about 1e-9 of each other. That's noise, not physics. tot_ht6m_short is different: that's a genuine roughly-1e-4 shift, and it's actually physics — I'll show its root cause on the next slide. The lesson we drew is that a 1e-10 binary-equivalence bar is simply too tight for floating-point-heavy modules like ray tracing and Fokker-Planck across compiler VERSIONS — not just across architectures, which is the usual assumption. The fix is mechanical and reproducible: an environment-gated capture dumps each case's actual gfortran-13.2 metrics as a CI artifact, and we commit those values as the new baselines. So the baselines are pinned to the exact compiler CI runs on, rather than to whatever machine happened to generate them first.

> **中文.** 最后一类失败是等价性基线,而这里我想说得精确一些,因为其中两条和第三条不是同一类问题。wrx_demo 和 wrx_iter01 的漂移纯粹是因为编译器版本——同一份源码,在 gfortran 8.5、13.2、15 下浮点重结合的方式不同,但彼此都在约 1e-9 以内。这是噪声,不是物理。tot_ht6m_short 则不同:那是一个真实的约 1e-4 偏移,而且确实是物理——它的根因我会在下一页展示。我们得到的教训是:对于射线追踪、Fokker-Planck 这类浮点密集的模块,1e-10 的二进制等价门槛实在太紧了,跨编译器版本就会破,而不只是跨体系结构——后者才是通常的假设。修复方法是机械且可复现的:一个环境门控的捕获把每个算例在 gfortran 13.2 下的实际指标作为 CI 工件导出,我们再把这些值提交为新的基线。这样基线就被钉在 CI 实际运行的那个确切编译器上,而不是钉在最初碰巧生成它的那台机器上。

---

## Slide 9 · Case study: the tot_ht6m q-solver refinement

**Explanation / 说明**

- **EN** — This slide diagnoses the ~1e-4 physics shift in the tot_ht6m_short baseline, tracing it to bpsi's EQ-solver refinements (finer flux-surface grid NMAX 200->400 plus EQLOOP under-relaxation) and showing the diagnostic signature: a global current redistribution with total current conserved and density completely frozen.
- **中** — 本页诊断 tot_ht6m_short 基线上约 1e-4 的物理偏移,把根因追溯到 bpsi 的 EQ 求解器改进(通量面网格从 NMAX 200 加密到 400,加上 EQLOOP 欠松弛),并给出其诊断特征:电流全局重分布、总电流守恒、密度完全冻结。

**Speaker script / 演讲词**

> **English.** This was the one baseline where the drift was not a compiler artifact but a genuine physics change, so I want to walk you through how we pinned it down. The root cause is a pair of EQ-solver refinements that bpsi brought in on the modelg=3 eq_load path: a finer flux-surface grid, NMAX going from 200 to 400, together with EQLOOP adaptive under-relaxation. What convinced us it was real and benign was the signature across all fifty radial rows: the current profile redistributes, going up in the core, down in the mid-radius region to minus 7.9e-4 at rho equals 0.74, and back up at the edge, and q, being its integral, moves down in the core and up outward. Crucially, the total current is conserved, the delta in AJT is only 3.9e-5, which is far smaller than the local 7.9e-4, and the density is completely frozen, zero of fifty rows changed. The profile is smooth with no NaNs. So we read this not as a bug but as a higher-accuracy solve, the owner approved it as intended, and we simply regenerated the baseline on gfortran-13.2.

> **中文.** 这是唯一一个偏移不是编译器伪影、而是真实物理变化的基线,所以我想带大家看看我们是怎么把它钉死的。根因是 bpsi 在 modelg=3 的 eq_load 路径上引入的两项 EQ 求解器改进:通量面网格加密,NMAX 从 200 提到 400,再加上 EQLOOP 自适应欠松弛。让我们确信它是真实且良性的,是它在全部五十行径向数据上的特征:电流剖面发生重分布,芯部升高、中径向区下降到 rho 等于 0.74 处的 -7.9e-4、边缘又回升,而 q 作为它的积分,则芯部下降、外侧上升。关键在于总电流守恒,AJT 的变化只有 3.9e-5,远小于局部的 7.9e-4,而且密度完全冻结,五十行里没有一行变化。剖面平滑,没有 NaN。所以我们把它判读为一次精度更高的求解,而非 bug,负责人也确认这是预期行为,我们就在 gfortran-13.2 上重新生成了基线。

---

## Slide 10 · Case study: a genuine review save

**Explanation / 说明**

- **EN** — This slide recounts how an early analysis mislabeled the tot_ht6m shift as core-localized because it read a truncated CI log, and how two independent pre-push reviewers caught the error against the full baseline; the takeaway is to verify against complete data and keep a reviewer gate.
- **中** — 本页讲述早期分析因为读了被截断的 CI 日志,错误地把 tot_ht6m 偏移判为芯部局域,以及两位独立的推送前审阅者如何对照完整基线抓出这个错误;结论是必须对照完整数据核实,并保留审阅门禁。

**Speaker script / 演讲词**

> **English.** This slide is the one I'm proudest of, because it's a case where the review process actually saved us from shipping a wrong conclusion. My early analysis called the shift core-localized, confined to rho less than or equal to 0.20 with nothing beyond it, and that was flatly wrong. It was an artifact of a truncated CI log: the comparator only prints about 52 of the 210 mismatches, and those happen to be the core rows, so reading the log alone made the change look core-only. Two independent pre-push reviewers noticed the contradiction against the full committed baseline and pushed back, and we corrected it to the global redistribution I just described before re-approving. The general takeaway is twofold: always verify your conclusions against the complete data, not whatever a tool happened to print, and keep an independent-reviewer gate. That gate caught three real issues the author missed in this effort, the link-time pl_view failure, a wrong root-cause attribution, and this localization error.

> **中文.** 这一页是我最自豪的,因为它是审阅流程真正把我们从一个错误结论里拉回来的案例。我早期的分析把这个偏移判为芯部局域,认为只集中在 rho 小于等于 0.20、之外为零,而这是彻底错的。它其实是被截断的 CI 日志造成的伪影:比较器只打印了 210 处不匹配里的大约 52 处,而这些恰好是芯部的行,所以单看日志就会觉得变化只在芯部。两位独立的推送前审阅者发现它与完整提交基线相矛盾并提出质疑,我们才把它更正为刚才讲的全局重分布,然后重新批准。普遍的结论有两点:一定要对照完整数据核实结论,而不是工具碰巧打印出来的那部分;并保留独立审阅门禁。这个门禁在本次工作中一共抓出了作者漏掉的三个真实问题:链接期的 pl_view 失败、一处错误的根因归属,以及这个局域化错误。

---

## Slide 11 · P1: old vs new fusion physics

**Explanation / 说明**

- **EN** — This slide contrasts kyoshimi tr's old fusion path (scalar MDLNF selector, hardcoded D+T via TRNFDT, 1-D SNF, analytic SIGMAM) with bpsi trx's new path (model_pnf selector, multi-reaction libnf, species-resolved source array, spline over tabulated svnf), and flags the reconnaissance finding that two core regression inputs already run MDLNF=1.
- **中** — 本页对比 kyoshimi tr 的旧聚变路径(标量 MDLNF 选择器、通过 TRNFDT 硬编码的 D+T、一维 SNF、解析式 SIGMAM)与 bpsi trx 的新路径(model_pnf 选择器、多反应 libnf、按核素分辨的源项数组、对表格化 svnf 的样条插值),并指出侦察发现两个核心回归输入已经在跑 MDLNF=1。

**Speaker script / 演讲词**

> **English.** Now we move to Phase 1, the actual point of the whole exercise: porting trx's newer fusion physics into tr. This table lays out old versus new. On the old kyoshimi tr side, fusion is selected by a scalar MDLNF, the reactions are hardcoded D-plus-T in the subroutine TRNFDT, the source is a one-dimensional SNF over radius, and the reactivity comes from an analytic SIGMAM of temperature. On the new bpsi trx side, the selector is model_pnf, the reactions expand to DT, DD, D-He3, TT, and T-He3 in the module libnf, the source becomes species-resolved, SNF_NSNNFNR indexed by species, reaction, and radius, and the reactivity is a spline over a tabulated svnf. The reconnaissance step corrected a premise in my original plan: the regression inputs tr_m0904 and tr_iter01 actually run MDLNF equals 1, fusion on, so naively retiring MDLNF would change two core baselines. That finding is exactly why I did a direct physics comparison before deciding the migration strategy, which is the next slide.

> **中文.** 现在进入第一阶段,也就是整件事真正的目的:把 trx 更新的聚变物理移植进 tr。这张表把新旧两侧摆开对比。旧的 kyoshimi tr 一侧,聚变由标量 MDLNF 选择,反应在子程序 TRNFDT 里硬编码为 D 加 T,源项是沿半径的一维 SNF,反应率来自温度的解析式 SIGMAM。新的 bpsi trx 一侧,选择器是 model_pnf,反应扩展为 DT、DD、D-He3、TT、T-He3,放在 libnf 模块里,源项变成按核素分辨的 SNF_NSNNFNR,以核素、反应、半径三重索引,反应率则是对表格化 svnf 的样条插值。侦察这一步纠正了我原计划里的一个前提:回归输入 tr_m0904 和 tr_iter01 实际上在跑 MDLNF 等于 1,也就是聚变开启,所以如果贸然退役 MDLNF,就会改动两个核心基线。正是这个发现,促使我在决定迁移策略之前先做了一次直接的物理对比,那就是下一页的内容。

---

## Slide 12 · P1: the reactivity comparison drives the decision

**Explanation / 说明**

- **EN** — This slide shows the old analytic DT reactivity formula SIGMAM and demonstrates that the new libnf table svnf_dt is the very same fit tabulated to two significant figures, agreeing to about 1% at the table points and at core fusion temperatures (libnf's raw-value spline diverges at the low-temperature edge, but the reactivity there is negligible); the conclusion is that migrating DT buys zero physics gain and that model_pnf's real value is its additive multi-reaction capability.
- **中** — 本页给出旧的解析式 DT 反应率公式 SIGMAM,并证明新的 libnf 表格 svnf_dt 就是同一个拟合、只是取到两位有效数字,在表格点与核心聚变温度处一致到约 1%(libnf 的原始值样条在低温边缘会偏离,但那里反应率可忽略);结论是迁移 DT 带来零物理增益,而 model_pnf 真正的价值在于其可叠加的多反应能力。

**Speaker script / 演讲词**

> **English.** This is the slide where the decision gets made, and it's made by physics, not by preference. The old analytic DT reactivity is this expression, 3.7e-18 times T_I to the minus two-thirds, times exp of minus 20 over T_I to the one-third, divided by an H correction, with T_I the effective ion temperature. The key finding is that the new libnf table svnf_dt is literally this same fit, just tabulated to two significant figures. Once you account for the units, svnf_dt is in cubic-centimeters per second and SIGMAM is in cubic-meters per second, the two agree to between 0.03 and 1.2 percent at the table points. There is one subtlety worth stating: libnf splines the raw reactivity against the log of temperature, so at core fusion temperatures — above roughly 5 keV — it stays within about one to two percent of the analytic form; but at the low-temperature edge, below about 3 keV, that raw-value spline overshoots badly. That is immaterial, though, because the reactivity there is negligible and essentially no fusion happens. So migrating the DT channel to model_pnf gains zero physics at the core — and in fact the analytic MDLNF is the smoother of the two. The real value of model_pnf is not a better DT number, it's the multi-reaction capability, DD, D-He3, TT, T-He3, and that capability is purely additive on top of the existing DT path.

> **中文.** 这就是做出决定的一页,而且这个决定是由物理、而非偏好来定的。旧的解析式 DT 反应率是这个表达式:3.7e-18 乘以 T_I 的负三分之二次方,乘以 exp 括号内负 20 除以 T_I 的三分之一次方,再除以一个 H 修正项,其中 T_I 是有效离子温度。关键发现是,新的 libnf 表格 svnf_dt 字面上就是同一个拟合,只是取到了两位有效数字。把单位对齐之后——svnf_dt 单位是立方厘米每秒,SIGMAM 是立方米每秒——两者在表格点上一致到 0.03 到 1.2 个百分点之间。这里有一个值得说明的细节:libnf 是把原始反应率对温度的对数做样条,所以在核心聚变温度、大约 5 keV 以上,它与解析式保持在约 1 到 2 个百分点以内;但在低温边缘、约 3 keV 以下,这种对原始值的样条会剧烈过冲。不过这无关紧要,因为那里的反应率可以忽略、基本不发生聚变。所以把 DT 通道迁移到 model_pnf 在核心区带来零物理增益——事实上,两者之中解析式 MDLNF 反而更平滑。model_pnf 真正的价值不在于更好的 DT 数值,而在于多反应能力——DD、D-He3、TT、T-He3——而这项能力是纯粹叠加在现有 DT 路径之上的。

---

## Slide 13 · P1: decision (Option A) and remaining plan

**Explanation / 说明**

- **EN** — This slide states the P1 decision: keep the exact old MDLNF/SIGMAM DT path bit-for-bit and add model_pnf as an additive, default-off multi-reaction path, then lists the remaining Tasks 2-10 and the deferred TGLF work.
- **中** — 这张幻灯片给出 P1 的决策:逐位保留旧的 MDLNF/SIGMAM DT 路径,并把 model_pnf 作为默认关闭的可加式多反应路径引入;随后列出剩余的 Task 2 到 10 以及暂缓的 TGLF 工作。

**Speaker script / 演讲词**

> **English.** Given that the DT reactivities agree to within about one percent, the decision is what I call Option A. We keep the exact old MDLNF and SIGMAM DT path so that all three regression baselines stay bit-for-bit identical, and we add model_pnf strictly as an additive multi-reaction path. Because it defaults to off, every existing regression gate holds trivially, and we then validate it against a bpsi-trx reference at one-times-ten-to-the-minus-ten in Tasks two and seven. Crucially, MDLNF is not retired. The remaining Tasks two through ten cover extracting the collision functions into trcoll and trlib, seating the fusion data model in the split trcomm, porting libnf, adding the generic tr_pnf dispatch gated by model_pnf greater than zero, building the bpsi-trx reference oracle to validate model_pnf equals one through four, exposing it through the C-ABI and MCP, and finally archiving trx and trm. TGLF is deferred because it needs the external GACODE library.

> **中文.** 既然 DT 反应率的差异只有约百分之一,我把这个决策称为方案 A。我们完整保留旧的 MDLNF 和 SIGMAM DT 路径,让三条回归基线逐位保持不变,同时把 model_pnf 严格作为一条可加的多反应路径引入。由于它默认关闭,所有现有的回归门槛都自然通过,之后我们在 Task 2 和 Task 7 里以 1e-10 的容差对照 bpsi-trx 参考实现来验证它。关键是,MDLNF 并不退役。剩下的 Task 2 到 10 包括:把碰撞函数抽取到 trcoll 和 trlib,在拆分后的 trcomm 中安置聚变数据模型,移植 libnf,加入受 model_pnf 大于零控制的通用 tr_pnf 派发,构建 bpsi-trx 参考基准来验证 model_pnf 等于 1 到 4,再通过 C-ABI 和 MCP 暴露接口,最后归档 trx 和 trm。TGLF 因为需要外部的 GACODE 库而暂缓。

---

## Slide 14 · Future plan

**Explanation / 说明**

- **EN** — This slide shows the phased roadmap timeline P0 through P4 leading to the upstream PR, with P0 marked done and P1 in progress, plus a per-phase bullet list of what each phase delivers.
- **中** — 这张幻灯片展示从 P0 到 P4、最终通向上游 PR 的分阶段路线图时间线,P0 标为已完成、P1 进行中,并配有每个阶段交付内容的要点列表。

**Speaker script / 演讲词**

> **English.** Here is the roadmap. P0, the merge and baseline, is done; P1, the TRX-to-tr fusion port, is where we are now. P1 means finishing Tasks two through ten: porting libnf and tr_pnf, validating model_pnf equals one through four against bpsi trx at one-times-ten-to-the-minus-ten, and archiving trx and trm. P2 then de-duplicates the shared parameters like RR, RA, and BB into plcomm. P3 cleans up the eq-to-pl interface and finishes the remaining F90-ification, and P4 does the directory reorganization and the move to CMake. Once those phases land, we take the whole thing upstream, from myfork to a k-yoshimi slash task pull request.

> **中文.** 这是整体路线图。P0,也就是合并与基线,已经完成;P1,即 TRX 到 tr 的聚变移植,是我们目前所处的阶段。P1 意味着完成 Task 2 到 10:移植 libnf 和 tr_pnf,以 1e-10 的容差对照 bpsi trx 验证 model_pnf 等于 1 到 4,并归档 trx 和 trm。接下来的 P2 会把 RR、RA、BB 等共享参数去重合并进 plcomm。P3 整理 eq 到 pl 的接口并完成剩余的 F90 化,P4 则做目录重组并迁移到 CMake。等这些阶段都落地后,我们就把整套工作推向上游,从 myfork 提交到 k-yoshimi 斜杠 task 的合并请求。

---

## Slide 15 · Repositories, links & current result

**Explanation / 说明**

- **EN** — The closing frame: a repo table with clickable links to the three repos, PR #1, the full report and these slides, followed by result badges and the closing statement that P0 is delivered CI-green and P1 is underway.
- **中** — 这是收尾页:一张仓库表,附有指向三个仓库、PR #1、完整报告和这份幻灯片的可点击链接,随后是成果徽章,以及 P0 已交付且 CI 通过、P1 进行中的收束陈述。

**Speaker script / 演讲词**

> **English.** Finally, here are the repositories and the concrete results. The unified fork lives at HengyuLi-Ozaki-lab slash task on branch kyoshimi-develop, delivered at commit d1f7f9e7; ats-fukuyama is the stale GitHub backup, and the Kyoto main-dev line bpsi is the base at fa9dd493. The CI validation and pull request number one happened in the private task-merge sandbox, and the links here also point to the full engineering report and these slides. The result badges summarize it: seven hundred thirty-six tests passed, ten conflict resolutions, P0 delivered at d1f7f9e7, and P1 Task one done. In short, P0 is delivered CI-green and P1 is underway. Thank you.

> **中文.** 最后是仓库和具体成果。统一后的 fork 位于 HengyuLi-Ozaki-lab 斜杠 task 的 kyoshimi-develop 分支,交付于提交 d1f7f9e7;ats-fukuyama 是陈旧的 GitHub 备份,京都主开发线 bpsi 则是基线,位于 fa9dd493。CI 验证和第一号合并请求是在私有的 task-merge 沙箱中完成的,这里的链接也指向完整的工程报告和这份幻灯片。成果徽章做了总结:736 个测试通过、10 处冲突解决、P0 交付于 d1f7f9e7、P1 的 Task 1 已完成。一句话概括:P0 已交付且 CI 全绿,P1 正在进行中。谢谢大家。

---

