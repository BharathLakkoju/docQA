"""Shared HTTP session for ingestion scripts.

This sandbox's DNS resolves public hosts to IPv6 first, but outbound IPv6
routing isn't actually usable here, so every new connection burns ~10-20s on
a doomed IPv6 attempt before falling back to IPv4. Forcing IPv4-only
resolution for the process removes that stall. Harmless (and unnecessary,
but also harmless) on networks where IPv6 does work.
"""
from __future__ import annotations

import socket

import requests
import urllib3.util.connection as urllib3_conn


def _allowed_gai_family():
    return socket.AF_INET


urllib3_conn.allowed_gai_family = _allowed_gai_family


def new_session() -> requests.Session:
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
