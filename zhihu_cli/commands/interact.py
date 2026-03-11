"""Interaction commands: vote, follow-question, collections, notifications."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager

import click

from ..auth import cookie_str_to_dict, get_cookie_string
from ..display import (
    console,
    format_count,
    make_table,
    print_error,
    print_info,
    print_success,
    strip_html,
    truncate,
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


@click.command()
@click.option("-l", "--limit", default=10, help="Number of items", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def notifications(limit: int, as_json: bool):
    """Show recent notifications."""
    with _get_client() as client:
        try:
            results = client.get_notifications(limit=limit)
            data = results.get("data", [])
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
        table.add_column("Content", ratio=1)

        for i, n in enumerate(data, 1):
            content = strip_html(n.get("content", {}).get("text", "—"))
            table.add_row(str(i), truncate(content, 80))

        console.print()
        console.print(table)
        console.print()
