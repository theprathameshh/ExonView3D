# ExonView3D

Explore how a gene's exons are laid out on its protein structure. Enter an NCBI Gene ID, pick a transcript, and ExonView3D shows the AlphaFold model in an interactive [Mol\*](https://molstar.org/) viewer with every exon in its own colour.

- **Gene search** by NCBI Gene ID
- **Transcript selection** with AlphaFold availability for each transcript
- **3D viewer** (Mol\*) loading the matching AlphaFold structure
- **Exon colouring**: one distinct colour per exon
- **Interactive annotations**: click an exon to highlight and focus it; hover over the structure to see which exon you are on
- **Information panel**: gene, transcript, UniProt, exon boundaries (protein and genomic), mapping coverage, protein and model details
- **Graceful errors** for unknown genes, transcripts without a structure, and network or certificate problems

Everything runs locally. No account or API key is needed.

## Requirements

| Requirement | Notes |
|---|---|
| Python 3.9 or newer | 3.11 or 3.12 recommended |
| pip and git | to install from a git repository |
| Internet access | to reach ENACTdb, UniProt and AlphaFold DB (data is cached locally afterwards) |
| A modern web browser with WebGL | Chrome, Edge, Firefox or Safari |

Python dependencies (`requests`, `biopython`) are installed automatically. **Node.js is not needed** to use the tool; the viewer is shipped pre-built.

## Installation

Use an isolated environment so the tool does not interfere with other packages.

**With venv**

```bash
python3 -m venv exonview3d-env
source exonview3d-env/bin/activate          # Windows: exonview3d-env\Scripts\activate
pip install "git+https://github.com/<OWNER>/ExonView3D.git"
```

**With conda**

```bash
conda create -n exonview3d python=3.11
conda activate exonview3d
pip install "git+https://github.com/<OWNER>/ExonView3D.git"
```

**With pipx** (installs the command globally, isolated)

```bash
pipx install "git+https://github.com/<OWNER>/ExonView3D.git"
```

Replace `<OWNER>/ExonView3D` with the repository location. For a private repository, use an SSH URL (`git+ssh://git@github.com/<OWNER>/ExonView3D.git`) or authenticate git as usual. To pin a version, append `@<tag-or-commit>` to the URL. To upgrade, add `--upgrade`.

Check the installation and your network access:

```bash
exonview3d --version
exonview3d check
```

## Quick start

```bash
exonview3d serve --gene 7157
```

This starts a local server and opens your browser on the viewer with TP53 loaded. Press `Ctrl+C` in the terminal to stop it. Other genes can be searched from the page.

## Command line

```text
exonview3d serve  [--gene ID] [--transcript ID] [--host H] [--port N] [--no-browser]
exonview3d gene   GENE_ID [--transcript ID] [--json]
exonview3d check
```

| Command | Purpose |
|---|---|
| `serve` | Start the interactive viewer (default address `http://127.0.0.1:8765`, reachable from this computer only). `--port 0` picks a free port. |
| `gene` | Terminal summary: list transcripts and their AlphaFold availability, or with `--transcript` show exons, coverage and the local structure file. `--json` prints machine-readable output. |
| `check` | Tests connectivity to ENACTdb, UniProt and AlphaFold DB and suggests fixes. |

Options shared by all commands:

| Option | Environment variable | Meaning |
|---|---|---|
| `--cache-dir DIR` | `EXONVIEW3D_CACHE_DIR` | Where AlphaFold files are cached (default: your per-user cache directory) |
| `--ca-bundle FILE` | `EXONVIEW3D_CA_BUNDLE` | PEM file with extra CA certificates for HTTPS |
| `--timeout SECONDS` | | Network timeout (default 30) |
| `-v`, `--verbose` | | Request logs and tracebacks |

Examples:

```bash
exonview3d gene 7157                                  # transcripts of TP53
exonview3d gene 7157 --transcript NP_001119584.1      # exon table
exonview3d gene 7157 -t NP_001119584.1 --json > tp53.json
```

## Using the viewer

1. Type an **NCBI Gene ID** (for example `7157` for TP53) and press Search. Gene IDs can be found at <https://www.ncbi.nlm.nih.gov/gene>.
2. Choose a **transcript**. A green *AlphaFold ✓* badge means a model whose sequence matches the transcript's protein exactly. Hover a grey badge to see why there is no structure. Tick the filter to hide transcripts without one.
3. The structure appears with each exon coloured. The **Exons** panel lists every exon with protein range, mapped structure residues, coverage and genomic coordinates.
4. **Click an exon** (in the list or on the coloured exon bar) to highlight and zoom to it. *Clear selection / reset view* restores the view.
5. **Hover over the structure** to see the residue and the exon it belongs to; the matching exon card is highlighted.

