# Hướng dẫn sử dụng API TTS

Tài liệu này mô tả cách dùng 2 API chính của hệ thống:
- HTTP: `POST /api/tts` (stream PCM)
- WebSocket: `GET /ws/tts` (stream PCM realtime)

Base URL production:
- `https://ttsapi.ai-box.vn`

---

## Xác thực (Authentication)

Tất cả API đều yêu cầu **API Key** để xác thực. Gửi key trong header `Authorization`:

```
Authorization: Bearer sk_live_xxxxxxxxxxxx
```

API Key được tạo từ Dashboard tại [https://tts.ai-box.vn](https://tts.ai-box.vn) sau khi đăng ký tài khoản.

> ⚠️ **Bảo mật**: Không chia sẻ API key. Nếu bị lộ, vào Dashboard → Xóa key cũ → Tạo key mới.

### Mã lỗi xác thực

| Status | Ý nghĩa |
|--------|---------|
| `401` | Thiếu API key hoặc key không hợp lệ / đã bị thu hồi |
| `402` | Số dư tài khoản không đủ, cần nạp thêm |

---

## 1) Lấy danh sách giọng đọc

### Endpoint
`GET /api/voices`

### Mục đích
Lấy danh sách `voice` và `style` để hiển thị cho người dùng.

### Ví dụ
```bash
curl https://ttsapi.ai-box.vn/api/voices
```

### Response mẫu
```json
{
  "voices": {
    "female": {
      "label": "Giọng nữ",
      "styles": {
        "vn_teacher": "Cô giáo Ngữ văn",
        "mien_tay": "Cô gái miền Tây"
      }
    },
    "male": {
      "label": "Giọng nam",
      "styles": {
        "vn_teacher": "Thầy giáo Ngữ văn"
      }
    }
  }
}
```

---

## 2) HTTP API: Stream PCM

### Endpoint
`POST /api/tts`

### URL đầy đủ
`https://ttsapi.ai-box.vn/api/tts`

### Content-Type request
`application/json`

### Body
```json
{
  "text": "Xin chào, đây là bản demo.",
  "voice": "female",
  "style": "mien_tay"
}
```

### Header bắt buộc
```
Authorization: Bearer sk_live_xxxxxxxxxxxx
Content-Type: application/json
```
- `text` (bắt buộc): nội dung cần đọc.
- `voice` (không bắt buộc): mặc định `female`.
- `style` (không bắt buộc): mặc định `vn_teacher`.

### Response
- Dạng stream nhị phân PCM 16-bit little-endian.
- Header chính:
  - `Content-Type: audio/pcm`
  - `X-Audio-Format: pcm_s16le`
  - `X-Sample-Rate: 24000`
  - `X-Channels: 1`
  - `X-Sample-Width: 2`

### Lưu ý quan trọng
API này trả **raw PCM**, không phải WAV/MP3.
- Nếu muốn lưu file WAV, client cần tự thêm WAV header.
- Nếu muốn phát realtime, client đọc stream tới đâu phát tới đó.

### Ví dụ Python (đọc stream)
```python
import requests

API_KEY = "sk_live_xxxxxxxxxxxx"
url = "https://ttsapi.ai-box.vn/api/tts"
payload = {
    "text": "Xin chào khách hàng.",
    "voice": "female",
    "style": "mien_tay",
}

with requests.post(url, json=payload, stream=True, timeout=(5, 120),
                   headers={"Authorization": f"Bearer {API_KEY}"}) as r:
    r.raise_for_status()
    for chunk in r.iter_content(chunk_size=4096):
        if not chunk:
            continue
        # Xử lý chunk PCM tại đây (phát loa / ghi file)
```

---

## 3) WebSocket API: Realtime PCM

### Endpoint
`wss://ttsapi.ai-box.vn/ws/tts`

### Client gửi
```json
{
  "text": "Xin chào, đây là websocket demo.",
  "voice": "female",
  "style": "mien_tay",
  "api_key": "sk_live_xxxxxxxxxxxx"
}
```

> ⚠️ WebSocket không hỗ trợ header `Authorization`, nên gửi `api_key` trong mỗi message JSON.

### Server trả
- Binary frame: PCM chunk.
- Khi hoàn tất:
```json
{ "type": "done", "chunks": 123, "bytes": 456789 }
```
- Khi lỗi:
```json
{ "type": "error", "message": "..." }
```

---

## 4) Mã lỗi thường gặp

| Status | Ý nghĩa |
|--------|---------|
| `400` | JSON không hợp lệ hoặc thiếu `text` |
| `401` | Thiếu API key / key không hợp lệ / đã bị thu hồi |
| `402` | Số dư tài khoản không đủ |
| `500` | Lỗi nội bộ server |
| `504` | TTS khởi tạo quá lâu, thử lại |

---

## 5) Khuyến nghị tích hợp cho khách hàng

1. Gọi `GET /api/voices` để lấy danh sách lựa chọn.
2. Với nhu cầu realtime: ưu tiên WebSocket `wss://ttsapi.ai-box.vn/ws/tts`.
3. Với nhu cầu request/response thuần HTTP: dùng `POST https://ttsapi.ai-box.vn/api/tts` và xử lý PCM stream.
4. Thêm timeout + retry ở client.
5. Không gửi text quá dài trong 1 request; nên chia đoạn nếu cần đọc dài.

---

## 6) Ghi chú tương thích

- Dữ liệu audio đầu ra là PCM 24kHz, mono, 16-bit.
- Nếu player/client yêu cầu WAV thì cần đóng gói WAV ở phía client.
