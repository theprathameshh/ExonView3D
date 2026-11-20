import argparse
import json
import logging
import sys
import threading
import webbrowser
from urllib.parse import urlencode

from . import __version__
from .config import resolve_ca_bundle
from .errors import ExonViewError, InvalidInput
from .server import _static_file, create_server
from .service import ExonViewService


# ----------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------

def _common_options():

    parent = argparse.ArgumentParser(add_help=False)

    group = parent.add_argument_group("connection and cache")

    group.add_argument(
        "--cache-dir",
        help="Directory for downloaded AlphaFold files "
             "(default: per-user cache, or $EXONVIEW3D_CACHE_DIR).",
    )
    group.add_argument(
        "--ca-bundle",
        help="PEM file with CA certificates for HTTPS requests "
             "(default: system certificates, or $EXONVIEW3D_CA_BUNDLE).",
    )
    group.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Network timeout in seconds (default: 30).",
    )
    group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print request logs and debugging information.",
    )

    return parent


def build_parser():

    common = _common_options()

    parser = argparse.ArgumentParser(
        prog="exonview3d",
        description="Explore exon organisation on AlphaFold protein "
                    "structures.",
    )

    parser.add_argument(
        "--version", action="version", version=f"exonview3d {__version__}"
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    serve = sub.add_parser(
        "serve",
        parents=[common],
        help="Start the interactive 3D viewer in your browser.",
        description="Start the local web viewer (Mol*) and open it in "
                    "your browser.",
    )
    serve.add_argument("--gene", help="NCBI Gene ID to load on start.")
    serve.add_argument("--transcript", help="Transcript to select on start.")
    serve.add_argument(
        "--host", default="127.0.0.1",
        help="Interface to listen on (default: 127.0.0.1, this computer only).",
    )
    serve.add_argument(
        "--port", type=int, default=8765,
        help="Port to listen on (default: 8765; 0 picks a free port).",
    )
    serve.add_argument(
        "--no-browser", action="store_true",
        help="Do not open a browser window automatically.",
    )
    serve.set_defaults(func=cmd_serve)

    gene = sub.add_parser(
        "gene",
        parents=[common],
        help="Look up a gene in the terminal.",
        description="List a gene's transcripts and AlphaFold availability, "
                    "or show exon details for one transcript.",
    )
    gene.add_argument("gene_id", help="NCBI Gene ID, for example 7157.")
    gene.add_argument(
        "-t", "--transcript",
        help="Show exon, UniProt and structure details for this transcript.",
    )
    gene.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON."
    )
    gene.set_defaults(func=cmd_gene)

    check = sub.add_parser(
        "check",
        parents=[common],
        help="Test connectivity to ENACTdb, UniProt and AlphaFold DB.",
    )
    check.set_defaults(func=cmd_check)

    return parser


def make_service(args):

    return ExonViewService(
        cache_dir=args.cache_dir,
        ca_bundle=resolve_ca_bundle(args.ca_bundle),
        timeout=args.timeout,
    )


# ----------------------------------------------------------------------
# serve
# ----------------------------------------------------------------------

def cmd_serve(args):

    if _static_file("app.js") is None or _static_file("index.html") is None:
        raise ExonViewError(
            "The bundled web interface (exonview3d/web/static/app.js) is "
            "missing.",
            hint="Reinstall the package, or build it from a source checkout: "
                 "see 'Developing' in the README.",
        )

    service = make_service(args)

    try:
        server = create_server(service, args.host, args.port)
    except OSError as error:
        raise ExonViewError(
            f"Could not listen on {args.host}:{args.port} ({error.strerror}).",
            hint="Choose another port with --port, or use --port 0.",
        ) from error

    port = server.server_address[1]
    shown_host = "localhost" if args.host in ("0.0.0.0", "::") else args.host

    query = {}

    if args.gene:
        query["gene"] = args.gene
    if args.transcript:
        query["transcript"] = args.transcript

    url = f"http://{shown_host}:{port}/"

    if query:
        url += "?" + urlencode(query)

    print(f"ExonView3D {__version__} is running at {url}")

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"Warning: listening on {args.host}; other computers on your "
            "network can reach this viewer.",
            file=sys.stderr,
        )

    print("Press Ctrl+C to stop.")

    if not args.no_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()

    return 0


# ----------------------------------------------------------------------
# gene
# ----------------------------------------------------------------------

def _table(headers, rows):

    widths = [len(header) for header in headers]

    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def line(cells):
        return "  ".join(
            str(cell).ljust(widths[i]) for i, cell in enumerate(cells)
        ).rstrip()

    print(line(headers))
    print(line(["-" * width for width in widths]))

    for row in rows:
        print(line(row))


def _segments_text(segments):

    if not segments:
        return "-"

    return ", ".join(
        f"{s['chain_id']}:{s['start']}-{s['end']}" for s in segments
    )


