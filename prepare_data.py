import json
import os
import subprocess
import argparse

def generate_dataset(input_file, output_jsonl):
    """
    Đọc file input (chứa các từ/câu tiếng Thái dạng Latin),
    dùng tavt2.py để dịch sang chữ Thái Việt,
    sau đó tạo file train.jsonl (format ChatML).
    """
    if not os.path.exists(input_file):
        print(f"Lỗi: Không tìm thấy file {input_file}")
        return

    # 1. Dùng tavt2.py để dịch toàn bộ file input ra file tạm
    temp_output = "temp_ketqua.txt"
    print(f"Đang dịch {input_file} sang chữ Thái Việt bằng tavt2.py...")
    subprocess.run(["python3", "tavt2.py", input_file, "-o", temp_output], check=True)

    # 2. Đọc file input và output song song
    with open(input_file, "r", encoding="utf-8") as f_in, \
         open(temp_output, "r", encoding="utf-8") as f_out, \
         open(output_jsonl, "w", encoding="utf-8") as f_jsonl:
        
        latin_lines = f_in.read().splitlines()
        taiviet_lines = f_out.read().splitlines()

        if len(latin_lines) != len(taiviet_lines):
            print("Lỗi: Số dòng của file input và file kết quả không khớp!")
            return

        count = 0
        for latin, taiviet in zip(latin_lines, taiviet_lines):
            latin = latin.strip()
            taiviet = taiviet.strip()
            
            if not latin or not taiviet:
                continue

            # Mẫu 1: Dịch từ Latin -> Thái Việt
            sample1 = {
                "messages": [
                    {"role": "system", "content": "Bạn là chuyên gia dịch thuật tiếng Việt và tiếng Thái (chữ Thái Việt). Hãy dịch chính xác, giữ nguyên nghĩa."},
                    {"role": "user", "content": f"Dịch sang tiếng Thái:\n{latin}"},
                    {"role": "assistant", "content": taiviet}
                ]
            }
            
            # Mẫu 2: Dịch từ Thái Việt -> Latin
            sample2 = {
                "messages": [
                    {"role": "system", "content": "Bạn là chuyên gia dịch thuật tiếng Việt và tiếng Thái (chữ Thái Việt). Hãy dịch chính xác, giữ nguyên nghĩa."},
                    {"role": "user", "content": f"Dịch sang tiếng Việt:\n{taiviet}"},
                    {"role": "assistant", "content": latin}
                ]
            }

            f_jsonl.write(json.dumps(sample1, ensure_ascii=False) + "\n")
            f_jsonl.write(json.dumps(sample2, ensure_ascii=False) + "\n")
            count += 2

    # Xóa file tạm
    if os.path.exists(temp_output):
        os.remove(temp_output)

    print(f"Đã tạo thành công {output_jsonl} với {count} mẫu dữ liệu (cả 2 chiều)!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tạo dataset jsonl từ file văn bản.")
    parser.add_argument("input_file", help="File chứa danh sách từ/câu tiếng Thái Latin")
    parser.add_argument("-o", "--output", default="train.jsonl", help="File output (mặc định: train.jsonl)")
    args = parser.parse_args()
    
    generate_dataset(args.input_file, args.output)
