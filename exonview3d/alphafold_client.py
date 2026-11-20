import json
from pathlib import Path

from ._http import HttpClient
from .errors import DataError, UpstreamError

ACCESSION_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")


class AlphaFoldClient:
    """Retrieves predictions and structure files from AlphaFold DB."""

    BASE_URL = "https://alphafold.ebi.ac.uk/api/prediction"

    def __init__(self, cache_dir, ca_bundle=None, timeout=60, session=None):

        self.cache_dir = Path(cache_dir)

        self.http = HttpClient(
            "AlphaFold DB",
            ca_bundle=ca_bundle,
            timeout=timeout,
            session=session,
        )

    @staticmethod
    def base_accession(accession):
        """P04637-2 -> P04637."""

        return str(accession).strip().split("-")[0]

    @staticmethod
    def _safe_accession(accession):

        text = str(accession).strip().upper()

        if not text or not set(text) <= ACCESSION_CHARS:
            raise DataError(f"Invalid UniProt accession: {accession!r}")

        return text

    def _metadata_file(self, accession):
        return self.cache_dir / accession / "metadata.json"

    def get_predictions(self, accession):
        """Return all AlphaFold DB predictions for a UniProt accession.

        Returns an empty list when AlphaFold DB has no entry. If the service
        cannot be reached, previously cached metadata is used when present.
        """

        accession = self._safe_accession(self.base_accession(accession))

        try:
            response = self.http.get(
                f"{self.BASE_URL}/{accession}",
                allow_404=True,
            )

        except UpstreamError:

            cached = self._metadata_file(accession)

            if cached.is_file():
                with open(cached) as handle:
                    return json.load(handle)

            raise

        if response is None:
            return []

        try:
            records = response.json()
        except ValueError as error:
            raise UpstreamError(
                "AlphaFold DB returned malformed JSON."
            ) from error

        if not isinstance(records, list):
            raise DataError("Unexpected AlphaFold DB response format.")

        records = [
            record for record in records
            if isinstance(record, dict) and record.get("modelEntityId")
        ]

        if records:
            metadata_file = self._metadata_file(accession)
            metadata_file.parent.mkdir(parents=True, exist_ok=True)

            with open(metadata_file, "w") as handle:
                json.dump(records, handle)

        return records

    @staticmethod
    def find_exact_sequence_match(sequence, predictions):
        """Return the prediction whose sequence equals `sequence`, or None."""

        if not sequence:
            return None

        matches = [
            prediction for prediction in predictions
            if prediction.get("sequence") == sequence
        ]

        if not matches:
            return None

        # Prefer reviewed entries, then a stable order by accession.
        matches.sort(
            key=lambda item: (
                not item.get("isUniProtReviewed", False),
                item.get("uniprotAccession", ""),
            )
        )

        return matches[0]

    def download_structure(self, prediction, fmt="cif"):
        """Download (or reuse) a structure file; returns its path."""

        fmt = fmt.lower()

        if fmt not in {"cif", "pdb"}:
            raise ValueError("Structure format must be 'cif' or 'pdb'")

        url = prediction.get(f"{fmt}Url")
        model_id = prediction.get("modelEntityId")
        version = prediction.get("latestVersion")
        accession = prediction.get("uniprotAccession")

        if not url or not model_id or version is None or not accession:
            raise DataError(
                f"AlphaFold DB metadata is incomplete for a {fmt.upper()} "
                "download."
            )

        accession = self._safe_accession(accession)

        directory = self.cache_dir / accession
        directory.mkdir(parents=True, exist_ok=True)

        output = directory / f"{model_id}-model_v{version}.{fmt}"

        if output.is_file() and output.stat().st_size > 0:
            return output

        response = self.http.get(url)

        if not response.content:
            raise UpstreamError("AlphaFold DB returned an empty structure.")

        temporary = output.with_suffix(output.suffix + ".tmp")

        try:
            temporary.write_bytes(response.content)
            temporary.replace(output)

        finally:
            if temporary.exists():
                temporary.unlink()

        return output
