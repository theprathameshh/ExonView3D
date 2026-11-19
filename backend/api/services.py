import json
from pathlib import Path

from django.conf import settings


PROJECT_ROOT = Path(settings.BASE_DIR).parent

EXON_PALETTE = [
    "#377eb8",
    "#e41a1c",
    "#4daf4a",
    "#ff7f00",
    "#984ea3",
    "#00a6a6",
    "#f781bf",
    "#a65628",
    "#999999",
    "#dede00",
]


def load_gene_data(gene_id):
    """
    Load previously generated ExonView3D gene results.
    """

    result_file = PROJECT_ROOT / "results" / f"gene_{gene_id}.json"

    if not result_file.is_file():
        raise FileNotFoundError(
            f"No results found for gene {gene_id}"
        )

    with result_file.open() as handle:
        return json.load(handle)


def get_transcript_data(gene_id, transcript_id):
    """
    Retrieve a specific transcript from gene results.
    """

    gene_data = load_gene_data(gene_id)

    for transcript in gene_data["transcripts"]:
        if transcript["transcript_id"] == transcript_id:
            return gene_data, transcript

    raise LookupError(
        f"Transcript {transcript_id} not found in gene {gene_id}"
    )


def build_structure_data(gene_data, transcript):
    """
    Prepare transcript and exon annotations for Mol*.
    """

    af = transcript.get("alphafold", {})

    if af.get("status") != "success":
        raise ValueError(
            "No successful AlphaFold mapping for this transcript."
        )

    structure_path = Path(af["structure_file"])

    if not structure_path.is_absolute():
        structure_path = PROJECT_ROOT / structure_path

    if not structure_path.is_file():
        raise FileNotFoundError(
            f"Structure file not found: {structure_path}"
        )

    exon_colours = {}

    exons = []

    for index, exon in enumerate(af["exon_structure_summary"]):

        colour = EXON_PALETTE[index % len(EXON_PALETTE)]

        exon_colours[exon["exon_id"]] = colour

        exons.append({
            "exon_id": exon["exon_id"],
            "protein_start": exon["protein_start"],
            "protein_end": exon["protein_end"],
            "protein_length": exon["protein_length"],
            "sequence": exon["protein_sequence"],
            "genomic_coordinates": exon["genomic_coordinates"],
            "mapped_residues": exon["mapped_residues"],
            "unmapped_residues": exon["unmapped_residues"],
            "coverage_percent": exon["coverage_percent"],
            "colour": colour,
            "structure_residue_segments": exon[
                "structure_residue_segments"
            ],
        })

    residue_mapping = [
        residue
        for residue in af["residue_mapping"]
        if residue.get("exon_id") is not None
    ]

    return {
        "gene": {
            "gene_id": gene_data["gene_id"],
            "gene_name": gene_data["gene_name"],
            "organism": gene_data["organism"],
        },
        "transcript": {
            "transcript_id": transcript["transcript_id"],
            "uniprot_id": transcript["uniprot_id"],
            "protein_length": transcript["protein_length"],
            "protein_sequence": transcript["protein_sequence"],
        },
        "structure": {
            "model_id": af["model_id"],
            "accession": af["accession"],
            "format": af["structure_format"],
            "chain_id": af["chain_id"],
            "sequence_identity_percent": af[
                "sequence_identity_percent"
            ],
            "sequence_coverage_percent": af[
                "sequence_coverage_percent"
            ],
        },
        "exons": exons,
        "residue_mapping": residue_mapping,
    }
