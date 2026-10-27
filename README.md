# LinkMedia Converter API

Docker-based FastAPI backend for LinkMedia Converter.

## Render deployment
1. Upload the contents of this folder to a GitHub repository.
2. In Render, choose **New → Web Service**, connect the repository, and select Docker runtime.
3. Set `FRONTEND_ORIGIN=https://linkmedia-converter.higgsfield.app`.
4. Deploy, then verify `https://YOUR-SERVICE.onrender.com/health` returns `{"ok":true,...}`.
5. Set the frontend API base URL to the service URL and redeploy the frontend.

## API
`POST /api/convert` with JSON such as `{"url":"https://www.youtube.com/watch?v=VIDEO_ID","format":"mp3"}`. Supported formats: `mp3`, `wav`, `mp4`. Successful requests return a downloadable file.

## Limitations
Use only content you own or have permission to download, and follow YouTube's terms and applicable law. This service does not bypass sign-in, DRM, age gates, or other access controls. This prototype has no authentication, request quotas, queue, or persistent storage; do not expose it for unrestricted public use without adding those controls. Render free services may sleep or have resource limits, and YouTube delivery changes can break yt-dlp compatibility.
