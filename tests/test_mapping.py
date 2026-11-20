from exonview3d.residue_mapper import ResidueMapper


def chain(sequence):
    return {
        "chain_id": "A",
        "sequence": sequence,
        "sequence_length": len(sequence),
        "residues": [
            {"chain_id": "A", "residue_number": i + 1, "insertion_code": "",
             "residue_name": "X", "amino_acid": aa}
            for i, aa in enumerate(sequence)
        ],
    }


def test_fast_path_matches_alignment():
    mapper = ResidueMapper()
    sequence = "MEEPQSDPSVEPPLSQETFSDLWKL"
    fast = mapper.map_sequence_to_chain(sequence, chain(sequence))
    slow = mapper.map_sequence_to_chain(sequence, chain(sequence), force_alignment=True)
    assert fast["mapping"] == slow["mapping"]
    assert fast["sequence_coverage_percent"] == 100.0
    assert fast["identity_percent"] == 100.0


def test_partial_structure_reports_unmapped_residues():
    mapper = ResidueMapper()
    result = mapper.map_sequence_to_chain("AAAACCCCGGGG", chain("AAAAGGGG"))
    assert result["sequence_coverage_percent"] < 100.0
    assert result["unmapped_positions"]
