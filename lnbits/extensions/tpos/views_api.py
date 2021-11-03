from http import HTTPStatus

from fastapi import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import check_invoice_status, create_invoice
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.core.views.api import api_payment
from lnbits.core.models import Wallet
from . import tpos_ext
from .crud import create_tpos, delete_tpos, get_tpos, get_tposs
from .models import CreateTposData


@tpos_ext.get("/api/v1/tposs", status_code=HTTPStatus.OK)
async def api_tposs(
    all_wallets: bool = Query(None), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [tpos.dict() for tpos in await get_tposs(wallet_ids)]


@tpos_ext.post("/api/v1/tposs", status_code=HTTPStatus.CREATED)
async def api_tpos_create(
    data: CreateTposData, wallet: WalletTypeInfo = Depends(get_key_type)
):
    tpos = await create_tpos(wallet_id=wallet.wallet.id, data=data)
    return tpos.dict()


@tpos_ext.delete("/api/v1/tposs/{tpos_id}")
async def api_tpos_delete(
    tpos_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    tpos = await get_tpos(tpos_id)

    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )
        # return {"message": "TPoS does not exist."}, HTTPStatus.NOT_FOUND

    if tpos.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your TPoS.")
        # return {"message": "Not your TPoS."}, HTTPStatus.FORBIDDEN

    await delete_tpos(tpos_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)
    # return "", HTTPStatus.NO_CONTENT


@tpos_ext.post("/api/v1/tposs/{tpos_id}/invoices", status_code=HTTPStatus.CREATED)
async def api_tpos_create_invoice(amount: int = Query(..., ge=1), tpos_id: str = None):
    tpos = await get_tpos(tpos_id)

    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )
        # return {"message": "TPoS does not exist."}, HTTPStatus.NOT_FOUND

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=tpos.wallet,
            amount=amount,
            memo=f"{tpos.name}",
            extra={"tag": "tpos"},
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))
        # return {"message": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@tpos_ext.get(
    "/api/v1/tposs/{tpos_id}/invoices/{payment_hash}", status_code=HTTPStatus.OK
)
async def api_tpos_check_invoice(tpos_id: str, payment_hash: str):
    tpos = await get_tpos(tpos_id)
    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )
    try:
        status = await api_payment(payment_hash)
    except Exception as exc:
        print(exc)
        return {"paid": False}
    return status