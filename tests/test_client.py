"""Tests for zhihu_cli.client module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from zhihu_cli.client import ZhihuClient
from zhihu_cli.config import DEFAULT_TIMEOUT, ZHIHU_API_V4, ZHIHU_CONTENT_DRAFTS_URL, ZHIHU_CONTENT_PUBLISH_URL
from zhihu_cli.exceptions import DataFetchError, LoginError


@pytest.fixture()
def client():
    """Create a ZhihuClient with dummy cookies."""
    c = ZhihuClient({"z_c0": "test_token"})
    yield c
    c.close()


def _make_response(status_code=200, json_data=None, text=""):
    """Create a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


# ── Context manager ───────────────────────────────────────────────────────────


class TestClientContextManager:
    def test_enter_returns_self(self):
        c = ZhihuClient({"z_c0": "token"})
        with c as client:
            assert client is c

    def test_exit_closes_session(self):
        c = ZhihuClient({"z_c0": "token"})
        with patch.object(c._session, "close") as mock_close:
            with c:
                pass
            mock_close.assert_called_once()


# ── _get error handling ───────────────────────────────────────────────────────


class TestClientGet:
    def test_401_raises_login_error(self, client):
        with patch.object(client._session, "get", return_value=_make_response(401)):
            with pytest.raises(LoginError):
                client._get("https://example.com")

    def test_403_raises_login_error(self, client):
        with patch.object(client._session, "get", return_value=_make_response(403)):
            with pytest.raises(LoginError):
                client._get("https://example.com")

    def test_500_raises_data_fetch_error(self, client):
        with patch.object(
            client._session, "get",
            return_value=_make_response(500, text="Internal Server Error"),
        ):
            with pytest.raises(DataFetchError, match="500"):
                client._get("https://example.com")

    def test_request_exception_raises_data_fetch_error(self, client):
        with patch.object(
            client._session, "get",
            side_effect=requests.ConnectionError("Connection refused"),
        ):
            with pytest.raises(DataFetchError, match="Request failed"):
                client._get("https://example.com")

    def test_invalid_json_raises_data_fetch_error(self, client):
        resp = _make_response(200)
        resp.json.side_effect = ValueError("No JSON")
        with patch.object(client._session, "get", return_value=resp):
            with pytest.raises(DataFetchError, match="Invalid JSON"):
                client._get("https://example.com")

    def test_200_returns_json(self, client):
        data = {"name": "test"}
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=data),
        ):
            result = client._get("https://example.com")
            assert result == data


# ── get_self_info ──────────────────────────────────────────────────────────────


class TestGetSelfInfo:
    def test_returns_user_dict(self, client, mock_user_info):
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=mock_user_info),
        ):
            result = client.get_self_info()
            assert result["name"] == "TestUser"
            assert result["answer_count"] == 42

    def test_returns_empty_dict_for_non_dict(self, client):
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=[]),
        ):
            result = client.get_self_info()
            assert result == {}


# ── search ─────────────────────────────────────────────────────────────────────


class TestSearch:
    def test_search_calls_api(self, client, mock_search_result):
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=mock_search_result),
        ) as mock_get:
            result = client.search("Python", search_type="general", limit=5)
            assert len(result["data"]) == 2

            call_args = mock_get.call_args
            assert "search_v3" in call_args[0][0]
            assert call_args[1]["params"]["q"] == "Python"
            assert call_args[1]["params"]["limit"] == 5


# ── get_hot_list ───────────────────────────────────────────────────────────────


class TestGetHotList:
    def test_returns_dict_with_data(self, client, mock_hot_list):
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=mock_hot_list),
        ):
            result = client.get_hot_list(limit=2)
            assert "data" in result
            assert len(result["data"]) == 2

    def test_fallback_on_error(self, client, mock_hot_list):
        call_count = 0
        original_data = mock_hot_list

        def side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails
                return _make_response(500, text="Error")
            # Fallback succeeds
            return _make_response(200, json_data=original_data)

        with patch.object(client._session, "get", side_effect=side_effect):
            result = client.get_hot_list()
            assert "data" in result

    def test_wraps_list_result(self, client):
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=[{"q": "test"}]),
        ):
            result = client.get_hot_list()
            assert isinstance(result, dict)
            assert "data" in result


# ── get_question ───────────────────────────────────────────────────────────────


class TestGetQuestion:
    def test_question_api_url(self, client):
        q_data = {"title": "Test Q", "answer_count": 5}
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=q_data),
        ) as mock_get:
            result = client.get_question("12345")
            assert result["title"] == "Test Q"
            assert "questions/12345" in mock_get.call_args[0][0]


