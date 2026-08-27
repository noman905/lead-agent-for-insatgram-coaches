import unittest
from unittest.mock import MagicMock, patch

from run_agent import (
    is_apify_credit_exhausted,
    ApifyCreditsExhaustedError,
    process_single_job,
    run_agent
)
from email_notifier import (
    send_summary_notification,
    send_apify_credits_alert,
    send_failure_notification
)


class MockApifyApiError(Exception):
    def __init__(self, message, status_code=None, error_type=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.type = error_type


class TestErrorHandlingAndCredits(unittest.TestCase):

    def test_is_apify_credit_exhausted_true_cases(self):
        # 1. Status code 402
        err1 = MockApifyApiError("Payment Required", status_code=402)
        self.assertTrue(is_apify_credit_exhausted(err1))

        # 2. Type matches limit
        err2 = MockApifyApiError("Some error", error_type="monthly-usage-limit-exceeded")
        self.assertTrue(is_apify_credit_exhausted(err2))

        # 3. String patterns
        test_strings = [
            "Monthly usage limit exceeded",
            "Actor run failed because you exceeded your usage limit",
            "Your account has run out of credit",
            "credits exhausted during actor execution",
            "Apify out of credits",
            "insufficient credit available",
            "not enough credit to run this actor",
            "Payment Required: quota exceeded",
            "Apify credits are out"
        ]
        for s in test_strings:
            self.assertTrue(is_apify_credit_exhausted(Exception(s)), f"Failed for: {s}")
            self.assertTrue(is_apify_credit_exhausted(s), f"Failed for string: {s}")

    def test_is_apify_credit_exhausted_false_cases(self):
        non_credit_errors = [
            "Google Search actor returned 0 results for this query.",
            "HTTPSConnectionPool(host='api.apify.com', port=443): Read timed out.",
            "Invalid URL format: not an instagram.com domain",
            "KeyError: 'defaultDatasetId'",
            "RateLimitError (429): Too many requests, retry after 5s",
            "Actor exited with status TIMEOUT"
        ]
        for s in non_credit_errors:
            self.assertFalse(is_apify_credit_exhausted(Exception(s)), f"Should be False for: {s}")

    def test_summary_email_content(self):
        sent_emails = []

        def mock_send(subject, body, recipient=None):
            sent_emails.append({"subject": subject, "body": body})
            return True

        with patch("email_notifier.send_email", side_effect=mock_send):
            done_jobs = [
                {"row_number": 2, "niche": "career coach", "state": "Connecticut", "leads_added": 10, "duplicates_skipped": 2},
                {"row_number": 4, "niche": "life coach", "state": "Florida", "leads_added": 5, "duplicates_skipped": 1}
            ]
            failed_jobs = [
                {"row_number": 3, "niche": "business coach", "state": "Texas", "error": "Google Search actor returned 0 results for this query."}
            ]

            send_summary_notification(done_jobs=done_jobs, failed_jobs=failed_jobs, total_leads_added=15)

            self.assertEqual(len(sent_emails), 1)
            mail = sent_emails[0]
            self.assertIn("2 Done, 1 Failed", mail["subject"])
            self.assertIn("Jobs Done (Success):  2", mail["body"])
            self.assertIn("Jobs Failed:          1", mail["body"])
            self.assertIn("Total New Leads:      15", mail["body"])
            self.assertIn("career coach / Connecticut", mail["body"])
            self.assertIn("business coach / Texas", mail["body"])
            self.assertIn("Google Search actor returned 0 results for this query.", mail["body"])

    def test_apify_credits_alert_email_content(self):
        sent_emails = []

        def mock_send(subject, body, recipient=None):
            sent_emails.append({"subject": subject, "body": body})
            return True

        with patch("email_notifier.send_email", side_effect=mock_send):
            send_apify_credits_alert(
                niche="career coach",
                state="Connecticut",
                reason="Monthly usage limit exceeded (HTTP 402)"
            )

            self.assertEqual(len(sent_emails), 1)
            self.assertIn("Apify credits are out — pipeline stopped.", sent_emails[0]["subject"])
            self.assertIn("Apify credits are out — pipeline stopped.", sent_emails[0]["body"])
            self.assertIn("Monthly usage limit exceeded", sent_emails[0]["body"])
            self.assertIn("Remaining rows in the Control tab have been left as 'Pending'", sent_emails[0]["body"])

    def test_process_single_job_regular_failure_continues(self):
        mock_control_sheet = MagicMock()
        mock_sh = MagicMock()

        with patch("run_agent.fetch_instagram_profiles_from_google", return_value=("query", [])):
            with patch("run_agent.append_run_log_entry") as mock_run_log:
                job = {"row_number": 3, "niche": "fitness coach", "state": "Ohio", "pages": "1"}
                result = process_single_job(mock_sh, mock_control_sheet, job)

                self.assertEqual(result["status"], "Failed")
                self.assertIn("0 results", result["error"])
                mock_control_sheet.update_cell.assert_any_call(3, 4, "Failed: Google Search actor returned 0 results after retry")
                mock_run_log.assert_called_once()

    def test_process_single_job_credit_exhaustion_resets_to_pending(self):
        mock_control_sheet = MagicMock()
        mock_sh = MagicMock()

        with patch("run_agent.fetch_instagram_profiles_from_google", side_effect=Exception("Monthly usage limit exceeded")):
            with patch("run_agent.append_run_log_entry"):
                job = {"row_number": 5, "niche": "executive coach", "state": "New York", "pages": "1"}
                
                with self.assertRaises(ApifyCreditsExhaustedError):
                    process_single_job(mock_sh, mock_control_sheet, job)

                mock_control_sheet.update_cell.assert_any_call(5, 4, "Pending")

    def test_run_agent_pipeline_continuation_and_summary_email(self):
        mock_sh = MagicMock()
        mock_control_sheet = MagicMock()
        mock_gc = MagicMock()
        mock_gc.open_by_key.return_value = mock_sh
        mock_sh.worksheet.return_value = mock_control_sheet

        jobs_in_queue = [
            {"row_number": 2, "niche": "coach 1", "state": "CA", "pages": "1", "status": "Pending"},
            {"row_number": 3, "niche": "coach 2", "state": "NY", "pages": "1", "status": "Pending"},
            {"row_number": 4, "niche": "coach 3", "state": "TX", "pages": "1", "status": "Pending"},
        ]

        def fake_process(sh, sheet, job):
            if job["row_number"] == 3:
                return {"status": "Failed", "row_number": 3, "niche": job["niche"], "state": job["state"], "error": "Google 0 results"}
            return {"status": "Done", "row_number": job["row_number"], "niche": job["niche"], "state": job["state"], "leads_added": 5, "duplicates_skipped": 1, "total_found": 6}

        with patch("os.path.exists", return_value=True), \
             patch("gspread.service_account", return_value=mock_gc), \
             patch("run_agent.ensure_sheet_structure"), \
             patch("run_agent.get_control_jobs", return_value=jobs_in_queue), \
             patch("run_agent.process_single_job", side_effect=fake_process), \
             patch("run_agent.send_summary_notification") as mock_summary_mail, \
             patch("run_agent.send_apify_credits_alert") as mock_alert_mail:

            run_agent()

            mock_summary_mail.assert_called_once()
            args, kwargs = mock_summary_mail.call_args
            done_list = kwargs.get("done_jobs") if "done_jobs" in kwargs else args[0]
            failed_list = kwargs.get("failed_jobs") if "failed_jobs" in kwargs else args[1]
            self.assertEqual(len(done_list), 2)
            self.assertEqual(len(failed_list), 1)
            self.assertEqual(failed_list[0]["row_number"], 3)
            mock_alert_mail.assert_not_called()

    def test_run_agent_pipeline_credit_exhaustion_stops_immediately(self):
        mock_sh = MagicMock()
        mock_control_sheet = MagicMock()
        mock_gc = MagicMock()
        mock_gc.open_by_key.return_value = mock_sh
        mock_sh.worksheet.return_value = mock_control_sheet

        jobs_in_queue = [
            {"row_number": 2, "niche": "coach 1", "state": "CA", "pages": "1", "status": "Pending"},
            {"row_number": 3, "niche": "coach 2", "state": "NY", "pages": "1", "status": "Pending"},
            {"row_number": 4, "niche": "coach 3", "state": "TX", "pages": "1", "status": "Pending"},
        ]

        executed_rows = []

        def fake_process(sh, sheet, job):
            executed_rows.append(job["row_number"])
            if job["row_number"] == 3:
                raise ApifyCreditsExhaustedError("credits exhausted")
            return {"status": "Done", "row_number": job["row_number"], "niche": job["niche"], "state": job["state"], "leads_added": 5, "duplicates_skipped": 1, "total_found": 6}

        with patch("os.path.exists", return_value=True), \
             patch("gspread.service_account", return_value=mock_gc), \
             patch("run_agent.ensure_sheet_structure"), \
             patch("run_agent.get_control_jobs", return_value=jobs_in_queue), \
             patch("run_agent.process_single_job", side_effect=fake_process), \
             patch("run_agent.send_summary_notification") as mock_summary_mail, \
             patch("run_agent.send_apify_credits_alert") as mock_alert_mail:

            run_agent()

            # Job 3 failed with credit exhaustion -> loop broke, Job 4 was not executed
            self.assertEqual(executed_rows, [2, 3])
            mock_alert_mail.assert_called_once()
            args, kwargs = mock_alert_mail.call_args
            niche = kwargs.get("niche")
            self.assertEqual(niche, "coach 2")
            mock_summary_mail.assert_not_called()


if __name__ == "__main__":
    unittest.main()
