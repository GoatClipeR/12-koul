"""Stable errors shared by the framework-independent domain boundary."""
class DomainError(ValueError):
    def __init__(self, code, details=None):
        self.code = code
        self.details = details or {}
        super().__init__(code)

    def as_dict(self):
        return {"code": self.code, "details": self.details}
