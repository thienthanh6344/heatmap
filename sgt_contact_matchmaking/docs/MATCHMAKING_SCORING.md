# TÀI LIỆU KỸ THUẬT: MATCHMAKING SCORING & RECOMMENDATION ENGINE (TASK 20)
**Module:** `sgt_contact_matchmaking`  
**Odoo Version:** 19.0 Community / Enterprise  
**Author:** SGT Engineering Team  
**Status:** Production Ready  

---

## 1. MỤC ĐÍCH HỆ THỐNG (PURPOSE)
Hệ thống **Matchmaking Scoring / Recommendation Engine** (Task 20) được thiết kế nhằm tự động phân tích dữ liệu một Liên hệ / Doanh nghiệp nguồn (**Source Contact**) trong Odoo CRM (`res.partner`) và tự động tìm kiếm, tính điểm tương đồng, xếp hạng và đề xuất **TOP 10** đối tác kinh doanh phù hợp nhất (**Top 10 Matching Companies**).

Các mục tiêu cốt lõi:
- **Tự động hóa kết nối giao thương:** Giúp bộ phận Sales & BizDev lập tức phát hiện các đối tác tiềm năng từ hội chợ triển lãm, danh mục sản phẩm và chuỗi cung ứng.
- **Tính toán minh bạch, có thể giải thích (Explainable AI / Scoring):** Mọi điểm số đều được chia nhỏ theo từng tiêu chí cụ thể và có lý do chi tiết kèm theo. Không dùng thuật toán "hộp đen" hay random/mock scoring trong môi trường production.
- **Trực quan hóa hiện đại:** Cung cấp giao diện CRM Card Dashboard và bảng đối soát trực quan ngay trên Odoo Contact form thông qua nút bấm **"Find Matching Companies"**.

---

## 2. NGUỒN DỮ LIỆU SỬ DỤNG (DATA SOURCES)

Hệ thống khai thác các trường dữ liệu thực tế từ model `res.partner` (tận dụng kế thừa các trường đã định nghĩa ở Task 7, Task 10, Task 11, Task 12, Task 19):

| Tiêu chí | Trường dữ liệu trong `res.partner` | Kiểu dữ liệu | Ý nghĩa |
| :--- | :--- | :--- | :--- |
| **Vai trò đối tác** | `x_type_contact` | `Selection` (`'buyer'`, `'seller'`, `'both'`) | Xác định tư cách Buyer (Mua), Seller (Bán) hoặc Both (Cả hai) |
| **Danh mục sản phẩm** | `x_product_category`<br>`category_id` | `Char` (chuỗi phân cách dấu phẩy)<br>`Many2many` (`res.partner.category`) | Các ngành hàng/danh mục mà đối tác cung cấp hoặc tìm kiếm |
| **Thông tin sản phẩm** | `x_product_details` | `Text` | Chi tiết quy cách, năng lực cung ứng, danh mục hàng hóa bổ trợ |
| **Sự kiện tham gia** | `x_event` | `Char` (chuỗi phân cách dấu phẩy) | Tên hội chợ, triển lãm, diễn đàn thương mại đã/sắp tham gia |
| **Ngành nghề** | `industry_id`<br>`x_fb_industry` | `Many2one` (`res.partner.industry`)<br>`Char` (fallback text) | Ngành kinh doanh tiêu chuẩn hoặc thông tin ngành từ Facebook/Lead |
| **Quốc gia** | `country_id`<br>`country_code` | `Many2one` (`res.country`) | Vị trí địa lý quốc gia của doanh nghiệp |
| **Thông tin cơ bản** | `name`, `email`, `phone`, `website`, `is_company` | Chuẩn Odoo | Định danh đối tác, phân biệt công ty / cá nhân đại diện |

---

## 3. CÔNG THỨC TÍNH ĐIỂM (SCORING FORMULA)

Tổng điểm tối đa là **95 điểm** theo đúng chuẩn quy định của Task 20:

$$\text{Total Score} = S_{\text{category}} + S_{\text{industry}} + S_{\text{event}} + S_{\text{buyer\_seller}} + S_{\text{country}}$$

