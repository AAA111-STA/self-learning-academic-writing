# 运行门禁与输入

这页供执行 Skill 的代理使用。临时输入由代理整理。用户可以直接发论文、讲自己的构思，并在看过提纲后用自然语言下达简短的开写指令。

需要 Python 3.9 或更新版本。以下示例从 Skill checkout 根目录执行。若 Skill 安装在其他位置，保持科研项目根目录作为命令的当前目录，把 `scripts/workflow.py` 替换成 Skill 中该脚本的完整路径。工作记录写到当前目录的 `.self-learning-academic-writing/runs/`。论文摘录、研究材料和临时 JSON 可放在 `.self-learning-academic-writing/inputs/`。更名前已有的会话记录可从旧目录恢复。跨会话写法偏好参见 [个人写作档案](writing-profile.md)。

启用钩子时使用其回传给智能体的会话标识。没有钩子时选择可复用的标识，例如 `paper-01`。同一论文的章节使用同一个标识。各章节和模式分别存档，一个会话可以存多章，每次操作当前选中的章节或翻译任务。同一章节的多轮反馈通过 `revise` 保留已经交付的版本。

```text
python scripts/workflow.py --session {session_id} chapters
python scripts/workflow.py --session {session_id} resume 引言
python scripts/workflow.py --session {session_id} show
```

`chapters` 查看已有任务，`resume` 切换到既有任务，`show` 取回当前任务的学习记录、提纲、稿件及版本。润色任务使用 `resume {章节} --mode polish`，英译任务使用 `resume {任务名} --mode translate`。旧版单章节记录会在下次保存时并入多章节存档。

## 1. 逐篇学习

命令示例中的花括号表示运行时替换的值。

实际使用 Skill 时，先从论文工作目录运行 `python scripts/workflow.py project-init`。首次自动创建 `.self-learning-academic-writing/references.md` 和同目录的 `writing-preferences.md`；以后恢复已有记录。作者新提供的范文用 `reference-add` 登记，可访问的原文用 `--file` 保存副本。用 `profile-show` 读取已确认的项目偏好。后续会话保持同一论文工作目录，可按 [项目参考文献库](reference-library.md) 找回文件和已读章节。

```text
python scripts/workflow.py --session {session_id} init 引言 {文献标识A} {文献标识B} --language zh
python scripts/workflow.py --session {session_id} study {文献标识A} {章节摘录.txt} {整文上下文.txt} {学习记录.json}
```

- 文献标识用 DOI、全文链接、文件名或其他可辨认的标识。一次登记用户指定的全部范文。目标是方法时就读方法。遇到合并章节或多段式摘要时，核实对应段落的边界。（例：从 `Results and Discussion` 中提取属于结果陈述的段落。）
- 目标章节摘录保留原有段落边界，用空行分段。整文上下文来自实际读取的目标章节之外的相关正文。两份材料都用 UTF-8，记录页码、段落、行号或其他可复核位置。先追踪研究问题、方法、证据和结论如何衔接，再选与目标章节有关的原文定位。缺材料时说明可做的局部分析与待补的整文内容。
- 每篇记录填写 `section`、`location` 和四项目标章节分析 `expression`（语言与衔接表达）、`grammar`（语法和句型）、`organization`（章节内各段的职责和整个推进顺序）、`concision`（信息取舍和表述效率）。四项均填写 `anchor`（短原文）、`observation`（实际做法和作用）、`application`（适用语境）。
- 有合适范例时，在 `sentence_patterns` 添加条目，每条包含 `anchor`（目标章节中实际出现的短例句）、`location`（页码、段落或其他定位）、`template`（用 `{槽位}` 替换原文特有的对象、数据或判断，保留句法骨架）、`application`（句子承担的任务及使用条件）。例如 `Compared with {baseline}, {model} yielded {direction} {metric} under {condition}.`。没有适用句式可以省略该字段。提纲里可注明哪一段适用哪种句式；授权后才为用户稿件生成仿写正文。
- 单独填写 `paper_context`，内含 `main_line`（整篇如何论证）、`section_role`（目标章节在全篇中承担什么任务）、`connections`（它如何呼应其他章节）及 `evidence`。其中 `evidence` 是至少一条来自目标章节之外的原文定位列表，每条含 `location` 和 `anchor`。
- 填写 `paragraph_transition`，内含 `from`、`to` 两条原文锚点及 `observation`、`application`。选择实际相邻的两个段落，解释后一段如何承接或推进前一段。单段章节（如单段摘要）分析同段中相邻的两个论证动作。
- 程序检查材料、原文锚点和段落顺序。代理核对摘录与指定论文及其原文版本的对应关系。校验通过后，章节摘录和学习记录自动写入项目参考文献库。初始化章任务时可复用同一文献、同一章节及相同附件版本的已有记录。修改已登记的学习记录会重置提纲和开写授权。

## 2. 设计章节逻辑

```text
python scripts/workflow.py --session {session_id} read-section-guide
python scripts/workflow.py --session {session_id} plan {提纲.json}
```

