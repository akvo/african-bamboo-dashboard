"""Access to finance metrics, computed from the stored snapshot.

Definitions are in docs/v30_access_to_finance_dashboard_plan.md
section 3.3. Data is reported as recorded: inactive members and
collateral that contradicts parcel titles are not corrected here.
"""

import datetime
from statistics import mean, median

# Pending client confirmation (#60).
YOUTH_MAX_AGE = 29
# Comparison groups smaller than this are not shown.
MIN_GROUP_SIZE = 5
FILTER_PARAMS = (
    "region",
    "woreda",
    "coop",
    "gender",
    "target_group",
    "youth",
    "loan_type",
)
# filter param -> member column
MEMBER_COLUMNS = {
    "region": "region",
    "woreda": "woreda",
    "coop": "coop_id",
    "gender": "gender",
    "target_group": "target_group",
}
# filter param -> cooperative column
COOP_COLUMNS = {"region": "region", "woreda": "woreda", "coop": "coop_id"}


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def total(rows, column):
    return sum(row[column] or 0 for row in rows)


def is_youth(member, as_of):
    dob = member["date_of_birth"]
    if dob is None:
        return False
    born = datetime.date.fromisoformat(dob)
    age = as_of.year - born.year - (
        (as_of.month, as_of.day) < (born.month, born.day)
    )
    return age <= YOUTH_MAX_AGE


def par30(loans):
    flagged = [loan for loan in loans if loan["par_30_flag"] == 1]
    return ratio(
        total(flagged, "outstanding_balance"),
        total(loans, "outstanding_balance"),
    )


def group(n, value):
    return {"n": n, "value": value if n >= MIN_GROUP_SIZE else None}


def income_change(members):
    changes = [
        m["income_current"] - m["income_baseline"]
        for m in members
        if m["income_current"] is not None
        and m["income_baseline"] is not None
    ]
    return group(len(changes), mean(changes) if changes else None)


def select_members(snapshot, filters):
    as_of = snapshot.data_as_of
    youth = filters.get("youth")
    return [
        m
        for m in snapshot.members
        if all(
            m[column] == filters[param]
            for param, column in MEMBER_COLUMNS.items()
            if filters.get(param)
        )
        and (not youth or is_youth(m, as_of) == (youth == "yes"))
    ]


