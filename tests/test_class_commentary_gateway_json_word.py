import json
import unittest
from types import SimpleNamespace

import ai_processor


class GatewayJsonWordProxyTest(unittest.TestCase):
    def _client(self, captured):
        return SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: captured.update(kwargs)
                )
            )
        )

    def _wrap(self, client):
        return ai_processor._JsonObjectWordEnsuringClient(client)

    def test_appends_json_word_when_last_user_message_lacks_it(self):
        captured = {}
        client = self._wrap(self._client(captured))
        client.chat.completions.create(
            model="m",
            messages=[
                {"role": "system", "content": "Return one JSON object."},
                {"role": "user", "content": '{"style_rules": [], "data": 1}'},
            ],
            response_format={"type": "json_object"},
        )
        user_content = captured["messages"][-1]["content"]
        self.assertTrue(ai_processor._JSON_OBJECT_WORD_RE.search(user_content))
        self.assertIn('{"style_rules": [], "data": 1}', user_content)
        self.assertEqual(len(captured["messages"]), 2)

    def test_leaves_messages_alone_when_word_present(self):
        captured = {}
        client = self._wrap(self._client(captured))
        messages = [
            {"role": "user", "content": "输出 JSON 格式结果。"},
        ]
        client.chat.completions.create(
            model="m",
            messages=messages,
            response_format={"type": "json_object"},
        )
        self.assertIs(captured["messages"], messages)

    def test_ignores_non_json_object_requests(self):
        captured = {}
        client = self._wrap(self._client(captured))
        messages = [{"role": "user", "content": "say hi"}]
        client.chat.completions.create(model="m", messages=messages)
        self.assertIs(captured["messages"], messages)
        self.assertNotIn("response_format", captured)

    def test_appends_text_part_for_multimodal_content(self):
        captured = {}
        client = self._wrap(self._client(captured))
        client.chat.completions.create(
            model="m",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "看图写评语"},
                        {"type": "image_url", "image_url": {"url": "http://x/y.png"}},
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )
        parts = captured["messages"][-1]["content"]
        self.assertEqual(parts[-1]["type"], "text")
        self.assertTrue(ai_processor._JSON_OBJECT_WORD_RE.search(parts[-1]["text"]))

    def test_does_not_mutate_caller_message_list(self):
        captured = {}
        client = self._wrap(self._client(captured))
        messages = [
            {"role": "user", "content": '{"a": 1}'},
        ]
        client.chat.completions.create(
            model="m",
            messages=messages,
            response_format={"type": "json_object"},
        )
        self.assertEqual(messages[0]["content"], '{"a": 1}')

    def test_underscore_suffixed_word_is_not_standalone(self):
        captured = {}
        client = self._wrap(self._client(captured))
        client.chat.completions.create(
            model="m",
            messages=[{"role": "user", "content": '{"json_mode": true}'}],
            response_format={"type": "json_object"},
        )
        self.assertIn("\n\njson", captured["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
