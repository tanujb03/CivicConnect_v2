from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import User
from backend.schemas.platform import DeviceTokenIn, DeviceTokenOut
from backend.services import push as push_service

router = APIRouter()           # mounted with prefix="/me": POST/GET /me/devices, DELETE /me/devices/{device_id}


@router.post("/devices", response_model=DeviceTokenOut, status_code=201)
def register_device(body: DeviceTokenIn, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Registers (or refreshes) the Expo push token of this installed app for the caller. Any signed-in role (citizen and field-worker apps).

    Upsert by token, so it is idempotent by nature and needs no Idempotency-Key: the same token is the same device row, bound to the caller (a token that belonged to another
    account is moved to the caller: the phone changed hands), ``revoked_at`` cleared, ``last_seen_at`` refreshed. 201 for a new device, 200 for an existing one. The token is never
    returned. At most PUSH_MAX_DEVICES_PER_USER (10) active devices per user: registering one more revokes the least recently seen one. Call it after every sign-in and whenever Expo hands out a new token.

    Remote push does not work in Expo Go (SDK 53 and later); it needs a development build or a store build."""
    row, created = push_service.register_device(db, user, body)
    db.commit()
    response.status_code = 201 if created else 200
    return push_service.out(row)


@router.get("/devices", response_model=list[DeviceTokenOut])
def my_devices(include_revoked: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The caller's own devices, newest first (active ones; ``include_revoked=true`` adds revoked ones). At most the 50 newest are returned, so it is not paged."""
    return [push_service.out(r) for r in push_service.list_devices(db, user, include_revoked=include_revoked)]


@router.delete("/devices/{device_id}", response_model=DeviceTokenOut)
def revoke_device(device_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Revokes one of the caller's devices (no more push to it; call it on sign-out). 200 with the device; idempotent by nature: repeating it keeps the first ``revoked_at``.
    A device id that is not the caller's answers 404 ``DEVICE_NOT_FOUND``."""
    row = push_service.revoke_device(db, user, device_id)
    db.commit()
    return push_service.out(row)
