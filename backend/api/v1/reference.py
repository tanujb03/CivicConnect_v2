"""Reference data for every authenticated client (apps load it once and revalidate with ``If-None-Match``)."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.core.http_cache import cached_json
from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import User
from backend.schemas.reference import DepartmentRefList, TaxonomyOut, WardRefList
from backend.services import reference as reference_service

router = APIRouter()
NOT_MODIFIED = {304: {"description": "Not Modified: the If-None-Match ETag is current."}}


@router.get("/taxonomy", responses={200: {"model": TaxonomyOut}, **NOT_MODIFIED})
def get_taxonomy(request: Request, user: User = Depends(current_user)):
    """Categories and subcategories exactly as in the AI taxonomy, plus severities, priorities, SLA classes and the taxonomy's departments. ETag + Cache-Control."""
    return cached_json(request, reference_service.taxonomy_payload(), max_age=3600)


@router.get("/departments", responses={200: {"model": DepartmentRefList}, **NOT_MODIFIED})
def get_departments(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return cached_json(request, {"items": reference_service.departments_payload(db)})


@router.get("/wards", responses={200: {"model": WardRefList}, **NOT_MODIFIED})
def get_wards(request: Request, include: Optional[Literal["boundary"]] = Query(default=None, description="``boundary`` adds each ward's GeoJSON boundary"),
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    return cached_json(request, {"items": reference_service.wards_payload(db, include_boundary=include == "boundary")})
