import json
import unittest
from pathlib import Path

from exonview3d.exon_parser import parse_gene


class TestExonParser(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        path = Path("data/enact_json_test.txt")

        with open(path) as f:
            cls.data = json.load(f)

        cls.result = parse_gene(cls.data)

    def test_gene_information(self):

        self.assertEqual(self.result["gene_id"], 1)
        self.assertIn("A1BG", self.result["gene_name"])

    def test_transcript_count(self):

        self.assertEqual(
            len(self.result["transcripts"]), 1
        )

    def test_protein_length(self):

        transcript = self.result["transcripts"][0]

        self.assertEqual(
            len(transcript["protein_sequence"]), 495
        )

    def test_exon_count(self):

        transcript = self.result["transcripts"][0]

        self.assertEqual(len(transcript["exons"]), 8)

    def test_exon_coordinates(self):

        transcript = self.result["transcripts"][0]

        for exon in transcript["exons"]:

            self.assertEqual(
                exon["end"] - exon["start"] + 1,
                exon["length"]
            )

            self.assertEqual(
                len(exon["sequence"]),
                exon["length"]
            )

    def test_complete_residue_mapping(self):

        transcript = self.result["transcripts"][0]

        mapping = transcript["residue_to_exon"]

        self.assertEqual(len(mapping), 495)

        self.assertEqual(
            sorted(mapping.keys()),
            list(range(1, 496))
        )

    def test_exon_sequence_reconstruction(self):

        transcript = self.result["transcripts"][0]

        reconstructed = "".join(
            exon["sequence"]
            for exon in transcript["exons"]
        )

        self.assertEqual(
            reconstructed,
            transcript["protein_sequence"]
        )


if __name__ == "__main__":
    unittest.main()
