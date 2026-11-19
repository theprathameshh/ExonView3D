from pathlib import Path
import json


class StructureAnnotator:
    """
    Generate PyMOL scripts for exon-specific
    colouring of AlphaFold structures.
    """

    # Qualitative colour palette.
    PALETTE = [
        "tv_blue",
        "tv_red",
        "tv_green",
        "tv_orange",
        "tv_purple",
        "tv_cyan",
        "tv_magenta",
        "tv_yellow",
        "salmon",
        "slate",
        "lime",
        "violet",
        "teal",
        "wheat",
        "deepblue",
    ]

    @classmethod
    def generate_pymol_script(
        cls,
        transcript,
        output_directory
    ):

        af = transcript.get("alphafold", {})

        if af.get("status") != "success":
            raise ValueError(
                "Transcript does not have a successful "
                "AlphaFold mapping."
            )

        structure_file = Path(af["structure_file"]).resolve()

        if not structure_file.is_file():
            raise FileNotFoundError(
                f"Structure file not found: {structure_file}"
            )

        output_directory = Path(output_directory)
        output_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        transcript_id = transcript["transcript_id"]

        script_file = (
            output_directory /
            f"{transcript_id}.pml"
        )

        session_file = (
            output_directory /
            f"{transcript_id}.pse"
        )

        chain_id = af["chain_id"]

        residue_mapping = af["residue_mapping"]

        exon_ids = list(dict.fromkeys(
            residue["exon_id"]
            for residue in residue_mapping
            if residue.get("exon_id") is not None
        ))

        if not exon_ids:
            raise ValueError(
                "No exon identifiers found in residue mapping."
            )

        lines = []

        lines.append("reinitialize")
        lines.append(
            f'load "{structure_file}", alphafold'
        )

        lines.append("hide everything")
        lines.append("show cartoon, alphafold")
        lines.append("color gray80, alphafold")

        lines.append("bg_color white")
        lines.append("set cartoon_fancy_helices, 1")
        lines.append("set ray_opaque_background, 1")

        lines.append("")

        lines.append("# Exon-specific colouring")

        exon_colours = {}

        for index, exon_id in enumerate(exon_ids):

            colour = cls.PALETTE[
                index % len(cls.PALETTE)
            ]

            exon_colours[exon_id] = colour

            residues = [
                residue
                for residue in residue_mapping
                if residue.get("exon_id") == exon_id
            ]

            selections = []

            for residue in residues:

                number = residue["structure_residue_number"]

                insertion = residue.get(
                    "insertion_code", ""
                )

                if insertion:
                    selections.append(
                        f"resi {number}{insertion}"
                    )
                else:
                    selections.append(
                        f"resi {number}"
                    )

            selection = (
                f"chain {chain_id} and ("
                + " or ".join(selections)
                + ")"
            )

            lines.append(
                f"color {colour}, alphafold and ({selection})"
            )

        lines.append("")

        lines.append("# Exon boundary markers")

        for exon in af["exon_structure_summary"]:

            start = exon["protein_start"]
            end = exon["protein_end"]

            selection = (
                f"alphafold and chain {chain_id} "
                f"and resi {start}+{end}"
            )

            lines.append(
                f"show spheres, ({selection}) and name CA"
            )

            lines.append(
                f"set sphere_scale, 0.35, ({selection})"
            )

        lines.append("")

        lines.append("# Structure appearance")

        lines.append("orient alphafold")
        lines.append("zoom alphafold")
        lines.append("set antialias, 2")

        lines.append("")

        lines.append("# Save PyMOL session")

        lines.append(
            f'save "{session_file.resolve()}"'
        )

        script_file.write_text(
            "\n".join(lines) + "\n"
        )

        colour_file = (
            output_directory /
            "exon_colours.json"
        )

        colour_file.write_text(
            json.dumps(
                exon_colours,
                indent=4
            )
        )

        return {
            "script_file": str(script_file),
            "session_file": str(session_file),
            "colour_file": str(colour_file),
            "number_of_exons": len(exon_ids)
        }
