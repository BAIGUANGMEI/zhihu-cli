"""Tests for CLI commands via Click's CliRunner."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zhihu_cli.cli import cli

# Patch target — ZhihuClient is lazy-imported inside function bodies via
# ``from ..client import ZhihuClient``, so we patch the *source* module.
_CLIENT_PATCH = "zhihu_cli.client.ZhihuClient"


@pytest.fixture()
def runner():
    return CliRunner()


def _make_mock_client(**method_returns):
    """Build a MagicMock that works as a context-manager ZhihuClient."""
    mock = MagicMock()
    for method, retval in method_returns.items():
        getattr(mock, method).return_value = retval
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


# ── CLI group ──────────────────────────────────────────────────────────────────


class TestCliGroup:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "zhihu-cli" in result.output
        assert "login" in result.output
        assert "search" in result.output

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_all_commands_registered(self, runner):
        result = runner.invoke(cli, ["--help"])
        expected = [
            "login", "logout", "status", "whoami",
            "search", "hot", "question", "answer", "answers",
            "feed", "topic",
            "user", "user-answers", "user-articles",
            "followers", "following",
            "vote", "follow-question",
            "collections", "notifications",
        ]
        for cmd in expected:
            assert cmd in result.output, f"Command '{cmd}' not found in help output"


# ── Auth commands ──────────────────────────────────────────────────────────────


class TestStatusCommand:
    def test_status_not_authenticated(self, runner, tmp_config_dir):
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 1
        assert "Not authenticated" in result.output

    def test_status_authenticated(self, runner, saved_cookies):
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Authenticated" in result.output


class TestLogoutCommand:
    def test_logout_removes_cookies(self, runner, saved_cookies):
        result = runner.invoke(cli, ["logout"])
        assert result.exit_code == 0
        assert "Logged out" in result.output

    def test_logout_no_cookies(self, runner, tmp_config_dir):
        result = runner.invoke(cli, ["logout"])
        assert result.exit_code == 0
        assert "No saved credentials" in result.output


class TestLoginCommand:
    def test_login_with_valid_cookie(self, runner, tmp_config_dir):
        result = runner.invoke(cli, ["login", "--cookie", "z_c0=test_abc"])
        assert result.exit_code == 0
        assert "Cookie saved" in result.output

    def test_login_with_invalid_cookie(self, runner, tmp_config_dir):
        result = runner.invoke(cli, ["login", "--cookie", "_xsrf=only_this"])
        assert result.exit_code == 1
        assert "z_c0" in result.output

    def test_login_help(self, runner):
        result = runner.invoke(cli, ["login", "--help"])
        assert result.exit_code == 0
        assert "--qrcode" in result.output
        assert "--cookie" in result.output


class TestWhoamiCommand:
    def test_whoami_not_authenticated(self, runner, tmp_config_dir):
        result = runner.invoke(cli, ["whoami"])
        assert result.exit_code == 1
        assert "Not authenticated" in result.output

    def test_whoami_shows_profile(self, runner, saved_cookies, mock_user_info):
        mc = _make_mock_client(get_self_info=mock_user_info)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["whoami"])
            assert result.exit_code == 0
            assert "TestUser" in result.output

    def test_whoami_json(self, runner, saved_cookies, mock_user_info):
        mc = _make_mock_client(get_self_info=mock_user_info)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["whoami", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["name"] == "TestUser"
            assert data["answer_count"] == 42


# ── Content commands ───────────────────────────────────────────────────────────


class TestSearchCommand:
    def test_search_not_authenticated(self, runner, tmp_config_dir):
        result = runner.invoke(cli, ["search", "Python"])
        assert result.exit_code == 1

    def test_search_displays_results(self, runner, saved_cookies, mock_search_result):
        mc = _make_mock_client(search=mock_search_result)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["search", "Python"])
            assert result.exit_code == 0
            assert "Python" in result.output

    def test_search_json(self, runner, saved_cookies, mock_search_result):
        mc = _make_mock_client(search=mock_search_result)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["search", "Python", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "data" in data

    def test_search_no_results(self, runner, saved_cookies):
        mc = _make_mock_client(search={"data": []})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["search", "nonexistent_xyz"])
            assert result.exit_code == 0
            assert "No results" in result.output

    def test_search_help(self, runner):
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0
        assert "--type" in result.output
        assert "--limit" in result.output


class TestHotCommand:
    def test_hot_displays_table(self, runner, saved_cookies, mock_hot_list):
        mc = _make_mock_client(get_hot_list=mock_hot_list)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["hot", "--limit", "2"])
            assert result.exit_code == 0
            assert "Trending" in result.output

    def test_hot_json(self, runner, saved_cookies, mock_hot_list):
        mc = _make_mock_client(get_hot_list=mock_hot_list)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["hot", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "data" in data


class TestQuestionCommand:
    def test_question_displays(self, runner, saved_cookies):
        q_data = {
            "title": "Test Question Title",
            "detail": "Some detail",
            "answer_count": 5,
            "follower_count": 10,
            "visit_count": 100,
        }
        mc = _make_mock_client(get_question=q_data)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["question", "12345"])
            assert result.exit_code == 0
            assert "Test Question Title" in result.output


class TestAnswerCommand:
    def test_answer_displays(self, runner, saved_cookies):
        ans_data = {
            "content": "<p>This is the answer</p>",
            "author": {"name": "Author1"},
            "voteup_count": 42,
            "comment_count": 3,
        }
        mc = _make_mock_client(get_answer=ans_data)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["answer", "67890"])
            assert result.exit_code == 0
            assert "Author1" in result.output


# ── User commands ──────────────────────────────────────────────────────────────


class TestUserCommand:
    def test_user_displays_profile(self, runner, saved_cookies, mock_user_info):
        mc = _make_mock_client(get_user_profile=mock_user_info)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["user", "test-user"])
            assert result.exit_code == 0
            assert "TestUser" in result.output


class TestUserAnswersCommand:
    def test_user_answers_empty(self, runner, saved_cookies):
        mc = _make_mock_client(get_user_answers={"data": []})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["user-answers", "test-user"])
            assert result.exit_code == 0
            assert "No answers" in result.output

    def test_user_answers_with_data(self, runner, saved_cookies):
        answers = {
            "data": [
                {
                    "question": {"title": "Q1"},
                    "voteup_count": 10,
                },
            ],
        }
        mc = _make_mock_client(get_user_answers=answers)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["user-answers", "test-user"])
            assert result.exit_code == 0
            assert "Q1" in result.output


# ── Interact commands ──────────────────────────────────────────────────────────


class TestVoteCommand:
    def test_vote_up(self, runner, saved_cookies):
        mc = _make_mock_client(vote_up=True)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["vote", "12345"])
            assert result.exit_code == 0
            assert "Upvoted" in result.output

    def test_vote_neutral(self, runner, saved_cookies):
        mc = _make_mock_client(vote_neutral=True)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["vote", "--neutral", "12345"])
            assert result.exit_code == 0
            assert "Cancelled" in result.output


class TestFollowQuestionCommand:
    def test_follow(self, runner, saved_cookies):
        mc = _make_mock_client(follow_question=True)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["follow-question", "99999"])
            assert result.exit_code == 0
            assert "Followed" in result.output

    def test_unfollow(self, runner, saved_cookies):
        mc = _make_mock_client(unfollow_question=True)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["follow-question", "--unfollow", "99999"])
            assert result.exit_code == 0
            assert "Unfollowed" in result.output


class TestCollectionsCommand:
    def test_collections_empty(self, runner, saved_cookies):
        mc = _make_mock_client(get_collections={"data": []})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["collections"])
            assert result.exit_code == 0
            assert "No collections" in result.output


class TestNotificationsCommand:
    def test_notifications_empty(self, runner, saved_cookies):
        mc = _make_mock_client(get_notifications={"data": []})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["notifications"])
            assert result.exit_code == 0
            assert "No notifications" in result.output

    def test_notifications_with_data(self, runner, saved_cookies):
        notif_data = {
            "data": [
                {"content": {"text": "Someone liked your answer"}},
            ],
        }
        mc = _make_mock_client(get_notifications=notif_data)
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["notifications"])
            assert result.exit_code == 0
            assert "Notifications" in result.output


class TestAskCommand:
    def test_ask_success(self, runner, saved_cookies):
        mc = _make_mock_client(create_question={"id": 123456})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["ask", "What is Python?"])
            assert result.exit_code == 0
            assert "123456" in result.output

    def test_ask_with_detail_and_topics(self, runner, saved_cookies):
        mc = _make_mock_client(create_question={"id": 789})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(
                cli, ["ask", "Title", "-d", "Detail text", "-t", "100", "-t", "200"]
            )
            assert result.exit_code == 0
            assert "789" in result.output

    def test_ask_no_id_returned(self, runner, saved_cookies):
        mc = _make_mock_client(create_question={})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["ask", "Q"])
            assert result.exit_code == 0
            assert "may have been created" in result.output

    def test_ask_error(self, runner, saved_cookies):
        mc = _make_mock_client()
        mc.create_question.side_effect = Exception("API error")
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["ask", "Q"])
            assert result.exit_code != 0


class TestPinCommand:
    def test_pin_success(self, runner, saved_cookies):
        mc = _make_mock_client(create_pin={"id": 999})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["pin", "Hello world"])
            assert result.exit_code == 0
            assert "999" in result.output

    def test_pin_no_id_returned(self, runner, saved_cookies):
        mc = _make_mock_client(create_pin={})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["pin", "Text"])
            assert result.exit_code == 0
            assert "may have been created" in result.output

    def test_pin_error(self, runner, saved_cookies):
        mc = _make_mock_client()
        mc.create_pin.side_effect = Exception("API error")
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["pin", "Text"])
            assert result.exit_code != 0


class TestArticleCommand:
    def test_article_success(self, runner, saved_cookies):
        mc = _make_mock_client(create_article={"id": "art123"})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["article", "Title", "Body text"])
            assert result.exit_code == 0
            assert "art123" in result.output

    def test_article_no_id_returned(self, runner, saved_cookies):
        mc = _make_mock_client(create_article={})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["article", "Title", "Body"])
            assert result.exit_code == 0
            assert "may have been published" in result.output

    def test_article_with_topics(self, runner, saved_cookies):
        mc = _make_mock_client(create_article={"id": "art456"})
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(
                cli, ["article", "T", "B", "-t", "100", "-t", "200"]
            )
            assert result.exit_code == 0
            assert "art456" in result.output

    def test_article_error(self, runner, saved_cookies):
        mc = _make_mock_client()
        mc.create_article.side_effect = Exception("API error")
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["article", "T", "B"])
            assert result.exit_code != 0


class TestImageOptions:
    _SAMPLE_INFO = {
        "src": "https://pic-private.zhihu.com/v2-abc~q75.jpg?auth=x",
        "original_src": "https://pic-private.zhihu.com/v2-abc~q75.jpg?auth=y",
        "watermark": "watermark",
        "watermark_src": "",
    }

    def test_pin_with_image(self, runner, saved_cookies, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)
        mc = _make_mock_client(
            upload_image=self._SAMPLE_INFO,
            create_pin={"id": "pin_img_1"},
        )
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["pin", "Hello", "-i", str(img)])
            assert result.exit_code == 0
            assert "pin_img_1" in result.output
            mc.upload_image.assert_called_once_with(str(img), source="pin")
            mc.create_pin.assert_called_once_with(
                title="Hello", content="", image_infos=[self._SAMPLE_INFO]
            )

    def test_ask_with_image(self, runner, saved_cookies, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)
        mc = _make_mock_client(
            upload_image=self._SAMPLE_INFO,
            create_question={"id": 12345},
        )
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["ask", "What?", "-i", str(img)])
            assert result.exit_code == 0
            assert "12345" in result.output
            mc.upload_image.assert_called_once()

    def test_article_with_image(self, runner, saved_cookies, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)
        mc = _make_mock_client(
            upload_image=self._SAMPLE_INFO,
            create_article={"id": "art_img_1"},
        )
        with patch(_CLIENT_PATCH, return_value=mc):
            result = runner.invoke(cli, ["article", "Title", "Body", "-i", str(img)])
            assert result.exit_code == 0
            assert "art_img_1" in result.output
            mc.upload_image.assert_called_once()
