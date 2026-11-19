def parse_transcript(gene_data, transcript):

    transcript_id = transcript["tId"]
    internal_id = str(transcript["id"])
    protein_length = int(transcript["length"])

    exon_records = {
        exon["exId"]: exon
        for exon in gene_data["exonsGenes"]
    }

    regions = transcript.get("exonsRegion")

    if not regions:
        raise ValueError(
            f"No exon-region information for {transcript_id}"
        )

    exon_regions = []
    protein_exons = []
    residue_to_exon = {}

    for region in regions.split("_"):

        exon_id, coordinates = region.split("$", 1)

        fields = list(map(int, coordinates.split(",")))

        if len(fields) not in (3, 5):
            raise ValueError(
                f"Unexpected coordinate format: {region}"
            )

        start, end, flag = fields[:3]

        if start < 1 or end < start:
            raise ValueError(
                f"Invalid protein coordinates: {region}"
            )

        if exon_id not in exon_records:
            raise ValueError(
                f"Exon record missing: {exon_id}"
            )

        record = exon_records[exon_id]

        sequence = record.get("aaseq") or ""

        coordinate_length = end - start + 1
        sequence_length = len(sequence)

        # Preserve all exon-region information.
        exon_info = {
            "exon_id": exon_id,
            "prefix": exon_id.split(".")[0],
            "start": start,
            "end": end,
            "flag": flag,
            "coordinate_fields": fields,
            "additional_coordinates": fields[3:],
            "sequence": sequence,
            "length": sequence_length,
            "protein_coordinate_length": coordinate_length,
            "genomic_coordinates": {
                "raw_start": record.get("rawst"),
                "raw_end": record.get("rawend"),
                "coding_start": record.get("codst"),
                "coding_end": record.get("codend")
            }
        }

        # Empty sequences are retained as region metadata.
        if sequence_length == 0:

            exon_info["classification"] = "zero_length"

            exon_regions.append(exon_info)
            continue

        # Every sequence-bearing region must match its
        # corresponding protein-coordinate span.
        if sequence_length != coordinate_length:
            raise ValueError(
                f"Sequence-coordinate mismatch for {exon_id}: "
                f"sequence={sequence_length}, "
                f"coordinates={coordinate_length}"
            )

        exon_info["classification"] = "protein_coding"

        exon_regions.append(exon_info)
        protein_exons.append(exon_info)

    # Sort protein-bearing segments by amino-acid coordinates.
    protein_exons.sort(key=lambda x: x["start"])

    # Validate overlaps and construct residue mapping.
    for exon in protein_exons:

        for position in range(exon["start"], exon["end"] + 1):

            if position in residue_to_exon:
                raise ValueError(
                    f"Overlapping exon coordinates at residue {position}"
                )

            residue_to_exon[position] = exon["exon_id"]

    # Validate complete protein coverage.
    expected_positions = set(
        range(1, protein_length + 1)
    )

    observed_positions = set(residue_to_exon)

    missing = sorted(expected_positions - observed_positions)
    extra = sorted(observed_positions - expected_positions)

    if missing or extra:
        raise ValueError(
            f"Incomplete protein coverage for {transcript_id}. "
            f"Missing={missing}, Extra={extra}"
        )

    # Reconstruct the protein sequence.
    protein_sequence = "".join(
        exon["sequence"] for exon in protein_exons
    )

    if len(protein_sequence) != protein_length:
        raise ValueError(
            f"Reconstructed protein length mismatch for {transcript_id}: "
            f"{len(protein_sequence)} != {protein_length}"
        )

    return {
        "transcript_id": transcript_id,
        "internal_transcript_id": internal_id,
        "uniprot_id": (transcript.get("swissprot") if transcript.get("swissprot") not in (False, None, "") else None),
        "protein_length": protein_length,
        "protein_sequence": protein_sequence,

        # All ENACTdb exon-region entries.
        "exon_regions": exon_regions,

        # Only sequence-bearing protein segments.
        "exons": protein_exons,

        "number_of_exon_regions": len(exon_regions),
        "number_of_protein_exons": len(protein_exons),

        "residue_to_exon": residue_to_exon
    }


def parse_gene(gene_data):

    parsed_transcripts = []

    for transcript in gene_data["trans"]:

        parsed = parse_transcript(
            gene_data,
            transcript
        )

        parsed_transcripts.append(parsed)

    return {
        "gene_name": gene_data["name"],
        "gene_id": gene_data["entrezid"],
        "organism": gene_data["organism"],
        "transcripts": parsed_transcripts
    }
