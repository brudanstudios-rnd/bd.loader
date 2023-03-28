import os
import base64
from typing import Callable, List, Optional, Union

from PySide2 import QtGui

os.environ["BD_AUTH0_CLIENT_ID"] = "U0nDaM5dmbJhxpjY8vYRGaPdfrOuNOPJ"
os.environ["BD_AUTH0_DOMAIN"] = "brudanstudios.eu.auth0.com"
os.environ["BD_GRAPHQL_WSS_ENDPOINT"] = "wss://oa-graphql.ddns.net/v1/graphql"
os.environ["BD_GRAPHQL_HTTPS_ENDPOINT"] = "https://oa-graphql.ddns.net/v1/graphql"
os.environ["BD_API_CACHE_EXPIRE_TIME"] = "84000"
os.environ["BD_API_CACHE_ALLOWABLE_METHODS"] = "POST,GET,HEAD"

from bd.api import Session

from .base import DBAccessor
from ..data_models import AssetInfo, AssetDetails, ProjectInfo
from ..threading_utils import RequestRunnable


class GraphQLAccessor(DBAccessor):
    def __init__(self):
        super().__init__()
        self._project: Optional[ProjectInfo] = None
        self._session = Session()

    def get_projects(self, excluded_titles) -> List[ProjectInfo]:
        result = self._session.execute(
            """
            query GetProjects($titles: [String!]!) {
                projects(where: {title: {_nin: $titles}, active: {_eq: true}}) {
                    id
                    title
                    thumbnail
                }
            }""",
            {"titles": excluded_titles},
        )
        items = result["projects"]

        projects = []

        for item in items:

            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(base64.b64decode(item["thumbnail"].encode("utf-8")))

            project = ProjectInfo(id=item["id"], title=item["title"], thumbnail=pixmap)
            projects.append(project)

        return projects

    def set_active_project(self, project: ProjectInfo) -> None:
        self._project = project

    def request_asset_types(self, callback: Callable[[List[str]], None]) -> None:
        if self._project is None:
            return

        def _request() -> List[str]:
            result = self._session.execute(
                """
                query GetAssetTypes($project_id: Int!) {
                    assets(
                        distinct_on: type, 
                        where: {
                            projects_id: {_eq: $project_id}, 
                            type: {_neq: "CAM"}
                        }
                    ) {
                        type
                    }
                }""",
                {"project_id": self._project.id},
            )
            items = result["assets"]
            return [item["type"] for item in items if item["type"]]

        RequestRunnable.execute(_request, callback)

    def request_asset_categories(
        self,
        asset_type: str,
        callback: Callable[[List[str]], None],
        asset_level: Optional[str] = None,  # TODO: remove
    ) -> None:

        if self._project is None or asset_type == "CHR" or asset_level == "ENV":
            return

        def _request() -> List[str]:
            result = self._session.execute(
                """
                query GetAssetCategories($project_id: Int!, $type: String!) {
                    assets(
                        distinct_on: category, 
                        where: {
                            projects_id: {_eq: $project_id}, 
                            type: {_eq: $type},
                            category: {_neq: ""}
                        }
                    ) {
                        category
                    }
                }""",
                {"project_id": self._project.id, "type": asset_type},
            )
            items = result["assets"]
            return [item["category"] for item in items if item["category"]]

        RequestRunnable.execute(_request, callback)

    def request_asset_levels(
        self, asset_type: str, callback: Callable[[List[str]], None]
    ) -> None:
        if self._project is None:
            return

        def _request() -> List[str]:
            result = self._session.execute(
                """
                query GetAssetLevels($project_id: Int!, $type: String!) {
                    assets(
                        distinct_on: level, 
                        where: {
                            projects_id: {_eq: $project_id}, 
                            type: {_eq: $type},
                            level: {_neq: ""}
                        }
                    ) {
                        level
                    }
                }""",
                {"project_id": self._project.id, "type": asset_type},
            )
            items = result["assets"]
            return [item["level"] for item in items if item["level"]]

        RequestRunnable.execute(_request, callback)

    def request_assets(
        self,
        asset_type: str,
        callback: Callable[[List[AssetInfo]], None],
        asset_level: Optional[str] = None,
        asset_category: Optional[str] = None,
    ) -> None:
        if self._project is None:
            return

        query_args = ["$project_id: Int!, $type: String!"]
        conditions = ["projects_id: {_eq: $project_id}", "type: {_eq: $type}"]
        variables = {"project_id": self._project.id, "type": asset_type}

        if asset_level:
            query_args.append("$level: String")
            conditions.append("level: {_eq: $level}")
            variables["level"] = asset_level

        if asset_category:
            query_args.append("$category: String")
            conditions.append("category: {_eq: $category}")
            variables["category"] = asset_category

        def _request() -> List[dict]:
            result = self._session.execute(
                """
                query GetAssets(%s) {
                    assets(
                        where: {
                            %s
                        },
                        order_by: {name: asc}
                    ) {
                        id
                        type
                        name
                        level
                        category
                    }
                }"""
                % (", ".join(query_args), ", ".join(conditions)),
                variables,
            )
            items = result["assets"]
            return items

        def _result_callback(items: List[dict]):
            callback(list(map(self._create_asset_info_from_db_item, items)))

        RequestRunnable.execute(_request, _result_callback)

    def request_assets_by_regex(
        self, regex: str, callback: Callable[[List[AssetInfo]], None]
    ) -> None:
        if not self._project:
            return

        def _request() -> List[dict]:
            result = self._session.execute(
                """
                query GetAsset($project_id: Int!, $regex: String!) {
                    assets(
                        where: {
                            projects_id: {_eq: $project_id}, 
                            type: {_neq: ""}, 
                            name: {_iregex: $regex}
                        },
                        order_by: {name: asc}
                    ) {
                        id
                        type
                        name
                        level
                        category
                    }
                }""",
                {"project_id": self._project.id, "regex": regex},
            )
            items = result["assets"]
            return items

        def _result_callback(items: List[dict]):
            callback(list(map(self._create_asset_info_from_db_item, items)))

        RequestRunnable.execute(_request, _result_callback)

    def request_asset_details(
        self,
        asset_info: AssetInfo,
        callback: Callable[[Union[AssetDetails, None]], None],
    ):
        if self._project is None:
            return

        def _request() -> Union[dict, None]:
            result = self._session.execute(
                """
                query GetAsset($id: Int!) {
                    assets_by_pk(id: $id) {
                        thumbnail
                        component {
                            created_at
                            revisions (order_by: {created_at:desc}, limit: 1) {
                                created_at
                                version
                            }
                        }
                    }
                }""",
                {"id": asset_info.id},
            )
            item = result["assets_by_pk"]

            thumbnail = QtGui.QPixmap()
            thumbnail.loadFromData(base64.b64decode(item["thumbnail"].encode("utf-8")))

            component = item["component"]
            created_at = component["created_at"]

            revision = component["revisions"][0]
            version = revision["version"]
            modified_at = revision["created_at"]

            return dict(
                thumbnail=thumbnail,
                version=version,
                created_at=created_at,
                modified_at=modified_at,
            )

        def _result_callback(asset_details_dict: Union[dict, None]):
            asset_details: Union[AssetDetails, None] = None

            if asset_details_dict:
                fullname = "_".join(
                    (
                        val
                        for val in [
                            asset_info.type,
                            asset_info.level,
                            asset_info.category,
                            asset_info.name,
                        ]
                        if val
                    )
                )
                asset_details = AssetDetails(
                    fullname=fullname,
                    version=asset_details_dict["version"],
                    created_at=asset_details_dict["created_at"],
                    modified_at=asset_details_dict["modified_at"],
                    thumbnail=asset_details_dict["thumbnail"],
                )

            callback(asset_details)

        RequestRunnable.execute(_request, _result_callback)

    def load_asset_icon_pixmap(self, asset_id: int) -> Union[QtGui.QPixmap, None]:
        result = self._session.execute(
            """
            query GetAsset($id: Int!) {
                assets_by_pk(id: $id) {
                    icon
                }
            }""",
            {"id": asset_id},
        )
        item = result["assets_by_pk"]

        icon = item.get("icon")
        if icon is None:
            return

        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(base64.b64decode(item["icon"].encode("utf-8")))
        return pixmap

    def _create_asset_info_from_db_item(self, item: dict):
        return AssetInfo(
            id=item["id"],
            type=item["type"],
            name=item["name"],
            level=item.get("level"),
            category=item.get("category"),
        )
