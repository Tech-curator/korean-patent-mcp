# Korean Patent MCP Server - Smithery Container Deployment
FROM python:3.12-slim

WORKDIR /app

# 1. Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. Copy all project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY README.md ./

# 3. Install dependencies into SYSTEM Python
# Proper hard install (not editable) for container deployment
RUN uv pip install --system .

# 4. Environment variables for Smithery
ENV TRANSPORT=http
ENV PORT=8081

# 5. Direct Execution - Do NOT use "uv run"
# Use "python" directly since package is installed in system site-packages
CMD ["python", "-m", "korean_patent_mcp.server"]
