# Git Docker Tool

一个轻量工具镜像，内置 `git`、`docker`、`docker compose`、`ssh`、`curl`、`jq`、`ttyd` 等常用命令，方便在 NAS 或服务器上通过网页终端管理宿主机 Docker 和拉取代码。

这个仓库只负责构建和发布镜像，不再保存运行用的 compose 模板。

## 文件

- `Dockerfile`: 定义工具镜像。
- `entrypoint.sh`: 启动时准备 `$HOME/.ssh`，检查 Docker socket，然后进入网页终端。
- `.github/workflows/docker-image.yml`: 推送版本 tag 时自动构建并发布多架构镜像。
- `.dockerignore`: 排除本地代码目录、Git 元数据和说明文件，缩小 Docker build context。

## 挂载目录

运行时建议挂载两个路径：

- `/workspace`: 持久化工作目录。Git 仓库、compose 项目、脚本和 SSH 配置都放这里；Dockerfile 已声明为 volume。
- `/var/run/docker.sock`: 宿主机 Docker socket。需要 bind mount 这个 socket，容器里的 `docker` / `docker compose` 才能管理宿主机容器。

容器默认设置了 `HOME=/workspace`，并把 root 用户的 home 也设为 `/workspace`，所以 Git 全局配置、SSH 配置和常见 CLI 的用户级配置都会写到这个持久化目录。通常只需要准备一个宿主机目录，例如 `/volume1/code`，然后挂载到容器内的 `/workspace`：

```text
/volume1/code
├── .ssh
└── your-projects
```

## 自动发布

推送 `v1.2.3` 这类 tag 会触发 GitHub Actions，构建 `linux/amd64` 和 `linux/arm64` 镜像，并发布到 DockerHub 和 GHCR。

需要配置仓库 secrets：

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

发布后的镜像 tag 形如：

```text
<DOCKERHUB_USERNAME>/<repo>:latest
<DOCKERHUB_USERNAME>/<repo>:v1.2.3
ghcr.io/<github-owner>/<repo>:latest
ghcr.io/<github-owner>/<repo>:v1.2.3
```

## 运行

启动容器并开放网页终端：

```bash
docker run -d \
  --name git-docker-tool \
  --restart unless-stopped \
  --memory 128m \
  -p 7681:7681 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /volume1/code:/workspace \
  ghcr.io/<github-owner>/<repo>:latest
```

浏览器打开：

```text
http://服务器IP:7681
```

默认账号密码：

```text
admin / adminadmin
```

也可以直接进入容器：

```bash
docker exec -it git-docker-tool bash
```

容器内默认工作目录和 HOME 都是 `/workspace`，所以宿主机的 `/volume1/code/.ssh` 会直接用于 `git clone`、`ssh` 等命令。

Git 全局用户名和邮箱也会持久化到宿主机的 `/volume1/code/.gitconfig`：

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## 本地构建

通常不需要本地构建，GitHub Actions 会发布镜像。需要临时调试时可以直接使用 Dockerfile：

```bash
docker build -t git-docker-tool:local .
```

## 权限说明

镜像默认以 root 运行，因为 NAS 上的 `/var/run/docker.sock` 通常只有 root 或 docker 组能访问。挂载 Docker socket 后，能进入这个容器的人基本等价于拥有宿主机 Docker 管理权限。

Dockerfile 不再接收 UID/GID 构建参数。UID/GID 是运行时进程身份，应该通过 `docker run --user UID:GID` 或 compose 的 `user:` 控制；环境变量本身不会改变进程的 UID/GID。当前推荐保持 root 运行，以减少 NAS 环境里的 socket 权限问题。