def compute_metrics(snapshot, filters):
    members = select_members(snapshot, filters)
    by_id = {m["member_id"]: m for m in members}
    loans = [
        loan
        for loan in snapshot.loans
        if loan["member_id"] in by_id
        and (
            not filters.get("loan_type")
            or loan["loan_type"] == filters["loan_type"]
        )
    ]
    active = [loan for loan in loans if loan["loan_status"] == "Active"]
    borrower_ids = {loan["member_id"] for loan in loans}
    borrowers = [by_id[i] for i in borrower_ids]
    non_borrowers = [
        m for m in members if m["member_id"] not in borrower_ids
    ]
    coops = [
        c
        for c in snapshot.cooperatives
        if all(
            c[column] == filters[param]
            for param, column in COOP_COLUMNS.items()
            if filters.get(param)
        )
    ]
    coop_ids = {c["coop_id"] for c in coops}
    active_coops = {
        by_id[loan["member_id"]]["coop_id"] for loan in active
    } & coop_ids

    amounts = [
        loan["loan_amount_etb"]
        for loan in loans
        if loan["loan_amount_etb"] is not None
    ]
    disbursed = sum(amounts)
    outstanding = total(active, "outstanding_balance")
    hectares = total(borrowers, "bamboo_area_ha")
    rated = [
        loan
        for loan in loans
        if loan["interest_rate"] is not None
        and loan["loan_amount_etb"] is not None
    ]

    collateral = {}
    for loan in loans:
        entry = collateral.setdefault(
            loan["collateral_type"],
            {"type": loan["collateral_type"], "loans": 0, "amount": 0},
        )
        entry["loans"] += 1
        entry["amount"] += loan["loan_amount_etb"] or 0

    written_off = total(
        [loan for loan in loans if loan["loan_status"] == "Written off"],
        "outstanding_balance",
    )

    scores = {}
    for loan in active:
        if loan["credit_score"] is not None:
            scores.setdefault(loan["member_id"], []).append(
                loan["credit_score"]
            )

    titled = {p["member_id"] for p in snapshot.parcels if p["title_deed_no"]}
    with_title = [m for m in members if m["member_id"] in titled]
    without_title = [m for m in members if m["member_id"] not in titled]
    trained = [
        loan
        for loan in active
        if by_id[loan["member_id"]]["training_completed"] == 1
    ]
    untrained = [
        loan
        for loan in active
        if by_id[loan["member_id"]]["training_completed"] == 0
    ]
    jobs = total(borrowers, "jobs_created")

    def borrowing(group_members):
        borrowing_count = sum(
            m["member_id"] in borrower_ids for m in group_members
        )
        return group(
            len(group_members), ratio(borrowing_count, len(group_members))
        )

    return {
        "data_as_of": snapshot.data_as_of.isoformat(),
        "youth_max_age": YOUTH_MAX_AGE,
        "reach": {
            "members": len(members),
            "borrowers": len(borrowers),
            "borrowing_rate": ratio(len(borrowers), len(members)),
            "women_share": ratio(
                sum(m["gender"] == "F" for m in borrowers), len(borrowers)
            ),
            "youth_share": ratio(
                sum(is_youth(m, snapshot.data_as_of) for m in borrowers),
                len(borrowers),
            ),
            "coops": len(coops),
            "coops_with_active_loans": len(active_coops),
            "coops_share": ratio(len(active_coops), len(coops)),
        },
        "volume": {
            "loans": len(loans),
            "disbursed": disbursed,
            "outstanding": outstanding,
            "average_loan": mean(amounts) if amounts else None,
            "median_loan": median(amounts) if amounts else None,
            "hectares": hectares,
            "value_per_ha": ratio(disbursed, hectares),
            "outstanding_share": ratio(outstanding, disbursed),
        },
        "loan_terms": {
            "average_interest_rate": ratio(
                sum(
                    loan["loan_amount_etb"] * loan["interest_rate"]
                    for loan in rated
                ),
                total(rated, "loan_amount_etb"),
            ),
            "collateral": list(collateral.values()),
        },
        "portfolio_quality": {
            "par30": par30(active),
            "written_off": written_off,
            "written_off_share": ratio(written_off, disbursed),
            "credit_score": (
                mean(mean(s) for s in scores.values()) if scores else None
            ),
            "credit_score_borrowers": len(scores),
        },
        "linked": {
            "borrowing_with_title": borrowing(with_title),
            "borrowing_without_title": borrowing(without_title),
            "par30_trained": group(len(trained), par30(trained)),
            "par30_untrained": group(len(untrained), par30(untrained)),
            "income_change_borrowers": income_change(borrowers),
            "income_change_non_borrowers": income_change(non_borrowers),
            "jobs_created": jobs,
            "jobs_per_million": ratio(jobs * 1_000_000, disbursed),
        },
    }


def distinct(rows, column):
    return sorted({row[column] for row in rows if row[column] is not None})


def filter_options(snapshot):
    woredas = {}
    for m in snapshot.members:
        if m["region"] and m["woreda"]:
            woredas.setdefault(m["region"], set()).add(m["woreda"])
    return {
        "regions": distinct(snapshot.members, "region"),
        "woredas": {k: sorted(v) for k, v in sorted(woredas.items())},
        "cooperatives": [
            {"value": c["coop_id"], "label": c["coop_name"]}
            for c in snapshot.cooperatives
        ],
        "genders": distinct(snapshot.members, "gender"),
        "target_groups": distinct(snapshot.members, "target_group"),
        "loan_types": distinct(snapshot.loans, "loan_type"),
    }
