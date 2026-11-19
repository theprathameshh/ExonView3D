from django.urls import path

from . import views

urlpatterns = [
    path(
        "genes/<int:gene_id>/transcripts/<str:transcript_id>/structure/",
        views.transcript_structure,
        name="transcript-structure",
    ),
    path(
        "genes/<int:gene_id>/transcripts/<str:transcript_id>/structure-file/",
        views.transcript_structure_file,
        name="transcript-structure-file",
    ),
]
