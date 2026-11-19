from django.shortcuts import render
from django.http import FileResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .services import (
    get_transcript_data,
    build_structure_data,
)


@api_view(["GET"])
def transcript_structure(request, gene_id, transcript_id):
    """
    Return transcript annotations and AlphaFold structure metadata.
    """

    try:
        gene_data, transcript = get_transcript_data(
            gene_id,
            transcript_id
        )

        structure_data = build_structure_data(
            gene_data,
            transcript
        )

        structure_data["structure"]["url"] = (
            f"/api/genes/{gene_id}/transcripts/"
            f"{transcript_id}/structure-file/"
        )

        return Response(structure_data)

    except FileNotFoundError as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_404_NOT_FOUND
        )

    except LookupError as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_404_NOT_FOUND
        )

    except ValueError as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
def transcript_structure_file(request, gene_id, transcript_id):
    """
    Serve the AlphaFold CIF structure file.
    """

    try:
        gene_data, transcript = get_transcript_data(
            gene_id,
            transcript_id
        )

        structure_data = build_structure_data(
            gene_data,
            transcript
        )

        from pathlib import Path
        from django.conf import settings

        structure_path = Path(
            transcript["alphafold"]["structure_file"]
        )

        if not structure_path.is_absolute():
            structure_path = Path(settings.BASE_DIR).parent / structure_path

        return FileResponse(
            open(structure_path, "rb"),
            content_type="chemical/x-mmcif",
            filename=structure_path.name
        )

    except (FileNotFoundError, LookupError, ValueError) as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_404_NOT_FOUND
        )
