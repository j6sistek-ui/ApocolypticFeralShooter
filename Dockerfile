FROM python:3.12-slim-bookworm
WORKDIR /project
COPY Scripts /project/Scripts
CMD ["python", "-m", "compileall", "-q", "Scripts"]
