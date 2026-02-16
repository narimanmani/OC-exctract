import unittest

import pandas as pd

from run_oc_pipeline import _compute_weekly_socio_technical_metrics


class WeeklySocioTechnicalMetricsTest(unittest.TestCase):
    def test_metrics_include_unmapped_behavior_and_switches(self) -> None:
        rows = [
            {
                "project": "org/repo",
                "commit_sha": "c1",
                "author_email": "alice@example.com",
                "author_date": "2025-04-01T10:00:00Z",
                "filename": "service-a/file1.py",
                "service": "service-a",
            },
            {
                "project": "org/repo",
                "commit_sha": "c2",
                "author_email": "alice@example.com",
                "author_date": "2025-04-02T10:00:00Z",
                "filename": "service-b/file2.py",
                "service": "service-b",
            },
            {
                "project": "org/repo",
                "commit_sha": "c3",
                "author_email": "bob@example.com",
                "author_date": "2025-04-03T10:00:00Z",
                "filename": "unknown/file3.py",
                "service": "__unmapped__",
            },
            {
                "project": "org/repo",
                "commit_sha": "c4",
                "author_email": "carol@example.com",
                "author_date": "2025-04-04T10:00:00Z",
                "filename": "service-a/file4.py",
                "service": "service-a",
            },
            {
                "project": "org/repo",
                "commit_sha": "c4",
                "author_email": "carol@example.com",
                "author_date": "2025-04-04T10:00:00Z",
                "filename": "service-a/file5.py",
                "service": "service-a",
            },
        ]
        df = pd.DataFrame(rows)

        metrics = _compute_weekly_socio_technical_metrics(
            df,
            project="org/repo",
            week_start=pd.to_datetime("2025-04-01", utc=True),
            week_end=pd.to_datetime("2025-04-07", utc=True),
        )

        self.assertEqual(metrics["active_devs"], 3)
        self.assertEqual(metrics["cross_service_devs"], 1)
        self.assertAlmostEqual(metrics["avg_services_per_dev"], 1.5)
        self.assertEqual(metrics["switch_count_total"], 1)


if __name__ == "__main__":
    unittest.main()
