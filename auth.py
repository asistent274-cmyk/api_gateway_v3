from fastapi import Header, HTTPException
from database import get_account_by_key, increment_usage


def check_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Prueft einen API-Key und findet den zugehoerigen Account.
    Kein Tages-/Tarif-Limit mehr -- jeder gueltige Key funktioniert unbegrenzt.
    (requests_used wird nur noch zu Info-Zwecken mitgezaehlt.)
    """
    account = get_account_by_key(x_api_key)
    if not account:
        raise HTTPException(status_code=401, detail="Ungueltiger API-Key")

    increment_usage(account["email"])
    return account
