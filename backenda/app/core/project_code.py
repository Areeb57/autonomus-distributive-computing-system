"""
Nine-digit project join code generator and normalization.
"""

from __future__ import annotations

import re
import secrets
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import ProjectCode


def generate_raw_nine_digit_code() -> str:
    """Generate a random 9-digit number as string."""
    # Generate 9 cryptographically random digits between 100000000 and 999999999
    code_int = secrets.randbelow(900_000_000) + 100_000_000
    return str(code_int)


generate_nine_digit_code = generate_raw_nine_digit_code


def format_nine_digit_code(raw: str) -> str:
    """Format 9-digit raw string into 'XXX-XXX-XXX' pattern."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 9:
        return raw
    return f"{digits[0:3]}-{digits[3:6]}-{digits[6:9]}"


def normalize_project_code(code: str) -> str:
    """
    Normalize user-entered project code by stripping dashes and whitespace,
    and returning formatted 'XXX-XXX-XXX' representation.
    """
    digits = re.sub(r"\D", "", code.strip())
    if len(digits) == 9:
        return format_nine_digit_code(digits)
    return code.strip()


async def generate_unique_project_code(
    db: AsyncSession,
    project_id: Any,
    max_retries: int = 10,
) -> ProjectCode:
    """
    Generate and persist a unique 9-digit project code, handling collision retries.
    """
    if isinstance(project_id, str):
        project_id = uuid.UUID(project_id)
    for _ in range(max_retries):
        raw_code = generate_raw_nine_digit_code()
        formatted_code = format_nine_digit_code(raw_code)

        # Check uniqueness in database
        stmt = select(ProjectCode).where(
            (ProjectCode.code == formatted_code) | (ProjectCode.code == raw_code)
        )
        existing = (await db.execute(stmt)).scalars().first()
        if not existing:
            project_code = ProjectCode(
                project_id=project_id,
                code=formatted_code,
                is_active=True,
            )
            db.add(project_code)
            await db.flush()
            return project_code

    raise RuntimeError("Failed to generate a unique 9-digit project code after maximum retries.")
