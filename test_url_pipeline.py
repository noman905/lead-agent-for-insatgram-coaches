"""Unit tests for google_scraper URL filtering, normalization, dedup, and query builders."""
import unittest
from unittest.mock import MagicMock, patch

from google_scraper import (
    build_search_query,
    build_retry_query,
    is_instagram_url,
    is_valid_profile_url,
    normalize_url,
    _clean_and_filter_urls,
    _cross_check_leads,
    get_existing_leads_urls,
)


class TestQueryBuilders(unittest.TestCase):

    def test_primary_query_format(self):
        q = build_search_query("branding coach", "Texas")
        self.assertEqual(q, '"branding coach" "Texas" instagram.com')

    def test_retry_query_format(self):
        q = build_retry_query("branding coach", "Texas")
        self.assertEqual(q, '"branding coach" coach "Texas" instagram')

    def test_query_strips_whitespace(self):
        q = build_search_query("  career coach  ", "  Connecticut  ")
        self.assertEqual(q, '"career coach" "Connecticut" instagram.com')


class TestIsInstagramUrl(unittest.TestCase):

    def test_valid_urls(self):
        self.assertTrue(is_instagram_url("https://www.instagram.com/johncoach"))
        self.assertTrue(is_instagram_url("https://instagram.com/brandingcoachtexas"))
        self.assertTrue(is_instagram_url("https://www.instagram.com/salescoach_usa"))

    def test_non_instagram_urls(self):
        self.assertFalse(is_instagram_url("https://facebook.com/johncoach"))
        self.assertFalse(is_instagram_url("https://linkedin.com/in/johncoach"))
        self.assertFalse(is_instagram_url("https://youtube.com/johncoach"))
        self.assertFalse(is_instagram_url("https://twitter.com/johncoach"))
        self.assertFalse(is_instagram_url("https://tiktok.com/@johncoach"))
        self.assertFalse(is_instagram_url("https://somewebsite.com/john-coach"))
        self.assertFalse(is_instagram_url("https://yelp.com/biz/john-coach"))

    def test_empty_and_none(self):
        self.assertFalse(is_instagram_url(""))
        self.assertFalse(is_instagram_url(None))


class TestIsValidProfileUrl(unittest.TestCase):

    def test_valid_profile_urls(self):
        self.assertTrue(is_valid_profile_url("https://instagram.com/johncoach"))
        self.assertTrue(is_valid_profile_url("https://www.instagram.com/brandingcoachtexas"))

    def test_junk_urls_removed(self):
        junk = [
            "https://instagram.com/explore/tags/brandingcoach",
            "https://instagram.com/p/ABC123xyz",
            "https://instagram.com/reel/XYZ456abc",
            "https://instagram.com/stories/johncoach/123",
            "https://instagram.com/accounts/login",
            "https://instagram.com/direct/inbox",
            "https://instagram.com/tv/somevideo",
            "https://instagram.com/hashtag/coach",
            "https://instagram.com/explore/locations/texas",
            "https://instagram.com/johncoach?igshid=abc123",
        ]
        for url in junk:
            self.assertFalse(is_valid_profile_url(url), f"Should be invalid: {url}")


class TestNormalizeUrl(unittest.TestCase):

    def test_lowercase(self):
        self.assertEqual(normalize_url("HTTPS://WWW.Instagram.com/JohnCoach/"),
                         "https://instagram.com/johncoach")

    def test_removes_www(self):
        self.assertEqual(normalize_url("https://www.instagram.com/johncoach"),
                         "https://instagram.com/johncoach")

    def test_removes_trailing_slash(self):
        self.assertEqual(normalize_url("https://instagram.com/johncoach/"),
                         "https://instagram.com/johncoach")

    def test_strips_whitespace(self):
        self.assertEqual(normalize_url("  https://instagram.com/johncoach  "),
                         "https://instagram.com/johncoach")

    def test_all_three_become_same(self):
        urls = [
            "https://WWW.Instagram.com/JohnCoach/",
            "https://www.instagram.com/johncoach",
            "HTTPS://instagram.com/JohnCoach/",
        ]
        normalized = [normalize_url(u) for u in urls]
        self.assertEqual(len(set(normalized)), 1)
        self.assertEqual(normalized[0], "https://instagram.com/johncoach")


class TestCleanAndFilterUrls(unittest.TestCase):

    def test_full_pipeline(self):
        raw = [
            "https://facebook.com/johncoach",           # non-IG
            "https://www.instagram.com/johncoach/",      # valid profile
            "https://instagram.com/explore/tags/coach",  # junk IG
            "https://instagram.com/p/ABC123",            # junk IG (post)
            "https://WWW.Instagram.com/JohnCoach/",      # duplicate after normalize
            "https://instagram.com/brandingcoach_tx",    # valid profile
            "https://instagram.com/salescoach?igshid=x", # junk (query param)
            "https://linkedin.com/in/john",              # non-IG
            "https://instagram.com/reel/XYZ456",         # junk IG (reel)
        ]
        result = _clean_and_filter_urls(raw)
        self.assertEqual(result, [
            "https://instagram.com/johncoach",
            "https://instagram.com/brandingcoach_tx",
        ])

    def test_empty_input(self):
        self.assertEqual(_clean_and_filter_urls([]), [])


class TestCrossCheckLeads(unittest.TestCase):

    def test_removes_existing_urls(self):
        existing = {
            "https://instagram.com/johncoach",
            "https://instagram.com/coachtexas_pro",
        }
        batch = [
            "https://instagram.com/johncoach",        # already exists
            "https://instagram.com/brandingcoach_tx",  # new
            "https://instagram.com/coachtexas_pro",    # already exists
            "https://instagram.com/salescoach_usa",    # new
        ]
        new_urls, skipped = _cross_check_leads(batch, existing)
        self.assertEqual(new_urls, [
            "https://instagram.com/brandingcoach_tx",
            "https://instagram.com/salescoach_usa",
        ])
        self.assertEqual(skipped, 2)

    def test_no_existing(self):
        batch = ["https://instagram.com/coach1", "https://instagram.com/coach2"]
        new_urls, skipped = _cross_check_leads(batch, set())
        self.assertEqual(new_urls, batch)
        self.assertEqual(skipped, 0)


class TestGetExistingLeadsUrls(unittest.TestCase):

    def test_reads_profile_url_column(self):
        mock_sh = MagicMock()
        mock_ws = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_ws.get_all_values.return_value = [
            ["Profile URL", "Username", "Full Name"],
            ["https://www.instagram.com/coach1/", "coach1", "Coach One"],
            ["https://WWW.Instagram.com/Coach2/", "coach2", "Coach Two"],
        ]
        result = get_existing_leads_urls(mock_sh)
        self.assertIn("https://instagram.com/coach1", result)
        self.assertIn("https://instagram.com/coach2", result)

    def test_falls_back_to_username_column(self):
        mock_sh = MagicMock()
        mock_ws = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_ws.get_all_values.return_value = [
            ["Username", "Full Name"],
            ["coach1", "Coach One"],
        ]
        result = get_existing_leads_urls(mock_sh)
        self.assertIn("https://instagram.com/coach1", result)


if __name__ == "__main__":
    unittest.main()
