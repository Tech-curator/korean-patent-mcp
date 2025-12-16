# Korean Patent MCP Server - Smithery Container Deployment
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY README.md ./

# Install dependencies with uv
RUN uv sync --frozen || uv pip install --system -e .

# Environment variables for Smithery
# - TRANSPORT: http (Smithery Container mode)
# - PORT: 8081 (Smithery sets this)
ENV TRANSPORT=http
ENV PORT=8081

# Start the MCP server
CMD ["uv", "run", "python", "-m", "korean_patent_mcp.server"]
