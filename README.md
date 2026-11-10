<div align="center">

# ☕ Morning Pulse

**Trợ lý AI tự động tổng hợp & tóm tắt tin tức Công Nghệ + Bóng Đá Thế Giới mỗi sáng**

[![Daily Digest Workflow](https://img.shields.io/badge/GitHub_Actions-Automated_05%3A45_AM-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](./.github/workflows/daily_digest.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Gemini AI](https://img.shields.io/badge/AI-Google_Gemini_%7C_OpenAI-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)](https://aistudio.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-success?style=for-the-badge)](./LICENSE)

*Không còn sợ "tối cổ"! Mỗi sáng thức dậy với một bản tin súc tích gửi thẳng về **Telegram**, **Discord** và lưu trữ ngay trên **GitHub** — hoàn toàn miễn phí 100% nhờ GitHub Actions.*

[📚 Xem Kho Lưu Trữ Bản Tin Hàng Ngày (Daily Digests)](./digests/README.md)

</div>

---

## ✨ Tính năng nổi bật

- 🔍 **Đa nguồn tin chất lượng:**
  - 🚀 **GitHub Trending:** Các repository mã nguồn mở đang tăng sao nhanh nhất trong ngày.
  - 🟧 **Hacker News:** Những chủ đề công nghệ & khởi nghiệp đang được tranh luận sôi nổi nhất.
  - 👽 **Reddit (`r/programming`, `r/technology`, `r/LocalLLaMA`, `r/soccer`):** Bắt trọn nhịp đập cộng đồng dev và bóng đá quốc tế.
  - 📰 **Báo Công Nghệ:** RSS từ *TechCrunch*, *The Verge*, *VnExpress Số Hóa*...
  - ⚽ **Bóng Đá Thế Giới:** Kết quả trận đấu, chuyển nhượng và tâm điểm sân cỏ đêm qua từ *BBC Sport*, *The Guardian*, *VnExpress Thể Thao*...
- 🧠 **Tóm tắt thông minh bằng AI (Tiếng Việt):**
  - Tích hợp **Google Gemini 3.1 / 3 (`gemini-3.1-pro-preview` & `gemini-3-flash-preview`)** hoặc **OpenAI / Groq / OpenRouter**.
  - Tự động chắt lọc "Tâm điểm sáng nay", bình luận từng chuyên mục và dịch/tóm tắt từng bài sang tiếng Việt tự nhiên.
  - Có cơ chế **Fallback thông minh**: Vẫn chạy mượt mà ngay cả khi chưa cấu hình API Key.
- 📬 **Đa kênh nhận tin:**
  - 📱 **Telegram Bot:** Định dạng HTML sạch đẹp, tự động chia trang nếu bản tin dài.
  - 💬 **Discord Webhook:** Hiển thị dạng **Rich Embeds** chia màu theo từng chuyên mục.
  - 📄 **GitHub Daily Digest:** Tự động tạo file `digests/YYYY-MM-DD.md` và cập nhật mục lục ngay trên repo mỗi sáng.
- ⚡ **Serverless 0 đồng:** Chạy tự động lúc **05:45 sáng (giờ Việt Nam)** hàng ngày bằng **GitHub Actions** mà không cần thuê VPS hay bật máy tính.

---

## 🗂️ Cấu trúc dự án

```text
morning-pulse/
├── .github/workflows/
│   └── daily_digest.yml       # Cronjob tự động chạy mỗi sáng trên GitHub Actions
├── digests/                   # Kho lưu trữ bản tin Markdown hàng ngày
├── src/
│   ├── config.py              # Quản lý cấu hình & biến môi trường
│   ├── models.py              # Data models chuẩn hóa
│   ├── scrapers/              # Module thu thập dữ liệu (GitHub, HN, Reddit, RSS)
│   ├── summarizer/            # Module AI tóm tắt (Gemini / OpenAI + Fallback)
│   └── notifiers/             # Module gửi tin (Telegram, Discord, Markdown)
├── config.yaml                # Tùy chỉnh nguồn tin, số lượng bài, ngôn ngữ
├── .env.example               # Mẫu cấu hình biến môi trường
├── main.py                    # Điểm chạy chính của chương trình
└── requirements.txt           # Danh sách thư viện Python
```

---

## 🚀 Hướng dẫn cài đặt & Sử dụng

### Cách 1: Chạy tự động miễn phí trên GitHub (Khuyên dùng)

1. **Đẩy dự án này lên GitHub** (hoặc bấm **Fork**).
2. Vào repository của bạn trên GitHub ➡️ **Settings** ➡️ **Secrets and variables** ➡️ **Actions** ➡️ **New repository secret**.
3. Thêm các biến sau (tùy thuộc kênh bạn muốn dùng):

| Tên Secret | Bắt buộc? | Mô tả cách lấy |
| :--- | :---: | :--- |
| `GEMINI_API_KEY` | Khuyên dùng | Lấy miễn phí tại [Google AI Studio](https://aistudio.google.com/app/apikey). |
| `TELEGRAM_BOT_TOKEN` | Tùy chọn | Chat với [`@BotFather`](https://t.me/BotFather) trên Telegram, gõ `/newbot` để nhận token. |
| `TELEGRAM_CHAT_ID` | Tùy chọn | Nhắn tin bất kỳ cho bot của bạn, sau đó lấy ID qua [`@userinfobot`](https://t.me/userinfobot). |
| `DISCORD_WEBHOOK_URL` | Tùy chọn | Trong kênh Discord: *Edit Channel* ➡️ *Integrations* ➡️ *Webhooks* ➡️ *New Webhook* ➡️ *Copy Webhook URL*. |

4. Vào tab **Actions** trên GitHub ➡️ Chọn workflow **☕ Morning Pulse Daily Digest** ➡️ Bấm **Run workflow** để kiểm tra ngay lập tức!

---

### Cách 2: Chạy thử trên máy cá nhân (Local)

```bash
# 1. Cài đặt các thư viện cần thiết
pip install -r requirements.txt

# 2. Tạo file .env từ file mẫu (nếu muốn test AI, Telegram, Discord)
cp .env.example .env

# 3. Chạy thử chế độ Dry-Run (Chỉ cào tin và xuất ra file Markdown trong thư mục digests/)
python main.py --dry-run

# 4. Chạy đầy đủ (Cào tin + AI tóm tắt + Gửi Telegram/Discord + Lưu Markdown)
python main.py
```

---

## ⚙️ Tùy biến nguồn tin (`config.yaml`)

Bạn có thể dễ dàng thêm/bớt các Subreddit, nguồn báo RSS hoặc số lượng tin mỗi chuyên mục ngay trong file [`config.yaml`](./config.yaml) mà không cần sửa code Python:

```yaml
sources:
  github_trending:
    enabled: true
    limit: 6
  reddit:
    enabled: true
    limit_per_sub: 3
    subreddits:
      - "programming"
      - "technology"
      - "LocalLLaMA"
      - "soccer"
```

---

## 📄 Giấy phép (License)

Dự án được phân phối dưới giấy phép **MIT License** — thoải mái sử dụng, chỉnh sửa và chia sẻ!
