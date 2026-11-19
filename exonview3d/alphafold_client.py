import json
import requests

from pathlib import Path


class AlphaFoldClient:

    BASE_URL = "https://alphafold.ebi.ac.uk/api/prediction"
    CACHE_DIR = Path("data/alphafold")

    def __init__(self, ca_bundle=None, timeout=60, cache_dir=None):

        self.ca_bundle = ca_bundle
        self.timeout = timeout

        self.cache_dir = Path(
            cache_dir if cache_dir else self.CACHE_DIR
        )

        self.session = requests.Session()

        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "ExonView3D/0.1"
        })

    def _verify_setting(self):

        return self.ca_bundle if self.ca_bundle else True

    def get_predictions(self, accession):

        if not accession or str(accession).lower() in {
            "false", "none", "null", ""
        }:
            raise ValueError("Invalid UniProt accession")

        accession = str(accession).strip()

        url = f"{self.BASE_URL}/{accession}"

        response = self.session.get(
            url,
            verify=self._verify_setting(),
            timeout=self.timeout
        )

        response.raise_for_status()

        records = response.json()

        if not isinstance(records, list):
            raise ValueError(
                "Unexpected AlphaFold DB response format"
            )

        if not records:
            raise ValueError(
                f"No AlphaFold predictions found for {accession}"
            )

        for record in records:

            if not isinstance(record, dict):
                raise ValueError(
                    "Invalid prediction record in AlphaFold response"
                )

            if not record.get("modelEntityId"):
                raise ValueError(
                    "Prediction record missing modelEntityId"
                )

        # Save prediction metadata locally

        accession_dir = self.cache_dir / accession
        accession_dir.mkdir(parents=True, exist_ok=True)

        metadata_file = accession_dir / "metadata.json"

        with open(metadata_file, "w") as handle:

            json.dump(
                records,
                handle,
                indent=4
            )

        return records

    @staticmethod
    def get_canonical_prediction(accession, predictions):

        canonical_model_id = f"AF-{accession}-F1"

        for prediction in predictions:

            if (
                prediction.get("modelEntityId")
                == canonical_model_id
                and prediction.get("uniprotAccession") == accession
            ):
                return prediction

        raise ValueError(
            f"Canonical AlphaFold model not found for {accession}"
        )
    
    @staticmethod
    def find_exact_sequence_match(sequence, predictions):

        if not sequence:
            raise ValueError("Query protein sequence is empty")

        matches = []

        for prediction in predictions:

            prediction_sequence = prediction.get("sequence", "")

            if not prediction_sequence:
                continue

            if sequence == prediction_sequence:

                matches.append(prediction)

        if not matches:
            return None

        # Prefer reviewed predictions.
        matches.sort(
            key=lambda x: (
                not x.get("isUniProtReviewed", False),
                x.get("uniprotAccession", "")
            )
        )

        return matches[0]

    def download_structure(self, prediction, format="cif"):

        format = format.lower()

        if format not in {"cif", "pdb"}:
            raise ValueError(
                "Structure format must be 'cif' or 'pdb'"
            )

        url_key = f"{format}Url"

        structure_url = prediction.get(url_key)

        if not structure_url:
            raise ValueError(
                f"{format.upper()} download URL unavailable"
            )

        model_id = prediction.get("modelEntityId")

        version = prediction.get("latestVersion")

        if not model_id or version is None:
            raise ValueError(
                "Prediction metadata missing model ID or version"
            )

        accession = prediction.get("uniprotAccession")

        if not accession:
            raise ValueError(
                "Prediction metadata missing UniProt accession"
            )

        accession_dir = self.cache_dir / accession
        accession_dir.mkdir(parents=True, exist_ok=True)

        filename = (
            f"{model_id}-model_v{version}.{format}"
        )

        output_file = accession_dir / filename

        # Reuse an existing non-empty structure

        if output_file.is_file() and output_file.stat().st_size > 0:
            return output_file

        response = self.session.get(
            structure_url,
            verify=self._verify_setting(),
            timeout=self.timeout
        )

        response.raise_for_status()

        if not response.content:
            raise ValueError(
                f"Downloaded structure is empty: {structure_url}"
            )

        # Write atomically to avoid incomplete cache files

        temporary_file = output_file.with_suffix(
            output_file.suffix + ".tmp"
        )

        try:

            with open(temporary_file, "wb") as handle:
                handle.write(response.content)

            temporary_file.replace(output_file)

        finally:

            if temporary_file.exists():
                temporary_file.unlink()

        return output_file

    def get_canonical_structure(
        self,
        accession,
        format="cif"
    ):

        predictions = self.get_predictions(accession)

        prediction = self.get_canonical_prediction(
            accession,
            predictions
        )

        structure_file = self.download_structure(
            prediction,
            format=format
        )

        return {
            "accession": accession,
            "prediction": prediction,
            "structure_file": str(structure_file),
            "format": format
        }
