from Bio.Align import PairwiseAligner


class ResidueMapper:

    def __init__(
        self,
        match_score=2.0,
        mismatch_score=-1.0,
        open_gap_score=-10.0,
        extend_gap_score=-0.5
    ):

        self.match_score = match_score

        self.aligner = PairwiseAligner()

        self.aligner.mode = "global"

        self.aligner.match_score = match_score
        self.aligner.mismatch_score = mismatch_score

        self.aligner.open_gap_score = open_gap_score
        self.aligner.extend_gap_score = extend_gap_score

    @staticmethod
    def compare_sequences(reference_sequence, structure_sequence):

        reference_sequence = reference_sequence.upper()
        structure_sequence = structure_sequence.upper()

        common_length = min(
            len(reference_sequence),
            len(structure_sequence)
        )

        identical_positions = sum(
            a == b
            for a, b in zip(
                reference_sequence,
                structure_sequence
            )
        )

        return {
            "reference_length": len(reference_sequence),
            "structure_length": len(structure_sequence),
            "identical_positions": identical_positions,
            "exact_match": (
                reference_sequence == structure_sequence
            ),
            "length_difference": (
                len(structure_sequence) - len(reference_sequence)
            ),
            "identity_percent": (
                100.0 * identical_positions / common_length
                if common_length else 0.0
            )
        }

    def map_sequence_to_chain(
        self,
        protein_sequence,
        chain_data,
        force_alignment=False
    ):

        protein_sequence = protein_sequence.upper()

        structure_sequence = chain_data["sequence"]

        residues = chain_data["residues"]

        if len(structure_sequence) != len(residues):
            raise ValueError(
                "Structure sequence and residue records have "
                "different lengths"
            )

        if not protein_sequence:
            raise ValueError("Empty protein sequence")

        mapping = [None] * len(protein_sequence)

        if structure_sequence == protein_sequence and not force_alignment:

            # Identical sequences: residues map one-to-one, so the
            # alignment step can be skipped.
            alignment_score = self.match_score * len(protein_sequence)
            aligned_structure = [(0, len(protein_sequence))]
            aligned_protein = [(0, len(protein_sequence))]

        else:

            alignment = self.aligner.align(
                structure_sequence,
                protein_sequence
            )[0]

            alignment_score = float(alignment.score)
            aligned_structure, aligned_protein = alignment.aligned

        identical_positions = 0
        mismatches = []

        for structure_block, protein_block in zip(
            aligned_structure,
            aligned_protein
        ):

            structure_start, structure_end = structure_block
            protein_start, protein_end = protein_block

            block_length = structure_end - structure_start

            if block_length != protein_end - protein_start:
                raise RuntimeError(
                    "Unexpected alignment block dimensions"
                )

            for offset in range(block_length):

                structure_index = structure_start + offset
                protein_index = protein_start + offset

                structure_residue = residues[structure_index]

                protein_aa = protein_sequence[protein_index]

                structure_aa = structure_sequence[structure_index]

                exact_match = protein_aa == structure_aa

                if exact_match:
                    identical_positions += 1

                else:
                    mismatches.append({
                        "protein_position": int(protein_index + 1),
                        "protein_amino_acid": protein_aa,
                        "structure_amino_acid": structure_aa
                    })

                mapping[protein_index] = {
                    "protein_position": int(protein_index + 1),
                    "amino_acid": protein_aa,
                    "chain_id": structure_residue["chain_id"],
                    "structure_residue_number": (
                        structure_residue["residue_number"]
                    ),
                    "insertion_code": (
                        structure_residue["insertion_code"]
                    ),
                    "structure_amino_acid": structure_aa,
                    "exact_match": exact_match
                }

        mapped_positions = sum(
            item is not None
            for item in mapping
        )

        unmapped_positions = [
            i + 1
            for i, item in enumerate(mapping)
            if item is None
        ]

        return {
            "chain_id": chain_data["chain_id"],
            "protein_length": len(protein_sequence),
            "structure_length": len(structure_sequence),
            "alignment_score": float(alignment_score),
            "mapped_positions": mapped_positions,
            "unmapped_positions": unmapped_positions,
            "identical_positions": identical_positions,
            "mismatches": mismatches,
            "identity_percent": (
                100.0 * identical_positions / mapped_positions
                if mapped_positions else 0.0
            ),
            "sequence_coverage_percent": (
                100.0 * mapped_positions / len(protein_sequence)
            ),
            "mapping": mapping
        }
