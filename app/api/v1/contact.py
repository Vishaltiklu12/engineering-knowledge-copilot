from fastapi import APIRouter, Depends

from app.api.deps import contact_rate_limit, get_contact_service, get_request_id
from app.schemas.common import MetaBody
from app.schemas.contact import ContactRequest, ContactResponse, ContactResponseData
from app.services.contact import ContactService

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("", response_model=ContactResponse, dependencies=[Depends(contact_rate_limit)])
def submit_contact(
    payload: ContactRequest,
    request_id: str = Depends(get_request_id),
    contact_service: ContactService = Depends(get_contact_service),
) -> ContactResponse:
    result = contact_service.submit(payload)
    return ContactResponse(
        data=ContactResponseData(
            delivery_mode=result.delivery_mode,
            message=result.message,
        ),
        meta=MetaBody(request_id=request_id),
    )
