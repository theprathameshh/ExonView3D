import re

from ._http import HttpClient
from .errors import DataError, GeneNotFound, InvalidInput, UpstreamError

GENE_ID_PATTERN = re.compile(r"^[0-9]{1,9}$")


def validate_gene_id(value):
    """Return a normalised NCBI Gene ID string, or raise InvalidInput."""

    text = str(value).strip()

    if not GENE_ID_PATTERN.match(text) or int(text) == 0:
        raise InvalidInput(
            f"'{text}' is not a valid NCBI Gene ID.",
            hint=(
                "Enter the numeric NCBI Gene ID, for example 7157 for TP53. "
                "Gene IDs can be looked up at https://www.ncbi.nlm.nih.gov/gene."
            ),
        )

    return str(int(text))


class EnactClient:
    """Retrieves gene, transcript and exon records from ENACTdb."""

    BASE_URL = "https://www.iscbglab.in/enactdb/ncbid"

    def __init__(self, ca_bundle=None, timeout=30, session=None):

        self.http = HttpClient(
            "ENACTdb",
            ca_bundle=ca_bundle,
            timeout=timeout,
            session=session,
        )

    def get_gene(self, gene_id):

        gene_id = validate_gene_id(gene_id)

        response = self.http.get(
            f"{self.BASE_URL}/{gene_id}/",
            params={"format": "json"},
            allow_404=True,
        )

        if response is None:
            raise GeneNotFound(
                f"Gene {gene_id} was not found in ENACTdb.",
                hint=(
                    "ENACTdb covers a subset of NCBI genes. Check the Gene ID "
                    "or try another gene."
                ),
            )

        content_type = response.headers.get("Content-Type", "").lower()

        if "json" not in content_type:
            raise UpstreamError(
                "ENACTdb returned an unexpected (non-JSON) response.",
                hint="The service may be temporarily unavailable.",
            )

        try:
            data = response.json()
        except ValueError as error:
            raise UpstreamError(
                "ENACTdb returned malformed JSON."
            ) from error

        if not isinstance(data, dict):
            raise DataError("Unexpected ENACTdb response format.")

        if "trans" not in data or "exonsGenes" not in data:

            # Unknown genes may be reported as an empty or "detail" payload.
            if not data or "detail" in data:
                raise GeneNotFound(
                    f"Gene {gene_id} was not found in ENACTdb."
                )

            raise DataError(
                "ENACTdb record is missing transcript or exon information."
            )

        if not data["trans"]:
            raise GeneNotFound(
                f"ENACTdb has no transcripts for gene {gene_id}."
            )

        return data
