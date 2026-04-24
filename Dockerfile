FROM alpine:3.20

RUN apk add --no-cache \
    bash \
    curl \
    docker-cli \
    docker-cli-compose \
    git \
    jq \
    openssh-client \
    rsync \
    ttyd \
    vim \
  && mkdir -p /workspace

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /workspace
VOLUME ["/workspace"]
EXPOSE 7681

USER root

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["ttyd", "-W", "-c", "admin:adminadmin", "-p", "7681", "bash"]
