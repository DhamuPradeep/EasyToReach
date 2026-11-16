import unittest
from database import get_connection, init_db
import json

class TestCloudSync(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_cloud_sheet_columns(self):
        conn = get_connection()
        shop = conn.execute("SELECT cloud_sheet_url, last_cloud_sync_at FROM shops WHERE id = 1").fetchone()
        self.assertIsNotNone(shop)
        conn.close()

if __name__ == "__main__":
    unittest.main()

