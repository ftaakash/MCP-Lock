# Analysis image for the malicious corpus (PREREG §3.2, DEVIATIONS #3).
# Code is mounted read-only at /repo; malware data lives only in the mcplock-mal volume (/data).
# Nothing from the corpus is ever executed: archives are parsed statically.
FROM python:3.11.9-slim
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock && useradd -m -u 1000 analyst
USER analyst
WORKDIR /repo
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/repo
