from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import asyncio
import sqlite3
import unittest

from pyapi.config import ContextConfig, ToolConfig
from pyapi.providers import ChatResult
from pyapi.services.conversation import complete_with_tools
from pyapi.store import MessageRecord
from pyapi.tools import execute_tool_call, parse_tool_call


def context_config() -> ContextConfig:
    return ContextConfig(max_response_tokens=100, max_history_messages=30)


class ToolTest(unittest.TestCase):
    def test_parse_tool_call_accepts_exact_json_payload(self) -> None:
        request = parse_tool_call('<tool_call>{"tool":"fetch_url","arguments":{"url":"https://example.com"}}</tool_call>')

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.tool, "fetch_url")
        self.assertEqual(request.arguments["url"], "https://example.com")

    def test_parse_tool_call_extracts_json_payload_with_surrounding_text(self) -> None:
        request = parse_tool_call(
            'Let me check.\n<tool_call>{"tool":"fetch_url","arguments":{"url":"https://example.com"}}</tool_call>'
        )

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.tool, "fetch_url")
        self.assertEqual(request.arguments["url"], "https://example.com")

    def test_parse_tool_call_ignores_normal_assistant_text(self) -> None:
        self.assertIsNone(parse_tool_call("Here is the answer."))

    def test_parse_tool_call_accepts_longcat_payload(self) -> None:
        request = parse_tool_call(
            """<longcat_tool_call>ls
<longcat_arg_key>path</longcat_arg_key>
<longcat_arg_value>.</longcat_arg_value>
<longcat_arg_key>recursive</longcat_arg_key>
<longcat_arg_value>false</longcat_arg_value>
<longcat_arg_key>max_entries</longcat_arg_key>
<longcat_arg_value>100</longcat_arg_value>
</longcat_tool_call>"""
        )

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.tool, "ls")
        self.assertEqual(request.arguments["path"], ".")
        self.assertEqual(request.arguments["recursive"], False)
        self.assertEqual(request.arguments["max_entries"], 100)

    def test_parse_tool_call_extracts_longcat_payload_with_surrounding_text(self) -> None:
        request = parse_tool_call(
            """Let me verify by testing it:<longcat_tool_call>fetch_url
<longcat_arg_key>url</longcat_arg_key>
<longcat_arg_value>https://example.com</longcat_arg_value>
</longcat_tool_call>"""
        )

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.tool, "fetch_url")
        self.assertEqual(request.arguments["url"], "https://example.com")

    def test_parse_tool_call_recovers_longcat_payload_without_opening_tag(self) -> None:
        request = parse_tool_call(
            """fetch_url
<longcat_arg_key>url</longcat_arg_key>
<longcat_arg_value>https://example.com</longcat_arg_value>
</longcat_tool_call>"""
        )

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.tool, "fetch_url")
        self.assertEqual(request.arguments["url"], "https://example.com")

    def test_ls_lists_files_inside_workspace(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.txt").write_text("hello")
            config = tool_config(root)

            result = execute_tool_call(config, parse_tool_call('<tool_call>{"tool":"ls","arguments":{"path":"."}}</tool_call>'))

            self.assertTrue(result.ok)
            self.assertIn("notes.txt", result.output)

    def test_read_file_reads_bounded_line_range(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.txt").write_text("one\ntwo\nthree\n")
            config = tool_config(root)

            result = execute_tool_call(
                config,
                parse_tool_call('<tool_call>{"tool":"read_file","arguments":{"path":"notes.txt","start_line":2,"max_lines":1}}</tool_call>'),
            )

            self.assertTrue(result.ok)
            self.assertIn("2: two", result.output)
            self.assertNotIn("1: one", result.output)

    def test_project_tree_lists_nested_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "apps").mkdir()
            (root / "apps" / "main.py").write_text("print('hi')")
            config = tool_config(root)

            result = execute_tool_call(
                config,
                parse_tool_call('<tool_call>{"tool":"project_tree","arguments":{"path":".","max_depth":2}}</tool_call>'),
            )

            self.assertTrue(result.ok)
            self.assertIn("apps/", result.output)
            self.assertIn("main.py", result.output)

    def test_grep_finds_text_inside_workspace(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.txt").write_text("Hello SQLite")
            config = tool_config(root)

            result = execute_tool_call(
                config,
                parse_tool_call(
                    '<tool_call>{"tool":"grep","arguments":{"pattern":"sqlite","path":".","case_sensitive":false}}</tool_call>'
                ),
            )

            self.assertTrue(result.ok)
            self.assertIn("notes.txt:1: Hello SQLite", result.output)

    def test_find_symbol_finds_code_references(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("def create_router():\n    return None\n")
            config = tool_config(root)

            result = execute_tool_call(
                config,
                parse_tool_call('<tool_call>{"tool":"find_symbol","arguments":{"symbol":"create_router","path":"."}}</tool_call>'),
            )

            self.assertTrue(result.ok)
            self.assertIn("main.py:1", result.output)

    def test_path_traversal_is_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            config = tool_config(Path(directory))

            result = execute_tool_call(
                config,
                parse_tool_call('<tool_call>{"tool":"ls","arguments":{"path":"../"}}</tool_call>'),
            )

            self.assertFalse(result.ok)
            self.assertIn("outside", result.output)

    def test_internet_tool_is_blocked_when_disabled(self) -> None:
        with TemporaryDirectory() as directory:
            config = tool_config(Path(directory), internet_enabled=False)

            result = execute_tool_call(
                config,
                parse_tool_call('<tool_call>{"tool":"fetch_url","arguments":{"url":"https://example.com"}}</tool_call>'),
            )

            self.assertFalse(result.ok)
            self.assertIn("internet tools are disabled", result.output)

    def test_curl_alias_is_blocked_by_same_internet_gate(self) -> None:
        with TemporaryDirectory() as directory:
            config = tool_config(Path(directory), internet_enabled=False)

            result = execute_tool_call(
                config,
                parse_tool_call('<tool_call>{"tool":"curl","arguments":{"url":"https://example.com"}}</tool_call>'),
            )

            self.assertFalse(result.ok)
            self.assertIn("internet tools are disabled", result.output)

    def test_sqlite_query_allows_select_only(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.sqlite"
            connection = sqlite3.connect(db_path)
            connection.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
            connection.execute("INSERT INTO notes (body) VALUES ('hello')")
            connection.commit()
            connection.close()
            config = tool_config(Path(directory), database_url=f"file:{db_path}")

            result = execute_tool_call(
                config,
                parse_tool_call('<tool_call>{"tool":"sqlite_query","arguments":{"query":"SELECT body FROM notes","max_rows":10}}</tool_call>'),
            )

            self.assertTrue(result.ok)
            self.assertIn("hello", result.output)

            blocked = execute_tool_call(
                config,
                parse_tool_call('<tool_call>{"tool":"sqlite_query","arguments":{"query":"DELETE FROM notes"}}</tool_call>'),
            )
            self.assertFalse(blocked.ok)
            self.assertIn("only allows SELECT", blocked.output)

    def test_explain_context_uses_current_session(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.sqlite"
            connection = sqlite3.connect(db_path)
            connection.executescript(
                """
                CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, created_at TEXT, updated_at TEXT);
                CREATE TABLE messages (
                  id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
                  provider TEXT, model TEXT, parent_message_id TEXT, active_response_id TEXT,
                  created_at TEXT
                );
                """
            )
            connection.execute("INSERT INTO sessions VALUES ('ses_1', 'test', 'now', 'now')")
            connection.execute("INSERT INTO messages VALUES ('msg_1', 'ses_1', 'user', 'hello', NULL, NULL, NULL, NULL, '1')")
            connection.commit()
            connection.close()
            config = tool_config(Path(directory), database_url=f"file:{db_path}")

            result = execute_tool_call(
                config,
                parse_tool_call('<tool_call>{"tool":"explain_context","arguments":{}}</tool_call>'),
                current_session_id="ses_1",
            )

            self.assertTrue(result.ok)
            self.assertIn('"sessionId": "ses_1"', result.output)

    def test_conversation_loop_runs_tool_then_returns_final_answer(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "notes.txt").write_text("phase three tool result")
                provider = FakeToolProvider()
                services = SimpleNamespace(
                    chat_provider=provider,
                    chat_config=None,
                    context=context_config(),
                    tools=tool_config(root),
                    catalog={},
                )

                result = await complete_with_tools(services, [message("user", "list files")])

                self.assertEqual(result.content, "I found notes.txt.")
                self.assertEqual(len(provider.histories), 2)
                self.assertIn("Tool result (ls, ok)", provider.histories[1][-1].content)

        asyncio.run(run())


def tool_config(root: Path, internet_enabled: bool = False, database_url: str = "file::memory:") -> ToolConfig:
    return ToolConfig(
        enabled=True,
        database_url=database_url,
        workspace_root=root,
        max_iterations=3,
        max_output_chars=12000,
        internet_enabled=internet_enabled,
        network_timeout_seconds=10,
        max_network_bytes=300000,
        crawl_max_pages=5,
    )


def message(role: str, content: str) -> MessageRecord:
    return MessageRecord(
        id=f"{role}_1",
        session_id="session_1",
        role=role,
        content=content,
        provider=None,
        model=None,
        parent_message_id=None,
        active_response_id=None,
        created_at="2026-05-20T00:00:00+00:00",
    )


class FakeToolProvider:
    provider = "fake"
    model = "fake-model"

    def __init__(self) -> None:
        self.histories: list[list[MessageRecord]] = []

    async def complete(
        self,
        history: list[MessageRecord],
        max_response_tokens: int,
        system_prompt: str | None = None,
    ) -> ChatResult:
        self.histories.append(list(history))
        if len(self.histories) == 1:
            return ChatResult(
                content='<tool_call>{"tool":"ls","arguments":{"path":"."}}</tool_call>',
                provider=self.provider,
                model=self.model,
            )
        return ChatResult(content="I found notes.txt.", provider=self.provider, model=self.model)


if __name__ == "__main__":
    unittest.main()
