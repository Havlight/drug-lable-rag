import re
import time

import requests
from lxml import etree
from pathvalidate import sanitize_filename
import os
import fitz
from io import BytesIO
from requests.exceptions import ChunkedEncodingError
from llama_parse import LlamaParse

parser = LlamaParse(
    api_key="llx-t4mG9drX8NEbhrjPFln5vhWUppRRLZRfJ85hvbBJwCRevKWh",
    result_type="markdown",
    verbose=True,
    language="ch_tra"
)
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br, zstd', 'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'max-age=0', 'Connection': 'keep-alive',
    'Host': 'mcp.fda.gov.tw', 'Referer': 'https://mcp.fda.gov.tw/im',
    'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not A Brand";v="99"', 'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"', 'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-User': '?1', 'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'}


def process_document_text(doc_text):
    # Step 1: Remove extra blank lines after headers
    lines = doc_text.splitlines()
    processed_lines = []
    skip_next_empty_line = False

    for line in lines:
        if line.startswith("#") and not line.strip().endswith(":"):
            processed_lines.append(line)
            skip_next_empty_line = True
        elif line.strip() == "" and skip_next_empty_line:
            continue
        else:
            processed_lines.append(line)
            skip_next_empty_line = False

    return "\n".join(processed_lines)


# Function to extract the indication text following #適應症
def extract_indication(doc_text):
    # Match any line containing "適應症" and capture any text after it
    match = re.search(r"#.*適\s*應\s*症.*[:：()【【[]?\n?(.*)", doc_text)
    return match.group(1).strip() if match else None


def scrape_one_page(code: str, management: str):
    folder_name = "一般仿單"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    # 發送請求並解析 HTML
    url = f"https://mcp.fda.gov.tw/im_detail_pdf/{management}字第{code}號/"
    try:
        print("正在爬取: " + url)
        response = requests.get(url, timeout=(10, 30), stream=True, headers=headers)
    except requests.exceptions.Timeout:
        print("Timed out")

    if response.status_code == 302:
        print("查無此仿單資料")
        return
    if response.url == "https://mcp.fda.gov.tw/im":
        print("查無此仿單資料")
        return

    content = response.content.decode(errors="ignore")
    html = etree.HTML(content)
    # 定義 XPath
    zh_name_xpath = "//label[text()='中文品名']/following-sibling::span[1]/text()"
    en_name_xpath = "//label[text()='英文品名']/following-sibling::span[1]/text()"
    code_xpath = "//label[text()='許可證號']/following-sibling::span[1]/text()"
    category_xpath = "//label[text()='藥品類別']/following-sibling::span[1]/text()"
    type_xpath = "//label[text()='劑型']/following-sibling::span[1]/text()"
    compony_xpath = "//label[text()='申請商地址']/following-sibling::span[1]/text()"
    expire_status_xpath = "//label[text()='註銷狀態']/following-sibling::span[1]/text()"
    expire_date_xpath = "normalize-space(//label[text()='有效日期']/following-sibling::span[1]/text())"
    # 提取 XPath 結果
    zh_name = sanitize_filename(''.join(html.xpath(zh_name_xpath)).strip())
    en_name = ''.join(html.xpath(en_name_xpath)).strip()
    code = ''.join(html.xpath(code_xpath)).strip()
    category = ''.join(html.xpath(category_xpath)).strip()
    type_ = ''.join(html.xpath(type_xpath)).strip()
    compony = ''.join(html.xpath(compony_xpath)).strip()
    expire_status = ''.join(html.xpath(expire_status_xpath)).strip()
    expire_date = ''.join(html.xpath(expire_date_xpath)).strip()

    if expire_status.find("已註銷") != -1:
        print("藥品已註銷")
        return True

    # 使用XPath找到PDF的<a>標籤的href屬性
    pdf_relative_url = html.xpath("//a[contains(text(), '.pdf')]/@href")

    if not pdf_relative_url:
        print("PDF 文件未找到")
        return True

    # Step 3: 完整PDF的URL
    base_url = "https://mcp.fda.gov.tw"
    pdf_url = [base_url + u for u in pdf_relative_url]

    # 使用中文品名作為 Markdown 檔名
    pdf_file_name = f"{code}-{zh_name}.pdf"
    pdf_file_path = os.path.join(folder_name, pdf_file_name)

    # Step 4: 下載PDF文件
    pdf_responses = []
    for u in pdf_url:
        pdf_responses.append(requests.get(u, stream=True, headers=headers))

    idx = find_first_text_pdf_position(pdf_responses)
    # 寫入pdf 若有文字則寫入 否則 寫入最後的
    with open(pdf_file_path, "wb") as f:
        f.write(pdf_responses[idx].content)

    # 使用 parser 加載保存的 PDF 文件
    try:
        documents = parser.load_data([pdf_file_path])
    except Exception as e:
        print(f"無法解析 PDF 文件: {e}")
        return
    # 保存解析後的 Markdown 文件
    zh_name = sanitize_filename(zh_name)
    md_file_name = f"{code}-{zh_name}.md"
    md_file_path = os.path.join(folder_name, md_file_name)
    indication = None  # Initialize indication to None
    with open(md_file_path, 'w', encoding='utf-8') as f:
        for document in documents:
            processed_text = process_document_text(document.text)
            f.write(processed_text + "\n")  # Write processed text

            # Attempt to extract indication for filename
            if not indication:  # Only try to get indication once
                indication = extract_indication(processed_text)
        # Rename the file after closing it
    if indication:
        indication = sanitize_filename(indication.split('。')[0][:40])
        new_md_filename = f"{md_file_path.rsplit('.', 1)[0]}-{indication}.md"
        print(f"新檔案名稱: {new_md_filename}")
        os.rename(md_file_path, new_md_filename)
    return True


