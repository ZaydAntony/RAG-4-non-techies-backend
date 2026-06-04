import os
import uuid

from django.conf import settings

from .supabase_client import (
    supabase,
    SUPABASE_BUCKET,
)


def is_production():
    return not settings.DEBUG


def upload_pdf(file_obj, session_id):


    filename = f"{uuid.uuid4()}_{file_obj.name}"

    storage_path = (
        f"{session_id}/{filename}"
    )

    file_obj.seek(0)

    supabase.storage.from_(
        SUPABASE_BUCKET
    ).upload(
        storage_path,
        file_obj.read(),
        {
            "content-type": "application/pdf"
        }
    )

    return storage_path


def download_pdf(storage_path):
    return (
        supabase.storage
        .from_(SUPABASE_BUCKET)
        .download(storage_path)
    )


def delete_pdf(storage_path):
    if not storage_path:
        return

    supabase.storage.from_(
        SUPABASE_BUCKET
    ).remove(
        [storage_path]
    )