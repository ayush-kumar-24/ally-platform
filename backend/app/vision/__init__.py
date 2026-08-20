"""Vision -- the founder's own long-term vision, kept in front of them.

Public surface (import from here, not from submodules):

    VisionTerritory, VisionSummary     frozen domain DTOs
    TERRITORY_KEYS                     the 6 valid territory keys
    VisionService                      business rules; build_vision_service() to construct
    VisionRepository                   persistence seam (InMemory / SqlAlchemy)
    errors                             VisionError and friends -> precise HTTP statuses

Backs the "Your Vision" page (frontend/src/pages/VisionPage.jsx). Every
territory and the summary start empty until the founder writes their own --
see models.py's TERRITORY_KEYS docstring and service.py's get_territories().
"""

from app.vision.errors import InvalidVisionInputError, InvalidVisionTerritoryError, VisionError
from app.vision.models import TERRITORY_KEYS, VisionSummary, VisionTerritory
from app.vision.repository import InMemoryVisionRepository, VisionRepository
from app.vision.service import VisionService, build_vision_service

__all__ = [
    "TERRITORY_KEYS",
    "InMemoryVisionRepository",
    "InvalidVisionInputError",
    "InvalidVisionTerritoryError",
    "VisionError",
    "VisionRepository",
    "VisionService",
    "VisionSummary",
    "VisionTerritory",
    "build_vision_service",
]
