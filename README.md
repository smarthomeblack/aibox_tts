# AIBOX TTS cho Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

Tích hợp Text-to-Speech (TTS) của [AI-BOX](https://tts.ai-box.vn) vào Home Assistant. Tích hợp này cho phép bạn chuyển đổi văn bản thành giọng nói tiếng Việt tự nhiên và phát trên các thiết bị `media_player` trong Home Assistant.

## ✨ Tính năng nổi bật

- 🇻🇳 Hỗ trợ giọng đọc tiếng Việt tự nhiên, chất lượng cao.
- 🗣️ Hỗ trợ nhiều **giọng đọc** (nam, nữ).
- 🎭 Hỗ trợ nhiều **phong cách đọc** (cô giáo Ngữ văn, cô gái miền Tây, v.v.).
- ⚡ **Streaming âm thanh trực tiếp** chuẩn PCM chất lượng 24kHz.
- ⚙️ Hỗ trợ thêm tích hợp và cấu hình bằng giao diện người dùng (UI Config Flow) hoàn toàn, không cần sửa file YAML.
- � Tự động đồng bộ các giọng đọc và phong cách từ máy chủ AIBOX.

## 📋 Yều cầu

1. Bạn cần có 1 tài khoản tại hệ thống **AIBOX TTS**.
2. Đăng nhập vào thiết lập [Dashboard AIBOX](https://tts.ai-box.vn) để tạo một **API Key**.

## 📦 Cài đặt

### Cách 1: Thông qua HACS (Khuyến nghị)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=smarthomeblack&repository=aibox_tts&category=integration)

- Tải về sau đó khởi động lại Home Assistant

### Cách 2: Cài đặt thủ công

1. Tải [phiên bản mới nhất](https://github.com/smarthomeblack/aibox_tts/releases/latest) của repo này về.
2. Copy thư mục `custom_components/aibox_tts` vào trong thư mục `custom_components` của Home Assistant.
3. Khởi động lại Home Assistant.

## ⚙️ Cấu hình

1. Chuyển tới **Cài đặt** (Settings) -> **Thiết bị & Dịch vụ** (Devices & Services).
2. Nhấn nút **+ Thêm tích hợp** (+ Add Integration).
3. Tìm kiếm **AIBOX TTS** và chọn.
4. Cửa sổ thiết lập hiện ra, nhập **API Key** bạn đã lấy ở [AIBOX](https://tts.ai-box.vn) vào ô tương ứng (Base URL thông thường có thể để mặc định là `https://ttsapi.ai-box.vn`).
5. Bấm Submmit. Ở bước tiếp theo, hãy chọn **Giọng nói** và **Phong cách** mặc định rồi nhấn hoàn thành.

## 🎮 Cách sử dụng

Bạn có thể sử dụng AIBOX TTS cho các mục đích đọc giọng nói thông qua action `tts.speak`.

### Ví dụ Automation

Đọc một sự kiện khi có chuyển động:

```yaml
action: tts.speak
target:
  entity_id: tts.aibox_tts
data:
  cache: true
  media_player_entity_id: media_player.phong_khach
  message: "Xin chào, đã phát hiện chuyển động tại phòng khách."
```

### Tuỳ biến giọng và phong cách trong mỗi script/automation

Bạn có thể truyền thêm `options` để đổi giọng nói cho phù hợp ngữ cảnh cụ thể:

```yaml
action: tts.speak
target:
  entity_id: tts.aibox_tts
data:
  cache: true
  media_player_entity_id: media_player.loa_phong_ngu
  message: "Chào buổi sáng tốt lành, hôm nay trời có mưa đấy."
  options:
    voice: female       # Giọng đọc (female, male...)
    style: mien_tay     # Phong cách (mien_tay, vn_teacher...)
```

## 🔍 Khắc phục sự cố

1. **Lỗi xác thực (Invalid Auth)**: Hãy chắc chắn bạn đã nhập chính xác API Key. Kiểm tra tài khoản tại bảng điều khiển AIBOX để chắc chắn rằng số dư (Credit) của bạn vẫn khả dụng để sử dụng.
2. **Lỗi không kết nối được (Cannot connect)**: Có thể do đường truyền từ Home Assistant đến server AIBOX không ổn định, hãy thử lại.
3. Nếu giọng đọc không phát, hãy xem logger của HA (Cài đặt -> Hệ thống -> Nhật ký) để tìm mã lỗi chính xác.

## 📸 Demo

<img title="AIBOX TTS" src="https://raw.githubusercontent.com/smarthomeblack/aibox_tts/refs/heads/main/1.png" width="100%"></img>

<img title="AIBOX TTS" src="https://raw.githubusercontent.com/smarthomeblack/aibox_tts/refs/heads/main/2.png" width="100%"></img>

<img title="AIBOX TTS" src="https://raw.githubusercontent.com/smarthomeblack/aibox_tts/refs/heads/main/3.png" width="100%"></img>

<img title="AIBOX TTS" src="https://raw.githubusercontent.com/smarthomeblack/aibox_tts/refs/heads/main/4.png" width="100%"></img>

---

## 📝💬 Hỗ trợ

AIBOX TTS - Phát triển bởi **smarthomeblack**
- Hỗ trợ về API: [https://tts.ai-box.vn](https://tts.ai-box.vn)
- GitHub Repository: [https://github.com/smarthomeblack/aibox_tts](https://github.com/smarthomeblack/aibox_tts)
