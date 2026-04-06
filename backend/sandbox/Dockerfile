FROM python:3.11-slim

LABEL maintainer="PubHAgent"
LABEL description="公共卫生数据分析沙箱环境"

WORKDIR /sandbox

RUN groupadd -r sandbox && useradd -r -g sandbox sandbox

COPY requirements.txt /sandbox/
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip

RUN mkdir -p /sandbox/workspace /sandbox/output && \
    chown -R sandbox:sandbox /sandbox

USER sandbox

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib

RUN mkdir -p /tmp/matplotlib

WORKDIR /sandbox/workspace

ENTRYPOINT ["python", "-c"]
