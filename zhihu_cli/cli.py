"""CLI entry point for zhihu-cli."""

from __future__ import annotations

import logging

import click

from . import __version__
from .commands.auth import login, logout, status, whoami
from .commands.content import answer, answers, feed, feeds, hot, question, search, topic
from .commands.interact import (
    article,
    ask,
    collections,
    delete_article_cmd,
    delete_pin,
    delete_question,
    follow_question,
    notifications,
    pin,
    vote,
)
from .commands.user import followers, following, user, user_answers, user_articles


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.version_option(version=__version__, prog_name="zhihu-cli")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def cli(verbose: bool):
    """zhihu-cli — Zhihu from your terminal."""
    _setup_logging(verbose)


# Auth
cli.add_command(login)
cli.add_command(logout)
cli.add_command(status)
cli.add_command(whoami)

# Content
cli.add_command(search)
cli.add_command(hot)
cli.add_command(question)
cli.add_command(answers)
cli.add_command(answer)
cli.add_command(feed)
cli.add_command(feeds)
cli.add_command(topic)

# User
cli.add_command(user)
cli.add_command(user_answers)
cli.add_command(user_articles)
cli.add_command(followers)
cli.add_command(following)

# Interactions
cli.add_command(vote)
cli.add_command(follow_question)
cli.add_command(ask)
cli.add_command(pin)
cli.add_command(article)
cli.add_command(delete_question)
cli.add_command(delete_pin)
cli.add_command(delete_article_cmd)
cli.add_command(collections)
cli.add_command(notifications)


if __name__ == "__main__":
    cli()
