import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / "scripts" / "workflow.py"
HOOK_CONFIG = WORKFLOW.with_name("host_hooks.py")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)
        self.turn = 0
        self.profile_directory = self.workspace / "profiles"

    def write(self, name, value):
        path = self.workspace / name
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run_workflow(self, *arguments, error=None, stdin=None, session="paper"):
        result = subprocess.run(
            [sys.executable, str(WORKFLOW), "--session", session, *arguments],
            cwd=self.workspace, input=stdin, capture_output=True, encoding="utf-8",
            env={**os.environ, "SELF_LEARNING_WRITING_PROFILE_DIR": str(self.profile_directory)},
            timeout=10,
        )
        if error is not None:
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(error, result.stderr)
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def status(self):
        return json.loads(self.run_workflow("status"))

    def prompt(self, message, session="paper"):
        self.turn += 1
        return self.run_workflow("prompt-hook", stdin=json.dumps({
            "hook_event_name": "UserPromptSubmit", "session_id": session,
            "turn_id": str(self.turn), "cwd": str(self.workspace), "prompt": message,
        }))

    def test_switching_chapters_migrates_and_keeps_finished_work(self):
        original = {
            "section": "引言", "round": 2, "references": ["intro-paper"],
            "study": {"intro-paper": {"round": 2, "location": "Introduction, paragraph 1"}},
            "plan": {"section_flow": "从已有研究到研究缺口。"},
            "final": {"text": "已认可的引言", "accepted": True},
            "history": [{"round": 1, "final": {"text": "第一轮引言"}}],
        }
        directory = self.workspace / ".self-academic-writting" / "runs"
        directory.mkdir(parents=True)
        self.write(directory / "paper.json", original)
        self.run_workflow("init", "结果", "results-paper", "--language", "zh")
        self.assertEqual(self.status()["section"], "结果")
        self.run_workflow("resume", "引言")
        self.assertEqual(json.loads(self.run_workflow("show")), original)
        self.run_workflow("resume", "结果")
        self.assertEqual(self.status()["missing_study"], ["results-paper"])

    def test_only_confirmed_preferences_persist_across_sessions(self):
        self.run_workflow("profile-use", "author-a")
        self.run_workflow("profile-propose", self.write("style.json", {
            "key": "evaluation", "text": "比较时写明验证条件。",
            "language": "both", "sections": ["结果"],
        }))
        self.prompt("先不要保存写作偏好")
        self.prompt("这版我满意")
        self.assertFalse((self.profile_directory / "author-a.json").exists())
        self.prompt("保存写作偏好")
        saved = json.loads(self.run_workflow("profile-use", "author-a", session="next"))
        self.assertEqual(saved["preferences"]["evaluation"]["text"], "比较时写明验证条件。")
        other = json.loads(self.run_workflow("profile-use", "author-b", session="other"))
        self.assertEqual(other["preferences"], {})
        self.run_workflow("profile-remove", "evaluation")
        self.assertIn("evaluation", json.loads(self.run_workflow("profile-show"))["preferences"])
        self.prompt("删除写作偏好")
        self.assertEqual(json.loads(self.run_workflow("profile-show", session="next"))["preferences"], {})

    def test_english_polish_has_its_own_authorization_and_keeps_original(self):
        source = "Under spatial validation, the mean error was 4 m."
        self.run_workflow("init", "结果", "result-paper", "--language", "zh")
        self.run_workflow(
            "init", "结果", "result-paper", "--mode", "polish", "--language", "en",
            "--source", self.write("draft.txt", source),
        )
        paper = {"main_line": "按验证条件比较误差", "section_role": "报告误差", "connections": "对应方法"}
        anchor = "The mean error was lower."
        note = {
            "section": "结果", "location": "Results, paragraphs 1–2",
            "paper_context": {
                **paper, "evidence": [{"location": "Methods", "anchor": "We used spatial validation."}],
            },
            "paragraph_transition": {
                "from": "We compared the estimates.", "to": anchor,
                "observation": "先交代比较再汇报结果", "application": "同样的验证条件",
            },
        }
        for key in ("expression", "grammar", "organization", "concision"):
            note[key] = {"anchor": anchor, "observation": "清楚陈述误差", "application": "汇报指标"}
        self.run_workflow(
            "study", "result-paper",
            self.write("excerpt.txt", f"We compared the estimates.\n\n{anchor}"),
            self.write("context.txt", "We used spatial validation."),
            self.write("study.json", note),
        )
        self.run_workflow("plan", self.write("plan.json", {
            "paper_context": paper, "section_purpose": "准确报告误差",
            "section_flow": "交代验证条件后汇报结果", "user_logic": "",
            "reference_decisions": "保留验证条件",
            "paragraphs": [{"point": "误差", "evidence": "现稿数值", "link": "收束"}],
        }))
        amended = self.write("polished.txt", "The mean error was 4 m under spatial validation.")
        self.prompt("开始写")
        self.run_workflow("save-draft", amended, error="明确开写或润色")
        self.prompt("开始润色结果")
        self.run_workflow("save-draft", amended, error="内置润色")
        self.assertIn("中英文学术润色", self.run_workflow("read-editor"))
        self.run_workflow("save-draft", amended)
        self.run_workflow("read-humanizer")
        review = {
            "paper_alignment": "条件对应方法", "section_flow": "准确报告结果",
            "paragraph_links": "独立段落", "sentence_links": "保留验证条件",
            "language_and_facts": "数值和单位未改", "source_fidelity": "与原文结论一致",
        }
        text = Path(amended).read_text(encoding="utf-8")
        self.assertEqual(
            self.run_workflow("finalize", self.write("revision.json", {"text": text, "review": review})).strip(),
            text,
        )
        self.run_workflow("resume", "结果")
        self.assertEqual(self.status()["language"], "zh")
        self.assertFalse(self.status()["final_ready"])
        self.run_workflow("resume", "结果", "--mode", "polish")
        self.assertEqual(json.loads(self.run_workflow("show"))["source"], source)

    def test_manuscript_translation_rejects_implicit_permission_and_missing_units(self):
        manifest = self.write("manuscript.json", {
            "units": [
                {"id": "p1", "text": "我们估计了误差。"},
                {"id": "p2", "text": "平均误差低于基线。"},
                {"id": "ref", "text": "[1] Existing Reference.", "verbatim": True},
            ],
            "glossary": {"误差": "error"},
        })
        self.run_workflow("translate-init", "full", "--scope", "manuscript", manifest)
        for message in ("开始写", "先不要翻译", "是否可以开始翻译？", "开始逐段翻译"):
            self.prompt(message)
            self.run_workflow("check-translate", error="明确的英译指令")
        self.prompt("开始翻译全文")
        self.run_workflow("check-translate")
        self.assertIn("简洁学术英译", self.run_workflow("read-translator"))
        first = json.loads(self.run_workflow("next-translation"))
        self.assertEqual(first["unit"]["id"], "p1")
        self.assertEqual(first["glossary"], {"误差": "error"})
        review = {"meaning": "忠实", "concision": "简洁", "terms_and_protected_content": "术语一致"}
        p1 = self.write("p1.json", {"text": "We estimated the error.", "review": review})
        p2 = self.write("p2.json", {"text": "The mean error was below baseline.", "review": review})
        check = self.write("check.json", {"review": {
            "coverage": "单元齐全", "terminology": "术语已统一",
            "concision": "已复核", "source_fidelity": "按原文范围",
        }})
        self.run_workflow("save-translation", "p2", p2, error="原文顺序")
        self.run_workflow("save-translation", "p1", p1)
        self.run_workflow("finish-translation", check, error="仍有原文单元")
        self.run_workflow("save-translation", "p2", p2)
        self.assertEqual(
            self.run_workflow("finish-translation", check).strip(),
            "We estimated the error.\n\nThe mean error was below baseline.\n\n[1] Existing Reference.",
        )

    def test_explicit_paragraph_request_does_not_authorize_manuscript(self):
        self.prompt("请把下面这段翻译成英文：平均误差降低了。")
        source = self.write("paragraph.json", {"units": [{"id": "p", "text": "平均误差降低了。"}]})
        self.run_workflow("translate-init", "full", "--scope", "manuscript", source, error="范围")
        self.run_workflow("translate-init", "selection", "--scope", "paragraph", source)
        self.run_workflow("check-translate")
        self.run_workflow("read-translator")
        result = self.write("result.json", {
            "text": "The mean error decreased.",
            "review": {"meaning": "保留方向", "concision": "用一句表达", "terms_and_protected_content": "术语一致"},
        })
        step = json.loads(self.run_workflow("save-translation", "p", result))
        self.assertEqual(step["text"], "The mean error decreased.")

    def test_host_hooks_feed_the_same_translation_gate(self):
        command = "请把下面这段翻译成英文：平均误差降低了。"
        source = self.write("paragraph.json", {"units": [{"id": "p", "text": "平均误差降低了。"}]})
        for host in ("codex", "claude", "qwen", "kimi", "zcode", "generic"):
            with self.subTest(host=host):
                payload = {
                    "hook_event_name": "UserPromptSubmit", "session_id": host,
                    "cwd": str(self.workspace), "prompt": command,
                }
                if host == "qwen":
                    payload["prompt"] = "Legacy model-bound text"
                    payload["submitted_prompt"] = command
                if host == "generic":
                    payload["role"] = "user"
                result = self.run_workflow("prompt-hook", "--host", host, stdin=json.dumps(payload))
                if host == "kimi":
                    self.assertIn("已收到明确英译请求", result)
                elif host == "generic":
                    self.assertIn("已收到明确英译请求", json.loads(result)["additional_context"])
                else:
                    self.assertIn("UserPromptSubmit", json.loads(result)["hookSpecificOutput"]["hookEventName"])
                self.run_workflow("translate-init", "p", "--scope", "paragraph", source, session=host)
                self.run_workflow("check-translate", session=host)

    def test_untrusted_or_out_of_scope_hook_inputs_do_not_authorize(self):
        command = "把这段翻译成英文"
        source = self.write("untrusted.json", {"units": [{"id": "p", "text": "误差降低。"}]})
        for host, fields, options in (
            ("qwen", {}, []),
            ("generic", {"role": "assistant"}, []),
            ("kimi", {"cwd": str(self.workspace.parent)}, ["--workspace", str(self.workspace)]),
        ):
            with self.subTest(host=host):
                message = json.dumps({
                    "hook_event_name": "UserPromptSubmit", "session_id": host,
                    "cwd": str(self.workspace), "prompt": command, **fields,
                })
                self.assertEqual(
                    self.run_workflow("prompt-hook", "--host", host, *options, stdin=message), "",
                )
                self.run_workflow("translate-init", "p", "--scope", "paragraph", source, session=host)
                self.run_workflow("check-translate", error="明确的英译指令", session=host)

    def test_hook_generator_outputs_scoped_host_settings(self):
        for host in ("codex", "claude", "qwen", "kimi", "zcode", "antigravity", "gemini", "deepseek"):
            with self.subTest(host=host):
                config = subprocess.check_output(
                    [sys.executable, str(HOOK_CONFIG), host], cwd=self.workspace, encoding="utf-8",
                )
                if host == "kimi":
                    self.assertIn('event = "UserPromptSubmit"', config)
                elif host == "antigravity":
                    config = json.loads(config)["academic-writing"]["PreInvocation"][0]["command"]
                else:
                    hooks = json.loads(config)["hooks"]
                    if host == "zcode":
                        self.assertIs(hooks["enabled"], True)
                    event = "BeforeAgent" if host == "gemini" else "UserPromptSubmit"
                    config = hooks[event][0]["hooks"][0]["command"]
                self.assertIn(f"--host {host} --workspace", config)
                self.assertIn(self.workspace.as_posix(), config)

    def test_antigravity_ignores_repeated_reports_of_the_last_user_input(self):
        command = "把这段翻译成英文"
        context = {
            "conversationId": "antigravity",
            "workspacePaths": [str(self.workspace)],
            "lastUserInput": command,
        }
        source = self.write("antigravity.json", {"units": [{"id": "p", "text": "平均误差降低了。"}]})
        result = self.run_workflow(
            "prompt-hook", "--host", "antigravity", stdin=json.dumps({**context, "invocationNum": 1}),
        )
        self.assertIn("已收到明确英译请求", json.loads(result)["injectSteps"][0]["ephemeralMessage"])
        self.run_workflow("translate-init", "first", "--scope", "paragraph", source, session="antigravity")
        self.run_workflow("check-translate", session="antigravity")
        duplicate = self.run_workflow(
            "prompt-hook", "--host", "antigravity", stdin=json.dumps({**context, "invocationNum": 2}),
        )
        self.assertEqual(duplicate, "")
        self.run_workflow("translate-init", "second", "--scope", "paragraph", source, session="antigravity")
        self.run_workflow("check-translate", error="明确的英译指令", session="antigravity")

    def test_context_only_hooks_never_authorize_a_continuation(self):
        for host, event in (("gemini", "BeforeAgent"), ("deepseek", "UserPromptSubmit")):
            with self.subTest(host=host):
                result = self.run_workflow("prompt-hook", "--host", host, stdin=json.dumps({
                    "hook_event_name": event,
                    "session_id": host,
                    "cwd": str(self.workspace),
                    "prompt": "把这段翻译成英文",
                }))
                self.assertIn("user-confirm", json.loads(result)["hookSpecificOutput"]["additionalContext"])
                source = self.write(f"{host}.json", {"units": [{"id": "p", "text": "误差降低了。"}]})
                self.run_workflow("translate-init", "p", "--scope", "paragraph", source, session=host)
                self.run_workflow("check-translate", error="明确的英译指令", session=host)

    def test_reference_library_preserves_sources_and_reuses_only_matching_sections(self):
        original = Path(self.write("temporary-upload.pdf", "Version one of the reference file."))
        reference = json.loads(self.run_workflow(
            "reference-add", "paper-a", "--title", "Paper A", "--doi", "10.1234/example",
            "--file", str(original),
        ))
        saved_copy = Path(reference["reference"]["local_files"][0]["local_path"])
        markdown = Path(reference["reference_index"])
        self.run_workflow("reference-add", "paper-b", "--title", "Paper B", "--source", "Publisher archive")
        self.run_workflow("reference-add", "another-label", "--doi", "https://doi.org/10.1234/example")
        self.run_workflow("init", "引言", "paper-a", "another-label", error="同一文献请只选一个")
        original.unlink()
        self.assertEqual(saved_copy.read_text(encoding="utf-8"), "Version one of the reference file.")
        self.run_workflow("init", "引言", "paper-a", "paper-b")

        first = "Earlier studies estimated regional averages."
        second = "We examine variation within regions."
        context = "We compared estimates across spatial units."
        excerpt = self.write("introduction.txt", first + "\n\n" + second)
        surroundings = self.write("context.txt", context)
        notes = {
            "section": "引言", "location": "Introduction, paragraphs 1–2",
            "paper_context": {
                "main_line": "由区域平均值切到区域内变异", "section_role": "提出问题",
                "connections": "引出按空间单元的比较",
                "evidence": [{"location": "Methods", "anchor": context}],
            },
            "paragraph_transition": {
                "from": first, "to": second, "observation": "从已有认识推进到研究问题",
                "application": "由研究现状引出问题",
            },
        }
        for name in ("expression", "grammar", "organization", "concision"):
            notes[name] = {"anchor": second, "observation": "用具体动词说明研究对象", "application": "引出问题"}
        self.run_workflow("study", "paper-a", excerpt, surroundings, self.write("study.json", notes))

        saved_notes = json.loads(self.run_workflow("reference-show", "another-label", "--section", "Introduction"))
        self.assertEqual(saved_notes["studies"]["引言"][0]["excerpt"], first + "\n\n" + second)
        self.assertIn(second, markdown.read_text(encoding="utf-8"))
        self.assertIn("Paper B", markdown.read_text(encoding="utf-8"))
        reuse = json.loads(self.run_workflow("init", "Introduction", "paper-a", "paper-b", session="next"))
        self.assertEqual(reuse["reused_study"], ["paper-a"])
        self.assertEqual(reuse["missing_study"], ["paper-b"])
        discussion = json.loads(self.run_workflow("init", "讨论", "paper-a", session="next"))
        self.assertEqual(discussion["missing_study"], ["paper-a"])
        self.assertTrue(saved_copy.exists())

        updated = self.write("updated.pdf", "Version two of the reference file.")
        self.run_workflow("reference-add", "paper-a", "--file", updated)
        new = json.loads(self.run_workflow("init", "引言", "paper-a", session="third"))
        self.assertEqual(new["missing_study"], ["paper-a"])
        self.assertIn("新版需重读", markdown.read_text(encoding="utf-8"))
        self.assertTrue(saved_copy.exists())

        self.run_workflow("reference-add", "paper-a", "--file", str(saved_copy))
        restored = json.loads(self.run_workflow("init", "引言", "paper-a", session="restored"))
        self.assertEqual(restored["reused_study"], ["paper-a"])
        self.assertNotIn("新版需重读", markdown.read_text(encoding="utf-8"))

    def test_reference_library_keeps_parallel_entries_in_one_index(self):
        listing = json.loads(self.run_workflow("references"))
        markdown = Path(listing["reference_index"])
        self.assertEqual(listing["references"], [])
        self.assertTrue(markdown.is_file())
        identifiers = [f"paper-{number}" for number in range(6)]
        with ThreadPoolExecutor(max_workers=4) as parallel:
            list(parallel.map(lambda ref: self.run_workflow("reference-add", ref), identifiers))
        listing = json.loads(self.run_workflow("references"))
        self.assertCountEqual([entry["id"] for entry in listing["references"]], identifiers)


if __name__ == "__main__":
    unittest.main()
