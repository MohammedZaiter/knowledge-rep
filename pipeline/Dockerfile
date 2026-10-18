# The graph pipeline as a one-shot container: map, SHACL gate, reasoner, VoID, load.
FROM python:3.12-slim-trixie
# HermiT runs on Java.
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-21-jre-headless && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY pipeline/requirements-pipeline.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-pipeline.txt \
 && pip install --no-cache-dir --no-deps morph-kgc==2.10.0
# The repository itself is mounted at /work (docker-compose.yml), so edits to
# the mapping, ontology or shapes need no rebuild.
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
CMD ["python", "pipeline/run.py"]
