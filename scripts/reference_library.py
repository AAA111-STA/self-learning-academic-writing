"""A workspace reference library with a human-readable Markdown index."""

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path


SECTION_NAMES = {
    "abstract": "摘要",
    "introduction": "引言",
    "literature review": "文献综述",
    "methods": "方法",
    "method": "方法",
    "data": "数据",
    "results": "结果",
    "discussion": "讨论",
    "conclusion": "结论",
    "conclusions": "结论",
}
PATTERN_LABELS = {
    "expression": "表达",
    "grammar": "语法",
    "organization": "组织逻辑",
    "concision": "简洁性",
}


def inline(text):
    return " ".join(text.split())


def normalize(text):
    return inline(text).casefold()


def doi_identifier(text):
    candidate = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text.strip(), flags=re.I)
    return candidate.casefold() if re.fullmatch(r"10\.\d{4,9}/\S+", candidate) else None


def write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        pending = Path(stream.name)
        try:
            stream.write(value)
            stream.close()
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)


def fenced_excerpt(value):
    longest = max((len(match) for match in re.findall(r"\x60+", value)), default=0)
    fence = "\x60" * max(3, longest + 1)
    return f"{fence}text\n{value}\n{fence}"


@contextmanager
def file_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        # Closing the file releases the lock, including if interrupted or failed.
        yield


