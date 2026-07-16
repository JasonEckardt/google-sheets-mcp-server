"""Tests for monitor_job_responses.py's classification and parsing helpers."""

import monitor_job_responses as monitor


class TestIsRejection:
    def test_common_english_phrasings(self):
        assert monitor.is_rejection("We regret to inform you that...")
        assert monitor.is_rejection("we will not be moving forward with your application")
        assert monitor.is_rejection("We've decided to pursue other candidates.")
        assert monitor.is_rejection("Unfortunately, we have selected another candidate.")

    def test_case_insensitive(self):
        assert monitor.is_rejection("REGRET TO INFORM")

    def test_french_phrasings(self):
        assert monitor.is_rejection("nous ne donnerons pas suite à votre candidature")
        assert monitor.is_rejection("nous avons décidé de sélectionner un autre profil")

    def test_positive_messages_pass_through(self):
        assert not monitor.is_rejection("We'd love to schedule an interview with you!")
        assert not monitor.is_rejection("Congratulations, we are moving forward with your offer.")

    def test_empty_and_none(self):
        assert not monitor.is_rejection("")
        assert not monitor.is_rejection(None)


class TestGuessCompany:
    def test_uses_display_name_when_present(self):
        assert monitor.guess_company("Acme Careers <no-reply@acme.com>") == "Acme Careers"

    def test_falls_back_to_domain(self):
        assert monitor.guess_company("no-reply@acme.com") == "Acme"

    def test_strips_ats_subdomains(self):
        assert monitor.guess_company("jobs@notify.dayforce.com") == "Dayforce"


class TestParseDate:
    def test_valid_rfc2822_date(self):
        assert monitor.parse_date("Tue, 07 Jul 2026 09:00:00 -0400") == "2026-07-07"

    def test_garbage_returns_empty(self):
        assert monitor.parse_date("not a date") == ""
        assert monitor.parse_date("") == ""


class TestBuildRow:
    def test_row_shape_and_status(self):
        detail = {
            "from": "Acme Careers <no-reply@acme.com>",
            "subject": "Interview invitation - Software Engineer",
            "date": "Tue, 07 Jul 2026 09:00:00 -0400",
            "snippet": "We'd like to schedule a call.",
            "link": "https://mail.google.com/mail/u/0/#all/abc123",
        }
        row = monitor.build_row(detail)
        assert len(row) == 15  # matches the sheet's 15 columns (A-O)
        assert row[0] == "Acme Careers"
        assert row[1] == "Interview invitation - Software Engineer"
        assert row[3] == "2026-07-07"
        assert row[4] == "Needs Review"
        assert "abc123" in row[14]