def cmd_gene(args):

    service = make_service(args)

    if args.transcript:

        detail = service.get_transcript(args.gene_id, args.transcript)

        if args.json:
            print(json.dumps(detail, indent=2))
            return 0

        _print_transcript(service, args, detail)
        return 0

    summary = service.search_gene(args.gene_id)

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    gene = summary["gene"]

    print(f"{gene['symbol']}  {gene['description']}")
    print(f"NCBI Gene ID {gene['gene_id']}  |  {gene['organism']}")
    print(
        f"{summary['summary']['transcripts']} transcripts, "
        f"{summary['summary']['with_structure']} with an AlphaFold structure\n"
    )

    rows = []

    for item in summary["transcripts"]:

        availability = item["alphafold"]

        rows.append((
            item["transcript_id"],
            item["uniprot_id"] or "-",
            item["protein_length"] if item["protein_length"] is not None else "-",
            item["number_of_exons"] if item["number_of_exons"] is not None else "-",
            "available" if item["structure_available"]
            else availability["status"],
        ))

    _table(("TRANSCRIPT", "UNIPROT", "AA", "EXONS", "ALPHAFOLD"), rows)

    unavailable = [
        item for item in summary["transcripts"]
        if not item["structure_available"]
    ]

    if unavailable:
        print("\nReasons for unavailable structures:")

        for status in sorted({i["alphafold"]["message"] for i in unavailable}):
            print(f"  - {status}")

    print(
        f"\nShow exon details:  exonview3d gene {gene['gene_id']} "
        "--transcript <TRANSCRIPT>"
    )
    print(f"Open the 3D viewer: exonview3d serve --gene {gene['gene_id']}")

    return 0


def _print_transcript(service, args, detail):

    gene = detail["gene"]
    transcript = detail["transcript"]
    uniprot = detail["uniprot"]
    structure = detail["structure"]
    mapping = detail["mapping"]

    print(f"{gene['symbol']} ({gene['gene_id']})  {gene['organism']}")
    print(f"Transcript : {transcript['transcript_id']}")
    print(
        f"Protein    : {detail['protein']['name'] or 'unknown name'}, "
        f"{transcript['protein_length']} aa, "
        f"{transcript['number_of_exons']} coding exons"
    )

    if uniprot["accession"]:

        validation = uniprot["validation"] or {}

        print(
            f"UniProt    : {uniprot['accession']} (from {uniprot['source']}); "
            f"sequence check: {validation.get('status', 'unavailable')}"
        )

    else:
        print("UniProt    : no accession available")

    if structure["status"] == "available":

        print(
            f"Structure  : {structure['model_id']} v{structure['model_version']}, "
            f"chain {structure['chain_id']}"
        )
        print(
            f"Mapping    : {mapping['mapped_residues']}/"
            f"{mapping['protein_length']} residues "
            f"({mapping['coverage_percent']}%)"
        )

        try:
            print(
                "File       : "
                f"{service.structure_file(gene['gene_id'], transcript['transcript_id'])}"
            )
        except ExonViewError:
            pass

    else:
        print(f"Structure  : unavailable ({structure['message']})")

    print()

    rows = [
        (
            exon["exon_id"],
            f"{exon['protein_start']}-{exon['protein_end']}",
            exon["protein_length"],
            _segments_text(exon["structure_residue_segments"]),
            "-" if exon["coverage_percent"] is None
            else f"{exon['coverage_percent']}%",
            exon["colour"],
        )
        for exon in detail["exons"]
    ]

    _table(
        ("EXON", "PROTEIN", "AA", "STRUCTURE", "COVERAGE", "COLOUR"), rows
    )


# ----------------------------------------------------------------------
# check
# ----------------------------------------------------------------------

def cmd_check(args):

    service = make_service(args)

    checks = [
        ("ENACTdb", lambda: service.enact.get_gene(7157)),
        ("UniProt", lambda: service.uniprot.get_record("P04637")),
        ("AlphaFold DB", lambda: service.alphafold.http.get(
            f"{service.alphafold.BASE_URL}/P04637"
        )),
    ]

    failures = 0

    for name, action in checks:

        try:
            action()
            print(f"  ok      {name}")

        except ExonViewError as error:
            failures += 1
            print(f"  FAILED  {name}: {error.message}")

            if error.hint:
                print(f"          {error.hint}")

    if failures:
        print(f"\n{failures} service(s) unreachable.")
        return 1

    print("\nAll services reachable.")
    return 0


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def main(argv=None):

    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        parser.print_help()
        return 2

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s: %(message)s",
    )

    try:
        return args.func(args)

    except ExonViewError as error:

        print(f"error: {error.message}", file=sys.stderr)

        if error.hint:
            print(f"hint:  {error.hint}", file=sys.stderr)

        if args.verbose:
            raise

        return 1

    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
