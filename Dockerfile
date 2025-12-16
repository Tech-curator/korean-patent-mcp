# Korean Patent MCP Server Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY README.md ./

# Install dependencies using uv
RUN uv pip install --system -e .

# Set environment variable placeholders (will be provided at runtime)
ENV KIPRIS_API_KEY=""
ENV MCP_HTTP_PORT="8000"

# Expose HTTP port for Smithery hosting
EXPOSE 8000

# Run the MCP server in HTTP mode
CMD ["python", "-m", "korean_patent_mcp.server", "--http"]
