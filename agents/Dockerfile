FROM python:3.13-slim
WORKDIR /app
COPY agents/requirements.txt /app/agents/requirements.txt
RUN pip install --no-cache-dir -r /app/agents/requirements.txt
COPY agents /app/agents
# so `python -m agents.serve` resolves the package
ENV PYTHONPATH=/app
EXPOSE 8010-8021
CMD ["python", "-m", "agents.serve", "project-manager"]
