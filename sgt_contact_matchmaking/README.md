# SGT Contact Match Making Addon (`sgt_contact_matchmaking`)
**Odoo 19 Module - Task 19 Enterprise Contact Similarity & Matchmaking Engine**

---

## 1. Overview & Mục Tiêu
Addon **SGT Contact Match Making** (`sgt_contact_matchmaking`) được thiết kế riêng cho **Odoo 19** nhằm mục đích:
- So sánh cặp 2 Contact bất kỳ trong hệ thống Odoo (`res.partner`).
- Tính điểm độ tương đồng tổng thể (**Overall Match Score: 0 – 100%**) theo thuật toán giải thích được (Explainable Scoring Engine).
- Phân loại độ tương thích rõ ràng theo 5 cấp độ:
  - **80 – 100%**: Very High Match (Xanh lá - Emerald `#10b981`)
  - **60 – 79%**: High Match (Xanh dương - Sapphire `#2563eb`)
  - **40 – 59%**: Medium Match (Hổ phách - Amber `#f59e0b`)
  - **20 – 39%**: Low Match (Cam - Orange `#f97316`)
  - **0 – 19%**: Very Low Match (Đỏ - Red `#ef4444`)
- Cung cấp giao diện hiện đại phong cách **Modern Business CRM Dashboard** với card đối chiếu song song, circular progress score indicator, progress bars cho từng tiêu chí, danh sách lý do trực quan (*Why are these contacts matched?*), và bảng so sánh chi tiết (*Difference View*) kèm badges phân loại (`MATCH`, `SIMILAR`, `DIFFERENT`, `MISSING`).
- Quản lý lịch sử match (`sgt.contact.match`) có cơ chế chuẩn hóa cặp đối xứng (`min_id` & `max_id`) chống duplicate history khi đảo thứ tự Contact A ↔ B.
- Tích hợp Smart Button `Match Contacts (<count>)` trên form Contact và launcher 1-click mở công cụ so sánh.
- **Phạm vi nghiêm ngặt**: Thực hiện trọn vẹn Task 19 Contact Match Making, **không lấn sang Task 20 AI Recommendation**.

---

## 2. Kiến Trúc & Cấu Trúc Addon
```
addons/sgt_contact_matchmaking/
│
├── __init__.py
├── __manifest__.py                      # Khai báo metadata, dependencies, assets CSS, views, demo data
│
├── models/
│   ├── __init__.py
│   ├── contact_match.py                 # Core model: sgt.contact.match & Scoring Engine, Normalization, HTML Generator
│   ├── contact_match_wizard.py          # Transient model: sgt.contact.match.wizard cho Interactive UI
│   └── res_partner.py                   # Extension: res.partner thêm smart button match_count & launcher action
│
├── views/
│   ├── contact_match_wizard_views.xml   # Form tương tác so sánh Contact A vs B, Side-by-side cards, Dashboard nhúng
│   ├── contact_match_views.xml          # List, Form, Search, Graph, Pivot views cho Lịch sử Match (sgt.contact.match)
│   ├── res_partner_views.xml            # Thêm Smart Button Match Contacts và Action launcher trên res.partner
│   └── menu_views.xml                   # Menu: Contacts -> Match Making (Compare Contacts, Match History, Match Analytics)
│
├── security/
│   ├── security.xml                     # res.groups: Contact Match User, Contact Match Manager
│   └── ir.model.access.csv              # Phân quyền CRUD chi tiết cho models
│
├── data/
│   ├── ir_sequence_data.xml             # Mã tham chiếu tự động: MTCH/%(range_year)s/00001
│   └── demo_data.xml                    # 9 contacts tạo thành 3 cặp High, 3 cặp Medium, 3 cặp Low
│
├── static/
│   └── src/
│       └── css/
│           └── contact_match.css        # CSS tùy biến cho Modern Business Dashboard
│
├── tests/
│   ├── __init__.py
│   └── test_contact_matchmaking.py      # Automated test suite kiểm tra toàn diện 12 kịch bản
│
└── README.md
```

---

## 3. Thuật Toán Scoring & Cấu Hình Trọng Số (Configurable Weights)

Toàn bộ trọng số được tập trung cấu hình trong từ điển `MATCH_WEIGHTS` tại [`contact_match.py`](models/contact_match.py):

