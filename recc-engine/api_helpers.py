import os

from fastapi import HTTPException


def update_keyword_counts(profile_keywords, new_keywords):
    """
    Updates the keyword counts in the profile.
    Handles migration if profile_keywords is a list (legacy).
    """
    if isinstance(profile_keywords, list):
        counts = {k: 1 for k in profile_keywords}
    else:
        counts = profile_keywords

    for kw in new_keywords:
        counts[kw] = counts.get(kw, 0) + 1

    return counts


def validate_user_id(user_id: str):
    if not user_id or user_id != os.path.basename(user_id) or user_id in [".", ".."]:
        raise HTTPException(status_code=400, detail="Invalid user ID")