Trong đó:
- $S_{\text{category}} \in \{0, 30\}$
- $S_{\text{industry}} \in \{0, 20\}$
- $S_{\text{event}} \in \{0, 20\}$
- $S_{\text{buyer\_seller}} \in \{0, 20\}$
- $S_{\text{country}} \in \{0, 5\}$
- $\text{Total Score} \in [0, 95]$

---

## 4. BẢNG ĐIỂM CHI TIẾT (SCORING CRITERIA MATRIX)

| Tiêu chí | Trọng số tối đa | Điều kiện cộng điểm | Điểm cộng | Ghi chú & Logic xử lý |
| :--- | :---: | :--- | :---: | :--- |
| **Product Category** | **+30** | Có ít nhất 1 danh mục sản phẩm trùng nhau | **+30** | Hỗ trợ so sánh tách chuỗi (phân cách bởi dấu `,`, `;`, `\n`) và chuẩn hóa chữ thường. **Chỉ cộng tối đa 30 điểm một lần duy nhất**, dù trùng 1 hay nhiều category. Không trùng: 0 điểm. |
| **Industry** | **+20** | Cùng ngành nghề kinh doanh | **+20** | So sánh thông qua `industry_id` (cùng ID) hoặc so khớp chuỗi không phân biệt hoa thường qua `x_fb_industry`. Giống: +20, khác: 0. |
| **Same Event** | **+20** | Cùng tham gia ít nhất 1 sự kiện / hội chợ | **+20** | Trích xuất danh sách sự kiện từ `x_event`. Nếu tập hợp sự kiện giao nhau $\neq \emptyset \implies +20$. **Chỉ cộng tối đa 20 điểm một lần duy nhất**. Không trùng: 0 điểm. |
| **Buyer / Seller Complementary** | **+20** | Vai trò bổ trợ giao thương tương thích:<br>• Buyer $\leftrightarrow$ Seller<br>• Seller $\leftrightarrow$ Buyer<br>• Both $\leftrightarrow$ Buyer<br>• Both $\leftrightarrow$ Seller<br>• Both $\leftrightarrow$ Both | **+20** | **Không cộng điểm (0 điểm)** nếu cùng là Buyer thuần túy (Buyer - Buyer) hoặc cùng là Seller thuần túy (Seller - Seller) vì không có tính chất bù trừ cung - cầu. |
| **Same Country** | **+5** | Cùng quốc gia | **+5** | So sánh `country_id` hoặc tên quốc gia. Trùng quốc gia: +5, khác quốc gia: 0 điểm. |
| **TỔNG CỘNG** | **95** | Đạt toàn bộ 5 tiêu chí tương thích hoàn hảo | **95** | Điểm tuyệt đối = 95/95. |

---

## 5. THUẬT TOÁN MATCHING (MATCHMAKING ALGORITHM)

Quy trình tính điểm diễn ra tuần tự qua các bước:

```
[Source Contact]
       │
       ▼
[Lọc tập ứng viên Candidate Pool] (Active = True, ID != Source.ID)
       │
       ▼
[Chuẩn hóa dữ liệu từng cặp] 
   • Trích xuất danh mục (lowercase, strip whitespace)
   • Trích xuất sự kiện (tokenized set)
   • Xác định vai trò (buyer/seller/both)
   • So khớp ngành nghề & quốc gia
       │
       ▼
[Tính điểm thành phần & ghi nhận lý do]
   • Category Match? -> +30 (Ghi nhận các category trùng)
   • Industry Match? -> +20 (Ghi nhận tên ngành)
   • Event Match?    -> +20 (Ghi nhận tên sự kiện)
   • Complementary?  -> +20 (Ghi nhận quan hệ Buyer-Seller)
   • Same Country?   -> +5  (Ghi nhận tên quốc gia)
       │
       ▼
[Tổng hợp điểm & Gán nhãn phân loại (Tier/Grade)]
   • 80 - 95: Excellent Match (Rất cao)
   • 60 - 79: Strong Match (Cao)
   • 40 - 59: Potential Match (Trung bình)
   • 20 - 39: Low Match (Thấp)
   • 0 - 19: Unfavorable (Rất thấp)
       │
       ▼
[Sắp xếp xác định Top 10]
```