每轮先读取对应章节的内置结构规则，结合指定范文和作者材料拟提纲。「结果与讨论」等合并章节需分别落实对应原则；自定义章节名可在 `init` 时用 `--guide-section 方法` 等指定映射，多章可重复该参数。

提纲 JSON 中的字段：

| 字段 | 填写内容 |
| --- | --- |
| `paper_context` | 用户论文的 `main_line`（研究问题到结论的整篇主线）、`section_role`（当前章节在全篇中的职责）、`connections`（与其他章节的衔接、呼应或待确认关系） |
| `section_purpose` | 这一节要解决的问题 |
| `section_flow` | 这一节从哪里起、如何推进、落在哪里，包含各段在本节中承担的作用 |
| `user_logic` | 用户提供的组织思路原意。用户未提供时填空字符串 |
| `reference_decisions` | 借鉴了哪些指定范文的哪些组织方式，以及为什么适合当前研究 |
| `section_guidance` | 以 `read-section-guide` 输出的章节名为键；每章填 `rule`（引用一条内置结构规则的原文）和 `application`（用研究材料落实到哪一段或为何保留现有结构）。给作者看应用和理由即可。 |
| `paragraphs` | 有序段落列表。各段填写 `point`（表达重点）、`evidence`（当前研究或已有可信依据）、`link`（和后文的衔接，末段可填收束作用） |
| `feedback_response` | 返修轮必填。说明用户反馈涉及哪些层次，以及本轮将怎样处理 |

登记成功后，向用户展示章节逻辑及选择依据。涉及步骤衔接时，在 `link` 写明前一步的产出怎样被后一步使用，或两步各回答什么问题。证据或研究结果不足处标记待补。用户的开写授权对应当时已登记的提纲及范文学习版本。

<a id="summary-results"></a>

### 摘要与结论：先覆盖完整结果，再决定取舍

此规则适用于摘要和结论的写作及润色。读完每篇范文对应章节及其全部结果小节、关键图表和图注，在实际读过的材料中整理出完整结果的文字及必要图表记录。每篇范文用 `study {标识} {章节摘录.txt} {整文上下文.txt} {学习记录.json} --results {范文完整结果.txt}`，在学习记录中填写 `results_coverage`。用户自己的结果也按研究问题逐项核对，用 `plan {提纲.json} --results {本文完整结果.txt}`，在提纲中填写 `results_selection`。两个对象结构相同：

- `blocks`：按实际结果组织逐项列出 `location`（小节、段落、图或表）、`anchor`（结果材料中的短原句）及 `use`（该发现是否纳入总结、具体支撑什么，或略去的理由）。合并的结果与讨论、无独立结果小节的文章，按实际结果块定位；图表上没有完整句子时，可转录标签和数值作为定位。
- `selection`：范文写作者怎样从完整结果取舍；用户稿写拟保留哪些关键结果、如何回应研究问题及哪些证据限制结论。

复用范文记录时，先打开已保存的完整结果和取舍笔记，确认原文版本一致。旧版未登记结果覆盖的记录可作为线索，须补读后再登记。缺少任意一边的完整结果时报告具体缺口，暂不提交正式提纲或正文。脚本核对结果原句和记录是否齐备，并把用户结果版本绑定到正式提纲；是否确实覆盖全文结果由代理对照原稿核查。交稿前把摘要或结论中的每个实质判断、数值和限定条件对照用户的实际结果，复核记入 `review.paper_alignment`。

## 3. 等待用户开写，然后起草与修订

从用户实际输入识别简短的明确指令，例如「开始写」「开始写引言」「按这个提纲开始写」或 `Start writing`。当前章节须一致，疑问、引述、否定及条件句不触发。提纲还未登记时，可继续做学习和提纲。提纲展示后需要新的开写指令。登记写作语言时中文用 `--language zh`，英文用 `--language en`。

启用 [授权钩子](agent-hooks.md) 的宿主可从真实用户消息接收指令。其余情况下用下面的命令，由用户本人在同一工作目录的交互式终端输入确认。正文交付后，同一命令也可记录用户满意。代理把填好路径及会话标识的命令交给用户，随后用 `status` 检查结果。

```text
python scripts/workflow.py --session {session_id} user-confirm
```

```text
python scripts/workflow.py --session {session_id} check-start
python scripts/workflow.py --session {session_id} read-section-guide --stage draft
python scripts/workflow.py --session {session_id} save-draft {完整初稿.txt}
python scripts/workflow.py --session {session_id} read-humanizer
python scripts/workflow.py --session {session_id} finalize {修订稿.json}
```

先通过 `check-start`，再读取本轮句式。按段落任务借鉴表达的作用，用稿件已有事实和语言改写，或据此核对已有句子。无需把内置句式逐字放进正文。除摘要、引言、讨论的独立句式表，还提供[其他章节的中英文表达](section-expressions.md)。按 [句子与措辞规则](prose-style.md) 组织正文并登记初稿。使用 `read-humanizer` 读取随 Skill 打包的 `academic-humanizer`，结合本 Skill 的规则复读和修订。修订结果 JSON 提供 `text`（可交付章节）和 `review` 对象。复核记录填写 `paper_alignment`（整篇主线与跨章节关系）、`section_flow`（章节整体论证）、`paragraph_links`（段落衔接）、`sentence_links`（句间承接与逻辑跳跃）、`language_and_facts`（语言与事实核对）。返修轮还须填写 `feedback_addressed`。

