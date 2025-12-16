# Korean Patent MCP Server - Container Deployment
FROM python:3.12-slim

WORKDIR /app

# Install uv for dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY README.md ./

# Install dependencies
RUN uv pip install --system -e .

# Environment variables (will be overridden at runtime)
ENV KIPRIS_API_KEY=""
ENV PORT=8000

# Expose the HTTP port
EXPOSE 8000

# Run the MCP server in HTTP mode
CMD ["python", "-m", "korean_patent_mcp.server", "--http"]
