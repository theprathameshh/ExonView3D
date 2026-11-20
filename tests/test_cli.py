import json

import pytest

from exonview3d import cli
from exonview3d.service import ExonViewService


@pytest.fixture(autouse=True)
def offline_service(monkeypatch, service):
    monkeypatch.setattr(cli, "make_service", lambda args: service)


def test_gene_table(capsys):
    assert cli.main(["gene", "7157"]) == 0
    out = capsys.readouterr().out
    assert "TP53" in out and "NP_001119584.1" in out and "12 with an AlphaFold" in out


def test_gene_json(capsys):
    assert cli.main(["gene", "7157", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["transcripts"] == 15


def test_transcript_detail(capsys):
    assert cli.main(["gene", "7157", "-t", "NP_001119584.1"]) == 0
    out = capsys.readouterr().out
    assert "393/393" in out and "D.1.A.2.0.0" in out


def test_errors_exit_nonzero_without_traceback(capsys):
    assert cli.main(["gene", "TP53"]) == 1
    err = capsys.readouterr().err
    assert "error:" in err and "hint:" in err and "Traceback" not in err


def test_missing_command_prints_help(capsys):
    assert cli.main([]) == 2
