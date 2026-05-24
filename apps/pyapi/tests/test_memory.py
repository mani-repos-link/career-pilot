from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pyapi.memory import (
    SCOPE_GLOBAL,
    SCOPE_SESSION,
    MemoryStore,
    format_memory_block,
)
from pyapi.store import Store


def db_url(directory: str) -> str:
    return f"sqlite:///{Path(directory) / 'test.sqlite'}"


class MemoryStoreTest(unittest.TestCase):
    def test_upsert_creates_and_then_updates_same_key(self) -> None:
        with TemporaryDirectory() as directory:
            url = db_url(directory)
            store = Store(url, create_tables=True)
            session = store.create_session("s")
            memories = MemoryStore(url)

            first = memories.upsert(SCOPE_SESSION, session.id, "target_role", "Senior Python")
            second = memories.upsert(SCOPE_SESSION, session.id, "target_role", "Staff Python")

            self.assertEqual(first.id, second.id)
            self.assertEqual(second.content, "Staff Python")
            store.close()

    def test_list_returns_session_and_global_memories(self) -> None:
        with TemporaryDirectory() as directory:
            url = db_url(directory)
            store = Store(url, create_tables=True)
            session = store.create_session("s")
            memories = MemoryStore(url)
            memories.upsert(SCOPE_SESSION, session.id, "active_jd", "linkedin/123")
            memories.upsert(SCOPE_GLOBAL, None, "email", "me@example.com")

            keys = {memory.key for memory in memories.list(session.id)}
            self.assertEqual(keys, {"active_jd", "email"})

            scoped = {memory.key for memory in memories.list(session.id, include_global=False)}
            self.assertEqual(scoped, {"active_jd"})
            store.close()

    def test_delete_returns_true_then_false(self) -> None:
        with TemporaryDirectory() as directory:
            url = db_url(directory)
            store = Store(url, create_tables=True)
            session = store.create_session("s")
            memories = MemoryStore(url)
            memories.upsert(SCOPE_SESSION, session.id, "key", "value")

            self.assertTrue(memories.delete(SCOPE_SESSION, session.id, "key"))
            self.assertFalse(memories.delete(SCOPE_SESSION, session.id, "key"))
            store.close()

    def test_session_scope_without_session_id_raises(self) -> None:
        with TemporaryDirectory() as directory:
            memories = MemoryStore(db_url(directory), create_tables=True)
            with self.assertRaises(ValueError):
                memories.upsert(SCOPE_SESSION, None, "k", "v")

    def test_global_scope_with_session_id_raises(self) -> None:
        with TemporaryDirectory() as directory:
            memories = MemoryStore(db_url(directory), create_tables=True)
            with self.assertRaises(ValueError):
                memories.upsert(SCOPE_GLOBAL, "ses_1", "k", "v")

    def test_invalid_scope_raises(self) -> None:
        with TemporaryDirectory() as directory:
            memories = MemoryStore(db_url(directory), create_tables=True)
            with self.assertRaises(ValueError):
                memories.upsert("workspace", "ses_1", "k", "v")


class FormatMemoryBlockTest(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(format_memory_block([], max_chars=100), "")

    def test_block_lists_scope_and_key(self) -> None:
        with TemporaryDirectory() as directory:
            url = db_url(directory)
            store = Store(url, create_tables=True)
            session = store.create_session("s")
            memories = MemoryStore(url)
            memories.upsert(SCOPE_SESSION, session.id, "active_jd", "linkedin/123")
            memories.upsert(SCOPE_GLOBAL, None, "email", "me@example.com")

            block = format_memory_block(memories.list(session.id), max_chars=1000)
            self.assertIn("Memories:", block)
            self.assertIn("[session] active_jd: linkedin/123", block)
            self.assertIn("[global] email: me@example.com", block)
            store.close()

    def test_truncation_adds_marker(self) -> None:
        with TemporaryDirectory() as directory:
            url = db_url(directory)
            store = Store(url, create_tables=True)
            session = store.create_session("s")
            memories = MemoryStore(url)
            memories.upsert(SCOPE_SESSION, session.id, "k", "x" * 500)

            block = format_memory_block(memories.list(session.id), max_chars=80)
            self.assertLessEqual(len(block), 80)
            self.assertIn("truncated", block)
            store.close()


if __name__ == "__main__":
    unittest.main()
