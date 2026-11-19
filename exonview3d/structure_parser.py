from pathlib import Path

from Bio.PDB import MMCIFParser
from Bio.SeqUtils import seq1


class StructureParser:

    def __init__(self):

        self.parser = MMCIFParser(
            QUIET=True,
            auth_chains=True,
            auth_residues=True
        )

    @staticmethod
    def residue_to_one_letter(residue_name):

        return seq1(
            residue_name,
            custom_map={
                "MSE": "M",
                "UNK": "X"
            }
        )

    def extract_structure(self, cif_file):

        cif_file = Path(cif_file)

        if not cif_file.is_file():
            raise FileNotFoundError(
                f"Structure file not found: {cif_file}"
            )

        structure = self.parser.get_structure(
            cif_file.stem,
            str(cif_file)
        )

        model = next(structure.get_models())

        chains = {}

        for chain in model:

            residues = []
            sequence = []

            for residue in chain:

                # Ignore water and other non-polymer residues.
                if residue.id[0] != " ":
                    continue

                residue_name = residue.resname.strip().upper()

                amino_acid = self.residue_to_one_letter(
                    residue_name
                )

                if not amino_acid:
                    continue

                residue_number = residue.id[1]
                insertion_code = residue.id[2].strip()

                residues.append({
                    "chain_id": chain.id,
                    "residue_number": residue_number,
                    "insertion_code": insertion_code,
                    "residue_name": residue_name,
                    "amino_acid": amino_acid
                })

                sequence.append(amino_acid)

            if residues:

                chains[chain.id] = {
                    "chain_id": chain.id,
                    "sequence": "".join(sequence),
                    "sequence_length": len(sequence),
                    "residues": residues
                }

        if not chains:
            raise ValueError(
                f"No amino acid residues found in {cif_file}"
            )

        return {
            "structure_file": str(cif_file),
            "chains": chains
        }

    def get_chain_sequences(self, cif_file):

        structure_data = self.extract_structure(cif_file)

        return {
            chain_id: data["sequence"]
            for chain_id, data
            in structure_data["chains"].items()
        }
