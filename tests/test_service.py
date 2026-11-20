import pytest
import requests

from exonview3d.errors import (
    CertificateError, GeneNotFound, InvalidInput, TranscriptNotFound,
    UpstreamError,
)

CANONICAL = "NP_001119584.1"


@pytest.mark.parametrize("bad", ["", "abc", "TP53", "-5", "0", "12 34", "1;2", "9" * 12])
def test_invalid_gene_ids_are_rejected(service, bad):
    with pytest.raises(InvalidInput):
        service.search_gene(bad)


def test_unknown_gene(service):
    with pytest.raises(GeneNotFound):
        service.search_gene(99999)


def test_gene_search_lists_transcripts_and_availability(service):
    result = service.search_gene("7157")
    assert result["gene"]["symbol"] == "TP53"
    assert result["summary"] == {"transcripts": 15, "with_structure": 12}

    by_id = {t["transcript_id"]: t for t in result["transcripts"]}
    assert by_id[CANONICAL]["structure_available"]
    assert by_id["NP_001119589.1"]["uniprot_id"] == "P04637-9"
    assert by_id["NP_001263626.1"]["alphafold"]["status"] == "no_exact_sequence_match"

    # transcripts with a structure are listed first
    flags = [t["structure_available"] for t in result["transcripts"]]
    assert flags == sorted(flags, reverse=True)


def test_gene_without_alphafold_model(service):
    result = service.search_gene(1)
    assert result["transcripts"][0]["alphafold"]["status"] == "no_alphafold_model"


def test_transcript_detail_matches_expected_tp53_mapping(service):
    detail = service.get_transcript(7157, CANONICAL)

    assert detail["structure"]["status"] == "available"
    assert detail["structure"]["model_id"] == "AF-P04637-F1"
    assert detail["structure"]["chain_id"] == "A"
    assert detail["mapping"] == {
        "mapped_residues": 393, "protein_length": 393, "coverage_percent": 100.0,
    }
    assert detail["uniprot"]["accession"] == "P04637"
    assert detail["uniprot"]["validation"]["status"] == "identical"
    assert detail["protein"]["name"] == "Cellular tumor antigen p53"

    exons = detail["exons"]
    assert len(exons) == 10
    assert len({e["colour"] for e in exons}) == 10
    assert exons[0]["structure_residue_segments"][0]["start"] == 1
    assert exons[0]["structure_residue_segments"][0]["end"] == 25
    # exons tile the protein exactly
    assert sum(e["protein_length"] for e in exons) == 393
    assert all(e["coverage_percent"] == 100.0 for e in exons)


def test_isoform_structure_is_matched_by_sequence(service):
    detail = service.get_transcript(7157, "NP_001119589.1")
    assert detail["structure"]["accession"] == "P04637-9"
    assert detail["mapping"]["coverage_percent"] == 100.0
    # ENACTdb lists no accession for this transcript; it comes from the match
    assert detail["uniprot"]["accession"] == "P04637-9"
    assert detail["uniprot"]["source"] == "AlphaFold sequence match"


def test_missing_structure_file_degrades_gracefully(service):
    # P04637-8 matches by sequence but its file is not served (HTTP 404).
    detail = service.get_transcript(7157, "NP_001119588.1")
    assert detail["structure"]["status"] == "download_failed"
    assert detail["mapping"] is None
    assert len(detail["exons"]) == 6
    assert detail["exons"][0]["coverage_percent"] is None


def test_transcript_without_structure_still_lists_exons(service):
    detail = service.get_transcript(7157, "NP_001263626.1")
    assert detail["structure"]["status"] == "no_exact_sequence_match"
    assert detail["exons"]


def test_unknown_transcript(service):
    with pytest.raises(TranscriptNotFound):
        service.get_transcript(7157, "NP_000000.0")


def test_invalid_transcript_id(service):
    with pytest.raises(InvalidInput):
        service.get_transcript(7157, "../../etc/passwd")


def test_results_are_cached(service, session):
    service.get_transcript(7157, CANONICAL)
    first = len(session.requested)
    service.get_transcript(7157, CANONICAL)
    assert len(session.requested) == first


def test_network_failure_is_reported_not_raised_raw(service, session):
    session.fail_with = requests.exceptions.ConnectionError("down")
    with pytest.raises(UpstreamError):
        service.search_gene(7157)


def test_ssl_failure_gives_ca_bundle_hint(service, session):
    session.fail_with = requests.exceptions.SSLError("bad cert")
    with pytest.raises(CertificateError) as info:
        service.search_gene(7157)
    assert "--ca-bundle" in info.value.hint


def test_alphafold_outage_keeps_gene_usable(service, session):
    original = session.get

    def flaky(url, **kwargs):
        if "alphafold.ebi.ac.uk/api" in url:
            raise requests.exceptions.ConnectionError("down")
        return original(url, **kwargs)

    session.get = flaky
    result = service.search_gene(7157)
    assert result["summary"]["with_structure"] == 0
    assert result["transcripts"][0]["alphafold"]["status"] == "lookup_failed"
