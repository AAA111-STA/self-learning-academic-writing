# self-learning-academic-writing

面向中文和英文期刊的学术写作 Skill。它在每次写作前学习作者指定的范文，也可在本机保存作者明确确认的个人写作偏好。各章分别存档，可随时切换。支持写作、润色和由作者明确发起的逐段或整篇英译。

## 使用

欢迎下载、安装和使用完整 Skill。可以下载仓库 ZIP，也可以用 Git 获取：

```sh
git clone https://github.com/AAA111-STA/self-learning-academic-writing.git
```

1. 保留整个 `self-learning-academic-writing` 目录。支持 Agent Skills 的宿主可按其方式加载 [SKILL.md](SKILL.md)。能够读取项目文件并执行 Python 的通用智能体，也可以直接按该入口执行。
2. 准备 Python 3.9 或更新版本。给智能体目标章节、范文原文和已有研究材料。它会先阅读并提交提纲。
3. 在已信任项目钩子的 Codex 聊天里发送与任务相符的指令，例如「开始写」「开始润色」「把这段翻译成英文」。其他宿主可在终端运行智能体提供的 `user-confirm` 命令，再输入明确指令。

完整门禁依赖宿主能读取项目文件和运行本地脚本。只支持聊天、无法执行 Python 的宿主可阅读写作规则，其会话无法运行代码门禁。想用 Codex 聊天钩子时，从本仓库根目录打开项目并审阅 [项目配置](.codex/hooks.json)。信任钩子后，配置命令从该目录运行。通用命令及材料格式见 [运行门禁与输入](references/workflow-inputs.md)。

本地学习记录、研究材料和历次稿件应放在工作目录的 `.self-learning-academic-writing/` 下。仓库忽略这个目录。经作者确认的 [个人写作档案](references/writing-profile.md) 默认保存在本机用户目录。

可在目录根运行 `python -m unittest discover -s tests`，核对章节恢复、偏好保存、润色和英译门禁。

## English

This skill supports writing and editing for Chinese- and English-language journals. It studies author-selected papers, keeps independent section histories, and can reuse writing preferences that each author explicitly saves. English translation is optional and requires an explicit request for selected paragraphs or the whole manuscript. Hosts with local files and Python 3.9+ can run the workflow. Codex can receive commands through its optional project hook. Other hosts use the terminal. Load [SKILL.md](SKILL.md) with the entire directory available.

## Third-party notices

The repository bundles `academic-humanizer` v0.3.3 by AIScientists-Dev. Its writing instructions and MIT license are included without edits. [Upstream project](https://github.com/AIScientists-Dev/academic-humanizer), [bundled license](references/vendor/academic-humanizer/LICENSE).

The editing and English translation guides use paragraph and evidence checks adapted from [Research Paper Writing Skills](https://github.com/Master-cai/Research-Paper-Writing-Skills) by Master-cai, based on Prof. Peng Sida's study notes, under [MIT](references/vendor/research-paper-writing/LICENSE). This skill defines its own translation authorization, scope and fidelity rules.
