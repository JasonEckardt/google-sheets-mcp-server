"""Tests for gmail_client.py's message-body extraction."""

import base64

import gmail_client


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


class TestExtractPlainText:
    def test_top_level_plain_text(self):
        payload = {"mimeType": "text/plain", "body": {"data": _b64("hello world")}}
        assert gmail_client._extract_plain_text(payload) == "hello world"

    def test_multipart_prefers_plain_part(self):
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<p>html</p>")}},
                {"mimeType": "text/plain", "body": {"data": _b64("plain text")}},
            ],
        }
        assert gmail_client._extract_plain_text(payload) == "plain text"

    def test_nested_multipart(self):
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": _b64("nested")}},
                    ],
                }
            ],
        }
        assert gmail_client._extract_plain_text(payload) == "nested"

    def test_no_plain_text_returns_empty(self):
        payload = {"mimeType": "text/html", "body": {"data": _b64("<p>html only</p>")}}
        assert gmail_client._extract_plain_text(payload) == ""

    def test_empty_payload(self):
        assert gmail_client._extract_plain_text({}) == ""
