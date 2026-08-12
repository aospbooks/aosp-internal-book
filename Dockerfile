FROM python:3.12-slim

# Install Playwright + Chromium first (largest layer, changes least often)
RUN pip install --no-cache-dir playwright && playwright install --with-deps chromium

RUN pip install --no-cache-dir properdocs mkdocs-material pymdown-extensions pypdf ebooklib lxml

# Install shared renderer (must come before plugins that depend on it)
COPY mkdocs-mermaid-renderer /opt/mkdocs-mermaid-renderer
RUN pip install --no-cache-dir /opt/mkdocs-mermaid-renderer

# Install plugins
COPY mkdocs-pdf-generate /opt/mkdocs-pdf-generate
COPY mkdocs-epub-generate /opt/mkdocs-epub-generate
RUN pip install --no-cache-dir /opt/mkdocs-pdf-generate /opt/mkdocs-epub-generate

WORKDIR /book
COPY . .

EXPOSE 8000
CMD ["properdocs", "serve", "-a", "0.0.0.0:8000"]
