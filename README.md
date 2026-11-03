# IPTV-Discovery

全国电视台公开/授权直播源发现、检测与播放列表生成工具。目标平台为 `linux/amd64` 和 `linux/arm64`，适合 NAS、Armbian、Docker 环境。

> 项目源码与部署文件正在整理上传。服务端口统一为 **18787**（宿主机与容器内部一致）。

## 计划部署方式

```bash
git clone https://github.com/ztesfyfi/IPTV-Discovery.git
cd IPTV-Discovery
cp .env.example .env
docker compose up -d --build
```

管理页面/API 文档：`http://NAS_IP:18787/docs`

## 目标能力

- 导入本地或远程 M3U/TXT 播放列表
- 频道名称归一化与央视、卫视频道匹配
- HTTP 可达性检测、延迟统计
- 可选 FFprobe 深度检测（分辨率、帧率、码率、编码）
- 导出 M3U、TXT、JSON
- SQLite 本地保存检测结果
- Docker 多架构：`linux/amd64`、`linux/arm64`

## 资源与安全

只使用公开可访问或你有权使用的直播地址。本项目只检测和管理播放地址，不转发视频流；不破解 DRM、不绕过登录鉴权或运营商组播访问控制。HTTP 可达不代表频道内容真实、官方或已获授权。

远程 URL 检查属于基础 SSRF 防护，部署时仍建议设置管理令牌、限制 API 网络访问，并配置出站防火墙策略。