---

## 6. CƠ CHẾ LẤY TOP 10 (TOP 10 RANKING & TIE-BREAKING)

Để đảm bảo kết quả nhất quán, công bằng và có thể tái tạo (Deterministic, không bị random):
1. **Tiêu chí sắp xếp chính:** `score DESC` (Ứng viên điểm cao nhất lên đầu).
2. **Tiêu chí phụ 1 (Tie-breaker 1):** `name ASC` (Nếu bằng điểm nhau, sắp xếp theo bảng chữ cái alphabet tên đối tác).
3. **Tiêu chí phụ 2 (Tie-breaker 2):** `id ASC` (Nếu trùng cả tên, sắp xếp theo ID tăng dần trong cơ sở dữ liệu).
4. **Giới hạn kết quả:** Trả về chính xác danh sách **10 đối tác đầu tiên** (hoặc ít hơn nếu tổng số contact trong hệ thống $< 10$).
5. **Gán thứ hạng:** Đánh số thứ tự từ `#1` đến `#10`.

---

## 7. CƠ CHẾ LOẠI TRỪ CHÍNH MÌNH (SELF-MATCH PREVENTION)

Để ngăn chặn lỗi logic đối tác tự kết nối với chính mình:
1. Khi truy vấn danh sách ứng viên từ ORM, áp dụng domain bắt buộc:
   ```python
   domain = [
       ('id', '!=', source_contact.id),
       ('active', '=', True),
   ]
   ```
2. Nếu đối tác là một cá nhân thuộc công ty (hoặc công ty mẹ), loại trừ thêm các liên hệ con (`parent_id == source.id`) nếu cùng đại diện cho một pháp nhân thương mại.
3. Trong method `calculate_match_score(source, target)`, kiểm tra điều kiện bảo vệ cấp độ 2:
   ```python
   if not source or not target or source.id == target.id:
       return {
           'score': 0.0,
           'reasons': ["Cannot match a contact with itself."],
           ...
       }
   ```

---

## 8. CƠ CHẾ GIẢI THÍCH ĐIỂM (EXPLANATION MECHANISM)

Mỗi kết quả match không chỉ có một con số vô cảm mà luôn đi kèm **Breakdown chi tiết** và **Structured Reasons List**:
- **Reasons List:** Mảng các chuỗi mô tả rõ lý do vì sao được cộng điểm.
  - Ví dụ: `✓ Product Category Match (+30 pts): Matching categories: electronics, iot devices`
  - Ví dụ: `✓ Complementary Business Match (+20 pts): buyer (ABC Trading) ↔ seller (Global Tech)`
  - Ví dụ: `✓ Industry Alignment (+20 pts): Same industry: Technology & Electronics`
  - Ví dụ: `✓ Shared Event Participation (+20 pts): Matching events: Vietnam Expo 2026`
  - Ví dụ: `✓ Same Country (+5 pts): Both based in Vietnam`
  - Nếu không đạt tiêu chí nào, hiển thị rõ lý do chưa trùng khớp (VD: `✗ No overlapping product categories (+0 pts)`).
- **Giao diện CRM Card:** Trực quan hóa bằng thanh tiến độ phần trăm (Progress Bar), huy hiệu phân hạng (Badge Tiers: Excellent, Strong, Potential, Low) và các checklist icon xanh `✓` / xám `✗`.

---

## 9. TẬP DỮ LIỆU DEMO (DEMO DATASET)

Tập dữ liệu demo được thiết kế trong file `data/demo_data_task20.xml` bao gồm 1 Source Contact và 12 Candidate Contacts phủ kín toàn bộ các dải điểm từ 0 đến 95:

