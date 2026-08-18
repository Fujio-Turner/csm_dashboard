from .stub import StubConnector


def connector() -> StubConnector:
    return StubConnector("m365_cal")
