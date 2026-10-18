# The access layer: serve.py, the TEXT2SPARQL contract (Session 7).
FROM python:3.12-slim
WORKDIR /app/access-layer
COPY access-layer/requirements-access-layer.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-access-layer.txt
COPY access-layer/ /app/access-layer/
COPY index.html README.md COURSE_CODE_SOURCES.json manifest.webmanifest sw.js /app/
COPY assets/ /app/assets/
COPY data/manifest.json /app/data/manifest.json
COPY ontology/ /app/ontology/
ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["python", "serve.py"]