| ID XML | Tên Doanh nghiệp | Vai trò | Category | Industry | Event | Country | Điểm dự kiến |
| :--- | :--- | :---: | :--- | :--- | :--- | :---: | :---: |
| `demo_source_partner_task20` | **ABC Trading Co., Ltd** (Source) | **Buyer** | Electronics, IoT Devices | Technology | Vietnam Expo 2026 | Vietnam | **(Gốc)** |
| `demo_cand_95_perfect` | Global Tech Supplier Co. | Seller | Electronics, Automation | Technology | Vietnam Expo 2026 | Vietnam | **95** |
| `demo_cand_75_no_country` | Tokyo Components Inc | Seller | Electronics, Semiconductors | Technology | Vietnam Expo 2026 | Japan | **75** |
| `demo_cand_70_no_event` | Hanoi Electronics Factory | Seller | IoT Devices, Electronics | Technology | Hanoi Trade Fair | Vietnam | **70** |
| `demo_cand_55_cat_bs` | Vina Supply Chain JSC | Both | Electronics, Hardware | Logistics | Saigon Logistics Day | Vietnam | **55** |
| `demo_cand_50_cat_ind` | NextGen Tech Solutions | Buyer (no BS) | IoT Devices, Cloud | Technology | TechInAsia 2026 | Singapore | **50** |
| `demo_cand_45_ind_event` | Asian Expo Marketing Group | Seller | Furniture, Home Decor | Technology | Vietnam Expo 2026 | Vietnam | **45** |
| `demo_cand_40_bs_event` | Saigon Hardware Hub | Seller | Machinery, Equipment | Retail | Vietnam Expo 2026 | Vietnam | **40** |
| `demo_cand_30_cat_only` | Da Nang Component Mart | Buyer (no BS) | Electronics, Tools | Retail | Da Nang Expo | Germany | **30** |
| `demo_cand_25_bs_country` | Mekong Goods Distribution | Seller | FMCG, Food | Agriculture | Mekong Fair | Vietnam | **25** |
| `demo_cand_20_event_only` | Viet Build Exhibition Co. | Buyer (no BS) | Construction, Cement | Construction | Vietnam Expo 2026 | Thailand | **20** |
| `demo_cand_05_country_only` | Saigon Ceramic Artistry | Buyer (no BS) | Ceramics, Porcelain | Arts & Crafts | Bat Trang Fair | Vietnam | **5** |
| `demo_cand_00_no_match` | European Luxury Fashion SARL | Buyer (no BS) | Fashion, Apparel | Textile & Garment | Paris Fashion Week | France | **0** |

---

## 10. DANH SÁCH TEST CASES (AUTOMATED TEST SUITE)

Tất cả 15 kịch bản kiểm thử được cài đặt đầy đủ trong file:  
`addons/sgt_contact_matchmaking/tests/test_matchmaking_recommendation_task20.py`

1. **TC1: Perfect Match (95 pts)** - Thử nghiệm ứng viên trùng khớp cả 5 tiêu chí (Category + Industry + Event + Buyer/Seller + Country).
2. **TC2: Category Only (+30 pts)** - Chỉ trùng danh mục sản phẩm, các tiêu chí khác khác biệt.
3. **TC3: Multiple Category Overlap Capping (+30 pts Max)** - Trùng 3 danh mục nhưng điểm chỉ cộng đúng 30 điểm một lần.
4. **TC4: Industry Only (+20 pts)** - Chỉ trùng ngành nghề kinh doanh.
5. **TC5: Event Only (+20 pts)** - Chỉ trùng sự kiện tham gia, không bị cộng trùng lặp nhiều lần.
6. **TC6: Buyer - Seller Complementary (+20 pts)** - Buyer ghép với Seller được cộng 20 điểm.
7. **TC7: Both - Buyer / Both - Seller (+20 pts)** - Đối tác có vai trò 'both' ghép với Buyer hoặc Seller đều được 20 điểm.
8. **TC8: Buyer - Buyer Non-Complementary (0 pts)** - Buyer ghép với Buyer không được cộng điểm bổ trợ.
9. **TC9: Seller - Seller Non-Complementary (0 pts)** - Seller ghép với Seller không được cộng điểm bổ trợ.
10. **TC10: Country Only (+5 pts)** - Chỉ cùng quốc gia, các tiêu chí khác không trùng.
11. **TC11: Zero Match (0 pts)** - Hai đối tác hoàn toàn khác biệt ở cả 5 tiêu chí.
12. **TC12: Self Match Exclusion (0 pts & Excluded)** - Kiểm tra thuật toán loại trừ chính mình, điểm trả về 0 và ứng viên không bao giờ xuất hiện trong danh sách.
13. **TC13: Missing / Null Fields Resilience** - Đối tác thiếu dữ liệu (None, False, chuỗi rỗng) không làm sập hệ thống (Zero Division / AttributeError Proof).
14. **TC14: Top 10 Limit & Sorting Order** - Đánh giá 12 ứng viên, kiểm tra kết quả trả về đúng 10 bản ghi và sắp xếp giảm dần theo điểm (`score DESC`).
15. **TC15: Explainable Reasons Breakdown** - Kiểm tra mảng `reasons` chứa đầy đủ văn bản giải thích các tiêu chí được cộng điểm.

