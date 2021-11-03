import re
from http import HTTPStatus
from typing import List

from fastapi import Query
from fastapi.params import Depends
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore

from lnbits.core.views.api import api_payment
from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import check_invoice_status, create_invoice
from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.extensions.lnticket.models import CreateFormData, CreateTicketData

from . import lnticket_ext
from .crud import (
    create_form,
    create_ticket,
    delete_form,
    delete_ticket,
    get_form,
    get_forms,
    get_ticket,
    get_tickets,
    set_ticket_paid,
    update_form,
)

# FORMS


@lnticket_ext.get("/api/v1/forms")
async def api_forms_get(
    r: Request,
    all_wallets: bool = Query(False),
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [form.dict() for form in await get_forms(wallet_ids)]


@lnticket_ext.post("/api/v1/forms", status_code=HTTPStatus.CREATED)
@lnticket_ext.put("/api/v1/forms/{form_id}")
# @api_check_wallet_key("invoice")
# @api_validate_post_request(
#     schema={
#         "wallet": {"type": "string", "empty": False, "required": True},
#         "name": {"type": "string", "empty": False, "required": True},
#         "webhook": {"type": "string", "required": False},
#         "description": {"type": "string", "min": 0, "required": True},
#         "amount": {"type": "integer", "min": 0, "required": True},
#         "flatrate": {"type": "integer", "required": True},
#     }
# )
async def api_form_create(
    data: CreateFormData, form_id=None, wallet: WalletTypeInfo = Depends(get_key_type)
):
    if form_id:
        form = await get_form(form_id)

        if not form:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail=f"Form does not exist."
            )
            # return {"message": "Form does not exist."}, HTTPStatus.NOT_FOUND

        if form.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail=f"Not your form."
            )
            # return {"message": "Not your form."}, HTTPStatus.FORBIDDEN

        form = await update_form(form_id, **data.dict())
    else:
        form = await create_form(data, wallet.wallet)
    return form.dict()


@lnticket_ext.delete("/api/v1/forms/{form_id}")
# @api_check_wallet_key("invoice")
async def api_form_delete(form_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    form = await get_form(form_id)

    if not form:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Form does not exist."
        )
        # return {"message": "Form does not exist."}, HTTPStatus.NOT_FOUND

    if form.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=f"Not your form.")
        # return {"message": "Not your form."}, HTTPStatus.FORBIDDEN

    await delete_form(form_id)

    # return "", HTTPStatus.NO_CONTENT
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


#########tickets##########


@lnticket_ext.get("/api/v1/tickets")
# @api_check_wallet_key("invoice")
async def api_tickets(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [form.dict() for form in await get_tickets(wallet_ids)]


@lnticket_ext.post("/api/v1/tickets/{form_id}", status_code=HTTPStatus.CREATED)
# @api_validate_post_request(
#     schema={
#         "form": {"type": "string", "empty": False, "required": True},
#         "name": {"type": "string", "empty": False, "required": True},
#         "email": {"type": "string", "empty": True, "required": True},
#         "ltext": {"type": "string", "empty": False, "required": True},
#         "sats": {"type": "integer", "min": 0, "required": True},
#     }
# )
async def api_ticket_make_ticket(data: CreateTicketData, form_id):
    form = await get_form(form_id)
    if not form:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"LNTicket does not exist."
        )
        # return {"message": "LNTicket does not exist."}, HTTPStatus.NOT_FOUND

    nwords = len(re.split(r"\s+", data.ltext))

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=form.wallet,
            amount=data.sats,
            memo=f"ticket with {nwords} words on {form_id}",
            extra={"tag": "lnticket"},
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))
        # return {"message": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR

    ticket = await create_ticket(
        payment_hash=payment_hash, wallet=form.wallet, data=data
    )

    if not ticket:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNTicket could not be fetched."
        )
        # return (
        #     {"message": "LNTicket could not be fetched."},
        #     HTTPStatus.NOT_FOUND,
        # )

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@lnticket_ext.get("/api/v1/tickets/{payment_hash}", status_code=HTTPStatus.OK)
async def api_ticket_send_ticket(payment_hash):
    ticket = await get_ticket(payment_hash)

    try:
        status = await api_payment(payment_hash)
        if status["paid"]:
            await set_ticket_paid(payment_hash=payment_hash)
            return {"paid": True}
    except Exception:
        return {"paid": False}

    return {"paid": False}


@lnticket_ext.delete("/api/v1/tickets/{ticket_id}")
# @api_check_wallet_key("invoice")
async def api_ticket_delete(ticket_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    ticket = await get_ticket(ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"LNTicket does not exist."
        )
        # return {"message": "Paywall does not exist."}, HTTPStatus.NOT_FOUND

    if ticket.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your ticket.")
        # return {"message": "Not your ticket."}, HTTPStatus.FORBIDDEN

    await delete_ticket(ticket_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)
    # return ""