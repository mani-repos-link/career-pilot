import asyncio
import unittest

from pyapi.hooks import HookHalt, HookRegistry


class HookRegistryTest(unittest.TestCase):
    def test_emit_runs_handlers_in_registration_order_and_mutates_payload(self) -> None:
        registry = HookRegistry()

        @registry.on("model.pre_call")
        def first(payload: dict) -> None:
            payload["trace"] = ["first"]

        @registry.on("model.pre_call")
        def second(payload: dict) -> None:
            payload["trace"].append("second")

        result = asyncio.run(registry.emit("model.pre_call", {}))
        self.assertEqual(result["trace"], ["first", "second"])

    def test_async_handler_is_awaited(self) -> None:
        registry = HookRegistry()

        @registry.on("model.pre_call")
        async def sleeper(payload: dict) -> None:
            await asyncio.sleep(0)
            payload["ran"] = True

        result = asyncio.run(registry.emit("model.pre_call", {}))
        self.assertTrue(result["ran"])

    def test_hook_halt_short_circuits_emit_and_returns_payload(self) -> None:
        registry = HookRegistry()
        seen: list[str] = []

        @registry.on("tool.pre_call")
        def halter(payload: dict) -> None:
            seen.append("halter")
            raise HookHalt({"result": "synthetic"})

        @registry.on("tool.pre_call")
        def never_runs(payload: dict) -> None:
            seen.append("never_runs")

        result = asyncio.run(registry.emit("tool.pre_call", {"request": "x"}))
        self.assertEqual(result, {"result": "synthetic"})
        self.assertEqual(seen, ["halter"])

    def test_handler_exception_is_logged_and_skipped(self) -> None:
        registry = HookRegistry()

        @registry.on("model.pre_call")
        def explodes(payload: dict) -> None:
            raise RuntimeError("kaboom")

        @registry.on("model.pre_call")
        def survivor(payload: dict) -> None:
            payload["ok"] = True

        result = asyncio.run(registry.emit("model.pre_call", {}))
        self.assertTrue(result.get("ok"))

    def test_emit_with_no_handlers_returns_payload_unchanged(self) -> None:
        registry = HookRegistry()
        result = asyncio.run(registry.emit("model.pre_call", {"a": 1}))
        self.assertEqual(result, {"a": 1})


if __name__ == "__main__":
    unittest.main()
