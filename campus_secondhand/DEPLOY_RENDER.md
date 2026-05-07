# Render 云部署步骤

在线访问网址：部署完成后，把 Render 生成的 `https://xxxx.onrender.com` 写到这里。

## 一、准备代码仓库

1. 把 `campus_secondhand` 整个文件夹上传到 GitHub。
2. 仓库中必须包含这些文件：
   - `app.py`
   - `init_db.py`
   - `schema.sql`
   - `campus_secondhand.db`
   - `static/style.css`
   - `requirements.txt`
   - `render.yaml`

## 二、在 Render 创建 Web Service

1. 打开 [Render](https://render.com/) 并登录。
2. 点击 `New`，选择 `Web Service`。
3. 连接 GitHub 仓库，选择本项目仓库。
4. 填写配置：
   - Language: `Python 3`
   - Build Command: `python init_db.py`
   - Start Command: `HOST=0.0.0.0 python -B app.py`
   - Instance Type: `Free`
5. 点击创建，等待部署完成。

## 三、提交时使用

部署成功后，Render 会提供一个公网地址，例如：

```text
https://campus-secondhand.onrender.com
```

把这个网址写到项目说明文件开头，并在录屏时从这个网址进入网站。

## 四、注意事项

- 免费服务长时间无人访问可能会休眠，第一次打开可能需要等待几十秒。
- 本项目使用 SQLite 文件，适合课程作业演示。云端重新部署时会按 `schema.sql` 恢复初始数据。
- 如果部署失败，重点检查日志里是否显示服务监听了 `0.0.0.0` 和 `$PORT`。
