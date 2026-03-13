import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from django.conf import settings
from django.core.management.base import (
    BaseCommand,
)

from api.v1.v1_odk.constants import (
    ATTACHMENTS_FOLDER,
)
from api.v1.v1_odk.models import Submission
from utils.encryption import decrypt
from utils.kobo_client import KoboClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Re-download attachments from Kobo "
        "using the large URL and apply EXIF "
        "orientation fix."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be "
            "re-downloaded without "
            "writing to disk.",
        )
        parser.add_argument(
            "--submission-uuid",
            type=str,
            default=None,
            help="Fix a single submission "
            "by UUID.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        sub_uuid = options["submission_uuid"]

        qs = Submission.objects.exclude(
            raw_data__isnull=True,
        )
        if sub_uuid:
            qs = qs.filter(uuid=sub_uuid)

        total = 0
        fixed = 0
        skipped = 0
        errors = 0

        for sub in qs.iterator():
            raw = sub.raw_data or {}
            attachments = raw.get(
                "_attachments", []
            )
            image_atts = [
                a
                for a in attachments
                if a.get(
                    "mimetype", ""
                ).startswith("image/")
                and a.get("uid")
            ]
            if not image_atts:
                continue

            total += len(image_atts)
            dest_dir = (
                Path(settings.STORAGE_PATH)
                / ATTACHMENTS_FOLDER
                / str(sub.uuid)
            )

            for att in image_atts:
                att_uid = att["uid"]
                basename = att.get(
                    "media_file_basename",
                    "img.jpg",
                )
                ext = (
                    basename.rsplit(".", 1)[-1]
                    or "jpg"
                )
                dest_file = (
                    dest_dir / f"{att_uid}.{ext}"
                )

                if not dest_file.exists():
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  Would fix: "
                        f"{dest_file}"
                    )
                    fixed += 1
                    continue

                try:
                    img = Image.open(dest_file)
                    transposed = (
                        ImageOps.exif_transpose(
                            img
                        )
                    )
                    if transposed is not img:
                        transposed.save(
                            dest_file
                        )
                        fixed += 1
                        self.stdout.write(
                            f"  Fixed: "
                            f"{dest_file}"
                        )
                    else:
                        skipped += 1
                except Exception as e:
                    errors += 1
                    logger.warning(
                        "Failed to fix %s: %s",
                        dest_file,
                        e,
                    )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would fix "
                    f"{fixed} of {total} "
                    f"attachments, "
                    f"skipped {skipped}."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Fixed {fixed} of "
                    f"{total} attachments, "
                    f"skipped {skipped}, "
                    f"errors {errors}."
                )
            )

        # Re-download from large URL
        if not dry_run and sub_uuid is None:
            self._redownload_from_large(qs)

    def _redownload_from_large(self, qs):
        """Re-download attachments that were
        originally fetched from medium URL."""
        from api.v1.v1_users.models import (
            SystemUser,
        )

        user = (
            SystemUser.objects.filter(
                kobo_url__isnull=False,
                kobo_username__isnull=False,
                kobo_password__isnull=False,
            )
            .exclude(kobo_url="")
            .first()
        )
        if not user:
            self.stdout.write(
                self.style.WARNING(
                    "No Kobo user found, "
                    "skipping re-download."
                )
            )
            return

        client = KoboClient(
            user.kobo_url,
            user.kobo_username,
            decrypt(user.kobo_password),
        )

        redownloaded = 0
        for sub in qs.iterator():
            raw = sub.raw_data or {}
            attachments = raw.get(
                "_attachments", []
            )
            image_atts = [
                a
                for a in attachments
                if a.get(
                    "mimetype", ""
                ).startswith("image/")
                and a.get("uid")
            ]
            if not image_atts:
                continue

            dest_dir = (
                Path(settings.STORAGE_PATH)
                / ATTACHMENTS_FOLDER
                / str(sub.uuid)
            )
            dest_dir.mkdir(
                parents=True, exist_ok=True
            )

            for att in image_atts:
                att_uid = att["uid"]
                basename = att.get(
                    "media_file_basename",
                    "img.jpg",
                )
                ext = (
                    basename.rsplit(".", 1)[-1]
                    or "jpg"
                )
                dest_file = (
                    dest_dir / f"{att_uid}.{ext}"
                )
                urls = [
                    att.get("download_url"),
                    att.get(
                        "download_large_url"
                    ),
                    att.get(
                        "download_medium_url"
                    ),
                    att.get(
                        "download_small_url"
                    ),
                ]
                urls = [u for u in urls if u]
                if not urls:
                    continue

                success = False
                for url in urls:
                    try:
                        resp = (
                            client.session.get(
                                url,
                                timeout=(
                                    client.timeout
                                ),
                            )
                        )
                        resp.raise_for_status()
                        img = Image.open(
                            BytesIO(
                                resp.content
                            )
                        )
                        img = (
                            ImageOps
                            .exif_transpose(img)
                        )
                        img.save(dest_file)
                        redownloaded += 1
                        success = True
                        break
                    except Exception:
                        continue
                if not success:
                    logger.warning(
                        "All URLs failed for "
                        "attachment %s",
                        att_uid,
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Re-downloaded {redownloaded}"
                f" attachments from Kobo."
            )
        )
