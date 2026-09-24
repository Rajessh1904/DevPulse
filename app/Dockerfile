# ---- build stage ----
FROM python:3.14-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- runtime stage ----
FROM python:3.14-slim
# --home is required here: without it, adduser --system creates no home
# directory at all, so $HOME is unset for the "app" user at runtime and
# Python's user-site lookup (site.getuserbase()) can't find the packages
# copied below, even though the files are physically present.
RUN addgroup --system app && adduser --system --ingroup app --home /home/app app
WORKDIR /app
COPY --from=builder /root/.local /home/app/.local
COPY main.py .
RUN chown -R app:app /home/app/.local
ENV HOME=/home/app \
    PATH=/home/app/.local/bin:$PATH \
    PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]