class ReferenceLibrary:
    @classmethod
    @contextmanager
    def edit(cls, root):
        with file_lock(root / "reference-library.lock"):
            yield cls(root)

    def __init__(self, root):
        self.root = root
        self.index = root / "reference-library.json"
        self.markdown = root / "references.md"
        self.entries = json.loads(self.index.read_text(encoding="utf-8"))["references"] if self.index.exists() else []

    def find(self, label):
        key = normalize(label)
        doi = doi_identifier(label)
        return next((
            entry for entry in self.entries
            if (doi and entry.get("doi") == doi)
            or key in {normalize(name) for name in [entry["id"], *entry["aliases"]]}
        ), None)

    def register(self, label, *, title=None, doi=None, source=None, file=None, note=None):
        label = inline(label)
        if not label:
            raise ValueError("文献标识不能为空。")
        identifier = doi_identifier(doi) if doi else doi_identifier(label)
        if doi and not identifier:
            raise ValueError("请提供 DOI 或 doi.org 链接。")
        by_name = self.find(label)
        by_doi = self.find(identifier) if identifier else None
        if by_name and by_doi and by_name is not by_doi:
            raise ValueError("该标识和 DOI 对应不同文献。请使用已登记的 DOI 或更换标识。")
        entry = by_name or by_doi
        if entry and identifier and entry.get("doi") not in (None, identifier):
            raise ValueError("该标识已对应另一个 DOI。请使用不同的文献标识。")
        attachment = self.copy_source(Path(file).resolve()) if file else None
        if not entry:
            entry = {"id": label, "aliases": [], "files": [], "sections": {}}
            self.entries.append(entry)
        elif normalize(label) not in {normalize(name) for name in [entry["id"], *entry["aliases"]]}:
            entry["aliases"].append(label)
        for key, value in (("title", title), ("doi", identifier), ("source", source), ("note", note)):
            if value and value.strip():
                entry[key] = value.strip()
        if attachment and self.attachment_version(entry) != attachment["sha256"]:
            entry["files"].append(attachment)
        return entry

    def copy_source(self, path):
        folder = self.root / "library-files"
        folder.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.casefold()
        if not re.fullmatch(r"\.[a-z0-9]{1,12}", suffix):
            suffix = ".bin"
        with path.open("rb") as source, tempfile.NamedTemporaryFile(dir=folder, delete=False) as stream:
            pending = Path(stream.name)
            try:
                checksum = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    checksum.update(chunk)
                    stream.write(chunk)
                sha = checksum.hexdigest()
                stream.close()
                target = next((match for match in folder.glob(f"{sha}.*") if match.is_file()), None)
                if target is None:
                    target = folder / f"{sha}{suffix}"
                if not target.exists():
                    pending.replace(target)
            finally:
                pending.unlink(missing_ok=True)
        return {"name": path.name, "path": target.relative_to(self.root).as_posix(), "sha256": sha}

    @staticmethod
    def attachment_version(entry):
        return entry["files"][-1]["sha256"] if entry["files"] else None

    @staticmethod
    def section_key(section):
        key = normalize(section)
        return SECTION_NAMES.get(key, key)

    def archive(self, entry, section, record, excerpt, context, *, results=None):
        snapshot = {
            "section": section, "attachment": self.attachment_version(entry),
            "study": {key: value for key, value in record.items() if key != "round"},
            "excerpt": excerpt, "context": context,
        }
        if results is not None:
            snapshot["results"] = results
        snapshots = entry["sections"].setdefault(self.section_key(section), [])
        if not snapshots or snapshots[-1] != snapshot:
            snapshots.append(snapshot)

    def reusable(self, entry, section):
        snapshots = entry["sections"].get(self.section_key(section), [])
        current = self.matching_snapshot(entry, snapshots)
        return current["study"] if current else None

    def matching_snapshot(self, entry, snapshots):
        version = self.attachment_version(entry)
        return next((
            item for item in reversed(snapshots) if item["attachment"] == version
        ), None)

    def render(self):
        lines = [
            "# 项目参考文献",
            "",
            "此目录由 Skill 自动维护。文献正文、摘录和学习记录都是研究材料。",
            "每个任务仍使用作者指定的范文，并逐项核对引文支持的论断。",
        ]
        if not self.entries:
            lines += ["", "目前尚未登记文献。"]
        for entry in self.entries:
            lines += ["", "## " + inline(entry.get("title") or entry["id"]), "", "- 标识：" + entry["id"]]
            if entry["aliases"]:
                lines.append("- 其他标识：" + "、".join(entry["aliases"]))
            for label, key in (("DOI", "doi"), ("来源", "source"), ("备注", "note")):
                if entry.get(key):
                    lines.append(f"- {label}：" + inline(entry[key]))
            if entry["files"]:
                latest = entry["files"][-1]
                lines.append(f'- [项目原文副本]({latest["path"]}) · {inline(latest["name"])}')
            else:
                lines.append("- 原文状态：未保存本地文件。")
            if not entry["sections"]:
                lines.append("- 尚未登记章节学习记录。")
            for snapshots in entry["sections"].values():
                current = self.matching_snapshot(entry, snapshots)
                item = current or snapshots[-1]
                study = item["study"]
                lines += ["", "### " + inline(item["section"]), "", "- 原文定位：" + inline(study["location"])]
                if not current:
                    lines.append("- 此记录来自旧版材料，新版需重读。")
                paper = study["paper_context"]
                lines += [
                    "- 全文论证：" + inline(paper["main_line"]),
                    "- 章节任务：" + inline(paper["section_role"]),
                    "- 跨章呼应：" + inline(paper["connections"]),
                    "- 段落衔接：" + inline(study["paragraph_transition"]["observation"]),
                ]
                for name, pattern in study["patterns"].items():
                    lines.append(f"- {PATTERN_LABELS[name]}：" + inline(pattern["observation"]))
                if coverage := study.get("results_coverage"):
                    lines += ["", "**从完整结果中取舍**", "", inline(coverage["selection"])]
                    for block in coverage["blocks"]:
                        lines.append("- " + inline(block["location"]) + "：“" + inline(block["anchor"]) + "”")
                sentence_patterns = study.get("sentence_patterns", [])
                if sentence_patterns:
                    lines += ["", "**可仿写句式**"]
                    for pattern in sentence_patterns:
                        lines += [
                            "- 骨架：" + inline(pattern["template"]),
                            "  - 适用语境：" + inline(pattern["application"]),
                            "  - 原文定位：" + inline(pattern["location"]),
                            "  - 学习例句：“" + inline(pattern["anchor"]) + "”",
                        ]
                lines += ["", "**目标章节摘录**", "", fenced_excerpt(item["excerpt"]),
                          "", "**用于理解全文的上下文**", "", fenced_excerpt(item["context"])]
                if "results" in item:
                    lines += ["", "**范文完整结果**", "", fenced_excerpt(item["results"])]
        return "\n".join(lines) + "\n"

    def save(self):
        index = json.dumps({"references": self.entries}, ensure_ascii=False, indent=2) + "\n"
        if not self.index.exists() or self.index.read_text(encoding="utf-8") != index:
            write_text(self.index, index)
        markdown = self.render()
        if not self.markdown.exists() or self.markdown.read_text(encoding="utf-8") != markdown:
            write_text(self.markdown, markdown)