# ── get_question_answers ──────────────────────────────────────────────────────


class TestGetQuestionAnswers:
    def test_returns_answers(self, client):
        ans_data = {"data": [{"id": 1, "voteup_count": 10}]}
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=ans_data),
        ):
            result = client.get_question_answers("12345", limit=5)
            assert len(result["data"]) == 1

    def test_sort_by_param(self, client):
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data={"data": []}),
        ) as mock_get:
            client.get_question_answers("12345", sort_by="created")
            params = mock_get.call_args[1]["params"]
            assert params["sort_by"] == "created"


# ── get_answer ─────────────────────────────────────────────────────────────────


class TestGetAnswer:
    def test_answer_api_url(self, client):
        ans = {"content": "Answer content", "voteup_count": 100}
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=ans),
        ) as mock_get:
            result = client.get_answer("67890")
            assert result["voteup_count"] == 100
            assert "answers/67890" in mock_get.call_args[0][0]


# ── get_user_profile ──────────────────────────────────────────────────────────


class TestGetUserProfile:
    def test_returns_profile(self, client, mock_user_info):
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=mock_user_info),
        ) as mock_get:
            result = client.get_user_profile("test-user")
            assert result["name"] == "TestUser"
            assert "members/test-user" in mock_get.call_args[0][0]


# ── vote ───────────────────────────────────────────────────────────────────────


class TestVote:
    def test_vote_up_success(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(200),
        ) as mock_post:
            result = client.vote_up("12345")
            assert result is True
            call_args = mock_post.call_args
            assert "voters" in call_args[0][0]
            assert call_args[1]["json"] == {"type": "up"}

    def test_vote_up_failure(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(403),
        ):
            result = client.vote_up("12345")
            assert result is False

    def test_vote_neutral(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(200),
        ):
            result = client.vote_neutral("12345")
            assert result is True

    def test_vote_network_error(self, client):
        with patch.object(
            client._session, "post",
            side_effect=requests.ConnectionError("timeout"),
        ):
            result = client.vote_up("12345")
            assert result is False


# ── follow_question ────────────────────────────────────────────────────────────


class TestFollowQuestion:
    def test_follow_success(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(200),
        ):
            assert client.follow_question("99999") is True

    def test_follow_204(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(204),
        ):
            assert client.follow_question("99999") is True

    def test_unfollow_success(self, client):
        with patch.object(
            client._session, "delete",
            return_value=_make_response(200),
        ):
            assert client.unfollow_question("99999") is True

    def test_follow_network_error(self, client):
        with patch.object(
            client._session, "post",
            side_effect=requests.ConnectionError("err"),
        ):
            assert client.follow_question("99999") is False


# ── get_feed ───────────────────────────────────────────────────────────────────


class TestGetFeed:
    def test_returns_dict(self, client):
        feed_data = {"data": [{"type": "answer"}]}
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=feed_data),
        ):
            result = client.get_feed(limit=5)
            assert isinstance(result, dict)
            assert "data" in result

    def test_wraps_list_result(self, client):
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data=[{"type": "answer"}]),
        ):
            result = client.get_feed()
            assert isinstance(result, dict)
            assert "data" in result


# ── get_collections ────────────────────────────────────────────────────────────


class TestGetCollections:
    def test_raises_when_no_url_token(self, client):
        with patch.object(
            client._session, "get",
            return_value=_make_response(200, json_data={}),
        ):
            with pytest.raises(LoginError):
                client.get_collections()

    def test_returns_collections(self, client):
        me_data = {"url_token": "test-user"}
        fav_data = {"data": [{"title": "My Collection", "item_count": 5}]}
        call_count = 0

        def side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if url.endswith("/me"):
                return _make_response(200, json_data=me_data)
            return _make_response(200, json_data=fav_data)

        with patch.object(client._session, "get", side_effect=side_effect):
            result = client.get_collections()
            assert len(result["data"]) == 1


# ── create_question ────────────────────────────────────────────────────────────


