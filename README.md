# IPTV Discovery

全国电视台公开/授权直播源发现、检测和播放列表生成 MVP。支持 Docker Compose，目标平台 linux/amd64 与 linux/arm64。

## 一键部署

NAS / Linux（x86_64、ARM64）：
```bash
git clone https://github.com/ztesfyfi/IPTV-Discovery.git
cd IPTV-Discovery
cp .env.example .env
# 编辑 .env，将 ADMIN_TOKEN 改成随机长字符串
docker compose up -d --build
```

访问运维面板 `http://NAS_IP:18787/ui`，API 文档 `http://NAS_IP:18787/docs`，健康检查 `http://NAS_IP:18787/health`。宿主机和容器内部端口均使用高位端口 **18787**。

## 功能

- 导入本地 M3U/TXT 或远程订阅
- 央视、卫视频道别名归一化匹配
- HTTP 可达性检测、FFprobe 深度检测
- 导出 M3U、TXT、JSON
- SQLite 持久化
- GitHub Actions 自动测试及构建 linux/amd64、linux/arm64 镜像

## 导入

把 M3U/TXT 文件放入 `data/imports/`：
```bash
curl -X POST http://127.0.0.1:18787/api/imports/local \
  -H 'Content-Type: application/json' -H 'X-Admin-Token: YOUR_TOKEN' \
  -d '{"filename":"list.m3u","source_name":"my-list"}'
```

远程订阅：
```bash
curl -X POST http://127.0.0.1:18787/api/imports/remote \
  -H 'Content-Type: application/json' -H 'X-Admin-Token: YOUR_TOKEN' \
  -d '{"url":"https://example.org/list.m3u","source_name":"authorized-list"}'
```

## 检测与导出

```bash
curl -X POST http://127.0.0.1:18787/api/checks/run -H 'X-Admin-Token: YOUR_TOKEN'
curl -o result.m3u http://127.0.0.1:18787/exports/result.m3u
curl -o result.txt http://127.0.0.1:18787/exports/result.txt
curl -o result.json http://127.0.0.1:18787/exports/result.json
```

深度检测（FFprobe）：
```bash
curl -X POST 'http://127.0.0.1:18787/api/checks/run?deep=true' -H 'X-Admin-Token: YOUR_TOKEN'
```

## API

- GET：`/health`、`/api/channels`、`/api/candidates`、`/api/sources`、`/api/checks/recent`
- POST：`/api/imports/local`、`/api/imports/remote`、`/api/checks/run`
- 导出：`/exports/result.m3u`、`/exports/result.txt`、`/exports/result.json`

所有写操作在配置 ADMIN_TOKEN 后均需提供 `X-Admin-Token`。请勿将管理 API 直接暴露到公网。

## 配置与性能

- `APP_PORT`：宿主机端口，默认 18787
- `ADMIN_TOKEN`：管理接口令牌，建议设为随机长字符串
- `MAX_CONCURRENCY`：快速检测并发，J3160 建议 4
- `DEEP_CONCURRENCY`：FFprobe 并发，J3160 建议 1
- `REQUEST_TIMEOUT`：HTTP 检测超时秒数
- `MAX_IMPORT_BYTES`：订阅文件最大字节数

数据保存在宿主机 `data/`。本项目只检测直播源并生成播放列表，不代理或转发视频流。频道清单只是匹配模板，不代表项目自带可用直播源。

只使用公开可访问或你有权使用的直播地址。本项目不破解 DRM、不绕过登录鉴权或运营商组播访问控制。HTTP 可达不代表频道内容真实、官方或获得授权。

远程导入和探测仅接受解析为公网地址的 HTTP(S) URL，并禁用自动重定向；这是基础 SSRF 防护，无法完全消除 DNS 重绑定等网络层风险。
