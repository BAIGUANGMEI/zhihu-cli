"""Custom exceptions for zhihu-cli."""


class LoginError(Exception):
    """Authentication failure."""


class DataFetchError(Exception):
    """Failed to fetch data from Zhihu."""