class TestCreateQuestion:
    def test_success(self, client):
        resp_data = {"id": 123456}
        with patch.object(
            client._session, "post",
            return_value=_make_response(200, json_data=resp_data),
        ) as mock_post:
            result = client.create_question("Test question")
            assert result == {"id": 123456}
            call_args = mock_post.call_args
            assert "questions" in call_args[0][0]
            payload = call_args[1]["json"]
            assert payload["title"] == "Test question"

    def test_with_detail_and_topics(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(201, json_data={"id": 789}),
        ) as mock_post:
            result = client.create_question("Q", detail="Detail", topic_ids=["1", "2"])
            assert result["id"] == 789
            payload = mock_post.call_args[1]["json"]
            assert payload["detail"] == "Detail"
            assert payload["topic_url_tokens"] == ["1", "2"]

    def test_401_raises_login_error(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(401),
        ):
            with pytest.raises(LoginError):
                client.create_question("Q")

    def test_failure_status(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(400, text="Bad Request"),
        ):
            with pytest.raises(DataFetchError):
                client.create_question("Q")

    def test_network_error(self, client):
        with patch.object(
            client._session, "post",
            side_effect=requests.ConnectionError("err"),
        ):
            with pytest.raises(DataFetchError):
                client.create_question("Q")

    def test_with_images_uses_content_publish(self, client):
        """Question with images routes through /content/publish."""
        publish_resp = _make_response(200, json_data={
            "code": 0,
            "data": {"result": '{"id": "q999", "type": "question"}'},
        })
        image_info = {
            "src": "https://pic-private.zhihu.com/v2-abc~q75.jpg?auth=x",
            "original_src": "https://pic-private.zhihu.com/v2-abc~q75.jpg?auth=y",
            "watermark": "watermark",
            "watermark_src": "",
        }
        with patch.object(
            client._session, "post",
            return_value=publish_resp,
        ) as mock_post:
            result = client.create_question(
                "Title?", detail="Desc",
                image_infos=[image_info],
            )
            assert result["id"] == "q999"
            call_url = mock_post.call_args[0][0]
            assert "content/publish" in call_url
            payload = mock_post.call_args[1]["json"]
            assert payload["action"] == "question"
            assert payload["data"]["title"]["title"] == "Title?"
            assert "v2-abc" in payload["data"]["hybrid"]["html"]


# ── create_pin ─────────────────────────────────────────────────────────────────


class TestCreatePin:
    def test_success(self, client):
        """Pin without images uses content/publish: draft then publish with title + hybrid."""
        draft_resp = _make_response(200, json_data={"data": {"content_id": "draft_pin_1"}})
        publish_resp = _make_response(200, json_data={
            "code": 0,
            "data": {"result": '{"id": 999, "type": "pin"}'},
        })
        with patch.object(
            client._session, "post",
            side_effect=[draft_resp, publish_resp],
        ) as mock_post:
            result = client.create_pin("Hello world", "Some content")
            assert result["id"] == 999
            assert mock_post.call_count == 2
            publish_call = mock_post.call_args_list[1]
            payload = publish_call[1]["json"]
            assert payload["action"] == "pin"
            assert payload["data"]["title"]["title"] == "Hello world"
            assert payload["data"]["hybrid"]["html"] == "<p>Some content</p>"
            assert payload["data"]["hybrid"]["textLength"] == 12
            assert "draft" in payload["data"] and "publish" in payload["data"]
            assert "traceId" in payload["data"]["publish"]

    def test_success_title_only(self, client):
        draft_resp = _make_response(200, json_data={"data": {"content_id": "d1"}})
        publish_resp = _make_response(200, json_data={
            "code": 0,
            "data": {"result": '{"id": 111, "type": "pin"}'},
        })
        with patch.object(
            client._session, "post",
            side_effect=[draft_resp, publish_resp],
        ):
            result = client.create_pin("Pin text", "")
            assert result["id"] == 111

    def test_401_raises_login_error(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(401),
        ):
            with pytest.raises(LoginError):
                client.create_pin("text", "")

    def test_failure_status(self, client):
        draft_resp = _make_response(200, json_data={"data": {"content_id": "d1"}})
        fail_resp = _make_response(403, text="Forbidden")
        with patch.object(
            client._session, "post",
            side_effect=[draft_resp, fail_resp],
        ):
            with pytest.raises(DataFetchError):
                client.create_pin("text", "")

    def test_network_error(self, client):
        with patch.object(
            client._session, "post",
            side_effect=requests.ConnectionError("err"),
        ):
            with pytest.raises(DataFetchError):
                client.create_pin("text", "")


# ── create_article ──────────────────────────────────────────────────────────────


