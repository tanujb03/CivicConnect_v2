"""AI gateway: the ONLY place where backend routes meet ``ai.inference``.

Routes speak the frozen §51A contract; the adapter speaks its own typed schemas. This package translates between them, resolves
what the adapter must never fetch itself (evidence bytes, candidate cases, triage context), enforces §51A.18 roles, persists
``AIAnalysis`` records and writes AI-override audit events. Storage is behind small ports (``ports.py``): the default
implementation is backed by the synthetic demo city so the full AI path works before the SQL repositories exist.
"""
from .deps import configure_gateway, get_actor, get_gateway
from .service import AIGateway

__all__ = ["AIGateway", "configure_gateway", "get_actor", "get_gateway"]
