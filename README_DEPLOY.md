# Macro DataHub Web Deploy 版

这个版本可以部署成一个别人能访问的网页。

## 本地运行

Windows 上双击：

```text
START_HERE.bat
```

浏览器打开：

```text
http://127.0.0.1:8000
```

## 部署到 Render / Railway / Fly.io 等云平台

这个包已经包含：

```text
Dockerfile
Procfile
render.yaml
```

云平台运行时需要：

```text
HOST=0.0.0.0
NO_BROWSER=1
PORT=平台自动提供
```

## API

首页：

```text
/
```

API 文档：

```text
/docs
```

示例接口：

```text
/series?country=US&indicator_code=CPI_YOY&start_date=2020-01&end_date=2025-12&frequency=M
```

## 注意

这是有后端的网页，不是纯静态 HTML。不能只把 `frontend/index.html` 上传到 GitHub Pages，因为查询功能需要 `app.py` 这个后端服务。
