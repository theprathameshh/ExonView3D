"""Application logic shared by the command line and the web viewer."""

import re
import threading
from collections import OrderedDict
from pathlib import Path

from .alphafold_client import AlphaFoldClient
from .colours import exon_colours
from .config import default_cache_dir
from .enact_client import EnactClient, validate_gene_id
from .errors import (
    DataError,
    ExonViewError,
    InvalidInput,
    StructureUnavailable,
    TranscriptNotFound,
    UpstreamError,
)
from .exon_parser import parse_gene
from .exon_structure_mapper import ExonStructureMapper
from .residue_mapper import ResidueMapper
from .structure_parser import StructureParser
from .uniprot_client import UniProtClient

TRANSCRIPT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

MAX_CACHED_GENES = 32
MAX_CACHED_DETAILS = 64


def validate_transcript_id(value):

    text = str(value).strip()

    if not TRANSCRIPT_ID_PATTERN.match(text):
        raise InvalidInput(f"'{text}' is not a valid transcript identifier.")

    return text


def _split_gene_name(name):
    """ENACTdb stores 'TP53 tumor protein p53' as one string."""

    symbol, _, description = str(name).partition(" ")

    return symbol, description.strip()


class _GeneBundle:
    """Everything known about one gene after the cheap lookups."""

    def __init__(self, gene_id, raw, parsed):

        self.gene_id = gene_id
        self.raw = raw
        self.parsed = parsed

        self.predictions = []
        self.prediction_errors = {}
        self.accessions = []
        self.matches = {}

    def find_transcript(self, transcript_id):

        for transcript in self.parsed["transcripts"]:
            if transcript["transcript_id"] == transcript_id:
                return transcript

        return None

    def find_skipped(self, transcript_id):

        for stub in self.parsed.get("skipped_transcripts", []):
            if stub["transcript_id"] == transcript_id:
                return stub

        return None


