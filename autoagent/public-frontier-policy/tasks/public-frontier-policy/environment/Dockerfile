FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

# Harbor provides task-local files separately at runtime. The environment build
# context is only this `environment/` directory, so do not COPY `../files` here.

# Install the Optiqal Python package. Update the ref if you want task builds
# to target a different branch or tag.
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir \
        "git+https://github.com/maxghenis/optiqal-ai.git@main#subdirectory=python"
