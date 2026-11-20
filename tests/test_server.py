import json
import urllib.error
import urllib.request

import pytest

from exonview3d.server import create_server, serve_in_thread


@pytest.fixture
def base_url(service):
    server = create_server(service, "127.0.0.1", 0)
    serve_in_thread(server)
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def fetch(url):
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


def test_index_and_assets_are_served(base_url):
    status, headers, body = fetch(base_url + "/")
    assert status == 200 and b"ExonView3D" in body
    status, _, body = fetch(base_url + "/assets/app.js")
    assert status == 200 and len(body) > 100_000


def test_gene_endpoint(base_url):
    status, _, body = fetch(base_url + "/api/gene/7157")
    data = json.loads(body)
    assert status == 200 and data["gene"]["symbol"] == "TP53"


def test_transcript_endpoint_includes_structure_url(base_url):
    status, _, body = fetch(base_url + "/api/gene/7157/transcript/NP_001119584.1")
    data = json.loads(body)
    assert status == 200
    assert data["structure"]["url"] == "/api/gene/7157/transcript/NP_001119584.1/structure.cif"
    # no local filesystem paths leak through the API
    assert "/cache" not in json.dumps(data) and "\\" not in json.dumps(data["structure"])


def test_structure_file_is_served_as_mmcif(base_url):
    status, headers, body = fetch(
        base_url + "/api/gene/7157/transcript/NP_001119584.1/structure.cif"
    )
    assert status == 200
    assert headers["Content-Type"] == "chemical/x-mmcif"
    assert body.startswith(b"data_")


@pytest.mark.parametrize("path, status, code", [
    ("/api/gene/abc", 400, "invalid_input"),
    ("/api/gene/99999", 404, "gene_not_found"),
    ("/api/gene/7157/transcript/NP_000000.0", 404, "transcript_not_found"),
    ("/api/gene/7157/transcript/NP_001263626.1/structure.cif", 404, "structure_unavailable"),
    ("/api/nothing", 404, "not_found"),
])
def test_errors_are_json(base_url, path, status, code):
    got_status, _, body = fetch(base_url + path)
    assert got_status == status
    assert json.loads(body)["error"]["code"] == code


def test_no_path_traversal_through_assets(base_url):
    for path in ("/assets/../cli.py", "/assets/..%2fcli.py", "/assets/%2e%2e/cli.py"):
        status, _, _ = fetch(base_url + path)
        assert status == 404


def test_only_get_is_allowed(base_url):
    request = urllib.request.Request(base_url + "/api/gene/7157", method="POST", data=b"")
    with pytest.raises(urllib.error.HTTPError) as info:
        urllib.request.urlopen(request)
    assert info.value.code == 405
