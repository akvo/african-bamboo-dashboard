import logging

from django.db import IntegrityError
from django.db.models import IntegerField, Max
from django.db.models.functions import Cast, Substr

from api.v1.v1_odk.constants import PREFIX_PLOT_ID
from api.v1.v1_odk.models import (
    MainPlot,
    MainPlotSubmission,
)

logger = logging.getLogger(__name__)

_PREFIX_LEN = len(PREFIX_PLOT_ID)
_MAX_RETRIES = 3


def generate_next_plot_uid(form):
    """Generate the next sequential Plot UID
    scoped to a form.

    Format: PLT00001, PLT00351, etc.
    Uses numeric Cast + Max to avoid lexicographic
    ordering issues.

    Args:
        form: FormMetadata instance (uses
            form.plot_uid_start as floor).

    Returns:
        str: e.g. "PLT00001", "PLT00351"
    """
    effective_min = form.plot_uid_start or 1

    result = MainPlot.objects.filter(
        form=form,
    ).aggregate(
        max_uid=Max(
            Cast(
                Substr("uid", _PREFIX_LEN + 1),
                IntegerField(),
            )
        )
    )
    max_uid = result["max_uid"]
    if max_uid is None:
        next_num = effective_min
    else:
        next_num = max(max_uid + 1, effective_min)
    return f"{PREFIX_PLOT_ID}{str(next_num).zfill(5)}"


def create_main_plot_for_submission(submission):
    """Create a MainPlot and link it to the
    submission on approval.

    Handles concurrent creation race via retry
    on IntegrityError (same pattern as farmer UID).

    Args:
        submission: Submission instance being
            approved.

    Returns:
        MainPlot or None: The created MainPlot,
            or None if submission has no plot.
    """
    plot = getattr(submission, "plot", None)
    if not plot:
        return None

    # Already linked — idempotent
    existing = MainPlotSubmission.objects.filter(
        submission=submission,
    ).select_related("main_plot").first()
    if existing:
        return existing.main_plot

    form = submission.form

    for attempt in range(_MAX_RETRIES):
        uid = generate_next_plot_uid(form)
        try:
            main_plot = MainPlot.objects.create(
                uid=uid,
                form=form,
            )
            MainPlotSubmission.objects.create(
                main_plot=main_plot,
                submission=submission,
            )
            return main_plot
        except IntegrityError:
            if attempt == _MAX_RETRIES - 1:
                logger.error(
                    "Failed to create MainPlot "
                    "after %d attempts for "
                    "submission %s",
                    _MAX_RETRIES,
                    submission.uuid,
                )
                raise
            continue
    return None


def unlink_main_plot_submission(submission):
    """Remove MainPlotSubmission link on revert.

    The MainPlot itself is retained to prevent
    UID gaps and support future resubmission
    linking.

    Args:
        submission: Submission instance being
            reverted.

    Returns:
        int: Number of links deleted.
    """
    deleted, _ = MainPlotSubmission.objects.filter(
        submission=submission,
    ).delete()
    return deleted
