import os
from fastapi import Header, HTTPException
from database import get_user_by_key, increment_usage, reset_if_new_day, TIER_LIMITS


def check_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Prueft den API-Key eines Nutzers, setzt taegliche Limits zurueck und
    blockt, wenn das Tages-Limit des jeweiligen Tarifs erreicht ist.
    Owner-Tarif (limit = None) ist immer unbegrenzt.
    """
    user = get_user_by_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Ungueltiger API-Key")

    reset_if_new_day(user["id"])
    user = get_user_by_key(x_api_key)  # frisch laden nach moeglichem Reset

    limit = TIER_LIMITS.get(user["tier"])
    if limit is not None and user["requests_used"] >= limit:
        raise HTTPException(
            status_code=402,
            detail=f"Tageslimit erreicht ({limit} Anfragen/Tag, Tarif: {user['tier']}). "
                   f"Reset um Mitternacht.",
        )

    increment_usage(user["id"])
    return user
    
