# Bộ chuyển đổi Latin → chữ Thái Việt Nam (Tai Viet, U+AA80–U+AADF) v2

Học trực tiếp từ dữ liệu bạn cung cấp, **chỉ dùng 1.114 dòng `FIXED_MANUALLY`**.

```bash
python3 build_model.py                       # học bảng -> model.json
python3 tavt2.py --eval                      # đánh giá lại trên chính từ điển
python3 tavt2.py vanban.txt -o ketqua.txt -r baocao.txt
python3 tavt2.py --csv tudien.csv --col "Từ Thái (Latinh)" -o ketqua.csv
```

## Kết quả

| | Độ chính xác | Ý nghĩa |
|---|---|---|
| **[A] Mục từ có trong từ điển** | **99,91%** (1072/1073) | tra bảng — dùng cho toàn bộ vốn từ đã có |
| [B] Âm tiết đã gặp, chỉ quy tắc | 95,83% | không tra bảng |
| [C] Âm tiết **mới**, quy tắc (5-fold CV) | 93,14% | mỗi âm tiết rời |
| [D] Mục từ **hoàn toàn mới** (5-fold CV) | 61,42% | cả cụm 2–3 âm tiết phải đúng hết |

**Vượt 97% chỉ đảm bảo cho [A]** — tức mọi từ nằm trong từ điển (1.073 mục,
729 âm tiết). Với từ hoàn toàn mới thì trần là ~93%/âm tiết và không thể cao
hơn, vì lý do ở mục "Giới hạn vật lý" bên dưới.

## Giới hạn vật lý: chữ Latin không ghi đủ thông tin

Chữ Thái Việt Nam mã hoá thanh bằng **lớp phụ âm đầu** (mỗi phụ âm có 2 dạng
LOW/HIGH, đọc giống nhau). Nguồn từ điển dùng **hệ truyền thống không đánh dấu
thanh** — chỉ 61/2.043 âm tiết có dấu thanh, phần lớn còn đặt sai vị trí, nên
mô hình bỏ hẳn dấu thanh và để lớp phụ âm mang thanh.

Ánh xạ thanh Việt → lớp (học từ dữ liệu, kèm độ nhất quán):

| dấu | lớp | nhất quán |
|---|---|---|
| hỏi | LOW | 99,6% |
| nặng | HIGH | 99,6% |
| huyền | HIGH | 98,8% |
| ngang | LOW | 98,1% |
| **sắc** | **LOW** | **91,7%** ← nguồn lỗi chính |

`sắc` lệch vì lớp còn phụ thuộc phụ âm đầu: với phụ âm vang (`m`, `n`, `h`,
`ng`) thì `sắc` → HIGH, với phụ âm tắc (`b`, `c`, `đ`, `p`) → LOW. Mô hình học
riêng bảng `(thanh, phụ âm đầu)` và lùi về `(thanh)` khi thiếu dữ liệu — cách
này nâng [C] từ 91,8% lên 93,1%. Phần dư lại là **thông tin từ vựng thuần tuý**,
chỉ giải được bằng từ điển.

## Làm sạch bằng tương quan giữa các mục

Bạn đã lưu ý dữ liệu `FIXED_MANUALLY` vẫn có sai sót. Đúng vậy, và chúng được
xử lý ở ba tầng:

1. **Loại cặp mâu thuẫn đa số** (220/2.043 ≈ 11%): một cặp bị loại nếu phụ âm
   đầu *hoặc* mẫu vần của nó trái với ánh xạ đa số học từ phần còn lại. Ví dụ
   `khảu → ꪹꪘꪱ` (phụ âm `n`) trong khi 30+ mục khác cho `kh → ꪄ/ꪅ`.
2. **Sửa lỗi tách từ** (`repair.py`): cột Latinh bị OCR cắt giữa âm tiết
   (`b ăư m ạy` → `băư mạy`), cột Unicode bị tách rời dấu phụ
   (`ꪮꪱꪚ ꪤ ꪲꪙ` → `ꪮꪱꪚ ꪤꪲꪙ`). Riêng bước này nâng [A] từ 94,7% lên 99,9%.