def scrape_one_page_retry(code, max_retry, management):
    max_retries = max_retry
    retry_count = 0
    while retry_count < max_retries:
        try:
            succ = scrape_one_page(code, management)
            return succ
        except Exception as e:
            retry_count += 1
            print(e)
            print(f"Retry {retry_count}/{max_retries} due to ChunkedEncodingError.")
            time.sleep(2)  # 暫停一段時間再重試


def find_first_text_pdf_position(pdf_responses):
    # 迭代每個PDF
    for index, response in enumerate(pdf_responses):
        if response.status_code == 200:
            # 將PDF數據存儲為BytesIO流
            pdf_stream = BytesIO(response.content)

            # 使用PyMuPDF來打開PDF文件
            with fitz.open(stream=pdf_stream, filetype="pdf") as pdf_file:
                for page_number in range(len(pdf_file)):
                    page = pdf_file.load_page(page_number)
                    text = page.get_text("text")

                    # 如果該頁有文本，返回該PDF的索引
                    if text.strip():  # 檢查是否有非空文本
                        return index

    # 如果沒有任何PDF包含文字，返回-1
    return -1


options = {
    1: "衛署藥製",
    2: "衛部藥製",
    3: "衛署藥輸",
    4: "衛部藥輸",
    5: "衛署成製",
    6: "衛部成製",
    7: "衛署菌疫製",
    8: "衛部菌疫製",
    9: "衛署菌疫輸",
    10: "衛部菌疫輸",
    11: "衛署成輸",
    12: "衛部成輸",
    13: "衛署罕藥輸",
    14: "衛部罕藥輸",
    15: "衛署罕藥製",
    16: "衛部罕藥製",
    17: "衛署罕菌疫製",
    18: "衛部罕菌疫製",
    19: "衛部罕菌疫輸",
    20: "衛署罕菌疫輸",
    21: "衛署藥陸輸",
    22: "衛部藥陸輸",
    23: "內衛藥製",
    24: "內衛藥輸",
    25: "內衛成製",
    26: "內衛菌疫製",
    27: "內衛菌疫輸"
}

api_key_pool = {1: 'llx-XBf4F270tLIbl2UAuyyOTZWjvmU9G1k2S5uxY2jywdLsQehV',
                2: 'llx-rySrnLnJmquA3xlx81utLkgDLefVZnP2DnljjQeaZDvwIeuc',
                3: 'llx-pvxcRA4SWBnryAlnGmD7ceo1b7JMUEaQlFoRlhDi7iYa944Z',
                4: 'llx-XVBhRFffHqnXbP05qoIR0eQYncBMp6cJLNy1zp7z4MmWJGoh',
                5: 'llx-VKH8qIJQLHkp7Sa4W2bspEJG6pga9WcBH1eyyTuiiekUVIW8',
                6: 'llx-ydIQmlGwmwS3De1fVxmnh4hFi4FlOEhPqMXtpetRo75cRAd7',
                7: 'llx-6JCKqMtIYwut8FwYuBPK0MEMi7ifxCU4njxeswg7CgKFoWav',
                8: 'llx-fVWdsClyJWG8ZhRiiBsECdugttp5J1bFuJNWEftJdo95Wp2m',
                9: 'llx-qfqlC82bfuXMcfiSYbBsTmgsvJXiqzxi7z6mbTWSB7Yh4tUs',
                10: 'llx-nCbcZiJR9lnLdmzTu0ZDxtG6ICYl7z4uT4kfLsweZ79a6LHu',
                11: 'llx-n007Cq3qktZcFazYfJ5AyTm7FPPzPeRsEMv0gtUVnlqtjh3f'}

"""034626"""


def main():
    while True:
        print("選擇操作模式：")
        print("1. 範圍抓取")
        print("2. 單次抓取")
        mode = input("請輸入選擇 (1 或 2): ")
        print(api_key_pool)
        api_key_index = int(input("請輸入選擇 api key id: "))
        parser.api_key = api_key_pool[api_key_index]
        print(f"使用api key :{api_key_pool[api_key_index]}")
        if mode == '1':
            try:
                start = int(input("請輸入起始代碼: "))
                end = int(input("請輸入結束代碼: "))
                delay = float(input("請輸入每次抓取的延遲時間（秒）: "))

                for i in range(start, end + 1):
                    code = f'{i:06d}'  # 將數字格式化為六位數
                    nums = [1, 3, 4]
                    for j in nums:
                        succ = scrape_one_page_retry(code, 3, options[j])
                        if succ:
                            break
                        time.sleep(delay)  # 延遲抓取
            except ValueError:
                print("請輸入有效的數字範圍和延遲時間。")
        elif mode == '2':
            code = input("請輸入要抓取的代碼 (六位數): ")
            print("選擇仿單證別")
            print(options)
            category = int(input("請輸入一個數字 (1-27): "))
            if len(code) == 6 and code.isdigit():
                scrape_one_page(code, management=options[category])
            else:
                print("代碼應為六位數字。")
        else:
            print("無效的選擇，請輸入1或2。")

        # 允許使用者決定是否繼續
        continue_choice = input("是否繼續操作? (y/n): ").lower()
        if continue_choice != 'y':
            break


if __name__ == "__main__":
    main()
