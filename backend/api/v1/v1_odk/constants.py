class ApprovalStatusTypes:
    PENDING = 0
    APPROVED = 1
    REJECTED = 2

    KoboStatusMap = {
        PENDING: "validation_status_on_hold",
        APPROVED: "validation_status_approved",
        REJECTED: "validation_status_not_approved",
    }
