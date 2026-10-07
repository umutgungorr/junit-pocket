FROM python:3.12.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
WORKDIR /workspace
COPY --chown=app:app . /workspace
USER 10001:10001

ENTRYPOINT ["python", "-m", "junit_pocket"]
CMD ["--help"]