class TestCreateArticle:
    def test_success(self, client):
        draft_resp = _make_response(200, json_data={"id": "draft123"})
        patch_resp = _make_response(200)
        publish_resp = _make_response(200, json_data={"id": "draft123", "title": "T"})
        call_count = 0

        def post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return draft_resp

        with patch.object(client._session, "post", side_effect=post_side_effect), \
             patch.object(client._session, "patch", return_value=patch_resp), \
             patch.object(client._session, "put", return_value=publish_resp):
            result = client.create_article("Title", "Body")
            assert result["id"] == "draft123"

    def test_draft_401_raises_login_error(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(401),
        ):
            with pytest.raises(LoginError):
                client.create_article("T", "C")

    def test_draft_failure(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(500, text="Server Error"),
        ):
            with pytest.raises(DataFetchError):
                client.create_article("T", "C")

    def test_draft_network_error(self, client):
        with patch.object(
            client._session, "post",
            side_effect=requests.ConnectionError("err"),
        ):
            with pytest.raises(DataFetchError):
                client.create_article("T", "C")

    def test_patch_failure(self, client):
        draft_resp = _make_response(200, json_data={"id": "d1"})
        patch_resp = _make_response(500, text="err")
        with patch.object(client._session, "post", return_value=draft_resp), \
             patch.object(client._session, "patch", return_value=patch_resp):
            with pytest.raises(DataFetchError):
                client.create_article("T", "C")

    def test_publish_failure(self, client):
        draft_resp = _make_response(200, json_data={"id": "d1"})
        patch_resp = _make_response(200)
        publish_resp = _make_response(500, text="err")
        with patch.object(client._session, "post", return_value=draft_resp), \
             patch.object(client._session, "patch", return_value=patch_resp), \
             patch.object(client._session, "put", return_value=publish_resp):
            with pytest.raises(DataFetchError):
                client.create_article("T", "C")

    def test_with_images_uses_content_publish(self, client):
        """Article with images routes through /content/publish."""
        draft_resp = _make_response(200, json_data={
            "data": {"content_id": "draft_a1"},
        })
        publish_resp = _make_response(200, json_data={
            "code": 0,
            "data": {"result": '{"id": "art_img", "type": "article"}'},
        })
        image_info = {
            "src": "https://pic-private.zhihu.com/v2-xyz~q75.jpg?auth=x",
            "original_src": "https://pic-private.zhihu.com/v2-xyz~q75.jpg?auth=y",
            "watermark": "watermark",
            "watermark_src": "",
        }
        with patch.object(
            client._session, "post",
            side_effect=[draft_resp, publish_resp],
        ) as mock_post:
            result = client.create_article(
                "Title", "<p>Body</p>",
                image_infos=[image_info],
            )
            assert result["id"] == "art_img"
            publish_call = mock_post.call_args_list[1]
            call_url = publish_call[0][0]
            assert "content/publish" in call_url
            payload = publish_call[1]["json"]
            assert payload["action"] == "article"
            assert payload["data"]["title"]["title"] == "Title"
            assert "v2-xyz" in payload["data"]["hybrid"]["html"]
            assert payload["data"]["draft"]["id"] == "draft_a1"


# ── upload_image ────────────────────────────────────────────────────────────────


