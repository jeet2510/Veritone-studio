import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from backend import create_app
from backend.config import Config


class SecurityWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_dir = Config.DB_DIR
        self.original_db_path = Config.DB_PATH
        self.original_env = {
            key: os.environ.get(key)
            for key in ("VERITONE_ADMIN_USER", "VERITONE_ADMIN_PASS")
        }
        Config.DB_DIR = Path(self.temp_dir.name)
        Config.DB_PATH = Config.DB_DIR / "veritone.db"
        os.environ["VERITONE_ADMIN_USER"] = "rootadmin"
        os.environ["VERITONE_ADMIN_PASS"] = "admin-password-long"
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")

    def tearDown(self):
        Config.DB_DIR = self.original_db_dir
        Config.DB_PATH = self.original_db_path
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp_dir.cleanup()

    def test_owner_scoping_and_admin_access(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get("/api/analyses").status_code, 401)

        alice = self.app.test_client()
        response = alice.post(
            "/api/auth/register",
            json={"username": "alice.writer", "password": "alice-password-long"},
        )
        self.assertEqual(response.status_code, 201)
        analysis = alice.post(
            "/api/analyze",
            data={"raw_text": "Moreover, careful review can reveal important details. A second sentence adds context."},
        )
        self.assertEqual(analysis.status_code, 201, analysis.get_json())
        analysis_id = analysis.get_json()["id"]

        bob = self.app.test_client()
        self.assertEqual(
            bob.post(
                "/api/auth/register",
                json={"username": "bob.writer", "password": "bob-password-long"},
            ).status_code,
            201,
        )
        self.assertEqual(bob.get(f"/api/analyses/{analysis_id}").status_code, 403)
        self.assertEqual(bob.delete(f"/api/analyses/{analysis_id}").status_code, 403)
        self.assertEqual(
            bob.get(f"/api/analyses/{analysis_id}/download/report").status_code, 403
        )
        self.assertEqual([row["id"] for row in bob.get("/api/analyses").get_json()], [])
        self.assertEqual(alice.get(f"/api/analyses/{analysis_id}").status_code, 200)

        admin = self.app.test_client()
        self.assertEqual(
            admin.post(
                "/api/auth/login",
                json={"username": "rootadmin", "password": "admin-password-long"},
            ).status_code,
            200,
        )
        self.assertEqual(admin.get("/api/admin/overview").get_json()["total_runs"], 1)
        self.assertEqual(admin.get(f"/api/admin/analyses/{analysis_id}").status_code, 200)
        self.assertEqual(
            admin.patch("/api/admin/users/1", json={"role": "user"}).status_code, 400
        )
        self.assertEqual(alice.get("/api/admin/overview").status_code, 403)
        self.assertEqual(admin.patch("/api/admin/users/3", json={"role": "admin"}).status_code, 200)
        self.assertEqual(
            admin.patch("/api/admin/users/3", json={"is_active": False}).status_code, 200
        )
        self.assertEqual(bob.get("/api/analyses").status_code, 401)

    def test_latex_upload_extracts_prose_without_size_cap(self):
        client = self.app.test_client()
        client.post(
            "/api/auth/register",
            json={"username": "latexwriter", "password": "latex-password-long"},
        )
        source = r"""\documentclass{article}
	itle{Preamble should not appear}
\begin{document}
\section{Methods}
The parser keeps this prose. % this comment should disappear
\begin{equation}
x + y = 1
\end{equation}
\begin{lstlisting}
hidden_implementation()
\end{lstlisting}
\end{document}"""
        response = client.post(
            "/api/analyze",
            data={"file": (BytesIO(source.encode("utf-8")), "draft.tex")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        extracted = response.get_json()["original_text"]
        self.assertIn("parser keeps this prose", extracted)
        self.assertNotIn("Preamble should not appear", extracted)
        self.assertNotIn("x + y", extracted)
        self.assertNotIn("hidden_implementation", extracted)
        self.assertNotIn("this comment should disappear", extracted)
        self.assertIsNone(self.app.config["MAX_CONTENT_LENGTH"])


if __name__ == "__main__":
    unittest.main()