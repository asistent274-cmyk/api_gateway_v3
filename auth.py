import os
from fastapi import Header, HTTPException


def check_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Prueft den API-Key gegen deinen einzigen, festen Key (Umgebungsvariable API_KEY).
    Kein Account-System, keine Limits -- nur du nutzt diese API.
    """
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="API_KEY ist auf dem Server nicht gesetzt")

    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Ungueltiger API-Key")

    return {"api_key": x_api_key}
