from .stub import StubConnector


def connector() -> StubConnector:
    return StubConnector("smtp_imap")
