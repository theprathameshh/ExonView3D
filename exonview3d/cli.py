import argparse
import json
import requests

from pathlib import Path

from .enact_client import EnactClient
from .exon_parser import parse_gene
from .uniprot_client import UniProtClient
from .alphafold_client import AlphaFoldClient
from .structure_parser import StructureParser
from .residue_mapper import ResidueMapper
from .exon_structure_mapper import ExonStructureMapper

def attach_alphafold_structure(
    transcript,
    predictions,
    alphafold_client,
    structure_parser,
    residue_mapper
):
    """
    Identify an exact AlphaFold sequence match, retrieve its
    structure, and map transcript exons to structure residues.

    """

    protein_sequence = transcript["protein_sequence"]

    # Find an exact sequence match among AlphaFold predictions.
    prediction = alphafold_client.find_exact_sequence_match(
        protein_sequence,
        predictions
    )

    if prediction is None:

        return {
            "status": "skipped",
            "reason": "no_exact_alphafold_sequence_match"
        }

    accession = prediction["uniprotAccession"]

    # Download the matched isoform structure.
    try:

        structure_file = alphafold_client.download_structure(
            prediction,
            format="cif"
        )

        # Parse the matched AlphaFold isoform structure.
        structure_data = structure_parser.extract_structure(
            structure_file
        )

        # Parse the matched AlphaFold isoform structure.
        structure_data = structure_parser.extract_structure(
            structure_file
        )

        # Attempt mapping against every available chain.
        chain_results = []

        for chain_id, chain_data in structure_data["chains"].items():

            mapping = residue_mapper.map_sequence_to_chain(
                protein_sequence,
                chain_data
            )

            chain_results.append(mapping)

        if not chain_results:

            raise ValueError(
                "No suitable structure chains found"
            )

        # Select the chain with the best coverage and identity.
        best_mapping = max(
            chain_results,
            key=lambda x: (
                x["sequence_coverage_percent"],
                x["identity_percent"]
            )
        )

        # Initially accept only exact, full-length matches.
        if (
            best_mapping["sequence_coverage_percent"] != 100.0
            or best_mapping["identity_percent"] != 100.0
        ):

            return {
                "status": "sequence_mismatch",
                "accession": accession,
                "model_id": prediction["modelEntityId"],
                "model_version": prediction["latestVersion"],
                "chain_id": best_mapping["chain_id"],
                "sequence_identity_percent": (
                    best_mapping["identity_percent"]
                ),
                "sequence_coverage_percent": (
                    best_mapping["sequence_coverage_percent"]
                ),
                "mapped_positions": (
                    best_mapping["mapped_positions"]
                )
            }

        # Connect each protein residue to its ENACTdb exon.
        residue_to_exon = transcript["residue_to_exon"]

        for residue in best_mapping["mapping"]:

            protein_position = residue["protein_position"]

            residue["exon_id"] = residue_to_exon.get(
                protein_position
            )
            
        exon_structure_summary = ExonStructureMapper.map_exons(
            transcript["exons"],
            best_mapping["mapping"]
        )

        return {
            "status": "success",
            "accession": accession,
            "model_id": prediction["modelEntityId"],
            "model_version": prediction["latestVersion"],
            "structure_file": str(structure_file),
            "structure_format": "cif",
            "chain_id": best_mapping["chain_id"],
            "sequence_identity_percent": (
                best_mapping["identity_percent"]
            ),
            "sequence_coverage_percent": (
                best_mapping["sequence_coverage_percent"]
            ),
            "mapped_positions": (
                best_mapping["mapped_positions"]
            ),
            "unmapped_positions": (
                best_mapping["unmapped_positions"]
            ),
            "mismatches": best_mapping["mismatches"],
            "residue_mapping": best_mapping["mapping"],
            "exon_structure_summary": exon_structure_summary,
        }

    except (
        requests.RequestException,
        ValueError,
        FileNotFoundError,
        OSError
    ) as error:

        return {
            "status": "error",
            "accession": accession,
            "error": str(error)
        }


