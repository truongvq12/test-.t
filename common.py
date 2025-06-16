import base64
import json
from typing import Type

from azure.cosmos import ContainerProxy
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from httpx import Response

from core.constants import ENCODING_DEFAULT, DbCollectionType, PermissionType
from core.messages import get_message
from models.access_rights import AccessRight
from models.ai_models import AiModel
from models.chat_histories import ChatHistory
from models.comments import Comment
from models.group_targets import GroupTarget
from models.login_stats import LoginStat
from models.logs import Log
from models.meeting_minutes import MeetingMinutes
from models.messages import Message
from models.speaker_identifications import SpeakerIdentification
from models.summaries import Summary
from models.targets import Target
from models.teams import Team
from models.usage_stats import UsageStat
from models.users import User
from models.white_papers import WhitePaper
from repositories.base import ModelType
from schemas.users import UserToken

model_dict = {
    DbCollectionType.USER.value: User,
    DbCollectionType.TEAM.value: Team,
    DbCollectionType.TARGET.value: Target,
    DbCollectionType.SUMMARY.value: Summary,
    DbCollectionType.SPEAKER_IDENTIFICATION.value: SpeakerIdentification,
    DbCollectionType.WHITE_PAPER.value: WhitePaper,
    DbCollectionType.MEETING_MINUTES.value: MeetingMinutes,
    DbCollectionType.GROUP_TARGET.value: GroupTarget,
    DbCollectionType.COMMENT.value: Comment,
    DbCollectionType.CHAT_HISTORY.value: ChatHistory,
    DbCollectionType.USAGE_STAT.value: UsageStat,
    DbCollectionType.LOGIN_STAT.value: LoginStat,
    DbCollectionType.ACCESS_RIGHT.value: AccessRight,
    DbCollectionType.AI_MODEL.value: AiModel,
    DbCollectionType.MESSAGE.value: Message,
    DbCollectionType.LOG.value: Log,
}

FILTER = "c.collection_name = @collection_name"


def insert_dummy_data(
    engine: ContainerProxy,
    collection: DbCollectionType,
    data: list,
):
    # Convert email fields to lowercase for each item in data

    for item in data:
        if "email" in item:
            item["email"] = item["email"].lower()
        _ = model_dict[collection.value](**item)
        engine.upsert_item(_.model_dump())


def delete_dummy_data(
    engine: ContainerProxy, collection: DbCollectionType, delete_ids: list
):
    for item in delete_ids:
        _ = model_dict[collection.value](**item)
        engine.delete_item(item=_.id, partition_key=_.partition_key)


def query_db(
    engine: ContainerProxy, collection: DbCollectionType, query: str, parameters: dict
):
    parameters = [{"name": k, "value": v} for k, v in parameters.items()]
    result = engine.query_items(
        query=query, parameters=parameters, enable_cross_partition_query=True
    )
    return [model_dict[collection.value](**item) for item in result]


def delete_db(engine: ContainerProxy, item: Type[ModelType]):
    engine.delete_item(item=item.id, partition_key=item.partition_key)


def update_db(engine: ContainerProxy, item: Type[ModelType]):
    engine.upsert_item(item.model_dump())


def find_by_id(engine: ContainerProxy, collection: DbCollectionType, target_id: str):
    condition = [FILTER, "c.target_id = @target_id"]
    condition = " AND ".join(condition)
    query = f"SELECT TOP 1 * FROM c WHERE {condition}"
    parameters = {"@target_id": target_id, "@collection_name": collection.value}
    targets = query_db(engine, collection, query, parameters)
    return targets[0] if len(targets) > 0 else None


def login_test_user(
    client: TestClient,
    id: str,
    email: str,
    username: str,
    permission: PermissionType,
):
    user_token = UserToken(
        user_id=id,
        user_email=email,
        user_name=username,
        permission=permission,
        is_admin=permission == PermissionType.ADMIN,
    )
    groups = "ADMIN_GROUP_TEST" if user_token.is_admin else "USER_GROUP_TEST"
    client.cookies.set(
        "x_ms_client_principal",
        base64.b64encode(
            json.dumps(
                {
                    "claims": [
                        {"typ": "preferred_username", "val": user_token.user_email},
                        {"typ": "name", "val": user_token.user_name},
                        {"typ": "groups", "val": groups},
                        {"typ": "groups", "val": "guests"},
                    ],
                }
            ).encode(ENCODING_DEFAULT)
        ).decode(ENCODING_DEFAULT),
    )
    client.cookies.set("x_ms_client_principal_name", user_token.user_email)


def logout_test_user(client: TestClient):
    client.cookies.delete("x_ms_client_principal")
    client.cookies.delete("x_ms_client_principal_name")


def assert_401(response: Response):
    msg = get_message("E01008")
    response_json = response.json()
    assert response.status_code == 401
    assert response_json["success"] is False
    assert response_json["message"] == msg
    assert response_json["data"]["error_code"] == "E01008"
    assert response_json["data"]["message"] == msg


def assert_403(response: Response):
    msg = get_message("E01006")
    response_json = response.json()
    assert response.status_code == 403
    assert response_json["success"] is False
    assert response_json["message"] == msg
    assert response_json["data"]["error_code"] == "E01006"
    assert response_json["data"]["message"] == msg


def assert_404(response: Response):
    msg = get_message("E01007")
    response_json = response.json()
    assert response.status_code == 404
    assert response_json["success"] is False
    assert response_json["message"] == msg
    assert response_json["data"]["error_code"] == "E01007"
    assert response_json["data"]["message"] == msg


