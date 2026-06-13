FROM alpine:3.20

RUN apk add --no-cache \
    bash \
    curl \
    docker-cli \
    docker-cli-compose \
    git \
    jq \
    openssh-client \
    python3 \
    rsync \
    ttyd \
    vim \
  && mkdir -p /workspace \
  && sed -i 's#^root:x:0:0:root:/root:#root:x:0:0:root:/workspace:#' /etc/passwd

COPY app /opt/git-docker-tool/app
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV HOME=/workspace
ENV PYTHONPATH=/opt/git-docker-tool
WORKDIR /workspace
VOLUME ["/workspace"]
EXPOSE 7680
EXPOSE 7681

USER root

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