3. **Tách riêng mục có đáp án cụt** (36 mục): `băư lem` trong CSV chỉ có `ꪻꪚ`,
   thiếu hẳn âm tiết hai. Không có đáp án để chấm nên để riêng, đánh dấu
   `DAP_AN_CUT_CAN_SOAT` trong file sạch.

## Kiểm chứng quyết định bỏ `HIGH_CONFIDENCE`

Bạn bảo bỏ, và số liệu xác nhận là đúng: mô hình học từ `FIXED_MANUALLY` khớp
**0/7.679** dòng `HIGH_CONFIDENCE`. Xem cột `Ký tự PDF Gốc` thì rõ lý do — đó
là nhiễu OCR thô (`'cao đi' | 'ꪠꪧ ꫝ' | 'MIO o'`). Cột "Độ Tin Cậy" của các dòng
này không phản ánh chất lượng thật. Đừng đưa chúng vào corpus huấn luyện.

## Chính tả: nguồn từ điển ≠ nguồn Kinh Thánh

Hai nguồn dùng quy ước Latin khác nhau, đừng trộn:

| | từ điển | Kinh Thánh (Ma-thi-ơ) |
|---|---|---|
| /əw/ | `ăư` | `âu` |
| nguyên âm dài | `oong`, `ôông`, `êêng` | `ong`, `ông`, `êng` |
| /aw/ | `au` → `ꪹ◌ꪱ` | `au` |
| /aːw/ | `ao` → `◌ꪱꪫ` | `ao` |
| dấu thanh | 5 dấu, không ngã | 5 dấu, không ngã |

Chạy `tavt2.py` trên `sample.txt` (Kinh Thánh) hiện hỏng 19,6% âm tiết đúng vì
lý do này. Muốn xử lý nguồn Kinh Thánh thì cần bộ từ điển đối chiếu riêng cho
quy ước đó — hoặc viết lớp chuẩn hoá `âu→ăư`, `ông→ôông`… trước khi chuyển.

Một điểm nữa: từ điển đặt dấu phụ **sau phụ âm cuối** (`ung → ◌ꪉꪴ`,
`ăng → ◌ꪉꪰ`) trong khi CLDR/Tai Dam đặt trước. Brase ghi nhận đúng sự dao động
này (23 trước / 9 sau trong một bản chép tay Tai Don). Mô hình học theo nguồn
của bạn, nên giữ nguyên quy ước của từ điển.

## Tệp

| tệp | nội dung |
|---|---|
| `model.json` | bảng phụ âm/vần/thanh + từ điển 729 âm tiết & 1.071 mục từ |
| `tavt2.py` | bộ chuyển đổi 3 tầng (từ → âm tiết → quy tắc) |
| `build_model.py` | học & đánh giá lại từ CSV gốc |
| `repair.py` | sửa lỗi tách từ trong nguồn |
| `taiviet_dictionary_clean.csv` | **1.109 mục đã làm sạch** — corpus dùng được |
| `errors.txt`, `eval_entries.txt` | chi tiết từng chỗ sai, để soát tay |

## Cần làm tiếp để vượt 97% trên từ mới

Chỉ có một cách: **mở rộng từ điển**. Mỗi ~600 âm tiết soát tay thêm sẽ phủ
thêm phần lớn văn bản thực tế, vì phân bố âm tiết rất lệch. Ưu tiên soát
`errors.txt` (những âm tiết mà quy tắc và dữ liệu bất đồng) — đó là chỗ mỗi giờ
công bỏ ra thu lại nhiều nhất.


---

# Cập nhật: bảng chuẩn từ giáo trình Tản Chụ Xiết Xương

## Ba lỗi trong ví dụ bạn gửi, và nguyên nhân

| lỗi | trước | sau |
|---|---|---|
| mẫu vần sai cấu trúc (hai nguyên âm-đứng-trước liền nhau) | `phổng → ꪹꪹꪠꪫ` | `ꪶꪠꪉ` |
| | `cộng → ꪹꪹꪁꪫ` | `ꪶꪁꪉ` |
| vần thiếu, bỏ nguyên chữ Latin | `huồm cưa hữa chuyến xửa khuốp ửa` | `ꪭꪺꪣ ꪹꪀ ꪹꪬ ꪊꪫꪸꪙ ꪹꪎ ꪄꪺꪚ ꪹꪮ` |
| chính tả `ong` hiểu sai | `Xong → ꪹꪎꪰꪉ` (/səŋ/) | `ꪎꪮꪉ` (/sɔːŋ/) |

