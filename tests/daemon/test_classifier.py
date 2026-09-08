import asyncio
import json
from types import SimpleNamespace

import mail_daemon.classifier as classifier
from mail_daemon.schema import EmailClassification


def test_build_email_context_single_message_wraps_body_as_data():
    body = {"from": "a@x.com", "subject": "Sujet", "date": "2026-01-01", "body_text": "Bonjour"}
    context = classifier.build_email_context(body, [body])
    assert "<email>" in context and "</email>" in context
    assert "Bonjour" in context
    assert "Ce fil contient" not in context  # pas de préambule de groupe pour un seul message


def test_build_email_context_group_lists_all_messages():
    body = {"from": "notifications@github.com", "subject": "PR #42 update 7", "date": "2026-01-07", "body_text": "..."}
    group = [
        {"from": "notifications@github.com", "subject": f"PR #42 update {i}", "date": f"2026-01-0{i}"}
        for i in range(1, 8)
    ]
    context = classifier.build_email_context(body, group)
    assert "Ce fil contient 7 nouveaux messages" in context
    assert context.count("PR #42 update") >= 7


def test_extract_json_object_ignores_surrounding_prose():
    text = 'Voici le résultat :\n{"resume": "x", "urgence": "info", "raison": "y"}\nVoilà.'
    assert classifier._extract_json_object(text) == '{"resume": "x", "urgence": "info", "raison": "y"}'


def test_extract_json_object_none_when_no_braces():
    assert classifier._extract_json_object("pas de json ici") is None


def test_parse_classification_accepts_markdown_fenced_json():
    content = '```json\n{"resume": "x", "urgence": "action", "raison": "y"}\n```'
    parsed = classifier._parse_classification(content)
    assert parsed == EmailClassification(resume="x", urgence="action", raison="y")


def test_parse_classification_rejects_invalid_urgence_value():
    content = '{"resume": "x", "urgence": "urgentissime", "raison": "y"}'
    assert classifier._parse_classification(content) is None


def test_parse_classification_rejects_missing_field():
    content = '{"resume": "x", "urgence": "info"}'
    assert classifier._parse_classification(content) is None


def test_parse_classification_none_on_empty_content():
    assert classifier._parse_classification(None) is None
    assert classifier._parse_classification("") is None


# -- classify_thread (boucle d'agent manuelle, groq mocké) --------------------


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def _completion(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeGroqClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeSession:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return SimpleNamespace(
            is_error=False,
            structured_content=None,
            content=[SimpleNamespace(text=json.dumps({"echo": arguments}))],
        )


def test_classify_thread_returns_parsed_output_when_model_answers_directly():
    client = FakeGroqClient([_completion(content='{"resume": "r", "urgence": "action", "raison": "j"}')])
    result = asyncio.run(
        classifier.classify_thread(client, session=FakeSession(), read_tools=[], model="m", context="ctx")
    )
    assert result == EmailClassification(resume="r", urgence="action", raison="j")
    assert client.calls[0]["model"] == "m"
    assert client.calls[0]["messages"][0]["role"] == "system"


def test_classify_thread_executes_a_tool_call_then_returns_final_answer():
    session = FakeSession()
    client = FakeGroqClient(
        [
            _completion(tool_calls=[_tool_call("call_1", "get_email", {"message_id": "<a@x>"})]),
            _completion(content='{"resume": "r", "urgence": "info", "raison": "j"}'),
        ]
    )
    result = asyncio.run(
        classifier.classify_thread(client, session=session, read_tools=[], model="m", context="ctx")
    )
    assert result == EmailClassification(resume="r", urgence="info", raison="j")
    assert session.calls == [("get_email", {"message_id": "<a@x>"})]
    # le deuxième appel modèle contient bien la réponse de l'outil dans les messages
    second_call_messages = client.calls[1]["messages"]
    assert any(m.get("role") == "tool" for m in second_call_messages)


def test_classify_thread_refuses_to_execute_a_write_tool_even_if_requested():
    session = FakeSession()
    client = FakeGroqClient(
        [
            _completion(tool_calls=[_tool_call("call_1", "move_to_trash", {"message_id": "<a@x>"})]),
            _completion(content='{"resume": "r", "urgence": "bruit", "raison": "j"}'),
        ]
    )
    asyncio.run(classifier.classify_thread(client, session=session, read_tools=[], model="m", context="ctx"))
    assert session.calls == []  # jamais exécuté, même halluciné par le modèle


def test_classify_thread_returns_none_when_final_output_does_not_validate():
    client = FakeGroqClient([_completion(content="pas du json valide")])
    result = asyncio.run(
        classifier.classify_thread(client, session=FakeSession(), read_tools=[], model="m", context="ctx")
    )
    assert result is None


def test_classify_thread_returns_none_after_too_many_tool_iterations():
    responses = [
        _completion(tool_calls=[_tool_call(f"call_{i}", "get_email", {"message_id": "<a@x>"})])
        for i in range(classifier.MAX_TOOL_ITERATIONS)
    ]
    client = FakeGroqClient(responses)
    result = asyncio.run(
        classifier.classify_thread(client, session=FakeSession(), read_tools=[], model="m", context="ctx")
    )
    assert result is None


def test_classify_thread_returns_none_on_api_error():
    class RaisingClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        async def _create(self, **kwargs):
            raise RuntimeError("timeout")

    result = asyncio.run(
        classifier.classify_thread(RaisingClient(), session=FakeSession(), read_tools=[], model="m", context="ctx")
    )
    assert result is None


def test_tool_to_groq_schema_uses_tool_input_schema():
    tool = SimpleNamespace(name="list_recent", description="Liste les mails", input_schema={"type": "object"})
    schema = classifier._tool_to_groq_schema(tool)
    assert schema == {
        "type": "function",
        "function": {"name": "list_recent", "description": "Liste les mails", "parameters": {"type": "object"}},
    }
