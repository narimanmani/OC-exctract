import unittest

import pandas as pd

from run_oc_pipeline import compute_weekly_sociotechnical_metrics


class WeeklySocioTechnicalMetricsTests(unittest.TestCase):
    def test_metrics_counts_and_switches(self) -> None:
        data = [
            {
                "project": "org/repo",
                "commit_sha": "c1",
                "author_email": "dev1@example.com",
                "author_login": None,
                "author_name": None,
                "author_date": "2025-01-01T10:00:00Z",
                "filename": "svc-a/file1.py",
                "service": "service-a",
            },
            {
                "project": "org/repo",
                "commit_sha": "c2",
                "author_email": "dev1@example.com",
                "author_login": None,
                "author_name": None,
                "author_date": "2025-01-02T10:00:00Z",
                "filename": "svc-b/file2.py",
                "service": "service-b",
            },
            {
                "project": "org/repo",
                "commit_sha": "c3",
                "author_email": None,
                "author_login": "dev2",
                "author_name": None,
                "author_date": "2025-01-02T12:00:00Z",
                "filename": "misc/readme.md",
                "service": "__unmapped__",
            },
            {
                "project": "org/repo",
                "commit_sha": "c4",
                "author_email": "dev3@example.com",
                "author_login": None,
                "author_name": None,
                "author_date": "2025-01-03T12:00:00Z",
                "filename": "svc-b/file3.py",
                "service": "service-b",
            },
        ]
        df = pd.DataFrame(data)

        metrics = compute_weekly_sociotechnical_metrics(
            df,
            project="org/repo",
            week_start=pd.Timestamp("2025-01-01", tz="UTC"),
            week_end=pd.Timestamp("2025-01-07", tz="UTC"),
        )

        self.assertEqual(metrics["active_devs"], 3)
        self.assertEqual(metrics["cross_service_devs"], 1)
        self.assertAlmostEqual(metrics["avg_services_per_dev"], 1.5, places=3)
        self.assertEqual(metrics["switch_count_total"], 1)


if __name__ == "__main__":
    unittest.main()
