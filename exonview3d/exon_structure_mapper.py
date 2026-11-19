class ExonStructureMapper:
    """
    Maps ENACTdb protein-coding exons onto AlphaFold
    structure residues.
    """

    @staticmethod
    def map_exons(exons, residue_mapping):

        # Index residue mappings by exon.
        exon_residues = {}

        for residue in residue_mapping:

            exon_id = residue.get("exon_id")

            if exon_id is None:
                continue

            exon_residues.setdefault(exon_id, []).append(residue)

        exon_summaries = []

        for exon in exons:

            exon_id = exon["exon_id"]

            residues = exon_residues.get(exon_id, [])

            residues.sort(
                key=lambda x: x["protein_position"]
            )

            expected_length = exon["length"]
            mapped_count = len(residues)

            # Identify unmapped protein positions.
            mapped_positions = {
                residue["protein_position"]
                for residue in residues
            }

            expected_positions = set(
                range(exon["start"], exon["end"] + 1)
            )

            unmapped_positions = sorted(
                expected_positions - mapped_positions
            )

            # Group consecutive structure residues.
            segments = []

            for residue in residues:

                number = residue["structure_residue_number"]
                insertion = residue["insertion_code"]
                chain = residue["chain_id"]

                if segments:

                    previous = segments[-1]

                    contiguous = (
                        previous["chain_id"] == chain
                        and previous["end_insertion_code"] == ""
                        and insertion == ""
                        and number == previous["end"] + 1
                    )

                    if contiguous:

                        previous["end"] = number

                        previous["protein_end"] = (
                            residue["protein_position"]
                        )

                        continue

                segments.append({
                    "chain_id": chain,
                    "start": number,
                    "end": number,
                    "start_insertion_code": insertion,
                    "end_insertion_code": insertion,
                    "protein_start": residue["protein_position"],
                    "protein_end": residue["protein_position"]
                })

            exon_summaries.append({

                "exon_id": exon_id,

                "protein_start": exon["start"],
                "protein_end": exon["end"],

                "protein_length": expected_length,
                "protein_sequence": exon["sequence"],

                "genomic_coordinates": (
                    exon["genomic_coordinates"]
                ),

                "mapped_residues": mapped_count,

                "unmapped_residues": len(unmapped_positions),

                "unmapped_positions": unmapped_positions,

                "coverage_percent": (
                    100.0 * mapped_count / expected_length
                    if expected_length else 0.0
                ),

                "structure_residue_segments": segments
            })

        return exon_summaries
