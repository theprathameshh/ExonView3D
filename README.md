# ExonView3D

**ExonView3D** is a Python-based tool for mapping gene-level exon organisation onto protein sequences and visualising exon-derived regions on three-dimensional protein structures.

The project combines biological data retrieval, transcript and exon parsing, protein sequence validation, AlphaFold structure retrieval, residue mapping, a Django REST API, and a browser-based 3D viewer powered by Mol*.

## Project Status

The current implementation has been tested using the human **TP53** gene.

| Parameter | Value |
|---|---|
| Gene | TP53 |
| NCBI Gene ID | 7157 |
| Transcript | NP_001119584.1 |
| UniProt accession | P04637 |
| AlphaFold model | AF-P04637-F1 |
| Structure chain | A |
| Structure length | 393 residues |
| Number of exons | 10 |
| Exon mapping coverage | 100% for all 10 exons |

### Implemented features

- Retrieval and parsing of gene, transcript, and exon information.
- Protein sequence reconstruction from exon annotations.
- Protein sequence validation using UniProt.
- Retrieval of AlphaFold protein structures.
- Mapping of protein residues to structure residues.
- Exon-specific structural annotations.
- Django REST API for exon metadata and structure files.
- Interactive browser-based protein visualisation using Mol*.
- Individual coloured structural representations for exons.
- Exon card hover interaction with the corresponding structural region.

The current implementation is a development prototype. Integration into the existing website and support for additional genes and transcripts are future development goals.

---

## Project Architecture

ExonView3D consists of three main components:

1. **Python package:** Retrieves biological data, processes transcripts and exons, validates protein sequences, retrieves AlphaFold structures, and maps protein residues to structure residues.
2. **Django backend:** Provides REST API endpoints for exon metadata and protein structure files.
3. **Vite + Mol* frontend:** Displays gene, transcript, and exon information and visualises exon regions on protein structures.

### Data Flow

```text
                 NCBI / ENACTdb
                       |
                       v
                Gene information
                       |
                       v
                Transcript parsing
                       |
                       v
                  Exon parsing
                       |
                       v
              Protein reconstruction
                       |
                       v
                UniProt validation
                       |
                       v
              AlphaFold DB retrieval
                       |
                       v
             Structure sequence parsing
                       |
                       v
               Residue mapping
                       |
                       v
             Exon structure annotation
                       |
                       v
                 JSON results
                       |
                       v
                Django REST API
                       |
                       v
                 Vite frontend
                       |
                       v
                 Mol* viewer
                       |
                       v
             Coloured exon regions
```

---

## Repository Structure

```text
ExonView3D/
│
├── exonview3d/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── enact_client.py
│   ├── exon_parser.py
│   ├── uniprot_client.py
│   ├── alphafold_client.py
│   ├── structure_parser.py
│   ├── residue_mapper.py
│   ├── exon_structure_mapper.py
│   └── structure_annotator.py
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   └── api/
│       ├── __init__.py
│       ├── urls.py
│       ├── views.py
│       └── services.py
│
├── web/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   │
│   └── src/
│       ├── main.js
│       └── style.css
│
├── data/
│   ├── alphafold/
│   ├── certificates/
│   └── ...
│
├── results/
│   ├── gene_1.json
│   ├── gene_7157.json
│   └── structures/
│
├── tests/
│   └── test_exon_parser.py
│
├── pyproject.toml
├── README.md
└── .gitignore
```

Some directories and files, including certificates and generated caches, are intentionally excluded from Git.

---

## Requirements

### Software

- Python 3.11 recommended
- Conda or another Python environment manager
- Node.js and npm
- Git

### Python dependencies

The Python package dependencies are defined in `pyproject.toml`.

The Django backend dependencies are listed in:

```text
backend/requirements.txt
```

### Frontend dependencies

| Package | Version |
|---|---|
| Mol* | 5.13.1 |
| Vite | 8.3.8 |

---

## Installation

### 1. Clone the repository

Clone the private repository after obtaining access:

```bash
git clone <private-repository-url>
cd ExonView3D
```

### 2. Create the Python environment

```bash
conda create -n exonview3D python=3.11
conda activate exonview3D
```

### 3. Install the Python package

Run this command from the project root:

```bash
pip install -e .
```

### 4. Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

### 5. Install frontend dependencies

```bash
cd web
npm install
cd ..
```

---

## Running ExonView3D

The backend and frontend run as separate development servers.

### 1. Start the Django backend

Open a terminal and activate the Python environment:

```bash
conda activate exonview3D
```

Navigate to the backend directory:

```bash
cd ExonView3D/backend
```

Start the Django development server:

```bash
python manage.py runserver 0.0.0.0:8000
```

The backend will be available at:

```text
http://localhost:8000/
```

### 2. Start the frontend

Open another terminal:

```bash
cd ExonView3D/web
```

Start the Vite development server:

```bash
npm run dev -- --host 0.0.0.0
```