def main():

    parser = argparse.ArgumentParser(
        description="ExonView3D: Gene-to-exon information retrieval"
    )

    parser.add_argument(
        "gene_id",
        type=int,
        help="NCBI Gene ID"
    )

    parser.add_argument(
        "--ca-bundle",
        default="data/certificates/combined-ca.pem"
    )

    parser.add_argument(
        "--output",
        default="results"
    )

    parser.add_argument(
        "--skip-uniprot-validation",
        action="store_true",
        help="Skip UniProt reference sequence validation"
    )

    parser.add_argument(
        "--alphafold",
        action="store_true",
        help="Retrieve AlphaFold structures and map protein residues"
    )

    args = parser.parse_args()

    ca_bundle = Path(args.ca_bundle)

    if not ca_bundle.is_file():
        raise FileNotFoundError(
            f"CA certificate bundle not found: {ca_bundle}"
        )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Retrieving NCBI Gene ID: {args.gene_id}")

    # Step 1: Retrieve ENACTdb data.

    enact_client = EnactClient(
        ca_bundle=str(ca_bundle)
    )

    gene_data = enact_client.get_gene(args.gene_id)

    print("ENACTdb response received.")

    # Step 2: Parse transcripts and reconstruct protein sequences.

    parsed_data = parse_gene(gene_data)

    print("Exon parsing and protein reconstruction completed.")

    # Step 3: UniProt reference validation.

    if args.skip_uniprot_validation:

        print("UniProt validation skipped.")

        for transcript in parsed_data["transcripts"]:

            transcript["reference_validation"] = {
                "status": "skipped",
                "accession": None,
                "reference_length": None,
                "exact_match": None,
                "comparison": None
            }

    else:

        uniprot_client = UniProtClient(
            ca_bundle=str(ca_bundle)
        )

        print("\nPerforming UniProt reference validation...")

        for transcript in parsed_data["transcripts"]:

            accession = transcript.get("uniprot_id")

            try:

                validation = uniprot_client.validate_sequence(
                    accession,
                    transcript["protein_sequence"]
                )

            except (requests.RequestException, ValueError) as error:

                validation = {
                    "status": "error",
                    "accession": accession,
                    "reference_length": None,
                    "exact_match": None,
                    "comparison": None,
                    "error": str(error)
                }

            transcript["reference_validation"] = validation

            print(
                f"{transcript['transcript_id']:22s} "
                f"UniProt={str(accession):10s} "
                f"Status={validation['status']}"
            )

    # Step 4: AlphaFold structure retrieval and residue mapping.

    if args.alphafold:

        print("\nPerforming AlphaFold structure retrieval...")

        alphafold_client = AlphaFoldClient(
            ca_bundle=str(ca_bundle)
        )

        structure_parser = StructureParser()
        residue_mapper = ResidueMapper()

        # Identify an available UniProt accession to retrieve
        # the complete set of AlphaFold predictions for this gene.
        seed_accession = next(
            (
                transcript.get("uniprot_id")
                for transcript in parsed_data["transcripts"]
                if transcript.get("uniprot_id")
            ),
            None
        )

        if seed_accession is None:

            print(
                "No UniProt accession available. "
                "AlphaFold retrieval skipped."
            )

        else:

            try:

                predictions = alphafold_client.get_predictions(
                    seed_accession
                )

                print(
                    f"Retrieved {len(predictions)} AlphaFold "
                    f"predictions using {seed_accession}."
                )

                for transcript in parsed_data["transcripts"]:

                    result = attach_alphafold_structure(
                        transcript,
                        predictions,
                        alphafold_client,
                        structure_parser,
                        residue_mapper
                    )

                    transcript["alphafold"] = result

                    print(
                        f"{transcript['transcript_id']:22s} "
                        f"AlphaFold={result['status']}"
                    )

            except (
                requests.RequestException,
                ValueError
            ) as error:

                print(f"AlphaFold prediction retrieval failed: {error}")

                for transcript in parsed_data["transcripts"]:

                    transcript["alphafold"] = {
                        "status": "error",
                        "error": str(error)
                    }

    # Step 5: Save output.

    output_file = output_dir / f"gene_{args.gene_id}.json"

    with open(output_file, "w") as f:

        json.dump(
            parsed_data,
            f,
            indent=4
        )

    # Step 6: Display summary.

    print("\nProcessing complete.")

    print("Gene:", parsed_data["gene_name"])
    print("Organism:", parsed_data["organism"])

    for transcript in parsed_data["transcripts"]:

        print("\nTranscript:", transcript["transcript_id"])
        print("UniProt:", transcript["uniprot_id"])
        print("Protein length:", transcript["protein_length"])
        print("Number of exons:", len(transcript["exons"]))

        if "reference_validation" in transcript:

            print(
                "Reference validation:",
                transcript["reference_validation"]["status"]
            )

        if "alphafold" in transcript:

            print(
                "AlphaFold:",
                transcript["alphafold"]["status"]
            )

            if transcript["alphafold"]["status"] == "success":

                print(
                    "Mapped residues:",
                    transcript["alphafold"]["mapped_positions"]
                )

    print("\nOutput:", output_file)


if __name__ == "__main__":
    main()