`review.section_expressions` 以输出的章节名为键，每章填写 `cue`（本章句式指南里使用的例句片段或用途原文）、`anchor`（最终正文中对应的原句）、`decision`（怎样仿写、调整或借此检查并保留了自然的表达）。脚本验证指南版本、条目和正文原句，实际取舍仍由智能体根据稿件判断。升级前已经交付的版本保留；进行中的旧提纲复读指南并重新登记，取得新的开写授权。

去 AI 味后复读最终正文。在 `review.prose_check` 中填写 `anchor`（最终正文中的一处原句或连续短段）和 `assessment`（例如如何删去套话或重复限定、如何让简称准确承接前文，或为何保留一项必要的依据、对象或限制）。有多处问题时逐处修订，记录一处代表性复核即可。脚本确认记录存在、原句能在最终正文定位；句子自然与否、依据是否成立仍要对照稿件由代理判断。通过脚本输出后向用户交付本轮正文，并等待反馈。

## 4. 收到反馈后开启下一轮

```text
python scripts/workflow.py --session {session_id} revise {用户反馈.txt}
python scripts/workflow.py --session {session_id} revise {用户反馈.txt} --references {更新后的全部文献标识}
```

收到用户对已交稿版本的修改意见时，登记反馈，本轮稿件和提纲保留在历史记录中。仅当用户调整范文清单时才使用 `--references`。复查上一轮学习是否仍适用，可用 `reuse-study {文献标识}` 将本项目已读的对应章节记录带入返修轮，或从保存的原文补读受影响内容。重新登记提纲后，等本轮明确开写，再完成正文、去 AI 味和复核。通过项目钩子或 `user-confirm` 收到「这版我满意」「就按这版定稿」或 `Accept this version` 时，将最新交稿标为用户已认可。后续有新意见时，仍可开启下一轮。

## 5. 润色已有中文稿或英文稿

```text
python scripts/workflow.py --session {session_id} init 讨论 {文献标识} --mode polish --source {现稿.txt} --language en
python scripts/workflow.py --session {session_id} read-editor
```

先登记现稿、读取章节结构指南并拟定修改方案。可以复用同章写作时已核对的相关范文记录，缺少的部分继续学习。展示方案后，等用户说「开始润色」或 `Start polishing`。其他宿主可通过 `user-confirm` 记录同一指令。获授权后，使用 `read-editor` 和 `read-section-guide --stage draft`，再执行 `save-draft`、`read-humanizer` 和 `finalize`。润色的 `review` 增加 `source_fidelity`，说明语义、数据、术语及用户允许的变动是否与本轮原稿对得上。返修轮以上一版润色稿为本轮原稿。中文稿选择 `zh`，英文稿或外部英译稿选择 `en`。

## 6. 可选的英译任务

只有用户明确要求英译才启动翻译。登记范围可选择 `paragraph`（选定段落逐段处理）或 `manuscript`（整篇）。原文清单按原序填写 `units`，每项有唯一的 `id` 和 `text`。设 `verbatim: true` 的项原样保留，例如应保留的文献条目。可填写 `glossary`，以原文术语为键、英文译法为值。整篇登记前应与实际原稿对照清单，确认所选范围内的标题、章节、题注及其他内容都在清单中。

```text
python scripts/workflow.py --session {session_id} translate-init {任务名} --scope paragraph {原文清单.json}
python scripts/workflow.py --session {session_id} check-translate
python scripts/workflow.py --session {session_id} read-translator
python scripts/workflow.py --session {session_id} next-translation
python scripts/workflow.py --session {session_id} save-translation {单元编号} {译文与复核.json}
python scripts/workflow.py --session {session_id} finish-translation {整稿复核.json}
```

授权钩子可从「把这段翻译成英文」或「把这篇论文翻译成英文」等指令取得本次相应范围的授权，也可先登记原文，再由用户说「开始翻译」。没有授权钩子时由用户通过 `user-confirm` 授权。确认脚本已授权才翻译。译文单元使用 `text` 及 `review`，复核至少填写 `meaning`、`concision` 和 `terms_and_protected_content`。逐段模式按段交付，整篇模式逐段核对并保存，检查整篇后统一交稿。交稿前如需统一已译术语，可向相应单元的 `save-translation` 加 `--replace`。最终复核对象 `review` 包含 `coverage`、`terminology`、`concision` 和 `source_fidelity`。

检查当前轮次、学习缺口、授权及任务进度时，用 `status`。

文件门禁覆盖经此工作流提交的成果。聊天直接输出、修改正式 Word 的授权和文献可读性仍由相应流程处理。
