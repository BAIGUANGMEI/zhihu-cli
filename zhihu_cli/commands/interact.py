"""Interaction commands: vote, follow-question, ask, pin, collections, notifications."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse

import click

from ..auth import cookie_str_to_dict, get_cookie_string
from ..display import (
    console,
    format_count,
    make_table,
    print_error,
    print_hint,
    print_info,
    print_success,
    print_warning,
    strip_html,
)


@contextmanager
def _get_client():
    from ..client import ZhihuClient

    cookie = get_cookie_string()
    if not cookie:
        print_error("Not authenticated — run [bold]zhihu login[/bold]")
        sys.exit(1)
    with ZhihuClient(cookie_str_to_dict(cookie)) as client:
        yield client


@click.command()
@click.argument("answer_id", type=int)
@click.option("--up", "action", flag_value="up", default=True, help="Upvote (default)")
@click.option("--neutral", "action", flag_value="neutral", help="Cancel vote")
def vote(answer_id: int, action: str):
    """Vote on an answer."""
    with _get_client() as client:
        try:
            if action == "up":
                client.vote_up(answer_id)
                print_success(f"Upvoted answer [bold]{answer_id}[/bold]")
            else:
                client.vote_neutral(answer_id)
                print_success(f"Cancelled vote on answer [bold]{answer_id}[/bold]")
        except Exception as e:
            print_error(f"Vote failed: {e}")
            sys.exit(1)


@click.command("follow-question")
@click.argument("question_id", type=int)
@click.option("--unfollow", is_flag=True, help="Unfollow instead")
def follow_question(question_id: int, unfollow: bool):
    """Follow or unfollow a question."""
    with _get_client() as client:
        try:
            if unfollow:
                client.unfollow_question(question_id)
                print_success(f"Unfollowed question [bold]{question_id}[/bold]")
            else:
                client.follow_question(question_id)
                print_success(f"Followed question [bold]{question_id}[/bold]")
        except Exception as e:
            print_error(f"Operation failed: {e}")
            sys.exit(1)


@click.command()
@click.option("-l", "--limit", default=10, help="Number of items", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def collections(limit: int, as_json: bool):
    """List your collections (收藏夹)."""
    with _get_client() as client:
        try:
            results = client.get_collections(limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch collections: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No collections found")
            return

        table = make_table(" My Collections ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", ratio=1)
        table.add_column("Items", width=10, justify="right")

        for i, col in enumerate(data, 1):
            title = col.get("title", "—")
            count = format_count(col.get("item_count", col.get("answer_count", 0)))
            table.add_row(str(i), title, count)

        console.print()
        console.print(table)
        console.print()


def _format_notification_line(n: dict) -> str:
    """Format a single notification (v2/recent) for display."""
    content = n.get("content") or {}
    actors = content.get("actors") or []
    verb = (content.get("verb") or "").strip()
    target = content.get("target") or {}
    target_text = strip_html(target.get("text", ""))
    names = ", ".join(a.get("name", "") for a in actors if a.get("name"))
    if names and verb:
        line = f"{names} {verb}"
    elif target_text:
        line = target_text
    else:
        line = verb or "—"
    if target_text and line != target_text:
        line = f"{line} · {target_text}"
    return line.strip() or "—"


@click.command()
@click.option("-l", "--limit", default=10, help="Number of items", show_default=True)
@click.option("--offset", default=0, help="Pagination offset (from paging.next)", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def notifications(limit: int, offset: int, as_json: bool):
    """Show recent notifications (v2/recent)."""
    with _get_client() as client:
        try:
            results = client.get_notifications(limit=limit, offset=offset)
            data = results.get("data", [])
            paging = results.get("paging", {})
        except Exception as e:
            print_error(f"Failed to fetch notifications: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No notifications")
            return

        table = make_table(" Notifications ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Read", width=5)
        table.add_column("Content", ratio=1)

        for i, n in enumerate(data, 1):
            is_read = "✓" if n.get("is_read") else "·"
            line = _format_notification_line(n)
            table.add_row(str(i), is_read, line)

        console.print()
        console.print(table)
        next_url = paging.get("next") or ""
        if not paging.get("is_end") and next_url and "offset=" in next_url:
            try:
                qs = parse_qs(urlparse(next_url).query)
                next_offset = (qs.get("offset") or [None])[0]
                if next_offset:
                    print_hint(f"Next page: zhihu notifications --offset {next_offset} -l {limit}")
            except Exception:
                pass
        console.print()


@click.command()
@click.argument("title")
@click.option("-d", "--detail", default="", help="Question description")
@click.option("-t", "--topic", "topics", multiple=True, help="Topic ID (repeatable)")
@click.option("-i", "--image", "images", multiple=True, help="Image file path (repeatable)")
def ask(title: str, detail: str, topics: tuple[str, ...], images: tuple[str, ...]):
    """Post a new question (发布提问)."""
    if not title.strip():
        print_error("Title cannot be empty")
        sys.exit(1)

    with _get_client() as client:
        try:
            image_infos = None
            if images:
                image_infos = []
                for img_path in images:
                    print_info(f"Uploading image: {img_path}")
                    info = client.upload_image(img_path, source="question")
                    image_infos.append(info)

            result = client.create_question(
                title=title.strip(),
                detail=detail,
                topic_ids=list(topics) if topics else None,
                image_infos=image_infos,
            )
            qid = result.get("id", "")
            if qid:
                print_success(
                    f"Question created!  ID: [bold]{qid}[/bold]\n"
                    f"  https://www.zhihu.com/question/{qid}"
                )
            else:
                print_warning("Question may have been created but no ID returned")
        except Exception as e:
            print_error(f"Failed to create question: {e}")
            sys.exit(1)


@click.command()
@click.argument("title")
@click.option("-c", "--content", default="", help="Pin body content (optional)")
@click.option("-i", "--image", "images", multiple=True, help="Image file path (repeatable)")
def pin(title: str, content: str, images: tuple[str, ...]):
    """Write a new pin / thought (发布想法). Title and content, payload similar to question."""
    if not title.strip():
        print_error("Title cannot be empty")
        sys.exit(1)

    with _get_client() as client:
        try:
            image_infos = None
            if images:
                image_infos = []
                for img_path in images:
                    print_info(f"Uploading image: {img_path}")
                    info = client.upload_image(img_path, source="pin")
                    image_infos.append(info)

            result = client.create_pin(
                title=title.strip(),
                content=content.strip(),
                image_infos=image_infos,
            )
            pid = result.get("id", "")
            if pid:
                print_success(
                    f"Pin published!  ID: [bold]{pid}[/bold]\n"
                    f"  https://www.zhihu.com/pin/{pid}"
                )
            else:
                print_warning("Pin may have been created but no ID returned")
        except Exception as e:
            print_error(f"Failed to create pin: {e}")
            sys.exit(1)


@click.command()
@click.argument("title")
@click.argument("content")
@click.option("-t", "--topic", "topics", multiple=True, help="Topic ID (repeatable)")
@click.option("-i", "--image", "images", multiple=True, help="Image file path (repeatable)")
def article(title: str, content: str, topics: tuple[str, ...], images: tuple[str, ...]):
    """Publish a new article (发布文章)."""
    if not title.strip():
        print_error("Title cannot be empty")
        sys.exit(1)
    if not content.strip():
        print_error("Content cannot be empty")
        sys.exit(1)

    with _get_client() as client:
        try:
            body = f"<p>{content.strip()}</p>"
            image_infos = None
            if images:
                image_infos = []
                for img_path in images:
                    print_info(f"Uploading image: {img_path}")
                    info = client.upload_image(img_path, source="article")
                    image_infos.append(info)

            result = client.create_article(
                title=title.strip(),
                content=body,
                image_infos=image_infos,
                topic_ids=list(topics) if topics else None,
            )
            aid = result.get("id", "")
            if aid:
                print_success(
                    f"Article published!  ID: [bold]{aid}[/bold]\n"
                    f"  https://zhuanlan.zhihu.com/p/{aid}"
                )
            else:
                print_warning("Article may have been published but no ID returned")
        except Exception as e:
            print_error(f"Failed to publish article: {e}")
            sys.exit(1)


@click.command("delete-question")
@click.argument("question_id", type=str)
@click.option("-y", "--yes", "skip_confirm", is_flag=True, help="Skip confirmation")
def delete_question(question_id: str, skip_confirm: bool):
    """Delete your own question (删除自己发布的提问)."""
    if not skip_confirm:
        click.confirm(f"Delete question {question_id}? This cannot be undone.", abort=True)
    with _get_client() as client:
        try:
            ok = client.delete_question(question_id)
            if ok:
                print_success(f"Question [bold]{question_id}[/bold] deleted")
            else:
                print_error("Delete request was not accepted by the server")
                sys.exit(1)
        except Exception as e:
            print_error(f"Delete failed: {e}")
            sys.exit(1)


@click.command("delete-pin")
@click.argument("pin_id", type=str)
@click.option("-y", "--yes", "skip_confirm", is_flag=True, help="Skip confirmation")
def delete_pin(pin_id: str, skip_confirm: bool):
    """Delete your own pin / thought (删除自己发布的想法)."""
    if not skip_confirm:
        click.confirm(f"Delete pin {pin_id}? This cannot be undone.", abort=True)
    with _get_client() as client:
        try:
            ok = client.delete_pin(pin_id)
            if ok:
                print_success(f"Pin [bold]{pin_id}[/bold] deleted")
            else:
                print_error("Delete request was not accepted by the server")
                sys.exit(1)
        except Exception as e:
            print_error(f"Delete failed: {e}")
            sys.exit(1)


@click.command("delete-article")
@click.argument("article_id", type=str)
@click.option("-y", "--yes", "skip_confirm", is_flag=True, help="Skip confirmation")
def delete_article_cmd(article_id: str, skip_confirm: bool):
    """Delete your own article (删除自己发布的文章)."""
    if not skip_confirm:
        click.confirm(f"Delete article {article_id}? This cannot be undone.", abort=True)
    with _get_client() as client:
        try:
            ok = client.delete_article(article_id)
            if ok:
                print_success(f"Article [bold]{article_id}[/bold] deleted")
            else:
                print_error("Delete request was not accepted by the server")
                sys.exit(1)
        except Exception as e:
            print_error(f"Delete failed: {e}")
            sys.exit(1)