Open the application in a browser:

```text
http://localhost:5173/
```

The Vite development server proxies `/api` requests to the Django backend.

---

## Backend API

The Django backend exposes endpoints for retrieving exon mapping information and protein structure files.

### 1. Retrieve exon structure information

```http
GET /api/genes/<gene_id>/transcripts/<transcript_id>/structure/
```

Example:

```http
GET /api/genes/7157/transcripts/NP_001119584.1/structure/
```

The response contains:

- Gene information
- Transcript information
- Protein information
- AlphaFold structure metadata
- Exon annotations
- Protein residue mappings
- Structure residue segments

An individual exon contains information similar to:

```json
{
  "exon_id": "D.1.A.2.0.0",
  "protein_start": 1,
  "protein_end": 25,
  "protein_length": 25,
  "protein_sequence": "MEEPQSDPSVEPPLSQETFSDLWKL",
  "mapped_residues": 25,
  "unmapped_residues": 0,
  "coverage_percent": 100.0,
  "structure_residue_segments": [
    {
      "chain_id": "A",
      "start": 1,
      "end": 25,
      "start_insertion_code": "",
      "end_insertion_code": "",
      "protein_start": 1,
      "protein_end": 25
    }
  ]
}
```

The `structure_residue_segments` field provides the structural residue ranges used by the Mol* viewer.

Protein sequence positions and structure residue numbering should not be assumed to be identical. The structure residue mapping is used for structural selection.

### 2. Retrieve the protein structure

```http
GET /api/genes/<gene_id>/transcripts/<transcript_id>/structure-file/
```

Example:

```http
GET /api/genes/7157/transcripts/NP_001119584.1/structure-file/
```

This endpoint serves the corresponding AlphaFold mmCIF structure file.

---

## Mol* Visualisation

The frontend uses Mol* to render and interact with protein structures directly in the browser.

The current implementation:

1. Retrieves exon and structure metadata from the Django API.
2. Loads the AlphaFold mmCIF structure.
3. Hides the default whole-protein cartoon representation.
4. Creates individual structural representations for the exons.
5. Assigns a distinct colour to each exon.
6. Displays exon information alongside the 3D structure.

### Exon Representation

Each exon is represented using its mapped structural residue segments.

The frontend uses MolScript selections based on:

- Chain identifier
- Structure residue numbering
- Exon-specific residue ranges

Each exon is assigned a colour from the exon palette returned by the backend.

This allows users to distinguish exon-derived regions within the same protein structure.

### Technologies

- [Mol*](https://molstar.org/) – molecular structure visualisation
- [Vite](https://vite.dev/) – frontend development and build tooling
- [Django](https://www.djangoproject.com/) – backend framework
- [Django REST Framework](https://www.django-rest-framework.org/) – REST API

---

## Configuration

### Django Settings

The Django secret key is read from an environment variable:

```python
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-development-only",
)
```

For local development, the fallback value can be used.

For deployment, configure a secure secret key through the environment:

```bash
export DJANGO_SECRET_KEY="your-secure-secret-key"
```

The current Django configuration is intended for local development. Before deployment, configure:

- `DEBUG = False`
- A production secret key
- Appropriate `ALLOWED_HOSTS`
- Production database settings
- Static file handling
- Production CORS settings
- HTTPS

Do not commit secret keys, credentials, or private certificates to the repository.

---

## Development Roadmap

The following features are planned for future development.

### Data Processing

- Support for additional genes and transcripts.
- Improved handling of alternative transcripts.
- More extensive validation of exon-to-protein mappings.
- Improved handling of discontinuous structural residue segments.

### Visualisation

- Improved exon selection and highlighting interactions.
- More detailed structural annotations.
- Improved display of exon boundaries.
- Additional structure representation and colour customisation options.

### Website Integration

- Integrate the Mol* viewer into the existing website.
- Replace the current standalone development interface with a reusable visualisation utility.
- Connect the frontend to the existing website's gene and transcript selection workflow.
- Support dynamic loading of genes, transcripts, and structures.

---

## Testing

The project currently includes Python tests under:

```text
tests/
```

Run the available tests from the project root:

```bash
pytest
```

The TP53 example can also be used to verify the data-processing and visualisation workflow.

---

## Current Limitations

- The frontend currently uses a predefined TP53 gene and transcript.
- The application is configured for local development.
- The Mol* visualisation is a standalone frontend prototype.
- Production deployment and integration with the existing website have not yet been implemented.
- Support for arbitrary genes and transcripts through the frontend remains under development.

---

## License

The project is currently under development. Licensing will be determined before public release.

---

## Acknowledgements

ExonView3D builds upon publicly available biological resources and software, including:

- NCBI Gene and ENACTdb for gene, transcript, and exon information.
- UniProt for protein sequence validation.
- AlphaFold Protein Structure Database for predicted protein structures.
- Mol* for interactive molecular structure visualisation.
- Django and Vite for backend and frontend development.