A transcript without a structure still shows its exon table; only the 3D view is replaced by an explanation.

## How it works

```text
Gene ID --> ENACTdb (transcripts, exons) --> protein reconstruction and validation
        --> UniProt accession(s) --> AlphaFold DB predictions
        --> exact sequence match per transcript --> download mmCIF
        --> residue mapping (protein position -> structure residue)
        --> exon -> residue segments --> Mol* component per exon
```

- Exon and transcript data come from [ENACTdb](https://www.iscbglab.in/enactdb/). Each transcript's protein is rebuilt from its exons and checked for complete, non-overlapping coverage.
- A structure is offered **only when an AlphaFold model's sequence equals the transcript's protein exactly**. This includes UniProt isoform models (for example `P04637-4`), so a transcript can have a structure even when ENACTdb lists no UniProt accession for it. Transcripts with no exact match are never mapped onto a different protein.
- When UniProt is reachable, the protein is also compared with the UniProt reference sequence and the result is shown in the panel.
- Downloaded AlphaFold files are cached, so repeat visits are fast and AlphaFold metadata is reused if the service is briefly unreachable.

## Troubleshooting

**`ssl_error` / "could not verify the server certificate".** Some networks, or servers with an incomplete certificate chain, fail verification. Obtain the missing CA certificate(s), concatenate them with your trusted bundle into a PEM file, and pass it:

```bash
exonview3d serve --ca-bundle /path/to/bundle.pem
# or
export EXONVIEW3D_CA_BUNDLE=/path/to/bundle.pem
```

`REQUESTS_CA_BUNDLE` is also honoured. Run `exonview3d check` to see which service is failing.

**"Could not connect" / timeouts.** Check your connection, proxy settings (`HTTPS_PROXY`), or raise `--timeout`.

**"Gene … was not found in ENACTdb".** ENACTdb covers a subset of NCBI genes. Check the ID or try another gene.

**A transcript shows "No structure".** The badge tooltip gives the reason: no UniProt accession, no AlphaFold model, or no model with an identical sequence.

**Port already in use.** Use `--port 0` or another `--port`.

**The 3D view is blank.** Make sure WebGL is enabled in your browser and graphics drivers are up to date.

**Security note.** The server binds to `127.0.0.1` by default. Using `--host 0.0.0.0` exposes the viewer to your network; it serves public data only, but do so deliberately.

## Developing

```bash
git clone https://github.com/<OWNER>/ExonView3D.git
cd ExonView3D
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
pytest
```

The tests run offline against recorded public responses (`tests/data`: TP53 and A1BG from ENACTdb, AlphaFold models for P04637).

The browser interface is written in `frontend/src/` and bundled, with Mol\* 5.13.1, into `exonview3d/web/static/`. The built files are committed so that `pip install` from git needs no Node.js. After editing the front end (Node.js 18 or newer):

```bash
cd frontend
npm ci
npm run build        # rewrites exonview3d/web/static/app.js and app.css
```

Commit the regenerated files together with your source changes.

### Layout

```text
exonview3d/
  cli.py                command line (serve, gene, check)
  server.py             local JSON API and static file server (standard library only)
  service.py            gene lookup, transcript details, structure mapping
  enact_client.py       ENACTdb
  uniprot_client.py     UniProt
  alphafold_client.py   AlphaFold DB
  exon_parser.py        transcript and exon parsing, protein reconstruction
  structure_parser.py   mmCIF reading
  residue_mapper.py     protein position -> structure residue
  exon_structure_mapper.py   exon -> structure residue segments
  colours.py            distinct exon colours
  web/static/           pre-built viewer (index.html, app.js, app.css)
frontend/               viewer source and build script
tests/                  offline test suite and fixtures
```

## Data sources and acknowledgements

- [ENACTdb](https://www.iscbglab.in/enactdb/) for gene, transcript and exon annotation
- [UniProt](https://www.uniprot.org/) for reference protein sequences
- [AlphaFold Protein Structure Database](https://alphafold.ebi.ac.uk/) for predicted structures
- [Mol\*](https://molstar.org/) for molecular visualisation

Please follow the terms of use and citation requirements of each resource.

## License

No license has been chosen yet. Add a `LICENSE` file before sharing the repository publicly.