def assert_search_viewmore_and_favorites(expected_items, out_html):
    # Parse the HTML content
    html = BeautifulSoup(out_html["data"]["html_results"], "html.parser")

    # Find all tags with the `data-target-id` attribute
    elements = html.find_all("article", attrs={"data-target-id": True})

    # Get all `data-target-id` values from HTML
    data_target_ids = [element["data-target-id"] for element in elements]

    # Extract all target_id from expected_items
    expected_target_ids = [item["target_id"] for item in expected_items]

    # Check with desired value
    assert data_target_ids == expected_target_ids

    # Check the record count
    assert out_html["data"]["record_count"] == len(expected_target_ids)
    assert len(elements) == len(expected_target_ids)


def assert_search_group(expected_items, out_html):
    # Parse the HTML content
    html = BeautifulSoup(out_html["data"], "html.parser")

    # Find all tags with the `data-target-id` attribute
    elements = html.find_all("article", attrs={"data-target-id": True})

    # Get all `data-target-id` values from HTML
    data_target_ids = [element["data-target-id"] for element in elements]

    # Extract all target_id from expected_items
    expected_target_ids = [item["target_id"] for item in expected_items]

    # Check with desired value
    assert data_target_ids == expected_target_ids

    assert len(elements) == len(expected_target_ids)


def assert_search_user(expected_items, out_html):
    # Parse the HTML content
    html = BeautifulSoup(out_html["data"], "html.parser")

    # Find all rows in the table body
    rows = html.find("tbody").find_all("tr")

    # Extract the desired information from each row
    extracted_info = []
    for row in rows:
        user_name = row.find_all("td")[0].text.strip()
        email = row.find_all("td")[1].text.strip()
        select_element = row.find("select", {"id": "ai_model"})
        selected_option = select_element.find("option", selected=True)
        if not selected_option:
            selected_option = select_element.find("option")
        selected_id = selected_option["value"] if selected_option else None
        extracted_info.append(
            {"user_name": user_name, "email": email, "ai_model_id": selected_id}
        )

    user_name = [item["user_name"] for item in extracted_info]
    email = [item["email"] for item in extracted_info]
    ai_model_id = [item["ai_model_id"] for item in extracted_info]

    # Define the expected information
    expected_user_name = [item["username"] for item in expected_items]
    expected_email = [item["email"] for item in expected_items]
    expected_ai_model_id = [item["ai_model_id"] for item in expected_items]

    # Check with desired value
    assert user_name == expected_user_name
    assert email == expected_email
    assert ai_model_id == expected_ai_model_id

    assert len(extracted_info) == len(expected_items)


def assert_search_data_empty(expected_text, out_html):
    # Parse the HTML content
    html = BeautifulSoup(out_html["data"], "html.parser")

    # Find the span tag containing the text
    span_tag = html.find("span", class_="fs-6 mb-5 p-2 border-0")

    # Extract the text from the span tag
    extracted_text = span_tag.text.strip() if span_tag else None

    # Check with desired value
    assert extracted_text == expected_text


def assert_search_viewmore_and_favorites_data_empty(expected_text, out_html):
    # Parse the HTML content
    html = BeautifulSoup(out_html["data"]["html_results"], "html.parser")

    # Find the span tag containing the text
    span_tag = html.find("span", class_="fs-6 mb-5 p-2 border-0")

    # Extract the text from the span tag
    extracted_text = span_tag.text.strip() if span_tag else None

    # Check with desired value
    assert extracted_text == expected_text


def assert_search_team_data_empty(expected_items, out_html):
    # Parse the HTML content
    html = BeautifulSoup(out_html["data"], "html.parser")

    # Find all tags with the `data-target-id` attribute
    data_target_ids = html.find_all("article", attrs={"data-target-id": True})

    # Extract all target_id from expected_items
    expected_target_ids = [item["target_id"] for item in expected_items]

    # Check with desired value
    assert data_target_ids == expected_target_ids

    assert len(data_target_ids) == len(expected_target_ids)


def assert_search_team(expected_items, out_html):
    # Parse the HTML content
    html = BeautifulSoup(out_html["data"], "html.parser")

    # Find all tags with the `data-target-id` attribute
    elements = html.find_all("article", attrs={"data-target-id": True})

    # Get all `data-target-id` values from HTML
    data_target_ids = [element["data-target-id"] for element in elements]

    # Extract all target_id from expected_items
    expected_target_ids = [item["target_id"] for item in expected_items]

    # Check with desired value
    assert data_target_ids == expected_target_ids

    assert len(data_target_ids) == len(expected_target_ids)


def assert_home_init(expected_items, out_html, name_card):
    html = BeautifulSoup(out_html, "html.parser")

    articles_share = html.find_all(id=name_card)

    articles = []
    for element in articles_share:
        articles.extend(element.find_all("article", attrs={"data-target-id": True}))

    target_ids = [element["data-target-id"] for element in articles]

    # Extract all target_id from expected_items
    expected_target_ids = [item["target_id"] for item in expected_items]

    assert target_ids == expected_target_ids
    assert len(target_ids) == len(expected_target_ids)


def assert_personal_init_and_fav_init(expected_items, out_html):
    html = BeautifulSoup(out_html, "html.parser")

    articles = html.find_all("article", attrs={"data-target-id": True})

    target_ids = [element["data-target-id"] for element in articles]

    # Extract all target_id from expected_items
    expected_target_ids = [item["target_id"] for item in expected_items]

    assert target_ids == expected_target_ids
    assert len(target_ids) == len(expected_target_ids)