class ExonViewService:

    def __init__(self, cache_dir=None, ca_bundle=None, timeout=30,
                 session=None):

        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()

        self.enact = EnactClient(
            ca_bundle=ca_bundle, timeout=timeout, session=session
        )
        self.uniprot = UniProtClient(
            ca_bundle=ca_bundle, timeout=timeout, session=session
        )
        self.alphafold = AlphaFoldClient(
            self.cache_dir / "alphafold",
            ca_bundle=ca_bundle,
            timeout=max(timeout, 60),
            session=session,
        )

        self.structure_parser = StructureParser()
        self.residue_mapper = ResidueMapper()

        self._lock = threading.RLock()
        self._bundles = OrderedDict()
        self._details = OrderedDict()

    # ------------------------------------------------------------------
    # Gene level
    # ------------------------------------------------------------------

    def _bundle(self, gene_id):

        gene_id = validate_gene_id(gene_id)

        with self._lock:

            if gene_id in self._bundles:
                self._bundles.move_to_end(gene_id)
                return self._bundles[gene_id]

            raw = self.enact.get_gene(gene_id)

            try:
                parsed = parse_gene(raw, strict=False)
            except (ValueError, KeyError, TypeError) as error:
                raise DataError(
                    f"The ENACTdb record for gene {gene_id} could not be "
                    f"interpreted: {error}"
                ) from error

            bundle = _GeneBundle(gene_id, raw, parsed)

            self._attach_alphafold(bundle)

            self._bundles[gene_id] = bundle

            while len(self._bundles) > MAX_CACHED_GENES:
                self._bundles.popitem(last=False)

            return bundle

    def _attach_alphafold(self, bundle):
        """Find AlphaFold models whose sequence equals each transcript's."""

        accessions = []

        for transcript in bundle.parsed["transcripts"]:

            accession = transcript.get("uniprot_id")

            if not UniProtClient.is_valid_accession(accession):
                continue

            base = AlphaFoldClient.base_accession(accession)

            if base not in accessions:
                accessions.append(base)

        bundle.accessions = accessions

        seen = set()

        for accession in accessions:

            try:
                records = self.alphafold.get_predictions(accession)

            except ExonViewError as error:
                bundle.prediction_errors[accession] = error.message
                continue

            for record in records:

                model_id = record.get("modelEntityId")

                if model_id in seen:
                    continue

                seen.add(model_id)
                bundle.predictions.append(record)

        for transcript in bundle.parsed["transcripts"]:

            bundle.matches[transcript["transcript_id"]] = (
                self.alphafold.find_exact_sequence_match(
                    transcript["protein_sequence"],
                    bundle.predictions,
                )
            )

    @staticmethod
    def _gene_info(bundle):

        raw = bundle.raw

        symbol, description = _split_gene_name(raw.get("name", ""))

        return {
            "gene_id": raw.get("entrezid"),
            "symbol": symbol,
            "description": description,
            "organism": raw.get("organism"),
        }

    @staticmethod
    def _alphafold_availability(bundle, transcript_id):
        """Describe whether a structure exists for a transcript."""

        match = bundle.matches.get(transcript_id)

        if match is not None:
            return {
                "status": "available",
                "message": (
                    f"AlphaFold model {match['modelEntityId']} matches this "
                    "protein sequence exactly."
                ),
                "model_id": match["modelEntityId"],
                "accession": match.get("uniprotAccession"),
            }

        if bundle.prediction_errors and not bundle.predictions:
            reason = next(iter(bundle.prediction_errors.values()))
            return {
                "status": "lookup_failed",
                "message": f"AlphaFold DB could not be queried: {reason}",
            }

        if not bundle.accessions:
            return {
                "status": "no_uniprot_accession",
                "message": (
                    "ENACTdb lists no UniProt accession for this gene, so "
                    "AlphaFold DB cannot be queried."
                ),
            }

        if not bundle.predictions:
            return {
                "status": "no_alphafold_model",
                "message": (
                    "AlphaFold DB has no prediction for UniProt "
                    + ", ".join(bundle.accessions)
                    + "."
                ),
            }

        if bundle.prediction_errors:
            return {
                "status": "lookup_failed",
                "message": (
                    "Some AlphaFold DB lookups failed, so no matching model "
                    "could be confirmed."
                ),
            }

        return {
            "status": "no_exact_sequence_match",
            "message": (
                "AlphaFold models exist for this gene, but none matches this "
                "transcript's protein sequence exactly."
            ),
        }

    def search_gene(self, gene_id):
        """Gene summary with every transcript and its AlphaFold status."""

        bundle = self._bundle(gene_id)

        transcripts = []

        for transcript in bundle.parsed["transcripts"]:

            tid = transcript["transcript_id"]
            availability = self._alphafold_availability(bundle, tid)
            match = bundle.matches.get(tid)

            transcripts.append({
                "transcript_id": tid,
                "uniprot_id": (
                    transcript.get("uniprot_id")
                    or (match.get("uniprotAccession") if match else None)
                ),
                "protein_length": transcript["protein_length"],
                "number_of_exons": len(transcript["exons"]),
                "structure_available": availability["status"] == "available",
                "alphafold": availability,
            })

        for stub in bundle.parsed.get("skipped_transcripts", []):

            transcripts.append({
                "transcript_id": stub["transcript_id"],
                "uniprot_id": stub.get("uniprot_id"),
                "protein_length": stub.get("protein_length"),
                "number_of_exons": None,
                "structure_available": False,
                "alphafold": {
                    "status": "annotation_error",
                    "message": (
                        "The exon annotation for this transcript could not "
                        f"be interpreted ({stub['error']})."
                    ),
                },
            })

        # Transcripts with a structure first; ENACTdb order otherwise.
        transcripts.sort(key=lambda item: not item["structure_available"])

        return {
            "gene": self._gene_info(bundle),
            "transcripts": transcripts,
            "summary": {
                "transcripts": len(transcripts),
                "with_structure": sum(
                    item["structure_available"] for item in transcripts
                ),
            },
        }

    # ------------------------------------------------------------------
    # Transcript level
    # ------------------------------------------------------------------

    def get_transcript(self, gene_id, transcript_id):
        """Exon, protein, UniProt and structure details for a transcript."""

        bundle = self._bundle(gene_id)
        transcript_id = validate_transcript_id(transcript_id)

        key = (bundle.gene_id, transcript_id)

        with self._lock:

            if key in self._details:
                self._details.move_to_end(key)
                return self._details[key][0]

            transcript = bundle.find_transcript(transcript_id)

            if transcript is None:

                stub = bundle.find_skipped(transcript_id)

                if stub is not None:
                    raise DataError(
                        f"The exon annotation for {transcript_id} could not "
                        f"be interpreted: {stub['error']}"
                    )

                raise TranscriptNotFound(
                    f"Transcript {transcript_id} is not part of gene "
                    f"{bundle.gene_id}.",
                    hint="Choose one of the transcripts listed for this gene.",
                )

            result, structure_path = self._build_transcript(bundle, transcript)

            self._details[key] = (result, structure_path)

            while len(self._details) > MAX_CACHED_DETAILS:
                self._details.popitem(last=False)

            return result

    def structure_file(self, gene_id, transcript_id):
        """Path of the AlphaFold mmCIF file for a transcript."""

        result = self.get_transcript(gene_id, transcript_id)

        key = (validate_gene_id(gene_id), validate_transcript_id(transcript_id))

        path = self._details[key][1]

        if path is None:
            raise StructureUnavailable(result["structure"]["message"])

        return path

    def _build_transcript(self, bundle, transcript):

        tid = transcript["transcript_id"]
        match = bundle.matches.get(tid)

        structure, summaries, path = self._map_structure(
            bundle, transcript, match
        )

        colours = exon_colours(len(transcript["exons"]))

        summary_by_id = {item["exon_id"]: item for item in summaries}

        exons = []

        for index, exon in enumerate(transcript["exons"]):

            mapped = summary_by_id.get(exon["exon_id"])

            exons.append({
                "index": index,
                "exon_id": exon["exon_id"],
                "protein_start": exon["start"],
                "protein_end": exon["end"],
                "protein_length": exon["length"],
                "sequence": exon["sequence"],
                "genomic": exon["genomic_coordinates"],
                "colour": colours[index],
                "mapped_residues": (
                    mapped["mapped_residues"] if mapped else None
                ),
                "unmapped_residues": (
                    mapped["unmapped_residues"] if mapped else None
                ),
                "coverage_percent": (
                    round(mapped["coverage_percent"], 2) if mapped else None
                ),
                "structure_residue_segments": (
                    mapped["structure_residue_segments"] if mapped else []
                ),
            })

        mapping = None

        if summaries:

            mapped_total = sum(item["mapped_residues"] for item in exons)

            mapping = {
                "mapped_residues": mapped_total,
                "protein_length": transcript["protein_length"],
                "coverage_percent": round(
                    100.0 * mapped_total / transcript["protein_length"], 2
                ),
            }

        uniprot = self._uniprot_section(transcript, match)

        protein_name = (
            uniprot["validation"].get("protein_name")
            if uniprot["validation"] else None
        ) or (match.get("uniprotDescription") if match else None)

        result = {
            "gene": self._gene_info(bundle),
            "transcript": {
                "transcript_id": tid,
                "protein_length": transcript["protein_length"],
                "number_of_exons": len(transcript["exons"]),
            },
            "protein": {
                "name": protein_name,
                "length": transcript["protein_length"],
                "sequence": transcript["protein_sequence"],
                "mean_plddt": match.get("globalMetricValue") if match else None,
            },
            "uniprot": uniprot,
            "structure": structure,
            "mapping": mapping,
            "exons": exons,
        }

        return result, path

    def _map_structure(self, bundle, transcript, match):
        """Download the matched model and map exons onto its residues.

        Returns (structure_info, exon_summaries, local_path_or_None).
        """

        availability = self._alphafold_availability(
            bundle, transcript["transcript_id"]
        )

        if match is None:
            return (
                {
                    "status": availability["status"],
                    "message": availability["message"],
                },
                [],
                None,
            )

        try:
            path = self.alphafold.download_structure(match, "cif")
            data = self.structure_parser.extract_structure(path)

        except UpstreamError as error:
            return (
                {"status": "download_failed", "message": error.message},
                [],
                None,
            )

        except (ExonViewError, ValueError, OSError) as error:
            return (
                {
                    "status": "structure_unreadable",
                    "message": f"The structure file could not be read: {error}",
                },
                [],
                None,
            )

        sequence = transcript["protein_sequence"]

        best = None

        for chain in data["chains"].values():

            mapping = self.residue_mapper.map_sequence_to_chain(
                sequence, chain
            )

            rank = (
                mapping["sequence_coverage_percent"],
                mapping["identity_percent"],
            )

            if best is None or rank > best[0]:
                best = (rank, mapping)

        mapping = best[1]

        if best[0] != (100.0, 100.0):
            return (
                {
                    "status": "sequence_mismatch",
                    "message": (
                        "The structure sequence differs from the transcript "
                        f"protein (coverage {mapping['sequence_coverage_percent']:.1f}%, "
                        f"identity {mapping['identity_percent']:.1f}%), so "
                        "exons cannot be mapped reliably."
                    ),
                },
                [],
                None,
            )

        residue_to_exon = transcript["residue_to_exon"]

        for residue in mapping["mapping"]:
            residue["exon_id"] = residue_to_exon.get(
                residue["protein_position"]
            )

        summaries = ExonStructureMapper.map_exons(
            transcript["exons"], mapping["mapping"]
        )

        structure = {
            "status": "available",
            "message": availability["message"],
            "model_id": match["modelEntityId"],
            "model_version": match.get("latestVersion"),
            "accession": match.get("uniprotAccession"),
            "chain_id": mapping["chain_id"],
            "format": "cif",
            "sequence_identity_percent": round(mapping["identity_percent"], 2),
            "sequence_coverage_percent": round(
                mapping["sequence_coverage_percent"], 2
            ),
        }

        return structure, summaries, path

    def _uniprot_section(self, transcript, match):
        """UniProt accession plus a best-effort sequence cross-check."""

        accession = transcript.get("uniprot_id")
        source = "ENACTdb" if accession else None

        if not accession and match is not None:
            accession = match.get("uniprotAccession")
            source = "AlphaFold sequence match"

        if not UniProtClient.is_valid_accession(accession):
            return {
                "accession": None,
                "source": None,
                "url": None,
                "validation": None,
            }

        try:
            validation = self.uniprot.validate_sequence(
                accession, transcript["protein_sequence"]
            )

        except ExonViewError as error:
            validation = {
                "status": "unavailable",
                "accession": accession,
                "message": error.message,
            }

        return {
            "accession": accession,
            "source": source,
            "url": f"https://www.uniprot.org/uniprotkb/{accession}/entry",
            "validation": validation,
        }
