# Korean Patent MCP Server - Smithery Container Deployment
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY README.md ./

# Install dependencies
RUN uv sync --frozen

# Smithery sets PORT to 8081
ENV PORT=8081

# Start the MCP server
CMD ["uv", "run", "python", "-m", "korean_patent_mcp.server", "--http"]
