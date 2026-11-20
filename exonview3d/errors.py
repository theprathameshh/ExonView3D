"""Exceptions with a machine-readable code, an HTTP status and a user hint.

Every failure that a user can reasonably cause or run into (bad input,
unknown gene, a remote service being down) is one of these, so the CLI and
the web API can report it cleanly instead of showing a traceback.
"""


class ExonViewError(Exception):
    code = "error"
    http_status = 500

    def __init__(self, message, hint=None):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_dict(self):
        payload = {"code": self.code, "message": self.message}
        if self.hint:
            payload["hint"] = self.hint
        return payload


class InvalidInput(ExonViewError):
    code = "invalid_input"
    http_status = 400


class GeneNotFound(ExonViewError):
    code = "gene_not_found"
    http_status = 404


class TranscriptNotFound(ExonViewError):
    code = "transcript_not_found"
    http_status = 404


class StructureUnavailable(ExonViewError):
    code = "structure_unavailable"
    http_status = 404


class DataError(ExonViewError):
    """Remote data was retrieved but is inconsistent or unparseable."""

    code = "data_error"
    http_status = 422


class UpstreamError(ExonViewError):
    """A remote service (ENACTdb, UniProt, AlphaFold DB) failed."""

    code = "upstream_error"
    http_status = 502


class CertificateError(UpstreamError):
    code = "ssl_error"
