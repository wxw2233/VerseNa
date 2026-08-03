# 局域网访问

VerseNa 1.1 支持由 FastAPI 直接托管前端，并使用访问令牌保护 API、文件资源和 WebSocket。局域网设备只需要访问一个地址：

```text
http://<运行设备的局域网 IP>:8002
```

首次以局域网模式启动时，VerseNa 会把访问令牌保存到 `backend/data/access_token`，并在启动面板中打印一次。尚未配置令牌时会自动生成强随机值；旧安装已有 `backend/.env` Token 时会迁移原值，不会擅自更换。首次访问时输入该共享令牌。验证成功后，浏览器保存 HttpOnly 会话 Cookie；令牌不会写入浏览器存储。后端重启后所有浏览器需要重新登录。

## Windows

在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-lan.ps1
```

脚本会创建基础 LAN 配置、构建缺失的前端并显示可访问地址。第一次启动时请同时记录后端面板打印的访问令牌。Windows 防火墙询问时仅允许“专用网络”。

## Termux

源码首次安装运行环境：

```bash
pkg update
pkg install python git nodejs-lts
git clone https://github.com/wxw2233/VerseNa.git
cd VerseNa
bash scripts/setup-termux.sh
termux-setup-storage
```

启动局域网服务：

```bash
bash scripts/start-termux.sh
```

Termux 源码部署会使用项目内的 `.venv`，运行数据默认保存在 `$HOME/.local/share/versena`。第一次启动时请记录终端面板打印的访问令牌。建议关闭 VerseNa/Termux 的电池优化；脚本在可用时会启用 `termux-wake-lock`。

## 手动配置

复制 `backend/.env.example` 为 `backend/.env` 后即可启动。局域网模式下未配置令牌时会自动生成；也可以提前生成并写入 `VERSENA_ACCESS_TOKEN`：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

至少使用 6 个字符。VerseNa 优先读取 `backend/data/access_token`，其次读取 `backend/.env` 中的 `VERSENA_ACCESS_TOKEN`。设置页修改后的令牌会写入前者，因此不会被旧的环境配置覆盖。

## 修改访问令牌

登录后打开 **设置 → 访问安全**：

1. 输入当前访问令牌。
2. 输入至少 6 个字符的新令牌，或点击生成按钮创建随机令牌。
3. 确认并更新令牌。

更新成功后，当前浏览器保持登录，其他设备和脚本使用的旧会话或旧 Bearer Token 会立即失效。请及时把新令牌安全地交给仍需访问的设备。

如果忘记令牌，请在运行 VerseNa 的设备上查看 `backend/data/access_token`；旧安装也可能仍使用 `backend/.env` 中的 `VERSENA_ACCESS_TOKEN`。不要通过聊天、截图或公开仓库传递令牌。

脚本调用 API 时也可以使用 Bearer Token：

```bash
curl -H "Authorization: Bearer <访问令牌>" http://<局域网IP>:8002/api/sessions
```

## 安全边界

- 仅在可信的家庭或办公局域网使用普通 HTTP。
- 公共 Wi-Fi、互联网访问或端口转发必须使用 HTTPS/VPN，推荐 Tailscale。
- 不要将 `backend/.env`、`backend/data/access_token`、访问令牌或备份文件提交到版本库。
- 令牌泄露时，在 **设置 → 访问安全** 中立即轮换令牌。
