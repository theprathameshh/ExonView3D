import requests
from pathlib import Path


class EnactClient:

    BASE_URL = "https://www.iscbglab.in/enactdb/ncbid"

    def __init__(self, ca_bundle=None, timeout=30):

        self.ca_bundle = ca_bundle
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "ExonView3D/0.1"
        })

    def get_gene(self, gene_id):

        url = f"{self.BASE_URL}/{gene_id}/"

        params = {"format": "json"}

        response = self.session.get(
            url,
            params=params,
            verify=self.ca_bundle if self.ca_bundle else True,
            timeout=self.timeout
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if "application/json" not in content_type:
            raise ValueError(
                f"Expected JSON but received {content_type}"
            )

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError("Unexpected ENACTdb response format")

        if "trans" not in data or "exonsGenes" not in data:
            raise ValueError("Missing transcript or exon information")

        return data
