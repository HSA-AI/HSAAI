FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
# FIX B-15: Copy both the service requirements and the shared
# packages/common/requirements.txt (referenced via `-r` from the service
# file) so pip can resolve the consolidated shared dependencies. Mirrors
# the source-tree layout so the `-r ../../packages/common/requirements.txt`
# reference resolves correctly inside the image.
COPY services/multi_agents/requirements.txt ./services/multi_agents/requirements.txt
COPY packages/common/requirements.txt ./packages/common/requirements.txt
RUN pip install --no-cache-dir -r ./services/multi_agents/requirements.txt
COPY services/multi_agents /app/multi_agents
COPY packages/common /app/packages/common
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
USER appuser
CMD ["uvicorn", "multi_agents.main:app", "--host", "0.0.0.0", "--port", "8040"]
