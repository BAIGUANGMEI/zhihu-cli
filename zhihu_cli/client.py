"""Zhihu API client using requests.

Uses Zhihu's web API endpoints with cookie-based authentication.
All operations use HTTP requests, no browser automation needed after login.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from .config import DEFAULT_HEADERS, DEFAULT_TIMEOUT, ZHIHU_API_V4
from .exceptions import DataFetchError, LoginError

logger = logging.getLogger(__name__)


class ZhihuClient:
    """Requests-based Zhihu API client.

    Uses cookie authentication to access Zhihu's V4 API.
    """

    def __init__(self, cookie_dict: dict):
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)
        for name, value in cookie_dict.items():
            self._session.cookies.set(name, value, domain=".zhihu.com")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """Close the session."""
        self._session.close()
        logger.info("Session closed.")

    def _get(self, url: str, params: dict | None = None) -> Any:
        """Make a GET request and return JSON response."""
        try:
            resp = self._session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise DataFetchError(f"Request failed: {e}") from e

        if resp.status_code == 401:
            raise LoginError("Session expired or not logged in")
        if resp.status_code == 403:
            raise LoginError("Access denied — check login status")
        if resp.status_code != 200:
            raise DataFetchError(
                f"API request failed with status {resp.status_code}: {resp.text[:200]}"
            )

        try:
            return resp.json()
        except ValueError as e:
            raise DataFetchError(f"Invalid JSON response: {e}") from e

    # ===== Self Info =====

    def get_self_info(self) -> dict:
        """Get current user's profile info."""
        url = f"{ZHIHU_API_V4}/me"
        result = self._get(url)
        if not isinstance(result, dict):
            return {}
        return result

    # ===== Search =====

    def search(self, keyword: str, search_type: str = "general",
               offset: int = 0, limit: int = 20) -> dict:
        """Search Zhihu content.

        Args:
            keyword: Search keyword.
            search_type: Type of search ('general', 'topic', 'people').
            offset: Pagination offset.
            limit: Number of results per page.
        """
        url = f"{ZHIHU_API_V4}/search_v3"
        params = {
            "t": search_type,
            "q": keyword,
            "correction": 1,
            "offset": offset,
            "limit": limit,
        }
        return self._get(url, params=params)

    # ===== Hot List =====

    def get_hot_list(self, limit: int = 50) -> dict:
        """Get Zhihu hot list (热榜)."""
        url = f"{ZHIHU_API_V4}/creators/rank/hot"
        params = {"domain": "0", "limit": limit}
        try:
            result = self._get(url, params=params)
        except DataFetchError:
            # Fallback to billboard API
            url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
            params = {"limit": limit}
            result = self._get(url, params=params)

        if isinstance(result, dict):
            return result
        return {"data": result if isinstance(result, list) else []}

    # ===== Question Detail =====

    def get_question(self, question_id: str) -> dict:
        """Get question detail."""
        url = f"{ZHIHU_API_V4}/questions/{question_id}"
        params = {
            "include": (
                "data[*].author,answer_count,follower_count,"
                "visit_count,comment_count,created_time,"
                "updated_time,detail,topics"
            ),
        }
        return self._get(url, params=params)

    # ===== Question Answers =====

    def get_question_answers(self, question_id: str,
                             offset: int = 0, limit: int = 20,
                             sort_by: str = "default") -> dict:
        """Get answers for a question.

        Args:
            question_id: The question ID.
            offset: Pagination offset.
            limit: Number of answers per page.
            sort_by: Sort order ('default' or 'updated').
        """
        url = f"{ZHIHU_API_V4}/questions/{question_id}/answers"
        params = {
            "include": (
                "data[*].content,voteup_count,comment_count,"
                "created_time,updated_time,author"
            ),
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
        }
        return self._get(url, params=params)

    # ===== Answer Detail =====

    def get_answer(self, answer_id: str) -> dict:
        """Get a single answer detail."""
        url = f"{ZHIHU_API_V4}/answers/{answer_id}"
        params = {
            "include": (
                "content,voteup_count,comment_count,"
                "created_time,updated_time,author,question"
            ),
        }
        return self._get(url, params=params)

    # ===== User Profile =====

    def get_user_profile(self, url_token: str) -> dict:
        """Get user profile by url_token.

        Args:
            url_token: The user's URL token (e.g., 'excited-vibe' from zhihu.com/people/excited-vibe).
        """
        url = f"{ZHIHU_API_V4}/members/{url_token}"
        params = {
            "include": (
                "answer_count,articles_count,follower_count,"
                "following_count,voteup_count,thanked_count,"
                "favorite_count,favorited_count,"
                "gender,badge,description,business,educations,"
                "employments,locations"
            ),
        }
        return self._get(url, params=params)

    # ===== User Answers =====

    def get_user_answers(self, url_token: str,
                         offset: int = 0, limit: int = 20,
                         sort_by: str = "created") -> dict:
        """Get a user's answers.

        Args:
            url_token: The user's URL token.
            offset: Pagination offset.
            limit: Number of answers per page.
            sort_by: Sort order ('created' or 'voteups').
        """
        url = f"{ZHIHU_API_V4}/members/{url_token}/answers"
        params = {
            "include": (
                "data[*].content,voteup_count,comment_count,"
                "created_time,question"
            ),
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
        }
        return self._get(url, params=params)

    # ===== User Articles =====

    def get_user_articles(self, url_token: str,
                          offset: int = 0, limit: int = 20,
                          sort_by: str = "created") -> dict:
        """Get a user's articles (涓撴爮鏂囩珷).

        Args:
            url_token: The user's URL token.
            offset: Pagination offset.
            limit: Number of articles per page.
            sort_by: Sort order ('created' or 'voteups').
        """
        url = f"{ZHIHU_API_V4}/members/{url_token}/articles"
        params = {
            "include": (
                "data[*].content,voteup_count,comment_count,"
                "created_time,updated_time"
            ),
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
        }
        return self._get(url, params=params)

    # ===== Followers / Following =====

    def get_followers(self, url_token: str,
                      offset: int = 0, limit: int = 20) -> dict:
        """Get a user's followers."""
        url = f"{ZHIHU_API_V4}/members/{url_token}/followers"
        params = {
            "include": "data[*].answer_count,articles_count,follower_count",
            "offset": offset,
            "limit": limit,
        }
        return self._get(url, params=params)

    def get_following(self, url_token: str,
                      offset: int = 0, limit: int = 20) -> dict:
        """Get a user's following."""
        url = f"{ZHIHU_API_V4}/members/{url_token}/followees"
        params = {
            "include": "data[*].answer_count,articles_count,follower_count",
            "offset": offset,
            "limit": limit,
        }
        return self._get(url, params=params)

    # ===== Feed =====

    def get_feed(self, limit: int = 20) -> dict:
        """Get recommended feed from homepage."""
        url = "https://www.zhihu.com/api/v3/feed/topstory/recommend"
        params = {
            "page_number": 1,
            "limit": limit,
            "action": "down",
        }
        result = self._get(url, params=params)
        if isinstance(result, dict):
            return result
        return {"data": result if isinstance(result, list) else []}

    # ===== Topics =====

    def get_topic(self, topic_id: str) -> dict:
        """Get topic detail."""
        url = f"{ZHIHU_API_V4}/topics/{topic_id}"
        return self._get(url)

    def get_topic_hot_questions(self, topic_id: str,
                                offset: int = 0, limit: int = 10) -> dict:
        """Get hot questions under a topic."""
        url = f"{ZHIHU_API_V4}/topics/{topic_id}/feeds/essence"
        params = {"offset": offset, "limit": limit}
        return self._get(url, params=params)

    # ===== Comments =====

    def get_answer_comments(self, answer_id: str,
                            offset: int = 0, limit: int = 20,
                            order: str = "normal") -> dict:
        """Get comments on an answer.

        Args:
            answer_id: The answer ID.
            offset: Pagination offset.
            limit: Number of comments per page.
            order: Sort order ('normal' or 'reverse').
        """
        url = f"{ZHIHU_API_V4}/answers/{answer_id}/comments"
        params = {
            "offset": offset,
            "limit": limit,
            "order": order,
            "status": "open",
        }
        return self._get(url, params=params)

    # ===== Vote =====

    def vote_up(self, answer_id: str) -> bool:
        """Vote up an answer."""
        url = f"{ZHIHU_API_V4}/answers/{answer_id}/voters"
        try:
            resp = self._session.post(url, json={"type": "up"}, timeout=DEFAULT_TIMEOUT)
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.error("Vote up failed: %s", e)
            return False

    def vote_neutral(self, answer_id: str) -> bool:
        """Cancel vote on an answer."""
        url = f"{ZHIHU_API_V4}/answers/{answer_id}/voters"
        try:
            resp = self._session.post(url, json={"type": "neutral"}, timeout=DEFAULT_TIMEOUT)
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.error("Vote cancel failed: %s", e)
            return False

    # ===== Follow Question =====

    def follow_question(self, question_id: str) -> bool:
        """Follow a question."""
        url = f"{ZHIHU_API_V4}/questions/{question_id}/followers"
        try:
            resp = self._session.post(url, timeout=DEFAULT_TIMEOUT)
            return resp.status_code in (200, 204)
        except requests.RequestException as e:
            logger.error("Follow question failed: %s", e)
            return False

    def unfollow_question(self, question_id: str) -> bool:
        """Unfollow a question."""
        url = f"{ZHIHU_API_V4}/questions/{question_id}/followers"
        try:
            resp = self._session.delete(url, timeout=DEFAULT_TIMEOUT)
            return resp.status_code in (200, 204)
        except requests.RequestException as e:
            logger.error("Unfollow question failed: %s", e)
            return False

    # ===== Collections =====

    def get_collections(self, offset: int = 0, limit: int = 20) -> dict:
        """Get current user's collections."""
        me = self.get_self_info()
        url_token = me.get("url_token", "")
        if not url_token:
            raise LoginError("Cannot retrieve user info — confirm login status")
        url = f"{ZHIHU_API_V4}/members/{url_token}/favlists"
        params = {"offset": offset, "limit": limit}
        return self._get(url, params=params)

    # ===== Notifications =====

    def get_notifications(self, limit: int = 20) -> dict:
        """Get user notifications."""
        url = f"{ZHIHU_API_V4}/notifications"
        params = {"limit": limit}
        return self._get(url, params=params)
