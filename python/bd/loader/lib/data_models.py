from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union

from PySide2.QtGui import QPixmap


@dataclass
class AssetDetails:
    fullname: str
    version: int
    created_at: datetime
    modified_at: datetime
    thumbnail: Optional[QPixmap] = None


@dataclass
class AssetInfo:
    id: Union[int, str]
    type: str
    name: str
    icon: Optional[QPixmap] = None
    details: Optional[AssetDetails] = None
