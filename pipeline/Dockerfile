# The graph pipeline as a one-shot container: map, SHACL gate, VoID, load.
FROM python:3.12-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-21-jre-headless && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY pipeline/requirements-pipeline.txt /work/pipeline/
COPY model/requirements.txt /work/model/
RUN pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r /work/pipeline/requirements-pipeline.txt \
 && pip install --no-cache-dir --no-deps morph-kgc==2.10.0
# The repository itself is mounted at /work (docker-compose.yml), so edits to
# the mapping, ontology or shapes need no rebuild.
ENV OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
CMD ["python", "pipeline/run.py"]
