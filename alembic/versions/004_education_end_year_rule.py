"""drop currently_studying/end_year mutual exclusivity constraint

Business rule change: end_year now represents either the expected
graduation year (when currently_studying = true) or the actual
graduation year (when currently_studying = false). Previously, end_year
was forbidden while currently_studying was true; that constraint no
longer reflects how the product uses this field, so it is dropped here.

All other constraints on the educations table are unaffected:
  - ck_educations_institution_not_blank
  - ck_educations_degree_not_blank
  - ck_educations_start_year_range
  - ck_educations_end_year_range
  - ck_educations_end_after_start
  - ck_educations_grade_not_blank

Revision ID: 004_education_end_year_rule
Revises: 003_education
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004_education_end_year_rule"
down_revision: Union[str, None] = "003_education"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_educations_currently_studying_no_end_year",
        "educations",
        type_="check",
    )


def downgrade() -> None:
    # Re-add the constraint for rollback. Note: if any rows were inserted
    # under the new rule with currently_studying=true AND end_year set,
    # this downgrade will fail until those rows are corrected — this is
    # expected and intentional, since silently violating data integrity
    # on rollback would be worse than a loud failure.
    op.create_check_constraint(
        "ck_educations_currently_studying_no_end_year",
        "educations",
        "(currently_studying = false) OR (end_year IS NULL)",
    )