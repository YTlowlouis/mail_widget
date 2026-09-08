from mail_mcp.parsing import (
    extract_unsubscribe_urls,
    html_to_text,
    parse_auth_results,
    truncate_body,
)


def test_parse_auth_results_all_pass():
    header = (
        "mx.google.com; spf=pass smtp.mailfrom=x; "
        "dkim=pass header.i=@x; dmarc=pass (p=REJECT) header.from=x"
    )
    assert parse_auth_results([header]) == {"spf": "pass", "dkim": "pass", "dmarc": "pass"}


def test_parse_auth_results_mixed_and_missing():
    header = "mx.google.com; spf=fail smtp.mailfrom=x; dkim=neutral header.i=@x"
    result = parse_auth_results([header])
    assert result == {"spf": "fail", "dkim": "neutral", "dmarc": "unknown"}


def test_parse_auth_results_no_header():
    assert parse_auth_results([]) == {"spf": "unknown", "dkim": "unknown", "dmarc": "unknown"}


def test_parse_auth_results_reads_first_match_across_multiple_headers():
    # Plusieurs en-têtes Authentication-Results peuvent être empilés par des relais
    # successifs ; on doit au moins détecter un résultat, jamais planter dessus.
    headers = ["spf=fail smtp.mailfrom=x", "dkim=pass header.i=@x; dmarc=none"]
    assert parse_auth_results(headers) == {"spf": "fail", "dkim": "pass", "dmarc": "none"}


def test_html_to_text_strips_tags_and_scripts():
    html = "<html><body><p>Bonjour</p><script>evil()</script><div>Salut</div></body></html>"
    text = html_to_text(html)
    assert "Bonjour" in text
    assert "Salut" in text
    assert "evil()" not in text


def test_html_to_text_decodes_entities():
    assert html_to_text("<p>Caf&eacute; &amp; th&eacute;</p>") == "Café & thé"


def test_truncate_body_short_text_untouched():
    text, truncated = truncate_body("bonjour", limit=2000)
    assert text == "bonjour"
    assert truncated is False


def test_truncate_body_cuts_at_limit():
    text, truncated = truncate_body("a" * 2500, limit=2000)
    assert truncated is True
    assert len(text) <= 2001  # 2000 + ellipse


def test_extract_unsubscribe_urls_both_kinds():
    header = "<https://example.com/unsub?id=1>, <mailto:unsub@example.com>"
    http_urls, mailto_urls = extract_unsubscribe_urls(header)
    assert http_urls == ["https://example.com/unsub?id=1"]
    assert mailto_urls == ["mailto:unsub@example.com"]


def test_extract_unsubscribe_urls_none():
    assert extract_unsubscribe_urls(None) == ([], [])