class TestUploadImage:
    def _poll_response(self):
        return _make_response(200, json_data={
            "status": "success",
            "src": "https://pic-private.zhihu.com/v2-abc123~q75.jpg?auth=x",
            "original_src": "https://pic-private.zhihu.com/v2-abc123~q75.jpg?auth=y",
            "watermark": "watermark",
            "watermark_src": "https://pic-private.zhihu.com/v2-wm~q75.jpg?auth=z",
        })

    def test_success_state_2(self, client, tmp_path):
        """Image not yet on server — full upload flow."""
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        register_resp = _make_response(200, json_data={
            "upload_file": {"image_id": "123", "object_key": "v2-abc123", "state": 2},
            "upload_token": {
                "access_key": "ak", "access_id": "aid", "access_token": "at",
            },
        })
        oss_resp = _make_response(200)
        poll_resp = self._poll_response()

        with patch.object(client._session, "post", return_value=register_resp), \
             patch.object(client._session, "get", return_value=poll_resp), \
             patch("requests.put", return_value=oss_resp) as mock_oss:
            result = client.upload_image(str(img_file))
            assert isinstance(result, dict)
            assert "pic-private.zhihu.com" in result["src"]
            mock_oss.assert_called_once()

    def test_success_state_1(self, client, tmp_path):
        """Image already exists — no OSS upload needed."""
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        register_resp = _make_response(200, json_data={
            "upload_file": {"image_id": "456", "state": 1},
        })
        poll_resp = self._poll_response()

        with patch.object(client._session, "post", return_value=register_resp), \
             patch.object(client._session, "get", return_value=poll_resp), \
             patch("requests.put") as mock_oss:
            result = client.upload_image(str(img_file))
            assert isinstance(result, dict)
            assert "src" in result
            mock_oss.assert_not_called()

    def test_file_not_found(self, client):
        with pytest.raises(DataFetchError, match="not found"):
            client.upload_image("/nonexistent/image.jpg")

    def test_register_failure(self, client, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        with patch.object(
            client._session, "post",
            return_value=_make_response(500, text="err"),
        ):
            with pytest.raises(DataFetchError):
                client.upload_image(str(img_file))

    def test_oss_upload_failure(self, client, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        register_resp = _make_response(200, json_data={
            "upload_file": {"image_id": "123", "object_key": "v2-abc", "state": 2},
            "upload_token": {
                "access_key": "ak", "access_id": "aid", "access_token": "at",
            },
        })
        with patch.object(client._session, "post", return_value=register_resp), \
             patch("requests.put", return_value=_make_response(403, text="Forbidden")):
            with pytest.raises(DataFetchError, match="OSS upload"):
                client.upload_image(str(img_file))

    def test_network_error(self, client, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        with patch.object(
            client._session, "post",
            side_effect=requests.ConnectionError("err"),
        ):
            with pytest.raises(DataFetchError):
                client.upload_image(str(img_file))


# ── create_pin with images ──────────────────────────────────────────────────────


class TestCreatePinWithImages:
    _SAMPLE_INFO = {
        "src": "https://pic-private.zhihu.com/v2-abc~q75.jpg?auth=x",
        "original_src": "https://pic-private.zhihu.com/v2-abc~q75.jpg?auth=y",
        "watermark": "watermark",
        "watermark_src": "",
    }

    def test_with_images_uses_content_publish(self, client):
        """Pin with images uses /content/publish endpoint; payload has title + hybrid like question."""
        draft_resp = _make_response(200, json_data={
            "data": {"content_id": "draft_p1"},
        })
        publish_resp = _make_response(200, json_data={
            "code": 0,
            "data": {"result": '{"id": "pin123", "type": "pin"}'},
        })
        with patch.object(
            client._session, "post",
            side_effect=[draft_resp, publish_resp],
        ) as mock_post:
            result = client.create_pin("My title", "Body content", image_infos=[self._SAMPLE_INFO])
            assert result["id"] == "pin123"
            publish_call = mock_post.call_args_list[1]
            call_url = publish_call[0][0]
            assert "content/publish" in call_url
            payload = publish_call[1]["json"]
            assert payload["data"]["draft"]["id"] == "draft_p1"
            assert payload["data"]["title"]["title"] == "My title"
            assert "hybrid" in payload["data"]
            assert "Body content" in payload["data"]["hybrid"]["html"]
            assert payload["data"]["hybrid"]["textLength"] == 12

    def test_without_images_uses_content_publish(self, client):
        """Pin without images uses content/publish (draft + publish), no media."""
        draft_resp = _make_response(200, json_data={"data": {"content_id": "draft_1"}})
        publish_resp = _make_response(200, json_data={
            "code": 0,
            "data": {"result": '{"id": 999, "type": "pin"}'},
        })
        with patch.object(
            client._session, "post",
            side_effect=[draft_resp, publish_resp],
        ) as mock_post:
            result = client.create_pin("text", "")
            assert result["id"] == 999
            assert mock_post.call_count == 2
            publish_call = mock_post.call_args_list[1]
            assert "content/publish" in publish_call[0][0]
            payload = publish_call[1]["json"]
            assert payload["data"].get("media") is None
            assert payload["data"]["title"]["title"] == "text"

    def test_with_images_401(self, client):
        with patch.object(
            client._session, "post",
            return_value=_make_response(401),
        ):
            with pytest.raises(LoginError):
                client.create_pin("text", "", image_infos=[self._SAMPLE_INFO])

    def test_with_images_failure(self, client):
        draft_resp = _make_response(200, json_data={
            "data": {"content_id": "draft_p2"},
        })
        publish_resp = _make_response(500, text="err")
        with patch.object(
            client._session, "post",
            side_effect=[draft_resp, publish_resp],
        ):
            with pytest.raises(DataFetchError):
                client.create_pin("text", "", image_infos=[self._SAMPLE_INFO])