| Tiêu Chí Đánh Giá | Trọng Số Max | Quy Tắc Tính Điểm & Điều Kiện Phân Loại |
| :--- | :---: | :--- |
| **Email Address** | **25.0** | • Giống hoàn toàn sau trim/lowercase: **+25.0** (`MATCH`)<br>• Cùng Corporate Domain (loại trừ `@gmail.com`, `@yahoo.com`...): **+10.0** (`SIMILAR`)<br>• Khác domain: **0.0** (`DIFFERENT`)<br>• Thiếu email: **0.0** (`MISSING`) |
| **Phone / Mobile** | **20.0** | • Giống hoàn toàn sau khi strip ký tự lạ/chuẩn hóa đầu số: **+20.0** (`MATCH`)<br>• Trùng 7 chữ số cuối (số nội hạt/chuyển vùng): **+10.0** (`SIMILAR`)<br>• Khác: **0.0** (`DIFFERENT`)<br>• Thiếu phone: **0.0** (`MISSING`) |
| **Company Entity** | **15.0** | • Cùng công ty mẹ (`parent_id`) hoặc tên công ty sau khi loại noise words (`Cty`, `TNHH`, `JSC`...): **+15.0** (`MATCH`)<br>• Jaccard Token Similarity $\ge 0.4$: **+8.0** (`SIMILAR`)<br>• Khác: **0.0** (`DIFFERENT`) |
| **Full Name** | **10.0** | • Trùng tên tuyệt đối: **+10.0** (`MATCH`)<br>• Trùng tên sau khi bỏ dấu tiếng Việt Unicode: **+8.5** (`SIMILAR`)<br>• Trùng $\ge 50\%$ từ trong tên: **+5.0** (`SIMILAR`) |
| **Job Position** | **10.0** | • Giống hoàn toàn chức danh: **+10.0** (`MATCH`)<br>• Chứa chung từ khóa cốt lõi (ví dụ *"Sales"* trong *"Sales Director"* vs *"Sales Executive"*) hoặc Jaccard $\ge 0.3$: **+6.0** (`SIMILAR`) |
| **Industry** | **10.0** | • Trùng ngành nghề kinh doanh (`industry_id` hoặc tên ngành): **+10.0** (`MATCH`) |
| **Location** | **5.0** | • Trùng cả Tỉnh/Thành phố hoặc Quốc gia: **+5.0** (`MATCH`)<br>• Trùng vùng miền/quốc gia riêng biệt: **+3.0** (`SIMILAR`) |
| **Tags / Categories** | **5.0** | • Trùng toàn bộ tập Tags (`category_id`): **+5.0** (`MATCH`)<br>• Có tag giao thoa: **+2.5 $\times$ số tag trùng** (max 5.0) (`SIMILAR`) |
| **TỔNG ĐIỂM** | **100.0** | **Chuẩn hóa về thang 0 – 100%** |

---

## 4. Cơ Chế Chuẩn Hóa Dữ Liệu (Data Normalization)
1. **Unicode Tiếng Việt**: Hàm `remove_vietnamese_diacritics(text)` chuẩn hóa các ký tự có dấu (`à, á, ả, ã, ạ, â, ầ, ấ, ă, đ, ê, ô, ơ, ư...`) sang ký tự ASCII không dấu tương ứng, đảm bảo *"Nguyễn Văn An"* và *"Nguyen Van An"* được nhận diện tương đồng cao.
2. **Số điện thoại**: Hàm `normalize_phone_number(phone)` loại bỏ khoảng trắng, dấu gạch nối `-`, dấu chấm `.`, ngoặc đơn `()`, chuẩn hóa mã quốc gia `+84` sang đầu số `0`.
3. **Email**: Trimming, lowercasing, tách riêng email domain và kiểm tra loại trừ các generic email providers (`gmail.com`, `yahoo.com`, `outlook.com`...).
4. **Tên Doanh Nghiệp**: Loại bỏ các hậu tố/tiền tố phổ biến (`CÔNG TY`, `TNHH`, `JSC`, `CP`, `CO.`, `LTD`, `CORP`, `ENTERPRISE`, `VIETNAM`...) trước khi so khớp token Jaccard.
5. **Chống Duplicate & Self-Match**:
   - Chặn tuyệt đối `Contact A == Contact B` (báo UserError/ValidationError thân thiện).
   - Khóa cặp đối xứng: `pair_key = min(id_a, id_b) + "_" + max(id_a, id_b)` đảm bảo thứ tự A↔B hoặc B↔A đều tái sử dụng 1 bản ghi duy nhất, cập nhật điểm thay vì tạo bản ghi rác.

---

## 5. Giao Diện Người Dùng (UI / UX)
- **Menu Đường Dẫn**:
  - `Contacts` $\rightarrow$ `Match Making` $\rightarrow$ `Compare Contacts` (Màn hình tương tác chính)
  - `Contacts` $\rightarrow$ `Match Making` $\rightarrow$ `Match History` (Lịch sử đã so sánh)
  - `Contacts` $\rightarrow$ `Match Making` $\rightarrow$ `Match Analytics` (Biểu đồ phân phối điểm Graph/Pivot)
  - Shortcut trên ứng dụng `CRM` $\rightarrow$ `Tools` $\rightarrow$ `Contact Match Making`