Ba nguyên nhân khác nhau:

1. **Một dòng hỏng thành luật.** Vần `ông` chỉ có đúng 1 dẫn chứng trong từ điển,
   và dẫn chứng đó là `ꪹꪹ◌ꪫ` — hai ký tự `ꪹ` liền nhau, cấu trúc không tồn tại.
   Đã thêm bộ lọc `wellformed()` loại mọi chuỗi kiểu này khỏi dữ liệu học.
2. **Từ điển không phủ hết vần.** `ưa`, `uôm`, `uôp`, `uyên` không có mục nào.
   Nay sinh từ bảng nguyên âm của giáo trình → **0% âm tiết bị bỏ sót** (trước là 7).
3. **Hai nguồn, hai quy ước chính tả khác nhau** — xem dưới.

## Quan trọng: nguồn của bạn dùng hai chính tả không tương thích

Trong từ điển Sơn La, `ong` có 5 dẫn chứng **nhất quán 100%** là `ꪹ◌ꪰꪉ` (/əŋ/),
còn /ɔŋ/ viết là `oong` (20 dẫn chứng). Trong giáo trình thì `ong` = /ɔŋ/ và
không có nguyên âm đôi. Nên `Xong` (= "hai") ra sai khi dùng bảng của từ điển.

Ngờ rằng đây là lỗi OCR trong CSV của bạn: `ơng` mất dấu móc thành `ong`
(cả hai đều cho `ꪹ◌ꪰꪉ`). Đáng kiểm lại trực tiếp trên bản PDF gốc.

Vì vậy nay có cờ chọn nguồn — **phải chọn đúng, không có mặc định an toàn**:

```bash
python3 tavt2.py vanban.txt -p textbook -o ketqua.txt   # Tản Chụ Xiết Xương
python3 tavt2.py vanban.txt -p dict     -o ketqua.txt   # từ điển Sơn La (mặc định)
```

## Bảng giáo trình đã số hoá: `tables_textbook.py`

22 phụ âm × 2 nhóm (tố tằm / tố xủng), 18 nguyên âm, 9 phụ âm cuối, 5 chữ đặc
biệt (`nưng` ꫜ, `cỗn` ꫛ, `ho hỡi` ꫞, `lải làu` ꫟). Dùng để đè lên các mẫu học
sai và lấp chỗ trống.

Hai chỗ bảng giáo trình phải nhường dữ liệu, vì bằng chứng quá mạnh:

- **`ơ` → `ꪹ◌ꪰ`** (106 dẫn chứng, nhất quán 100%), không phải `ꪹ◌ꪷ` như CLDR.
  Nguồn Sơn La dùng dấu `ꪰ` cho /ə/.
- **`o` phụ thuộc ngữ cảnh**: âm tiết mở → `ꪷ` (MAI KHIT), âm tiết đóng → `ꪮ`
  (LOW O). Khớp cả CLDR lẫn dữ liệu.

## Phát hiện đáng giá nhất từ giáo trình

Ghi chú cuối bảng phụ âm: *"các phụ âm nhóm cao được thể hiện bằng chữ in HOA"*.

Tức chính tả của giáo trình mã hoá **lớp thanh bằng chữ hoa/thường** — đúng
thông tin mà chính tả dấu-thanh của từ điển làm mất, và là nguồn gốc của trần
93% ở phần trước. Nếu bạn OCR được giáo trình mà **giữ nguyên phân biệt hoa/thường**
ở cột chữ Việt, lớp thanh không còn phải đoán và độ chính xác trên từ mới sẽ
vượt xa 93%. Đây là thứ đáng ưu tiên nhất khi cấu hình OCR — đừng để pipeline
lowercase toàn bộ.

## Số liệu sau khi sửa

| | trước | sau |
|---|---|---|
| Mục từ trong từ điển | 99,91% | 99,91% |
| Âm tiết mới (5-fold CV) | 93,14% | **93,36%** |
| Âm tiết bỏ sót trên văn bản mẫu | 7 | **0** |
| Chuỗi sai cấu trúc | có | **0** (`validate.py` sạch) |
