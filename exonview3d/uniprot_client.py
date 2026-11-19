import requests


class UniProtClient:

    BASE_URL = "https://rest.uniprot.org/uniprotkb"

    def __init__(self, ca_bundle=None, timeout=30):

        self.ca_bundle = ca_bundle
        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update({
            "Accept": "text/plain",
            "User-Agent": "ExonView3D/0.1"
        })

        self.sequence_cache = {}

    @staticmethod
    def is_valid_accession(accession):

        if accession is None:
            return False

        return str(accession).strip().lower() not in {
            "", "false", "none", "null"
        }

    def get_sequence(self, accession):

        if not self.is_valid_accession(accession):
            return None

        accession = str(accession).strip()

        if accession in self.sequence_cache:
            return self.sequence_cache[accession]

        url = f"{self.BASE_URL}/{accession}.fasta"

        response = self.session.get(
            url,
            verify=self.ca_bundle if self.ca_bundle else True,
            timeout=self.timeout
        )

        response.raise_for_status()

        sequence = "".join(
            line.strip()
            for line in response.text.splitlines()
            if line.strip() and not line.startswith(">")
        ).upper()

        if not sequence:
            raise ValueError(
                f"Empty UniProt sequence for {accession}"
            )

        self.sequence_cache[accession] = sequence

        return sequence

    @staticmethod
    def compare_sequences(query_sequence, reference_sequence):

        query_sequence = query_sequence.upper()
        reference_sequence = reference_sequence.upper()

        common_length = min(
            len(query_sequence),
            len(reference_sequence)
        )

        matches = 0
        mismatches = []

        for i in range(common_length):

            query_aa = query_sequence[i]
            reference_aa = reference_sequence[i]

            if query_aa == reference_aa:
                matches += 1
            else:
                mismatches.append({
                    "position": i + 1,
                    "query": query_aa,
                    "reference": reference_aa
                })

        length_difference = (
            len(query_sequence) - len(reference_sequence)
        )

        return {
            "query_length": len(query_sequence),
            "reference_length": len(reference_sequence),
            "length_difference": length_difference,
            "identical_positions": matches,
            "mismatches": mismatches,
            "number_of_mismatches": len(mismatches),
            "exact_match": query_sequence == reference_sequence
        }

    def validate_sequence(self, accession, query_sequence):

        if not self.is_valid_accession(accession):

            return {
                "status": "unavailable",
                "accession": None,
                "reference_length": None,
                "exact_match": None,
                "comparison": None
            }

        reference_sequence = self.get_sequence(accession)

        comparison = self.compare_sequences(
            query_sequence,
            reference_sequence
        )

        return {
            "status": (
                "identical"
                if comparison["exact_match"]
                else "different"
            ),
            "accession": accession,
            "reference_length": len(reference_sequence),
            "exact_match": comparison["exact_match"],
            "comparison": comparison
        }
