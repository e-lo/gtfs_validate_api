import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_missing_file_and_url():
    response = client.post("/validate", data={})
    assert response.status_code == 400
    assert "You must provide either a file or a URL" in response.text

def test_both_file_and_url():
    with open("tests/dummy.zip", "wb") as f:
        f.write(b"dummy content")
    with open("tests/dummy.zip", "rb") as f:
        response = client.post("/validate", data={"url": "http://example.com/feed.zip"}, files={"file": ("dummy.zip", f, "application/zip")})
    assert response.status_code == 400
    assert "Provide only one of file or URL" in response.text

def test_invalid_file_type():
    with open("tests/dummy.txt", "w") as f:
        f.write("not a zip")
    with open("tests/dummy.txt", "rb") as f:
        response = client.post("/validate", files={"file": ("dummy.txt", f, "text/plain")})
    assert response.status_code == 400
    assert "GTFS feed must be a .zip" in response.text

def test_invalid_url():
    response = client.post("/validate", data={"url": "http://example.com/feed.txt"})
    assert response.status_code == 400
    assert "A valid GTFS .zip URL must be provided." in response.text 