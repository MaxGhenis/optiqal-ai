FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY files/ /app/

# Install the Optiqal Python package. Update the ref if you want task builds
# to target a different branch or tag.
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir \
        "git+https://github.com/maxghenis/optiqal-ai.git@main#subdirectory=python"

RUN chmod +x /app/agent.py
