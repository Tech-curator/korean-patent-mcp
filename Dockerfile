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

# Set environment variable placeholder (will be provided at runtime)
ENV KIPRIS_API_KEY=""

# Run the MCP server
CMD ["python", "-m", "korean_patent_mcp.server"]