- **Màn Hình Tương Tác (`Compare Contacts`)**:
  - Hero Header chào mừng chuyên nghiệp với badge phiên bản Task 19.
  - Card chọn lựa Contact A và Contact B với input tìm kiếm thông minh.
  - Hai thẻ Contact Card song song hiển thị Avatar initials, Chức vụ, Công ty, Email, Phone.
  - Vòng tròn đo điểm Circular SVG Gauge hiển thị điểm % lớn và nhãn cấp độ có màu sắc tương ứng.
  - Thanh đo tiến độ (Progress bars) trực quan cho từng tiêu chí trong 8 tiêu chí.
  - Khối lý do rõ ràng: *"Why are these contacts matched?"* với icon `✓` cho điểm tương đồng và `⚠` cho cảnh báo sai lệch.
  - Bảng so sánh chi tiết (*Difference View*) với 4 huy hiệu màu sắc:
    - `MATCH` (Xanh lá)
    - `SIMILAR` (Xanh dương)
    - `DIFFERENT` (Đỏ)
    - `MISSING` (Xám)
- **Smart Button Trên Contact Form**:
  - Nút stat `Match Contacts (<count>)` nằm gọn trong `button_box` của `res.partner`.
  - Action dropdown trong menu Action của Contact: `Compare & Match Contact` mở trực tiếp công cụ so sánh với Contact đó được điền sẵn ở vị trí Contact A.

---

## 6. Hướng Dẫn Cài Đặt Trên Odoo 19

### Cách 1: Qua Giao Diện Odoo (Apps)
1. Đăng nhập vào Odoo 19 với tài khoản Quản trị viên (`http://127.0.0.1:8070`).
2. Vào menu **Apps** (Ứng dụng).
3. Bật chế độ **Developer Mode** (hoặc bấm **Update Apps List**).
4. Tìm kiếm từ khóa: `sgt_contact_matchmaking` hoặc `SGT Contact Match Making`.
5. Bấm nút **Activate** (Kích hoạt).

### Cách 2: Qua XML-RPC / Python Script
```python
import xmlrpc.client

url = "http://127.0.0.1:8070"
db = "odoo_01"
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, "tranthien442005@gmail.com", "123456", {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# Tìm và cài đặt module
mod_id = models.execute_kw(db, uid, "123456", "ir.module.module", "search", [[("name", "=", "sgt_contact_matchmaking")]])
models.execute_kw(db, uid, "123456", "ir.module.module", "button_immediate_install", [mod_id])
print("Module installed successfully!")
```

---

## 7. Chạy Bộ Kiểm Thử Tự Động (Automated Test Suite)
Bộ kiểm thử bao gồm **12 kịch bản toàn diện** tại `addons/sgt_contact_matchmaking/tests/test_contact_matchmaking.py`:
- **CASE 1**: Cặp Contact gần giống (Near Identical) $\rightarrow$ Đạt điểm $\ge 80\%$ (`very_high`).
- **CASE 2**: Cặp cùng công ty & domain $\rightarrow$ Đạt điểm $40 – 79\%$ (`medium`/`high`).
- **CASE 3**: Cặp hoàn toàn khác biệt $\rightarrow$ Đạt điểm $< 20\%$ (`very_low`).
- **CASE 4**: Contact khuyết Email $\rightarrow$ Xử lý an toàn, gán badge `MISSING`, 0 crash.
- **CASE 5**: Contact khuyết Phone $\rightarrow$ Xử lý an toàn, gán badge `MISSING`, 0 crash.
- **CASE 6**: Chọn trùng Contact A == Contact B $\rightarrow$ ValidationError chuẩn xác.
- **CASE 7**: Chuẩn hóa khóa đối xứng (`min_id_max_id`) $\rightarrow$ Tái sử dụng bản ghi, chống duplicate history.
- **CASE 8**: Smart button `match_count` & `action_view_matches()` trên `res.partner`.
- **CASE 9**: Launcher 1-click `action_start_match_making()` tự động điền Contact A.
- **CASE 10**: Wizard sinh Dashboard HTML chuẩn Modern CRM.
- **CASE 11**: Kiểm tra Difference View với các badge `MATCH`, `SIMILAR`, `DIFFERENT`, `MISSING`.
- **CASE 12**: Nút `action_recalculate()` cập nhật lại điểm khi dữ liệu gốc thay đổi.

### Lệnh chạy test:
```powershell
& "C:\Users\trant\AppData\Local\Python\pythoncore-3.14-64\python.exe" addons/sgt_contact_matchmaking/tests/test_contact_matchmaking.py
```
**Kết quả**: `ALL 12 TEST CASES PASSED 100%! TASK 19 SGT CONTACT MATCH MAKING IS FULLY VERIFIED!`
