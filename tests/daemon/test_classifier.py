import asyncio
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


class _FakeRunner:
    def __init__(self, parsed_output=None, raise_exc=None):
        self._parsed_output = parsed_output
        self._raise_exc = raise_exc

    async def until_done(self):
        if self._raise_exc:
            raise self._raise_exc
        return SimpleNamespace(parsed_output=self._parsed_output)


class _FakeToolRunnerFactory:
    def __init__(self, parsed_output=None, raise_exc=None):
        self.parsed_output = parsed_output
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeRunner(self.parsed_output, self.raise_exc)


def _fake_client(factory):
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(tool_runner=factory)))


def test_classify_thread_returns_parsed_output_on_success(monkeypatch):
    monkeypatch.setattr(classifier, "async_mcp_tool", lambda tool, session: (tool, session))
    expected = EmailClassification(resume="Un résumé", urgence="action", raison="réponse attendue")
    factory = _FakeToolRunnerFactory(parsed_output=expected)
    client = _fake_client(factory)

    result = asyncio.run(
        classifier.classify_thread(client, session="fake-session", read_tools=[], model="m", context="<email>...</email>")
    )

    assert result == expected
    assert factory.calls[0]["output_format"] is EmailClassification
    assert factory.calls[0]["system"] == classifier.SYSTEM_PROMPT


def test_classify_thread_returns_none_when_output_does_not_validate(monkeypatch):
    monkeypatch.setattr(classifier, "async_mcp_tool", lambda tool, session: (tool, session))
    factory = _FakeToolRunnerFactory(parsed_output=None)
    client = _fake_client(factory)

    result = asyncio.run(
        classifier.classify_thread(client, session="fake-session", read_tools=[], model="m", context="ctx")
    )

    assert result is None


def test_classify_thread_returns_none_on_api_error(monkeypatch):
    monkeypatch.setattr(classifier, "async_mcp_tool", lambda tool, session: (tool, session))
    factory = _FakeToolRunnerFactory(raise_exc=RuntimeError("timeout"))
    client = _fake_client(factory)

    result = asyncio.run(
        classifier.classify_thread(client, session="fake-session", read_tools=[], model="m", context="ctx")
    )

    assert result is None


def test_classify_thread_only_wraps_read_tools_it_is_given():
    # classify_thread ne filtre pas lui-même (c'est mcp_tools.list_read_tools qui le fait en amont),
    # mais il ne doit jamais élargir la liste reçue.
    monkeypatch_calls = []

    def fake_async_mcp_tool(tool, session):
        monkeypatch_calls.append(tool)
        return tool

    import mail_daemon.classifier as clf

    original = clf.async_mcp_tool
    clf.async_mcp_tool = fake_async_mcp_tool
    try:
        factory = _FakeToolRunnerFactory(parsed_output=EmailClassification(resume="r", urgence="bruit", raison="x"))
        client = _fake_client(factory)
        read_tools = [SimpleNamespace(name="list_recent"), SimpleNamespace(name="get_email")]
        asyncio.run(clf.classify_thread(client, session="s", read_tools=read_tools, model="m", context="ctx"))
    finally:
        clf.async_mcp_tool = original

    assert [t.name for t in monkeypatch_calls] == ["list_recent", "get_email"]
