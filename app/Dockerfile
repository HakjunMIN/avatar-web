FROM mcr.microsoft.com/azurelinux/base/python:3.12

RUN tdnf distro-sync -y && \
    tdnf install -y ca-certificates && \
    tdnf clean all

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml uv.lock* /app/
WORKDIR /app

# Install dependencies with uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY . /app

ENTRYPOINT [ "uv", "run", "python", "-m", "flask", "run", "-h", "0.0.0.0", "-p", "5000" ]