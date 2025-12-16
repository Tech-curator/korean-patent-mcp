"""
Korean Patent MCP - MCP Server for KIPRIS API
한국 특허정보 검색서비스(KIPRIS)를 위한 MCP 서버

This package provides an MCP (Model Context Protocol) server that enables
AI assistants to search and analyze Korean patents through the KIPRIS API.
"""

__version__ = "0.1.0"
__author__ = "DiME"
__email__ = "kh25@techcurator.kr"

from .server import main

__all__ = ["main"]
