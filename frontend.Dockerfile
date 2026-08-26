# 前端镜像：多阶段构建
#   阶段 1（build）—— Node 20 构建出静态资源
#   阶段 2 —— nginx 托管静态资源 + 反代 /api 到 backend 容器
FROM node:20-alpine AS build
WORKDIR /app
# 先复制依赖清单并安装（使用国内 npm 镜像），依赖不变时命中层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com
# 再复制源码并构建
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
