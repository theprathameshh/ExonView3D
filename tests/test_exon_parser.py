import json
from pathlib import Path

import pytest

from exonview3d.exon_parser import parse_gene

DATA = Path(__file__).parent / "data"


def load(name):
    return json.loads((DATA / name).read_text())


def test_a1bg_gene_information():
    result = parse_gene(load("enact_1.json"))
    assert result["gene_id"] == 1
    assert "A1BG" in result["gene_name"]
    assert len(result["transcripts"]) == 1


def test_tp53_all_transcripts_cover_their_protein():
    result = parse_gene(load("enact_7157.json"))
    assert len(result["transcripts"]) == 15
    for transcript in result["transcripts"]:
        assert len(transcript["protein_sequence"]) == transcript["protein_length"]
        assert set(transcript["residue_to_exon"]) == set(
            range(1, transcript["protein_length"] + 1)
        )


def test_lenient_parsing_skips_a_broken_transcript():
    data = load("enact_7157.json")
    data["trans"][1]["exonsRegion"] = "garbage"

    with pytest.raises(ValueError):
        parse_gene(data)

    result = parse_gene(data, strict=False)
    assert len(result["transcripts"]) == 14
    assert result["skipped_transcripts"][0]["transcript_id"] == data["trans"][1]["tId"]