---

## 11. VÍ DỤ TÍNH ĐIỂM CỤ THỂ CHO 2 DOANH NGHIỆP

### Ví dụ 1: Đối tác Global Tech Supplier Co.
- **Source:** ABC Trading Co., Ltd (`buyer`, `Electronics, IoT Devices`, `Technology`, `Vietnam Expo 2026`, `Vietnam`)
- **Target:** Global Tech Supplier Co. (`seller`, `Electronics, Automation`, `Technology`, `Vietnam Expo 2026`, `Vietnam`)

**Chi tiết tính điểm từng bước:**
1. **Product Category:** 
   - Source: `{"electronics", "iot devices"}`
   - Target: `{"electronics", "automation"}`
   - Giao nhau: `{"electronics"}` $\implies$ **+30 điểm**
2. **Industry:**
   - Cùng ngành `Technology` $\implies$ **+20 điểm**
3. **Same Event:**
   - Cùng tham gia `Vietnam Expo 2026` $\implies$ **+20 điểm**
4. **Buyer/Seller Complementary:**
   - Source là `Buyer`, Target là `Seller` $\implies$ Tương thích bù trừ cung cầu $\implies$ **+20 điểm**
5. **Same Country:**
   - Cùng quốc gia `Vietnam` $\implies$ **+5 điểm**

$$\mathbf{\text{Tổng điểm}} = 30 + 20 + 20 + 20 + 5 = \mathbf{95 / 95\text{ điểm}}\quad (\text{Tier: Excellent Match})$$

---

### Ví dụ 2: Đối tác NextGen Tech Solutions
- **Source:** ABC Trading Co., Ltd (`buyer`, `Electronics, IoT Devices`, `Technology`, `Vietnam Expo 2026`, `Vietnam`)
- **Target:** NextGen Tech Solutions (`buyer`, `IoT Devices, Cloud`, `Technology`, `TechInAsia 2026`, `Singapore`)

**Chi tiết tính điểm từng bước:**
1. **Product Category:**
   - Giao nhau danh mục `iot devices` $\implies$ **+30 điểm**
2. **Industry:**
   - Cùng ngành `Technology` $\implies$ **+20 điểm**
3. **Same Event:**
   - `Vietnam Expo 2026` $\neq$ `TechInAsia 2026` $\implies$ **0 điểm**
4. **Buyer/Seller Complementary:**
   - Source là `Buyer`, Target cũng là `Buyer` $\implies$ Cùng là bên mua, không bổ trợ giao thương $\implies$ **0 điểm**
5. **Same Country:**
   - `Vietnam` $\neq$ `Singapore` $\implies$ **0 điểm**

$$\mathbf{\text{Tổng điểm}} = 30 + 20 + 0 + 0 + 0 = \mathbf{50 / 95\text{ điểm}}\quad (\text{Tier: Potential Match})$$
