# GitHub Pages Client

## Mục tiêu
Client web tách rời backend Flask, chạy trực tiếp trên GitHub Pages.

## Cách bật GitHub Pages
1. Push repo lên GitHub.
2. Vào **Settings → Pages**.
3. Ở **Build and deployment**:
   - Source: **Deploy from a branch**
   - Branch: **main**
   - Folder: **/docs**
4. Save và chờ URL Pages được cấp.

## Cấu hình trong client
- File client: `docs/index.html`
- Mặc định API base: `https://hotantai.id.vn`
- Có thể đổi ngay trong ô `API Base URL` nếu cần.

## Lưu ý
- Backend phải chạy HTTPS và mở CORS.
- Client dùng Bearer token (`Authorization`) để gọi API bảo vệ.
