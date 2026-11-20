"""Thin wrapper around requests that raises ExonViewError subclasses."""

import requests

from .errors import CertificateError, UpstreamError

from . import __version__

USER_AGENT = f"ExonView3D/{__version__}"

SSL_HINT = (
    "The TLS certificate of the remote server could not be verified. "
    "If your network uses a custom or incomplete certificate chain, pass "
    "--ca-bundle /path/to/bundle.pem (or set EXONVIEW3D_CA_BUNDLE). "
    "See the 'Troubleshooting' section of the README."
)


class HttpClient:

    def __init__(self, service, ca_bundle=None, timeout=30, session=None,
                 accept="application/json"):

        self.service = service
        self.ca_bundle = ca_bundle
        self.timeout = timeout

        self.session = session or requests.Session()
        self.session.headers.update({
            "Accept": accept,
            "User-Agent": USER_AGENT,
        })

    def get(self, url, params=None, allow_404=False):
        """GET a URL. Returns None for 404 when allow_404 is set."""

        kwargs = {"params": params, "timeout": self.timeout}

        # Leave verify unset by default so REQUESTS_CA_BUNDLE is honoured.
        if self.ca_bundle:
            kwargs["verify"] = self.ca_bundle

        try:
            response = self.session.get(url, **kwargs)

        except requests.exceptions.SSLError as error:
            raise CertificateError(
                f"Could not verify the {self.service} server certificate.",
                hint=SSL_HINT,
            ) from error

        except requests.exceptions.Timeout as error:
            raise UpstreamError(
                f"{self.service} did not respond in time.",
                hint="Check your connection and try again.",
            ) from error

        except requests.exceptions.RequestException as error:
            raise UpstreamError(
                f"Could not connect to {self.service}.",
                hint="Check your internet connection and try again.",
            ) from error

        if response.status_code == 404 and allow_404:
            return None

        if response.status_code >= 400:
            raise UpstreamError(
                f"{self.service} returned HTTP {response.status_code}."
            )

        return response
