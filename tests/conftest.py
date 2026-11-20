"""Offline test harness: a fake `requests` session replaying fixtures."""

import json
from pathlib import Path

import pytest
import requests

from exonview3d.service import ExonViewService

DATA = Path(__file__).parent / "data"

ENACT = "https://www.iscbglab.in/enactdb/ncbid"
AF_API = "https://alphafold.ebi.ac.uk/api/prediction"
UNIPROT = "https://rest.uniprot.org/uniprotkb"


class FakeResponse:

    def __init__(self, status_code=200, content=b"", content_type="application/json"):
        self.status_code = status_code
        self.content = content
        self.headers = {"Content-Type": content_type}

    @property
    def text(self):
        return self.content.decode()

    def json(self):
        return json.loads(self.content)


class FakeSession:
    """Serves bundled fixtures; records every requested URL."""

    def __init__(self):
        self.headers = {}
        self.requested = []
        self.fail_with = None
        self.routes = {}

        predictions = json.loads(
            (DATA / "alphafold_P04637_predictions.json").read_text()
        )

        self.routes[f"{ENACT}/7157/"] = FakeResponse(
            content=(DATA / "enact_7157.json").read_bytes()
        )
        self.routes[f"{ENACT}/1/"] = FakeResponse(
            content=(DATA / "enact_1.json").read_bytes()
        )
        self.routes[f"{AF_API}/P04637"] = FakeResponse(
            content=json.dumps(predictions).encode()
        )

        # Only two models have a local structure file; the rest are 404.
        for name in ("AF-P04637-F1-model_v6.cif", "AF-P04637-9-F1-model_v6.cif"):
            self.routes[f"https://alphafold.ebi.ac.uk/files/{name}"] = FakeResponse(
                content=(DATA / "alphafold" / name).read_bytes(),
                content_type="chemical/x-mmcif",
            )

        for record in predictions:
            accession = record["uniprotAccession"]
            if accession in ("P04637", "P04637-9"):
                fasta = (
                    f">sp|{accession}|P53_HUMAN Cellular tumor antigen p53 "
                    f"OS=Homo sapiens OX=9606 GN=TP53 PE=1 SV=4\n"
                    + record["sequence"] + "\n"
                )
                self.routes[f"{UNIPROT}/{accession}.fasta"] = FakeResponse(
                    content=fasta.encode(), content_type="text/plain"
                )

    def get(self, url, **kwargs):

        self.requested.append(url)

        if self.fail_with is not None:
            raise self.fail_with

        return self.routes.get(url, FakeResponse(status_code=404))


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def service(tmp_path, session):
    return ExonViewService(cache_dir=tmp_path / "cache", session=session)
