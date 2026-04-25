"""Content browsing commands: search, hot, question, answer, feed, topic."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager

import click

from ..auth import cookie_str_to_dict, get_cookie_string
from ..display import (
    console,
    format_count,
    format_stats_line,
    make_table,
    print_error,
    print_hint,
    print_info,
    strip_html,
)


@contextmanager
def _get_client():
    """Create an authenticated ZhihuClient."""
    from ..client import ZhihuClient

    cookie = get_cookie_string()
    if not cookie:
        print_error("Not authenticated — run [bold]zhihu login[/bold]")
        sys.exit(1)
    with ZhihuClient(cookie_str_to_dict(cookie)) as client:
        yield client


@click.command()
@click.argument("query")
@click.option("-t", "--type", "search_type", default="general",
              type=click.Choice(["general", "people", "topic"]),
              help="Search scope")
@click.option("-l", "--limit", default=10, help="Max results", show_default=True)
@click.option("-a", "--answers", default=3, help="Answers per question (0=hide)", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def search(query: str, search_type: str, limit: int, answers: int, as_json: bool):
    """Search Zhihu content."""
    with _get_client() as client:
        try:
            results = client.search(query, search_type=search_type, limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Search failed: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info(f'No results for "{query}"')
            return

        for idx, item in enumerate(data, 1):
            obj = item.get("object", item)
            item_type = item.get("type", obj.get("type", "—"))
            item_id = str(obj.get("id", "—"))
            title = strip_html(obj.get("title", obj.get("name", "—")))

            console.print()
            console.print(f"[title]  {idx}. [{item_type}] {title}  [/title]")
            console.print(f"  [dim]ID: {item_id}[/dim]")

            # pick useful info snippet
            if "follower_count" in obj:
                console.print(f"  {format_count(obj['follower_count'])} followers")
            elif "excerpt" in obj:
                console.print(f"  {strip_html(obj['excerpt'])}")
            elif "answer_count" in obj:
                console.print(f"  {format_count(obj['answer_count'])} answers")

            # Show answers for answer/question type results
            if answers > 0 and item_type == "search_result" and item_id != "—":
                q_id = obj.get("question", {}).get("id", item_id)
                try:
                    ans_result = client.get_question_answers(
                        str(q_id), limit=answers,
                    )
                    ans_data = ans_result.get("data", [])
                except Exception:
                    ans_data = []

                if ans_data:
                    for a in ans_data:
                        a_author = a.get("author", {}).get("name", "—")
                        a_content = strip_html(a.get("excerpt", a.get("content", "")))
                        a_upvotes = format_count(a.get("voteup_count", 0))
                        console.print(
                            f"    [dim]{a_author}:[/dim] {a_content}  [dim]{a_upvotes} upvotes[/dim]"
                        )

        console.print()


@click.command()
@click.option("-l", "--limit", default=50, help="Number of hot questions", show_default=True)
@click.option("-a", "--answers", default=3, help="Answers per question (0=hide)", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def hot(limit: int, answers: int, as_json: bool):
    """Show trending questions (热榜)."""
    with _get_client() as client:
        try:
            results = client.get_hot_list(limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch hot list: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("Hot list is empty")
            return

        for idx, item in enumerate(data, 1):
            target = item.get("target", item.get("question", item))
            title = strip_html(target.get("title", "—"))
            q_id = target.get("id", "")
            reaction = item.get("reaction", {})
            heat = item.get("detail_text", "")
            if not heat:
                pv = reaction.get("pv", reaction.get("new_pv", 0))
                heat = format_count(pv) + " views" if pv else "—"

            console.print()
            console.print(f"[title]  {idx}. {title}  [/title]")
            console.print(f"  [dim]{heat}[/dim]")

            if answers > 0 and q_id:
                try:
                    ans_result = client.get_question_answers(
                        str(q_id), limit=answers,
                    )
                    ans_data = ans_result.get("data", [])
                except Exception:
                    ans_data = []

                if ans_data:
                    for a in ans_data:
                        a_author = a.get("author", {}).get("name", "—")
                        a_excerpt = strip_html(a.get("excerpt", a.get("content", "")))
                        a_upvotes = format_count(a.get("voteup_count", 0))
                        console.print(
                            f"    [dim]{a_author}:[/dim] {a_excerpt}  [dim]{a_upvotes} upvotes[/dim]"
                        )
                else:
                    console.print("    [dim]No answers[/dim]")

        console.print()


@click.command()
@click.argument("question_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def question(question_id: int, as_json: bool):
    """View question details."""
    with _get_client() as client:
        try:
            q = client.get_question(question_id)
        except Exception as e:
            print_error(f"Failed to fetch question: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(q, indent=2, ensure_ascii=False))
            return

        title = strip_html(q.get("title", "—"))
        detail = strip_html(q.get("detail", "—"))

        console.print()
        console.print(f"[title]  {title}  [/title]")
        console.print()
        if detail and detail != "—":
            console.print(detail)
            console.print()

        stats = format_stats_line({
            "Answers": q.get("answer_count", 0),
            "Followers": q.get("follower_count", 0),
            "Views": q.get("visit_count", 0),
        })
        console.print(stats)
        console.print()


@click.command()
@click.argument("question_id", type=int)
@click.option("-l", "--limit", default=5, help="Number of answers", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.option("--sort", "sort_by", default="default",
              type=click.Choice(["default", "created"]),
              help="Sort order")
def answers(question_id: int, limit: int, as_json: bool, sort_by: str):
    """List answers for a question."""
    with _get_client() as client:
        try:
            results = client.get_question_answers(question_id, limit=limit, sort_by=sort_by)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch answers: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No answers yet")
            return

        table = make_table(f" Answers — Q{question_id} ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Author", width=14)
        table.add_column("Excerpt", ratio=1)
        table.add_column("Upvotes", width=10, justify="right")

        for i, ans in enumerate(data, 1):
            author = ans.get("author", {}).get("name", "Anonymous")
            excerpt = strip_html(ans.get("excerpt", ans.get("content", "—")))
            upvotes = format_count(ans.get("voteup_count", 0))
            table.add_row(str(i), author, excerpt, f"[bold]{upvotes}[/bold]")

        console.print()
        console.print(table)
        console.print()


@click.command()
@click.argument("answer_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.option("-c", "--comments", is_flag=True, help="Show comments")
@click.option("-l", "--limit", default=0, help="Number of comments (0=all)", show_default=True)
def answer(answer_id: int, as_json: bool, comments: bool, limit: int):
    """Read a specific answer."""
    with _get_client() as client:
        try:
            ans = client.get_answer(answer_id)
        except Exception as e:
            print_error(f"Failed to fetch answer: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(ans, indent=2, ensure_ascii=False))
            return

        author = ans.get("author", {}).get("name", "Anonymous")
        content = strip_html(ans.get("content", "—"))

        console.print()
        console.print(f"[title]  Answer by {author}  [/title]")
        console.print()
        console.print(content)
        console.print()

        stats = format_stats_line({
            "Upvotes": ans.get("voteup_count", 0),
            "Comments": ans.get("comment_count", 0),
        })
        console.print(stats)
        console.print()

        if comments:
            try:
                if limit <= 0:
                    # Fetch all comments via pagination
                    all_comments = []
                    offset = 0
                    page_size = 20
                    while True:
                        result = client.get_answer_comments(
                            str(answer_id), offset=offset, limit=page_size,
                        )
                        c_data = result.get("data", [])
                        all_comments.extend(c_data)
                        paging = result.get("paging", {})
                        if paging.get("is_end", True) or not c_data:
                            break
                        offset += len(c_data)
                    c_data = all_comments
                else:
                    result = client.get_answer_comments(str(answer_id), limit=limit)
                    c_data = result.get("data", [])
            except Exception as e:
                print_error(f"Failed to fetch comments: {e}")
                return

            if not c_data:
                print_info("No comments")
                return

            for i, c in enumerate(c_data, 1):
                c_content = strip_html(c.get("content", ""))
                c_likes = format_count(c.get("vote_count", 0))
                console.print(f"  [dim]{i}.[/dim] {c_content}  [dim]{c_likes} likes[/dim]")
            console.print()


@click.command()
@click.option("-l", "--limit", default=10, help="Number of items", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def feed(limit: int, as_json: bool):
    """Show recommended feed (推荐)."""
    with _get_client() as client:
        try:
            results = client.get_feed(limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch feed: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("Feed is empty")
            return

        table = make_table(" Recommended Feed ")
        table.add_column("ID", style="dim", min_width=12)
        table.add_column("Type", width=8)
        table.add_column("Title / Excerpt", ratio=1)
        table.add_column("Author", width=14)

        for item in data:
            target = item.get("target", {})
            item_type = target.get("type", "—")
            item_id = str(target.get("id", "—"))
            title = strip_html(
                target.get("title", "")
                or target.get("question", {}).get("title", "")
                or strip_html(target.get("excerpt", "—"))
            )
            author = target.get("author", {}).get("name", "—")
            table.add_row(item_id, item_type, title, author)

        console.print()
        console.print(table)
        console.print()


@click.command()
@click.option("-l", "--limit", default=6, help="Number of feed items", show_default=True)
@click.option("-c", "--comment-limit", default=10, help="Comments per item (0=hide)", show_default=True)
def feeds(limit: int, comment_limit: int):
    """Show recommended feed with comments (推荐+评论)."""
    with _get_client() as client:
        try:
            results = client.get_feed(limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch feed: {e}")
            sys.exit(1)

        if not data:
            print_info("Feed is empty")
            return

        for idx, item in enumerate(data, 1):
            target = item.get("target", {})
            item_type = target.get("type", "—")
            item_id = str(target.get("id", "—"))
            title = strip_html(
                target.get("title", "")
                or target.get("question", {}).get("title", "")
                or strip_html(target.get("excerpt", "—"))
            )
            author = target.get("author", {}).get("name", "—")

            console.print()
            console.print(
                f"[title]  {idx}. [{item_type}] {title}  [/title]"
            )
            console.print(f"  [dim]ID: {item_id}  Author: {author}[/dim]")

            if item_type == "answer":
                try:
                    ans = client.get_answer(item_id)
                    content = strip_html(ans.get("content", ""))
                except Exception:
                    content = strip_html(target.get("excerpt", ""))
            else:
                content = strip_html(target.get("content", target.get("excerpt", "")))

            if content:
                console.print(f"  {content}")

            if comment_limit > 0 and item_type == "answer":
                try:
                    c_result = client.get_answer_comments(item_id, limit=comment_limit)
                    c_data = c_result.get("data", [])
                except Exception:
                    c_data = []

                if c_data:
                    for i, c in enumerate(c_data, 1):
                        c_content = strip_html(c.get("content", ""))
                        c_likes = format_count(c.get("vote_count", 0))
                        console.print(
                            f"    [dim]{i}.[/dim] {c_content}  [dim]{c_likes} likes[/dim]"
                        )
                else:
                    console.print("    [dim]No comments[/dim]")

        console.print()


@click.command()
@click.argument("topic_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def topic(topic_id: int, as_json: bool):
    """View topic details and hot questions."""
    with _get_client() as client:
        try:
            t = client.get_topic(topic_id)
        except Exception as e:
            print_error(f"Failed to fetch topic: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(t, indent=2, ensure_ascii=False))
            return

        name = t.get("name", "—")
        intro = strip_html(t.get("introduction", ""))

        console.print()
        console.print(f"[title]  # {name}  [/title]")
        if intro:
            console.print()
            console.print(intro)

        stats = format_stats_line({
            "Followers": t.get("followers_count", 0),
            "Questions": t.get("questions_count", 0),
        })
        console.print()
        console.print(stats)

        # Hot questions under this topic
        try:
            hot_q = client.get_topic_hot_questions(topic_id, limit=10)
            q_data = hot_q.get("data", [])
        except Exception:
            q_data = []

        if q_data:
            table = make_table(" Hot Questions ")
            table.add_column("#", style="dim", width=4)
            table.add_column("Question", ratio=1)
            table.add_column("Answers", width=10, justify="right")

            for i, item in enumerate(q_data, 1):
                q_title = strip_html(item.get("title", "—"))
                q_answers = format_count(item.get("answer_count", 0))
                table.add_row(str(i), q_title, q_answers)

            console.print()
            console.print(table)

        console.print()
