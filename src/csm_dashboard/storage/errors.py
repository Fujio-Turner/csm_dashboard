class CouchbaseLiteError(Exception):
    def __init__(self, message: str, domain: int = 0, code: int = 0):
        self.domain = domain
        self.code = code
        super().__init__(message)


class CouchbaseLiteNotFound(CouchbaseLiteError):
    pass


class CouchbaseLiteNotAvailable(CouchbaseLiteError):
    pass
