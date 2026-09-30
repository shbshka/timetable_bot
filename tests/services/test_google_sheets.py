import base64
import json

from src.services import google_sheets


def test_google_credentials_loads_base64_service_account(monkeypatch) -> None:
    # Arrange
    calls = []

    class FakeCredentials:
        @classmethod
        def from_service_account_info(cls, info, scopes=None):
            calls.append(("info", info, scopes))
            return "base64-credentials"

        @classmethod
        def from_service_account_file(cls, path, scopes=None):
            calls.append(("file", path, scopes))
            return "file-credentials"

    encoded = base64.b64encode(
        json.dumps({"type": "service_account", "project_id": "test"}).encode("utf-8")
    ).decode("ascii")
    monkeypatch.setenv("SERVICE_ACCOUNT_BASE64", encoded)
    monkeypatch.setattr(google_sheets, "Credentials", FakeCredentials)

    # Act
    credentials = google_sheets.get_google_credentials()

    # Assert
    assert credentials == "base64-credentials"
    assert calls[0][0] == "info"
    assert calls[0][2] == google_sheets.SCOPES


def test_google_credentials_uses_local_file_when_base64_is_absent(monkeypatch) -> None:
    # Arrange
    calls = []

    class FakeCredentials:
        @classmethod
        def from_service_account_file(cls, path, scopes=None):
            calls.append((path, scopes))
            return "file-credentials"

    monkeypatch.delenv("SERVICE_ACCOUNT_BASE64", raising=False)
    monkeypatch.setattr(google_sheets, "Credentials", FakeCredentials)

    # Act
    credentials = google_sheets.get_google_credentials()

    # Assert
    assert credentials == "file-credentials"
    assert calls[0][0].endswith("credentials.json")
    assert calls[0][1] == google_sheets.SCOPES