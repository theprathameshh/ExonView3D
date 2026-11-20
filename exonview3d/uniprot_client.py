import re

from ._http import HttpClient
from .errors import UpstreamError

ACCESSION_PATTERN = re.compile(r"^[A-Za-z0-9]{6,10}(-[0-9]+)?$")


class UniProtClient:
    """Retrieves UniProt reference sequences for validation."""

    BASE_URL = "https://rest.uniprot.org/uniprotkb"

    def __init__(self, ca_bundle=None, timeout=30, session=None):

        self.http = HttpClient(
            "UniProt",
            ca_bundle=ca_bundle,
            timeout=timeout,
            session=session,
            accept="text/plain",
        )

        self.cache = {}

    @staticmethod
    def is_valid_accession(accession):

        if accession is None:
            return False

        text = str(accession).strip()

        if text.lower() in {"", "false", "none", "null"}:
            return False

        return bool(ACCESSION_PATTERN.match(text))

    @staticmethod
    def parse_fasta(text):
        """Return (header, sequence) from FASTA text."""

        header = ""
        sequence = []

        for line in text.splitlines():

            line = line.strip()

            if not line:
                continue

            if line.startswith(">"):
                if not header:
                    header = line[1:]
                continue

            sequence.append(line)

        return header, "".join(sequence).upper()

    @staticmethod
    def protein_name(header):
        """Extract the protein name from a UniProt FASTA header."""

        if not header:
            return None

        parts = header.split(" ", 1)

        if len(parts) < 2:
            return None

        name = parts[1].split(" OS=")[0].strip()

        return name or None

    def get_record(self, accession):
        """Return {'accession', 'sequence', 'protein_name'} or None."""

        if not self.is_valid_accession(accession):
            return None

        accession = str(accession).strip()

        if accession in self.cache:
            return self.cache[accession]

        response = self.http.get(
            f"{self.BASE_URL}/{accession}.fasta",
            allow_404=True,
        )

        if response is None:
            self.cache[accession] = None
            return None

        header, sequence = self.parse_fasta(response.text)

        if not sequence:
            raise UpstreamError(
                f"UniProt returned an empty sequence for {accession}."
            )

        record = {
            "accession": accession,
            "sequence": sequence,
            "protein_name": self.protein_name(header),
        }

        self.cache[accession] = record

        return record

    @staticmethod
    def compare_sequences(query_sequence, reference_sequence):

        query_sequence = query_sequence.upper()
        reference_sequence = reference_sequence.upper()

        common_length = min(len(query_sequence), len(reference_sequence))

        mismatches = [
            {
                "position": i + 1,
                "query": query_sequence[i],
                "reference": reference_sequence[i],
            }
            for i in range(common_length)
            if query_sequence[i] != reference_sequence[i]
        ]

        return {
            "query_length": len(query_sequence),
            "reference_length": len(reference_sequence),
            "length_difference": len(query_sequence) - len(reference_sequence),
            "identical_positions": common_length - len(mismatches),
            "mismatches": mismatches,
            "number_of_mismatches": len(mismatches),
            "exact_match": query_sequence == reference_sequence,
        }

    def validate_sequence(self, accession, query_sequence):
        """Compare a transcript protein with the UniProt sequence."""

        record = self.get_record(accession)

        if record is None:
            return {
                "status": "unavailable",
                "accession": accession,
                "reference_length": None,
                "exact_match": None,
                "protein_name": None,
            }

        comparison = self.compare_sequences(
            query_sequence, record["sequence"]
        )

        return {
            "status": "identical" if comparison["exact_match"] else "different",
            "accession": record["accession"],
            "reference_length": comparison["reference_length"],
            "exact_match": comparison["exact_match"],
            "number_of_mismatches": comparison["number_of_mismatches"],
            "length_difference": comparison["length_difference"],
            "protein_name": record["protein_name"],
        }
