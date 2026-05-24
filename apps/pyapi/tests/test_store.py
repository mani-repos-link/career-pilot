from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from pyapi.store import Store
from pyapi.config import ContextConfig
from pyapi.context import build_llm_context


class StoreTest(unittest.TestCase):
    def context_config(self, max_history_messages: int = 4) -> ContextConfig:
        return ContextConfig(
            max_response_tokens=100,
            max_history_messages=max_history_messages,
            max_memory_chars=2000,
        )

    def test_session_and_message_lifecycle(self) -> None:
        with TemporaryDirectory() as directory:
            store = Store(f"sqlite:///{Path(directory) / 'test.sqlite'}", create_tables=True)
            session = store.create_session("Test")
            message = store.create_message(session.id, "user", "Hello")

            self.assertEqual(store.list_sessions()[0].id, session.id)
            self.assertEqual(store.list_messages(session.id)[0].id, message.id)

            renamed = store.update_session_title(session.id, "Renamed chat")
            self.assertEqual(renamed.title, "Renamed chat")
            self.assertEqual(store.get_session(session.id).title, "Renamed chat")

            store.delete_session(session.id)
            self.assertEqual(store.list_sessions(), [])
            store.close()

    def test_message_pagination_returns_latest_and_older_pages(self) -> None:
        with TemporaryDirectory() as directory:
            store = Store(f"sqlite:///{Path(directory) / 'test.sqlite'}", create_tables=True)
            session = store.create_session("Test")

            for content in ["one", "two", "three", "four"]:
                store.create_message(session.id, "user", content)
                time.sleep(0.001)

            latest, has_more = store.list_messages_page(session.id, limit=2)
            self.assertTrue(has_more)
            self.assertEqual([message.content for message in latest], ["three", "four"])

            older, has_more = store.list_messages_page(session.id, limit=2, before=latest[0].created_at)
            self.assertFalse(has_more)
            self.assertEqual([message.content for message in older], ["one", "two"])

            store.close()

    def test_context_uses_only_active_response_for_prompt(self) -> None:
        with TemporaryDirectory() as directory:
            store = Store(f"sqlite:///{Path(directory) / 'test.sqlite'}", create_tables=True)
            session = store.create_session("Test")
            prompt = store.create_message(session.id, "user", "Explain this")
            first = store.create_message(
                session.id,
                "assistant",
                "First answer",
                parent_message_id=prompt.id,
                make_active=True,
            )
            second = store.create_message(
                session.id,
                "assistant",
                "Second answer",
                parent_message_id=prompt.id,
                make_active=True,
            )

            context = store.list_context_messages(session.id)
            self.assertEqual([message.content for message in context], ["Explain this", "Second answer"])

            store.set_active_response(session.id, first.id)
            context = store.list_context_messages(session.id)
            self.assertEqual([message.content for message in context], ["Explain this", "First answer"])

            self.assertEqual(store.list_messages(session.id)[0].active_response_id, first.id)
            self.assertEqual(store.list_messages(session.id)[1].parent_message_id, prompt.id)
            self.assertEqual(store.list_messages(session.id)[2].parent_message_id, prompt.id)
            self.assertEqual(second.content, "Second answer")
            store.close()

    def test_build_llm_context_caps_recent_messages(self) -> None:
        with TemporaryDirectory() as directory:
            store = Store(f"sqlite:///{Path(directory) / 'test.sqlite'}", create_tables=True)
            session = store.create_session("Test")

            for content in ["one", "two", "three", "four", "five"]:
                store.create_message(session.id, "user", content)
                time.sleep(0.001)

            context = self.context_config(max_history_messages=3)
            messages = store.list_context_messages(session.id)

            self.assertEqual(
                [message.content for message in build_llm_context(messages, context)],
                ["three", "four", "five"],
            )
            store.close()


if __name__ == "__main__":
    unittest.main()
