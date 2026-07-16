"""Tests for server.py's pure helpers (no Google API access needed)."""

import pytest

import server


class TestColLetterToIndex:
    def test_single_letters(self):
        assert server._col_letter_to_index("A") == 0
        assert server._col_letter_to_index("E") == 4
        assert server._col_letter_to_index("Z") == 25

    def test_double_letters(self):
        assert server._col_letter_to_index("AA") == 26
        assert server._col_letter_to_index("AZ") == 51
        assert server._col_letter_to_index("BA") == 52

    def test_lowercase_accepted(self):
        assert server._col_letter_to_index("aa") == 26


class TestResolveSpreadsheetId:
    def test_explicit_id_wins(self, monkeypatch):
        monkeypatch.setattr(server, "DEFAULT_SPREADSHEET_ID", "default-id")
        assert server._resolve_spreadsheet_id("explicit-id") == "explicit-id"

    def test_falls_back_to_default(self, monkeypatch):
        monkeypatch.setattr(server, "DEFAULT_SPREADSHEET_ID", "default-id")
        assert server._resolve_spreadsheet_id(None) == "default-id"

    def test_raises_when_nothing_set(self, monkeypatch):
        monkeypatch.setattr(server, "DEFAULT_SPREADSHEET_ID", "")
        with pytest.raises(ValueError):
            server._resolve_spreadsheet_id(None)
