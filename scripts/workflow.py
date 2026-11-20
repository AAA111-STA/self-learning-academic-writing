"""Run the academic-writing workflow from any agent with local Python access."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from host_hooks import CONTEXT_ONLY, HOSTS, format_context, submission
from reference_library import ReferenceLibrary, file_lock, inline, write_text


ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "self-learning-academic-writing"
WORK_DATA = f".{SKILL_NAME}"
LEGACY_WORK_DATA = ".self-academic-writting"
HUMANIZER = ROOT / "references" / "vendor" / "academic-humanizer" / "guide.md"
ACADEMIC_EDITING = ROOT / "references" / "academic-editing.md"
ENGLISH_TRANSLATION = ROOT / "references" / "english-translation.md"
PATTERNS = ("expression", "grammar", "organization", "concision")
PAPER_FIELDS = ("main_line", "section_role", "connections")
REVIEW_FIELDS = ("paper_alignment", "section_flow", "paragraph_links", "sentence_links", "language_and_facts")
TRANSLATION_UNIT_REVIEW = ("meaning", "concision", "terms_and_protected_content")
TRANSLATION_FINAL_REVIEW = ("coverage", "terminology", "concision", "source_fidelity")


class GateError(Exception):
    """The current input cannot advance the workflow."""


def require(condition, message):
    if not condition:
        raise GateError(message)


def required_text(record, field):
    value = record.get(field)
    require(isinstance(value, str) and value.strip(), f"缺少有效的 {field}。")
    return value.strip()


def read_text(path):
    value = Path(path).read_text(encoding="utf-8-sig").strip()
    require(value, f"文件为空：{path}")
    return value


def read_object(path):
    value = json.loads(read_text(path))
    require(isinstance(value, dict), f"需要 JSON 对象：{path}")
    return value


def digest(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def safe_identifier(value, message):
    require(
        isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value),
        message,
    )
    # Keep identifiers portable as Windows file names and stable on all hosts.
    require(value.upper() not in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)),
    }, message)
    return value


def state_path(session, workspace=None):
    safe_identifier(session, "需要当前会话的有效 session_id。")
    workspace = Path.cwd() if workspace is None else Path(workspace)
    current = workspace / WORK_DATA / "runs" / f"{session}.json"
    legacy = workspace / LEGACY_WORK_DATA / "runs" / f"{session}.json"
    return legacy if legacy.exists() and not current.exists() else current


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def task_key(mode, label):
    return f"{mode}:{label}"


def read_session(path):
    if not path.exists():
        return {"schema": 2, "active": None, "tasks": {}}
    data = read_object(path)
    if data.get("schema") == 2:
        return data
    # Preserve a previous release's single-chapter state on first update.
    key = task_key("write", required_text(data, "section"))
    return {"schema": 2, "active": key, "tasks": {key: data}}


def active_task(session):
    state = session["tasks"].get(session["active"])
    require(state, "先登记或切换到要处理的章节或翻译任务。")
    return state


def profile_path(alias):
    alias = safe_identifier(alias, "个人档案标识须为字母、数字、短横线或下划线。").lower()
    configured = os.environ.get("SELF_LEARNING_WRITING_PROFILE_DIR")
    folder = Path(configured).expanduser() if configured else Path.home() / WORK_DATA / "profiles"
    return folder / f"{alias}.json"


def read_profile(alias):
    path = profile_path(alias)
    if path.exists():
        return read_object(path)
    return {"schema": 1, "profile": path.stem, "preferences": {}}


def read_project_preferences(root):
    path = root / "writing-preferences.json"
    return read_object(path) if path.exists() else {"schema": 1, "preferences": {}}


def render_project_preferences(root, record):
    path = root / "writing-preferences.md"
    lines = [
        "# 项目写作偏好", "",
        "仅适用于当前论文项目。此文件由 Skill 根据作者已确认的偏好生成。",
    ]
    if not record["preferences"]:
        lines += ["", "尚无已确认的项目写作偏好。"]
    for key, item in record["preferences"].items():
        sections = "、".join(map(inline, item["sections"])) or "全部章节"
        lines += ["", f"## {key}", "", inline(item["text"]), "",
                  f"- 语言：{item['language']}", f"- 章节：{sections}"]
    content = "\n".join(lines) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        write_text(path, content)
    return path


def initialize_project_preferences(root):
    with file_lock(root / "writing-preferences.lock"):
        # Keep generated documents, source copies and session data out of default Git adds.
        ignore = root / ".gitignore"
        if not ignore.exists():
            write_text(ignore, "*\n")
        return render_project_preferences(root, read_project_preferences(root))


def stage_preference(data, args, root):
    scope = args.scope
    target = {"scope": scope}
    if scope == "personal":
        target["profile"] = required_text(data, "profile")
    if args.action == "profile-propose":
        item = read_object(args.input)
        key = safe_identifier(required_text(item, "key"), "偏好需要有效的 key。").lower()
        language = item.get("language", "both")
        require(language in ("zh", "en", "both"), "language 须为 zh、en 或 both。")
        sections = item.get("sections", [])
        require(
            isinstance(sections, list) and all(isinstance(s, str) and s.strip() for s in sections),
            "sections 须为章节名列表。所有章节适用时可留空。",
        )
        pending = {
            **target, "action": "save", "key": key,
            "preference": {
                "text": required_text(item, "text"),
                "language": language,
                "sections": [section.strip() for section in sections],
            },
        }
    else:
        key = safe_identifier(args.key, "偏好需要有效的 key。").lower()
        record = read_profile(target["profile"]) if scope == "personal" else read_project_preferences(root)
        require(key in record["preferences"], "该范围内没有这条偏好。")
        pending = {**target, "action": "remove", "key": key}
    data["pending_preference"] = pending
    return pending


def profile_decision(data, prompt, root):
    commands = {
        "保存写作偏好": ("save", "project"),
        "savethiswritingpreference": ("save", "project"),
        "删除写作偏好": ("remove", "project"),
        "removethiswritingpreference": ("remove", "project"),
        "保存个人写作偏好": ("save", "personal"),
        "savethispersonalwritingpreference": ("save", "personal"),
        "删除个人写作偏好": ("remove", "personal"),
        "removethispersonalwritingpreference": ("remove", "personal"),
    }
    decision = commands.get(normalize_prompt(prompt).casefold())
    if decision is None:
        return None
    action, scope = decision
    pending = data.get("pending_preference")
    require(pending and pending["action"] == action, "先展示要保存或删除的具体偏好，再确认。")
    require("scope" in pending, "旧版偏好提案未标明范围，请重新登记后确认。")
    require(scope == pending["scope"], "确认指令的范围与待处理偏好不一致。")
    alias = pending.get("profile")
    path = profile_path(alias) if scope == "personal" else root / "writing-preferences.json"
    with file_lock(path.with_suffix(".lock")):
        record = read_profile(alias) if scope == "personal" else read_project_preferences(root)
        if action == "save":
            record["preferences"][pending["key"]] = pending["preference"]
        else:
            record["preferences"].pop(pending["key"], None)
        save_state(path, record)
        if scope == "project":
            render_project_preferences(root, record)
    data.pop("pending_preference")
    target = f"个人档案 {alias}" if scope == "personal" else "当前项目"
    return f"{target} 已更新写作偏好 {pending['key']}。"


def confirm_profile_from_terminal(data, root):
    require(sys.stdin.isatty(), "profile-confirm 需要用户在交互式终端亲自输入。")
    require(data.get("pending_preference"), "先展示要保存或删除的具体偏好。")
    emit(data["pending_preference"])
    try:
        command = input("请输入与所列范围一致的确认指令（如「保存写作偏好」或「保存个人写作偏好」）：")
    except EOFError as error:
        raise GateError("未收到偏好确认。") from error
    decision = profile_decision(data, command, root)
    require(decision, "未收到明确的偏好修改指令。")
    return decision


def current_round(state):
    return state.get("round", 1)


def needs_full_results(state):
    return ReferenceLibrary.section_key(state["section"]) in ("摘要", "结论")


def missing_study(state):
    def ready(note):
        return note.get("round") == current_round(state) and (
            not needs_full_results(state) or bool(note.get("results_coverage"))
        )

    return [
        reference for reference in state["references"]
        if not ready(state["study"].get(reference, {}))
    ]


def require_study(state):
    missing = missing_study(state)
    require(not missing, "尚未完成这些指定范文的对应章节学习：" + "、".join(missing))


def require_open_round(state):
    require(not state.get("final"), "本轮已交付。如用户提出修改，请先登记反馈开启下一轮。")


def plan_revision(state):
    require_open_round(state)
    require_study(state)
    require(state.get("plan"), "先梳理并登记章节提纲。")
    if needs_full_results(state):
        require(state["plan"].get("results_hash"), "摘要和结论须核对本文完整结果后重新登记提纲。")
    content = [
        current_round(state), state["section"], state["references"],
        state["study"], state["plan"],
    ]
    if state.get("mode") == "polish":
        content.extend(("polish", state["source"]))
    if state.get("language"):
        content.append(state["language"])
    return digest(content)


def require_start(state):
    revision = plan_revision(state)
    require(
        state.get("authorization", {}).get("revision") == revision,
        "当前章节尚未收到与本轮提纲对应的明确开写或润色指令。",
    )


def status(state):
    if state.get("mode") == "translate":
        return translation_status(state)
    version = state.get("final", {})
    return {
        "mode": state.get("mode", "write"),
        "language": state.get("language"),
        "section": state["section"],
        "round": current_round(state),
        "references": state["references"],
        "missing_study": missing_study(state),
        "feedback_registered": bool(state.get("feedback")),
        "plan_ready": bool(state.get("plan")) and (
            not needs_full_results(state) or bool(state["plan"].get("results_hash"))
        ),
        "writing_authorized": not version and bool(state.get("authorization")),
        "draft_ready": bool(state.get("draft")),
        "humanizer_read": bool(state.get("humanizer")),
        "final_ready": bool(version),
        "accepted": bool(version.get("accepted")),
    }


def invalidate_writing(state):
    for field in ("authorization", "draft", "humanizer", "editor_read", "final"):
        state.pop(field, None)


def object_fields(record, field, required_fields):
    item = record.get(field)
    require(isinstance(item, dict), f"缺少 {field} 记录。")
    return {name: required_text(item, name) for name in required_fields}


def normal_text(value):
    return " ".join(value.split())


def read_paper_context(notes, context, section):
    paper = object_fields(notes, "paper_context", PAPER_FIELDS)
    evidence = notes["paper_context"].get("evidence")
    require(isinstance(evidence, list) and evidence, "整篇论文分析需要章节之外的原文定位。")
    paper["evidence"] = []
    for item in evidence:
        require(isinstance(item, dict), "整文定位应为 JSON 对象。")
        location = required_text(item, "location")
        anchor = required_text(item, "anchor")
        normalized = normal_text(anchor)
        require(normalized in context and normalized not in section, "整文定位须来自目标章节之外的正文。")
        paper["evidence"].append({"location": location, "anchor": anchor})
    return paper


def read_transition(notes, excerpt):
    transition = object_fields(notes, "paragraph_transition", ("from", "to", "observation", "application"))
    paragraphs = [normal_text(part) for part in re.split(r"\n(?:[ \t]*\n)+", excerpt)]
    before = normal_text(transition["from"])
    after = normal_text(transition["to"])
    if len(paragraphs) > 1:
        adjacent = any(
            before in left and after in right for left, right in zip(paragraphs, paragraphs[1:])
        )
    else:
        start = paragraphs[0].find(before)
        adjacent = start >= 0 and paragraphs[0].find(after, start + len(before)) >= 0
    require(adjacent, "衔接例句须来自相邻段落。单段章节须按原文顺序定位相邻论证动作。")
    return transition


def read_sentence_patterns(notes, source_text):
    examples = notes.get("sentence_patterns", [])
    require(isinstance(examples, list), "sentence_patterns 应为句式条目的列表。")
    patterns = []
    for item in examples:
        require(isinstance(item, dict), "每条 sentence_patterns 记录应为 JSON 对象。")
        pattern = {key: required_text(item, key) for key in ("anchor", "location", "template", "application")}
        anchor = normal_text(pattern["anchor"])
        template = normal_text(pattern["template"])
        require(anchor in source_text, "句式例句不在所读章节中。")
        require(template != anchor and re.search(r"\{[^{}]+\}", template), "句式骨架需用 {槽位} 标出要替换的内容。")
        patterns.append(pattern)
    return patterns


def read_results_coverage(record, field, results_text):
    coverage = object_fields(record, field, ("selection",))
    blocks = record[field].get("blocks")
    require(isinstance(blocks, list) and blocks, f"{field} 须逐项记录结果小节的定位与取舍。")
    coverage["blocks"] = []
    locations = set()
    for item in blocks:
        require(isinstance(item, dict), f"{field} 的结果条目须为 JSON 对象。")
        block = {key: required_text(item, key) for key in ("location", "anchor", "use")}
        location = normal_text(block["location"]).casefold()
        anchor = normal_text(block["anchor"])
        require(location not in locations, f"{field} 的结果定位重复：{block['location']}")
        require(anchor in results_text, f"{field} 的结果原句须来自结果材料：{block['location']}")
        locations.add(location)
        coverage["blocks"].append(block)
    return coverage


def record_study(state, reference, excerpt_path, context_path, notes_path, results_path):
    require_open_round(state)
    require(reference in state["references"], f"该文献未由用户指定：{reference}")
    excerpt = read_text(excerpt_path)
    context = read_text(context_path)
    notes = read_object(notes_path)
    require(required_text(notes, "section") == state["section"], "范文记录的章节与写作目标不一致。")
    location = required_text(notes, "location")
    source_text = normal_text(excerpt)
    paper_context = read_paper_context(notes, normal_text(context), source_text)
    transition = read_transition(notes, excerpt)
    patterns = {}
    for category in PATTERNS:
        item = object_fields(notes, category, ("anchor", "observation", "application"))
        require(normal_text(item["anchor"]) in source_text, f"{category} 的例句不在所读章节中。")
        patterns[category] = item
    record = {
        "round": current_round(state),
        "location": location,
        "excerpt_hash": digest(excerpt),
        "context_hash": digest(context),
        "paper_context": paper_context,
        "paragraph_transition": transition,
        "patterns": patterns,
    }
    sentence_patterns = read_sentence_patterns(notes, source_text)
    if sentence_patterns:
        record["sentence_patterns"] = sentence_patterns
    results = None
    if needs_full_results(state):
        require(results_path, "摘要和结论须用 --results 提供范文完整研究结果。")
        results = read_text(results_path)
        record["results_coverage"] = read_results_coverage(notes, "results_coverage", normal_text(results))
        record["results_hash"] = digest(results)
    assign_study(state, reference, record)
    return record, excerpt, context, results


def assign_study(state, reference, record):
    if state["study"].get(reference) != record:
        state["study"][reference] = record
        state.pop("plan", None)
        invalidate_writing(state)


def record_plan(state, path, results_path):
    require_open_round(state)
    require_study(state)
    plan = read_object(path)
    # The receipt is issued here from an actual file, never from the outline JSON.
    plan.pop("results_hash", None)
    if needs_full_results(state):
        require(results_path, "摘要和结论须用 --results 提供本文完整研究结果。")
        results = read_text(results_path)
        plan["results_selection"] = read_results_coverage(
            plan, "results_selection", normal_text(results),
        )
        plan["results_hash"] = digest(results)
    required_text(plan, "section_purpose")
    object_fields(plan, "paper_context", PAPER_FIELDS)
    required_text(plan, "section_flow")
    user_logic = plan.get("user_logic")
    require(isinstance(user_logic, str), "user_logic 应为字符串。用户未提供思路时留空。")
    required_text(plan, "reference_decisions")
    if state.get("feedback"):
        required_text(plan, "feedback_response")
    paragraphs = plan.get("paragraphs")
    require(isinstance(paragraphs, list) and paragraphs, "提纲应包含至少一个段落。")
    for paragraph in paragraphs:
        require(isinstance(paragraph, dict), "每条提纲应是 JSON 对象。")
        for field in ("point", "evidence", "link"):
            required_text(paragraph, field)
    if state.get("plan") != plan:
        state["plan"] = plan
        invalidate_writing(state)


def record_revision(state, path, references):
    require(state.get("final"), "先完成本轮交付。若用户还在修改提纲，请在本轮更新提纲。")
    feedback = read_text(path)
    new_references = reference_ids(references) if references is not None else state["references"]
    state.setdefault("history", []).append({
        "round": current_round(state),
        "references": state["references"],
        "feedback": state.get("feedback"),
        "study": state["study"],
        "plan": state["plan"],
        "source": state.get("source"),
        "draft": state.get("draft"),
        "final": state["final"],
    })
    if state.get("mode") == "polish":
        state["source"] = state["final"]["text"]
    state["round"] = current_round(state) + 1
    state["references"] = new_references
    state["study"] = {
        ref: state["study"][ref] for ref in new_references if ref in state["study"]
    }
    state["feedback"] = feedback
    state.pop("plan", None)
    invalidate_writing(state)


def normalize_prompt(prompt):
    return re.sub(r"\s+", "", prompt).rstrip("。！!.")


def is_start(prompt, section, mode):
    normalized = normalize_prompt(prompt)
    section = re.escape(normalize_prompt(section))
    if mode == "polish":
        return bool(
            re.fullmatch(rf"(?:请|可以|现在)?开始润色(?:{section}|正文|这节)?(?:吧|了)?", normalized)
            or re.fullmatch(rf"(?:please)?startpolishing(?:{section}|thissection)?", normalized, re.IGNORECASE)
        )
    return bool(
        re.fullmatch(
            rf"(?:好[,，]?)?(?:请|可以|现在)?(?:按(?:这个|当前)提纲)?开始写(?:{section}|正文|这节|这一节|这一部分)?(?:吧|了)?",
            normalized,
        )
        or re.fullmatch(rf"(?:please)?startwriting(?:{section}|thissection)?", normalized, re.IGNORECASE)
    )


def is_satisfaction(prompt):
    return normalize_prompt(prompt).casefold() in {
        "满意", "满意了", "这版满意", "这版我满意", "这版可以了", "这版定稿", "就按这版定稿", "定稿",
        "acceptthisversion",
    }


def translation_request(prompt):
    parts = re.split(r"[：:]", prompt, maxsplit=1)
    command = normalize_prompt(parts[0]).casefold().removeprefix("请")
    inline = len(parts) == 2 and bool(parts[1].strip())
    if command in {
        "把这段翻译成英文", "将这段翻译成英文", "把这段翻成英文", "把下面这段翻译成英文",
        "翻译这一段", "translatethisparagraphintoenglish", "pleasetranslatethisparagraphintoenglish",
    }:
        return "paragraph", True
    if command in {
        "把这篇论文翻译成英文", "把全文翻译成英文", "把全文都翻译成英文", "将全文翻译成英文",
        "translatethewholemanuscriptintoenglish", "pleasetranslatethewholemanuscriptintoenglish",
    }:
        return "manuscript", True
    if command in {"开始逐段翻译", "逐段翻译成英文", "逐段英译", "逐段翻译", "starttranslatingparagraphbyparagraph"}:
        return "paragraph", inline
    if command in {
        "开始翻译整篇", "开始翻译全文", "整篇翻译成英文", "整篇文章翻译成英文",
        "全文翻译成英文", "翻译全文", "整篇英译",
    }:
        return "manuscript", inline
    if command in {"开始翻译", "翻译成英文", "开始英译", "starttranslating", "translateintoenglish"}:
        return "active", inline
    return None, False


def translation_revision(state):
    require_open_round(state)
    return digest((state["section"], state["scope"], state["units"], state["glossary"]))


def authorize_translation(state, scope, receipt):
    require(scope in {"active", state["scope"]}, "翻译指令的范围与登记范围不同。")
    state["authorization"] = {"revision": translation_revision(state), **receipt}
    return f"用户已授权英译《{state['section']}》。"


def require_translation_start(state):
    require(
        state.get("authorization", {}).get("revision") == translation_revision(state),
        "等待用户对当前原文和范围下达明确的英译指令。",
    )


def next_translation_unit(state):
    return next((
        unit for unit in state["units"]
        if not unit["verbatim"] and unit["id"] not in state["translated"]
    ), None)


def translation_status(state):
    version = state.get("final", {})
    unit = next_translation_unit(state)
    return {
        "mode": "translate",
        "section": state["section"],
        "scope": state["scope"],
        "translation_authorized": not version and bool(state.get("authorization")),
        "translated_units": len(state["translated"]),
        "expected_units": sum(not unit["verbatim"] for unit in state["units"]),
        "next_unit": unit["id"] if unit else None,
        "final_ready": bool(version),
        "accepted": bool(version.get("accepted")),
    }


def init_translation(data, args):
    label = args.name.strip()
    require(label, "需要给翻译任务一个名称。")
    manifest = read_object(args.input)
    units = manifest.get("units")
    require(isinstance(units, list) and units, "翻译清单需要有序的 units 列表。")
    glossary = manifest.get("glossary", {})
    require(isinstance(glossary, dict), "glossary 应为中文术语到英文术语的对象。")
    glossary = {term: required_text(glossary, term) for term in glossary}
    ordered = []
    ids = set()
    for unit in units:
        require(isinstance(unit, dict), "翻译单元须是 JSON 对象。")
        identifier = required_text(unit, "id")
        require(identifier not in ids, f"翻译单元编号重复：{identifier}")
        ids.add(identifier)
        verbatim = unit.get("verbatim", False)
        require(isinstance(verbatim, bool), "verbatim 需要为 true 或 false。")
        ordered.append({"id": identifier, "text": required_text(unit, "text"), "verbatim": verbatim})
    require(any(not unit["verbatim"] for unit in ordered), "清单没有需要英译的正文。")
    key = task_key("translate", label)
    state = data["tasks"].get(key)
    if state:
        require(
            (state["scope"], state["units"], state["glossary"]) == (args.scope, ordered, glossary),
            "同名翻译任务的原文、术语或范围不同。请用新任务名保留旧版。",
        )
    else:
        state = {
            "mode": "translate", "section": label, "scope": args.scope,
            "units": ordered, "glossary": glossary, "translated": {},
        }
    if pending := data.get("pending_translation"):
        authorize_translation(state, pending["scope"], pending["receipt"])
        data.pop("pending_translation")
    data["tasks"][key] = state
    data["active"] = key
    return state


def handle_translation(args, state):
    require_translation_start(state)
    if args.action == "check-translate":
        return translation_status(state)
    if args.action == "read-translator":
        guide = read_text(ENGLISH_TRANSLATION)
        state["translator_read"] = translation_revision(state)
        return guide
    require(state.get("translator_read") == translation_revision(state), "先读取内置英译流程。")
    unit = next_translation_unit(state)
    if args.action == "next-translation":
        return {"unit": unit, "glossary": state["glossary"]}
    if args.action == "save-translation":
        if args.replace:
            require(args.unit in state["translated"], "只能替换已经翻译的单元。")
        else:
            require(unit and args.unit == unit["id"], "须按原文顺序提交当前翻译单元。")
        result = read_object(args.input)
        state["translated"][args.unit] = {
            "text": required_text(result, "text"),
            "review": object_fields(result, "review", TRANSLATION_UNIT_REVIEW),
        }
        progress = {"unit": args.unit, **translation_status(state)}
        if state["scope"] == "paragraph":
            progress["text"] = state["translated"][args.unit]["text"]
        return progress
    if args.action == "finish-translation":
        require(not unit, "仍有原文单元没有译文。")
        checks = object_fields(read_object(args.input), "review", TRANSLATION_FINAL_REVIEW)
        text = "\n\n".join(
            item["text"] if item["verbatim"] else state["translated"][item["id"]]["text"]
            for item in state["units"]
        )
        state["final"] = {"text": text, "review": checks}
        return text
    raise GateError("请使用英译命令，或先切换到写作／润色任务。")


def record_user_decision(state, prompt, receipt):
    section = state["section"]
    if is_satisfaction(prompt):
        require(state.get("final"), "需要先交付本轮，才能确认本轮稿件。")
        state["final"]["accepted"] = receipt
        return f"用户已确认当前《{section}》本轮稿件满意。"
    mode = state.get("mode", "write")
    if mode == "translate":
        scope, _ = translation_request(prompt)
        return authorize_translation(state, scope, receipt) if scope else None
    if is_start(prompt, section, mode):
        state["authorization"] = {"revision": plan_revision(state), **receipt}
        action = "润色" if mode == "polish" else "撰写"
        return f"用户已授权{action}当前《{section}》提纲对应的正文。"
    return None


def prompt_hook(host, workspace=None):
    event = submission(json.load(sys.stdin), host)
    if event is None:
        return
    session = required_text(event, "session")
    workspace_candidates = event.get("workspaces") or [event.get("cwd") or Path.cwd()]
    workspaces = [Path(location).resolve() for location in workspace_candidates]
    if workspace is not None:
        workspace = Path(workspace).resolve()
        if not any(location.is_relative_to(workspace) for location in workspaces):
            return
    workspace = workspace or workspaces[0]
    path = state_path(session, workspace)
    prefix = f"{SKILL_NAME} 会话 {session}。"
    data = read_session(path)
    prompt = event["prompt"]

    def hook_context(message):
        response = format_context(host, prefix + message)
        if isinstance(response, str):
            print(response)
        else:
            emit(response)

    if host in CONTEXT_ONLY:
        state = data["tasks"].get(data["active"])
        context = "使用此 Skill 时，请用终端的 user-confirm 或 profile-confirm 确认。"
        if state:
            context += " 当前阶段：" + json.dumps(status(state), ensure_ascii=False)
        hook_context(context)
        return
    if host == "antigravity":
        # PreInvocation can report the same last submitted user text many times.
        fingerprint = digest(prompt)
        if data.get("last_antigravity_input") == fingerprint:
            return
        data["last_antigravity_input"] = fingerprint
        save_state(path, data)

    try:
        preference_result = profile_decision(data, prompt, workspace / WORK_DATA)
    except GateError as error:
        hook_context(str(error))
        return
    if preference_result:
        save_state(path, data)
        hook_context(preference_result)
        return
    receipt = {"source": host, "turn": event["turn"]}
    scope, new_target = translation_request(prompt)
    previous_pending = data.pop("pending_translation", None)
    state = data["tasks"].get(data["active"], {})
    if scope and (state.get("mode") != "translate" or state.get("final") or new_target):
        if scope != "active":
            data["pending_translation"] = {"scope": scope, "receipt": receipt}
        if previous_pending or scope != "active":
            save_state(path, data)
        hook_context("已收到明确英译请求。按用户指定范围登记原文。范围未明时先确认逐段或整篇。")
        return
    if data["active"] is None:
        if previous_pending:
            save_state(path, data)
        hook_context("使用该 Skill 时，在论文目录运行 project-init 建档，再登记用户指定范文和写作章节。")
        return
    try:
        decision = record_user_decision(state, prompt, receipt)
    except GateError as error:
        if previous_pending:
            save_state(path, data)
        hook_context(str(error))
        return
    if decision:
        save_state(path, data)
        hook_context(decision)
        return
    has_work = state.get("translated") if state.get("mode") == "translate" else state.get("draft")
    if state.get("authorization") and not has_work:
        state.pop("authorization")
        previous_pending = True
    if previous_pending:
        save_state(path, data)
    hook_context("当前阶段：" + json.dumps(status(state), ensure_ascii=False))


def terminal_confirmation(state):
    require(sys.stdin.isatty(), "user-confirm 需要用户在交互式终端亲自输入。")
    section = state["section"]
    if state.get("final"):
        expected = "这版我满意 / Accept this version"
    elif state.get("mode") == "translate":
        expected = "开始翻译 / Start translating"
    elif state.get("mode") == "polish":
        expected = f"开始润色{section} / Start polishing"
    else:
        expected = f"开始写{section} / Start writing"
    if not state.get("final"):
        if state.get("mode") == "translate":
            translation_revision(state)
        else:
            plan_revision(state)
    try:
        prompt = input(f"《{section}》第 {current_round(state)} 轮。确认时输入「{expected}」：")
    except EOFError as error:
        raise GateError("未收到确认。") from error
    decision = record_user_decision(state, prompt, {"source": "user-terminal"})
    require(decision, "未收到与当前任务匹配的明确指令。")
    print(decision)


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def reference_ids(values):
    references = [value.strip() for value in values]
    require(references and all(references) and len(set(references)) == len(references), "指定范文须非空且彼此唯一。")
    return references


def init_chapter(data, args):
    references = reference_ids(args.references)
    section = args.section.strip()
    require(section, "需要明确写作章节。")
    require(not args.source or args.mode == "polish", "只有润色任务接收已有稿件 --source。")
    key = task_key(args.mode, section)
    state = data["tasks"].get(key)
    source = read_text(args.source) if args.source else (state or {}).get("source")
    require(args.mode != "polish" or source, "润色需用 --source 登记用户现稿。")
    language = args.language or (state or {}).get("language")

    if state is None:
        state = {
            "mode": args.mode, "section": section, "round": 1,
            "references": references, "study": {},
        }
    elif (references, source, language) != (
        state["references"], state.get("source"), state.get("language"),
    ):
        require_open_round(state)
        archived = deepcopy({name: value for name, value in state.items() if name != "previous_setups"})
        state.setdefault("previous_setups", []).append(archived)
        state["references"] = references
        state["study"] = {ref: note for ref, note in state["study"].items() if ref in references}
        state.pop("plan", None)
        invalidate_writing(state)
    if source:
        state["source"] = source
    if language:
        state["language"] = language
    data["tasks"][key] = state
    data["active"] = key
    return state


def register_selected_references(library, references):
    entries = [library.register(reference) for reference in references]
    require(len({entry["id"] for entry in entries}) == len(entries), "同一文献请只选一个标识。")
    return entries


def apply_saved_study(state, reference, library, entry):
    note = library.reusable(entry, state["section"])
    if note is None or (needs_full_results(state) and not note.get("results_coverage")):
        return False
    assign_study(state, reference, {**deepcopy(note), "round": current_round(state)})
    return True


def reference_details(library, entry, *, include_studies=False, section=None):
    result = {key: value for key, value in entry.items() if key not in ("files", "sections")}
    result["available_sections"] = [notes[-1]["section"] for notes in entry["sections"].values()]
    files = [dict(file, local_path=str(library.root / file["path"])) for file in entry["files"]]
    result["local_files"] = files
    if include_studies:
        result["studies"] = entry["sections"] if section is None else {
            library.section_key(section): entry["sections"].get(library.section_key(section), [])
        }
        result["active_attachment"] = library.attachment_version(entry)
    return result


def manage_references(args):
    root = Path.cwd() / WORK_DATA
    if args.action == "reference-show":
        library = ReferenceLibrary(root)
        entry = library.find(args.reference)
        require(entry, "项目目录里没有这篇文献。")
        emit(reference_details(library, entry, include_studies=True, section=args.section))
        return
    preferences = initialize_project_preferences(root)
    with ReferenceLibrary.edit(root) as library:
        if args.action == "reference-add":
            entry = library.register(
                args.reference, title=args.title, doi=args.doi,
                source=args.source, file=args.file, note=args.note,
            )
            library.save()
            emit({"reference_index": str(library.markdown), "writing_preferences": str(preferences),
                  "reference": reference_details(library, entry)})
            return
        library.save()
        emit({
            "reference_index": str(library.markdown),
            "writing_preferences": str(preferences),
            "references": [reference_details(library, entry) for entry in library.entries],
        })


def run(args):
    if args.action == "prompt-hook":
        prompt_hook(args.host, args.workspace)
        return
    if args.action in ("project-init", "references", "reference-add", "reference-show"):
        manage_references(args)
        return
    path = state_path(args.session)
    data = read_session(path)
    root = Path.cwd() / WORK_DATA
    if args.action == "profile-use":
        alias = profile_path(args.alias).stem
        if data.get("profile") != alias:
            data["profile"] = alias
            data.pop("pending_preference", None)
        save_state(path, data)
        emit(read_profile(alias))
        return
    if args.action == "profile-show":
        if args.scope == "personal":
            emit(read_profile(required_text(data, "profile")))
        else:
            markdown = initialize_project_preferences(root)
            emit({**read_project_preferences(root), "writing_preferences": str(markdown)})
        return
    if args.action in {"profile-propose", "profile-remove"}:
        pending = stage_preference(data, args, root)
        save_state(path, data)
        emit(pending)
        return
    if args.action == "profile-confirm":
        decision = confirm_profile_from_terminal(data, root)
        save_state(path, data)
        print(decision)
        return
    if args.action == "init":
        state = init_chapter(data, args)
        preferences = initialize_project_preferences(root)
        reused = []
        with ReferenceLibrary.edit(root) as library:
            entries = register_selected_references(library, state["references"])
            if not state.get("final"):
                missing = set(missing_study(state))
                previous = data["tasks"].get(task_key("write", state["section"]), {})
                for reference, entry in zip(state["references"], entries):
                    if reference not in missing:
                        continue
                    if apply_saved_study(state, reference, library, entry):
                        reused.append(reference)
                    elif state["mode"] == "polish" and not needs_full_results(state) and not entry["files"] and not entry["sections"]:
                        # A fileless study created before the reference library existed.
                        note = previous.get("study", {}).get(reference)
                        if note and note.get("round") == current_round(previous):
                            assign_study(state, reference, {**deepcopy(note), "round": current_round(state)})
                            reused.append(reference)
            library.save()
        save_state(path, data)
        emit({**status(state), "reference_index": str(library.markdown),
              "writing_preferences": str(preferences), "reused_study": reused})
        return
    if args.action == "translate-init":
        state = init_translation(data, args)
        preferences = initialize_project_preferences(root)
        with ReferenceLibrary.edit(root) as library:
            library.save()
        save_state(path, data)
        emit({**status(state), "reference_index": str(library.markdown), "writing_preferences": str(preferences)})
        return
    if args.action == "chapters":
        entries = [status(state) for state in data["tasks"].values()]
        emit({
            "active": data["active"],
            "chapters": [entry for entry in entries if entry["mode"] != "translate"],
            "translations": [entry for entry in entries if entry["mode"] == "translate"],
        })
        return
    if args.action == "resume":
        key = task_key(args.mode, args.section.strip())
        require(key in data["tasks"], "该章节或翻译任务尚未登记。")
        data["active"] = key
        save_state(path, data)
        emit(status(data["tasks"][key]))
        return
    state = active_task(data)
    if args.action == "show":
        emit(state)
        return
    if args.action == "user-confirm":
        terminal_confirmation(state)
        save_state(path, data)
        return
    if args.action == "status":
        emit(status(state))
        return
    if state.get("mode") == "translate":
        value = handle_translation(args, state)
        if args.action in {"read-translator", "save-translation", "finish-translation"}:
            save_state(path, data)
        if isinstance(value, str):
            print(value)
        else:
            emit(value)
        return
    if args.action == "study":
        record, excerpt, context, results = record_study(
            state, args.reference, args.excerpt, args.context, args.notes, args.results,
        )
        with ReferenceLibrary.edit(Path.cwd() / WORK_DATA) as library:
            entry = library.register(args.reference)
            library.archive(entry, state["section"], record, excerpt, context, results=results)
            library.save()
    elif args.action == "reuse-study":
        require_open_round(state)
        require(args.reference in state["references"], f"该文献未由用户指定：{args.reference}")
        library = ReferenceLibrary(Path.cwd() / WORK_DATA)
        entry = library.find(args.reference)
        require(
            entry and apply_saved_study(state, args.reference, library, entry),
            "当前版本没有可用的对应章节记录。请读取项目里的原文并登记本节学习。",
        )
    elif args.action == "plan":
        record_plan(state, args.input, args.results)
    elif args.action == "revise":
        record_revision(state, args.input, args.references)
        with ReferenceLibrary.edit(Path.cwd() / WORK_DATA) as library:
            register_selected_references(library, state["references"])
            library.save()
    elif args.action == "check-start":
        require_start(state)
        emit(status(state))
        return
    elif args.action == "read-editor":
        require(state.get("mode") == "polish", "请先切换到润色任务。")
        require_start(state)
        guide = read_text(ACADEMIC_EDITING)
        state["editor_read"] = plan_revision(state)
        save_state(path, data)
        print(guide)
        return
    elif args.action == "save-draft":
        require_start(state)
        if state.get("mode") == "polish":
            require(state.get("editor_read") == plan_revision(state), "润色现稿前先读取内置润色流程。")
        draft = read_text(args.input)
        if state.get("draft") != draft:
            state["draft"] = draft
            state.pop("humanizer", None)
            state.pop("final", None)
    elif args.action == "read-humanizer":
        require_start(state)
        require(state.get("draft"), "先完成并登记整节初稿。")
        skill = read_text(HUMANIZER)
        state["humanizer"] = {"source": "bundled", "draft_hash": digest(state["draft"])}
        save_state(path, data)
        print(skill)
        return
    elif args.action == "finalize":
        require_start(state)
        require(
            state.get("draft") and state.get("humanizer", {}).get("draft_hash") == digest(state["draft"]),
            "先读取内置 academic-humanizer 并修订当前初稿。",
        )
        review = read_object(args.input)
        checks = object_fields(review, "review", REVIEW_FIELDS)
        final = required_text(review, "text")
        prose_check = object_fields(review["review"], "prose_check", ("anchor", "assessment"))
        require(normal_text(prose_check["anchor"]) in normal_text(final), "prose_check 的原句须在最终正文中。")
        checks["prose_check"] = prose_check
        if state.get("mode") == "polish":
            checks.update(object_fields(review, "review", ("source_fidelity",)))
        if state.get("feedback"):
            checks.update(object_fields(review, "review", ("feedback_addressed",)))
        state["final"] = {"text": final, "review": checks}
        save_state(path, data)
        print(final)
        return
    else:
        raise GateError("请先切换到对应的工作模式。")
    save_state(path, data)
    emit(status(state))


def main():
    # Codex and PowerShell may use different console encodings on Windows.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", help="stable writing session identifier")
    sub = parser.add_subparsers(dest="action", required=True)
    hook = sub.add_parser("prompt-hook")
    hook.add_argument("--host", choices=HOSTS, default="codex")
    hook.add_argument("--workspace", type=Path, help="only accept sessions in this workspace")
    sub.add_parser("profile-use").add_argument("alias")
    for action, field in (("profile-propose", "input"), ("profile-remove", "key"), ("profile-show", None)):
        profile = sub.add_parser(action)
        profile.add_argument("--scope", choices=("project", "personal"), default="project")
        if field:
            profile.add_argument(field)
    sub.add_parser("profile-confirm")
    sub.add_parser("project-init", help="initialize both workspace Markdown archives")
    sub.add_parser("references", help="create or list the workspace bibliography")
    entry = sub.add_parser("reference-add")
    entry.add_argument("reference")
    entry.add_argument("--title")
    entry.add_argument("--doi")
    entry.add_argument("--source", help="public source or URL")
    entry.add_argument("--file", type=Path, help="user-supplied original to retain in this workspace")
    entry.add_argument("--note")
    show_reference = sub.add_parser("reference-show")
    show_reference.add_argument("reference")
    show_reference.add_argument("--section")
    init = sub.add_parser("init")
    init.add_argument("section")
    init.add_argument("references", nargs="+")
    init.add_argument("--mode", choices=("write", "polish"), default="write")
    init.add_argument("--source", help="UTF-8 manuscript text for polish mode")
    init.add_argument("--language", choices=("zh", "en"))
    resume = sub.add_parser("resume")
    resume.add_argument("section")
    resume.add_argument("--mode", choices=("write", "polish", "translate"), default="write")
    translation = sub.add_parser("translate-init")
    translation.add_argument("name")
    translation.add_argument("--scope", choices=("paragraph", "manuscript"), required=True)
    translation.add_argument("input")
    translation_unit = sub.add_parser("save-translation")
    translation_unit.add_argument("unit")
    translation_unit.add_argument("input")
    translation_unit.add_argument("--replace", action="store_true")
    study = sub.add_parser("study")
    study.add_argument("reference")
    study.add_argument("excerpt")
    study.add_argument("context")
    study.add_argument("notes")
    study.add_argument("--results", help="UTF-8 complete reference results for abstract or conclusion")
    sub.add_parser("reuse-study").add_argument("reference")
    revise = sub.add_parser("revise")
    revise.add_argument("input")
    revise.add_argument("--references", nargs="+")
    plan = sub.add_parser("plan")
    plan.add_argument("input")
    plan.add_argument("--results", help="UTF-8 complete author results for abstract or conclusion")
    for action in ("save-draft", "finalize", "finish-translation"):
        sub.add_parser(action).add_argument("input")
    for action in (
        "status", "chapters", "show", "check-start", "read-editor", "read-humanizer",
        "check-translate", "read-translator", "next-translation", "user-confirm",
    ):
        sub.add_parser(action)
    try:
        run(parser.parse_args())
    except (GateError, ValueError, OSError) as error:
        print(f"写作流程未通过：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
