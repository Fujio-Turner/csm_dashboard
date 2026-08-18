from .stub import StubConnector


def connector() -> StubConnector:
    return StubConnector("google_cal")
