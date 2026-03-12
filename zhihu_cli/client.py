"""Zhihu API client using requests.

Uses Zhihu's web API endpoints with cookie-based authentication.
All operations use HTTP requests, no browser automation needed after login.
"""

from __future__ import annotations

import base64
import email.utils
import hashlib
import hmac
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from .config import (
    DEFAULT_TIMEOUT,
    get_browser_headers,
    ZHIHU_API_V4,
    ZHIHU_CONTENT_DRAFTS_URL,
    ZHIHU_CONTENT_PUBLISH_URL,
    ZHIHU_IMAGE_API,
    ZHIHU_OSS_UPLOAD_URL,
    ZHIHU_ZHUANLAN_API,
)
from .exceptions import DataFetchError, LoginError

logger = logging.getLogger(__name__)


class ZhihuClient:
    """Requests-based Zhihu API client.

    Uses cookie authentication to access Zhihu's V4 API.
    """

    def __init__(self, cookie_dict: dict):
        self._session = requests.Session()
        self._session.headers.update(get_browser_headers())
        for name, value in cookie_dict.items():
            self._session.cookies.set(name, value, domain=".zhihu.com")
        # CSRF token required by write APIs
        xsrf = cookie_dict.get("_xsrf", "")
        if xsrf:
            self._session.headers["x-xsrftoken"] = xsrf

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

    # ===== Image Upload =====

    def upload_image(self, file_path: str,
                     source: str = "article") -> dict:
        """Upload an image to Zhihu and return image info.

        Handles the full flow: register → OSS upload → poll → return info.

        Args:
            file_path: Path to the image file.
            source: Upload context ('article', 'pin', etc.).

        Returns:
            Dict with keys: src, original_src, watermark, watermark_src.
        """
        path = Path(file_path)
        if not path.is_file():
            raise DataFetchError(f"Image file not found: {file_path}")

        image_data = path.read_bytes()
        md5_hex = hashlib.md5(image_data).hexdigest()

        # Step 1: Register image with Zhihu
        try:
            resp = self._session.post(
                ZHIHU_IMAGE_API,
                json={"image_hash": md5_hex, "source": source},
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise DataFetchError(f"Image registration failed: {e}") from e
        if resp.status_code != 200:
            raise DataFetchError(
                f"Image registration failed ({resp.status_code}): {resp.text[:200]}"
            )
        data = resp.json()
        upload_file = data["upload_file"]
        image_id = upload_file["image_id"]
        state = upload_file["state"]

        # Step 2: Upload to OSS if needed
        if state == 2:
            obj_key = upload_file["object_key"]
            self._upload_to_oss(obj_key, image_data, data["upload_token"])
        elif state != 1:
            raise DataFetchError(f"Unexpected image state: {state}")

        # Step 3: Poll until image processing completes
        image_info = self._poll_image(str(image_id))

        # Step 4: Get image dimensions
        try:
            with Image.open(path) as img:
                image_info["width"], image_info["height"] = img.size
        except Exception:
            image_info.setdefault("width", 0)
            image_info.setdefault("height", 0)

        return image_info

    def _upload_to_oss(self, obj_key: str, data: bytes,
                       token: dict) -> None:
        """Upload image data to Alibaba Cloud OSS."""
        content_type = "image/jpeg"
        date = email.utils.formatdate(usegmt=True)
        security_token = token["access_token"]
        access_id = token["access_id"]
        access_key = token["access_key"]

        string_to_sign = (
            f"PUT\n\n{content_type}\n{date}\n"
            f"x-oss-security-token:{security_token}\n"
            f"/zhihu-pics/{obj_key}"
        )
        signature = base64.b64encode(
            hmac.new(
                access_key.encode(), string_to_sign.encode(), hashlib.sha1
            ).digest()
        ).decode()

        headers = {
            "Content-Type": content_type,
            "Date": date,
            "x-oss-security-token": security_token,
            "Authorization": f"OSS {access_id}:{signature}",
        }
        try:
            resp = requests.put(
                f"{ZHIHU_OSS_UPLOAD_URL}/{obj_key}",
                data=data, headers=headers, timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise DataFetchError(f"OSS upload failed: {e}") from e
        if resp.status_code != 200:
            raise DataFetchError(
                f"OSS upload failed ({resp.status_code}): {resp.text[:200]}"
            )

    def _poll_image(self, image_id: str, max_attempts: int = 15,
                    interval: float = 2.0) -> dict:
        """Poll image status until processing completes."""
        import time
        for _ in range(max_attempts):
            try:
                resp = self._session.get(
                    f"{ZHIHU_IMAGE_API}/{image_id}", timeout=DEFAULT_TIMEOUT,
                )
            except requests.RequestException as e:
                raise DataFetchError(f"Image poll failed: {e}") from e
            if resp.status_code != 200:
                raise DataFetchError(
                    f"Image poll failed ({resp.status_code}): {resp.text[:200]}"
                )
            data = resp.json()
            if data.get("status") == "success":
                return {
                    "src": data["src"],
                    "original_src": data["original_src"],
                    "watermark": data.get("watermark", "watermark"),
                    "watermark_src": data.get("watermark_src", ""),
                }
            time.sleep(interval)
        raise DataFetchError("Image processing timed out")

    # ===== Helpers =====

    @staticmethod
    def _build_img_html(image_infos: list[dict]) -> str:
        """Build HTML img tags from image info dicts."""
        tags = []
        for info in image_infos:
            src = info["src"]
            original = info.get("original_src", src)
            wm = info.get("watermark", "watermark")
            wm_src = info.get("watermark_src", "")
            w = info.get("width", 0)
            h = info.get("height", 0)
            tags.append(
                f'<img src="{src}" data-caption="" data-size="normal"'
                f' data-rawwidth="{w}" data-rawheight="{h}"'
                f' data-watermark="{wm}" data-original-src="{original}"'
                f' data-watermark-src="{wm_src}"'
                f' data-private-watermark-src=""/>'
            )
        return "".join(tags)

    def _create_content_draft(self, action: str) -> str:
        """Create a content draft and return the content_id."""
        try:
            resp = self._session.post(
                ZHIHU_CONTENT_DRAFTS_URL, json={"action": action},
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise DataFetchError(f"Create draft failed: {e}") from e
        if resp.status_code == 401:
            raise LoginError("Session expired or not logged in")
        if resp.status_code != 200:
            raise DataFetchError(
                f"Create draft failed ({resp.status_code}): {resp.text[:200]}"
            )
        data = resp.json()
        content_id = data.get("data", {}).get("content_id", "")
        if not content_id:
            raise DataFetchError("Draft created but no content_id returned")
        return str(content_id)

    def _content_publish(self, payload: dict) -> dict:
        """Post to the unified content/publish endpoint."""
        headers = {"x-requested-with": "fetch"}
        try:
            resp = self._session.post(
                ZHIHU_CONTENT_PUBLISH_URL, json=payload,
                headers=headers, timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise DataFetchError(f"Publish failed: {e}") from e

        if resp.status_code == 401:
            raise LoginError("Session expired or not logged in")
        if resp.status_code not in (200, 201):
            raise DataFetchError(
                f"Publish failed ({resp.status_code}): {resp.text[:200]}"
            )
        try:
            data = resp.json()
        except ValueError:
            return {}
        code = data.get("code")
        if code is not None and code != 0:
            msg = data.get("message") or data.get("toast_message") or "Unknown error"
            raise DataFetchError(f"Publish failed: {msg}")
        result_str = data.get("data", {}).get("result", "")
        if result_str:
            try:
                return json.loads(result_str)
            except (ValueError, TypeError):
                pass
        return data

    # ===== Create Question =====

    def create_question(self, title: str, detail: str = "",
                        topic_ids: list[str] | None = None,
                        image_infos: list[dict] | None = None) -> dict:
        """Create a new question.

        Args:
            title: Question title.
            detail: Question detail / description (HTML supported).
            topic_ids: List of topic IDs to tag on the question.
            image_infos: Optional list of image info dicts from upload_image.

        Returns:
            API response dict (contains question id on success).
        """
        if image_infos:
            html = detail + self._build_img_html(image_infos)
            payload = {
                "action": "question",
                "data": {
                    "title": {"title": title},
                    "topic": {"topics": list(topic_ids) if topic_ids else []},
                    "hybrid": {
                        "html": html,
                        "textLength": len(detail),
                    },
                    "extra_info": {"publisher": "pc"},
                    "questionConfig": {"type": "0"},
                    "draft": {"disabled": 1},
                },
            }
            return self._content_publish(payload)

        url = f"{ZHIHU_API_V4}/questions"
        payload_simple: dict[str, Any] = {
            "title": title,
            "detail": detail,
        }
        if topic_ids:
            payload_simple["topic_url_tokens"] = topic_ids
        try:
            resp = self._session.post(url, json=payload_simple, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise DataFetchError(f"Create question failed: {e}") from e

        if resp.status_code == 401:
            raise LoginError("Session expired or not logged in")
        if resp.status_code not in (200, 201):
            raise DataFetchError(
                f"Create question failed ({resp.status_code}): {resp.text[:200]}"
            )
        try:
            return resp.json()
        except ValueError:
            return {}

    # ===== Create Pin (想法) =====

    def create_pin(self, title: str, content: str = "",
                   image_infos: list[dict] | None = None) -> dict:
        """Create a new pin (想法).

        Args:
            title: Pin title (similar to question title).
            content: Pin body content (optional, HTML supported when using images).
            image_infos: Optional list of image info dicts from upload_image.

        Returns:
            API response dict (contains pin id on success).
        """
        if image_infos:
            return self._create_pin_with_images(title, content, image_infos)

        # No images: use content/publish API with same payload shape as with-images
        draft_id = self._create_content_draft("pin")
        body_html = f"<p>{content.strip()}</p>" if content.strip() else ""
        text_len = len(content.strip())
        payload = {
            "action": "pin",
            "data": {
                "publish": {
                    "traceId": f"{int(time.time() * 1000)},{uuid.uuid4()}",
                },
                "commentsPermission": {"comment_permission": "all"},
                "extra_info": {"view_permission": "all", "publisher": "pc"},
                "draft": {"disabled": 1, "id": draft_id},
                "title": {"title": title},
                "hybrid": {
                    "html": body_html,
                    "textLength": text_len,
                },
            },
        }
        return self._content_publish(payload)

    def _create_pin_with_images(self, title: str, content: str,
                                image_infos: list[dict]) -> dict:
        """Create a pin with images via the content/publish API.
        Payload structure aligned with question: title + hybrid (html/content).
        """
        draft_id = self._create_content_draft("pin")
        medias = [
            {
                "image": {
                    "width": info.get("width", 0),
                    "height": info.get("height", 0),
                    "url": info["src"],
                    "originalUrl": info.get("original_src", info["src"]),
                    "watermark": info.get("watermark", "watermark"),
                    "watermarkUrl": info.get("watermark_src", ""),
                }
            }
            for info in image_infos
        ]
        html = content + self._build_img_html(image_infos) if content else self._build_img_html(image_infos)
        payload = {
            "action": "pin",
            "data": {
                "publish": {"traceId": f"{int(time.time() * 1000)},{uuid.uuid4()}"},
                "commentsPermission": {"comment_permission": "all"},
                "extra_info": {"view_permission": "all", "publisher": "pc"},
                "draft": {"disabled": 1, "id": draft_id},
                "title": {"title": title},
                "hybrid": {
                    "html": html,
                    "textLength": len(title) + len(content),
                },
                "media": {"medias": medias},
            },
        }
        return self._content_publish(payload)

    # ===== Create Article (专栏文章) =====

    def create_article(self, title: str, content: str,
                        topic_ids: list[str] | None = None,
                        image_infos: list[dict] | None = None) -> dict:
        """Create and publish a new article.

        Workflow: create draft → set title/content → publish.
        When images are provided, uses the content/publish API instead.

        Args:
            title: Article title.
            content: Article body (HTML).
            topic_ids: Optional list of topic IDs.
            image_infos: Optional list of image info dicts from upload_image.

        Returns:
            API response dict (contains article id on success).
        """
        if image_infos:
            html = content + self._build_img_html(image_infos)
            draft_id = self._create_content_draft("article")
            payload = {
                "action": "article",
                "data": {
                    "title": {"title": title},
                    "hybrid": {
                        "html": html,
                        "textLength": len(content),
                    },
                    "extra_info": {"publisher": "pc"},
                    "draft": {"disabled": 1, "id": draft_id},
                    "commentsPermission": {"comment_permission": "anyone"},
                },
            }
            return self._content_publish(payload)

        base = ZHIHU_ZHUANLAN_API

        # Step 1: create draft
        try:
            resp = self._session.post(
                f"{base}/articles/drafts", json={}, timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise DataFetchError(f"Create article draft failed: {e}") from e
        if resp.status_code == 401:
            raise LoginError("Session expired or not logged in")
        if resp.status_code != 200:
            raise DataFetchError(
                f"Create article draft failed ({resp.status_code}): {resp.text[:200]}"
            )
        try:
            draft = resp.json()
        except ValueError as e:
            raise DataFetchError(f"Invalid draft response: {e}") from e
        draft_id = draft.get("id", "")
        if not draft_id:
            raise DataFetchError("Draft created but no ID returned")

        # Step 2: update draft with title and content
        patch_data: dict[str, Any] = {"title": title, "content": content}
        if topic_ids:
            patch_data["topics"] = topic_ids
        try:
            resp = self._session.patch(
                f"{base}/articles/{draft_id}/draft",
                json=patch_data,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise DataFetchError(f"Update article draft failed: {e}") from e
        if resp.status_code not in (200, 204):
            raise DataFetchError(
                f"Update article draft failed ({resp.status_code}): {resp.text[:200]}"
            )

        # Step 3: publish
        publish_data = {"column": None, "commentPermission": "anyone"}
        try:
            resp = self._session.put(
                f"{base}/articles/{draft_id}/publish",
                json=publish_data,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            raise DataFetchError(f"Publish article failed: {e}") from e
        if resp.status_code == 401:
            raise LoginError("Session expired or not logged in")
        if resp.status_code != 200:
            raise DataFetchError(
                f"Publish article failed ({resp.status_code}): {resp.text[:200]}"
            )
        try:
            return resp.json()
        except ValueError:
            return {}

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
