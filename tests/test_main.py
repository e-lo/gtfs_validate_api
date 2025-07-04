import os

os.environ["APP_ENV"] = "development"
os.environ["DISABLE_EMAIL_AND_API_KEY"] = "False"
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8081"
os.environ["MAIL_FROM"] = "test@example.com"
os.environ["MAIL_USERNAME"] = "testuser"
os.environ["MAIL_PASSWORD"] = "testpass"
os.environ["MAIL_PORT"] = "587"
os.environ["MAIL_SERVER"] = "smtp.example.com"
os.environ["MAIL_STARTTLS"] = "true"
os.environ["MAIL_SSL_TLS"] = "false"
import subprocess
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app, get_md_intro, get_md_section
import re


@pytest.fixture(scope="session", autouse=True)
def start_firestore_emulator():
    # Check if the emulator is already running
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("localhost", 8081))
    sock.close()
    if result != 0:
        # Start the emulator as a subprocess
        proc = subprocess.Popen(
            [
                "gcloud",
                "beta",
                "emulators",
                "firestore",
                "start",
                "--host-port=localhost:8081",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait for the emulator to start
        time.sleep(5)
        yield
        proc.terminate()
    else:
        yield


client = TestClient(app)


def test_missing_file_and_url():
    response = client.post("/validate", data={})
    assert response.status_code == 400
    assert "You must provide either a file or a URL" in response.text


def test_both_file_and_url():
    with open("tests/dummy.zip", "wb") as f:
        f.write(b"dummy content")
    with open("tests/dummy.zip", "rb") as f:
        response = client.post(
            "/validate",
            data={"url": "http://example.com/feed.zip"},
            files={"file": ("dummy.zip", f, "application/zip")},
        )
    assert response.status_code == 400
    assert "Provide only one of file or URL" in response.text


def test_invalid_file_type():
    with open("tests/dummy.txt", "w") as f:
        f.write("not a zip")
    with open("tests/dummy.txt", "rb") as f:
        response = client.post(
            "/validate", files={"file": ("dummy.txt", f, "text/plain")}
        )
    assert response.status_code == 400
    assert "GTFS feed must be a .zip" in response.text


def test_invalid_url():
    response = client.post("/validate", data={"url": "http://example.com/feed.txt"})
    assert response.status_code == 400
    assert "A valid GTFS .zip URL must be provided." in response.text


def test_get_md_intro_basic():
    md = """# GTFS Validator Micro-service\n\nIntro text here.\n\n## Section 1\nContent 1\n"""
    assert get_md_intro(md) == "# GTFS Validator Micro-service\n\nIntro text here."


def test_get_md_intro_no_section():
    md = """# GTFS Validator Micro-service\n\nJust intro, no sections."""
    assert get_md_intro(md) == "# GTFS Validator Micro-service\n\nJust intro, no sections."


def test_get_md_section_basic():
    md = """# Title\n\n## Section 1\nContent 1\n\n### Subsection\nSubcontent\n\n## Section 2\nContent 2\n"""
    result = get_md_section(md, "## Section 1")
    assert "Content 1" in result
    assert "### Subsection" in result
    assert "Subcontent" in result
    assert "## Section 2" not in result


def test_get_md_section_end_of_file():
    md = """# Title\n\n## Section 1\nContent 1\n"""
    result = get_md_section(md, "## Section 1")
    assert "Content 1" in result


def test_get_md_section_not_found():
    md = "# Title\n\n## Section 1\nContent 1\n"
    assert get_md_section(md, "## Not Present") == ""
