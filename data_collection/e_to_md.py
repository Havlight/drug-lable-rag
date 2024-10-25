import time
import requests
from lxml import etree
from pathvalidate import sanitize_filename
import os
import re
from markdownify import MarkdownConverter


class CustomMarkdownConverter(MarkdownConverter):
    def convert_td(self, el, text, convert_as_inline):
        colspan = 1
        if 'colspan' in el.attrs and el['colspan'].isdigit():
            colspan = int(el['colspan'])
        return ' ' + text.strip() + ' |' * colspan


def md(html, **options):
    return CustomMarkdownConverter(**options).convert(html)


def scrape_one_page(code: str, management: str | None):
    folder_name = "電子仿單"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    # 發送請求並解析 HTML
    url = f"https://mcp.fda.gov.tw/im_detail_1/{management}字第{code}號/"
    try:
        print("正在爬取: " + url)
        response = requests.get(url)
    except requests.exceptions.Timeout:
        print("Timed out")

    if response.url == "https://mcp.fda.gov.tw/im":
        print("查無此仿單資料")
        return

    content = response.content.decode()
    html = etree.HTML(content)

    # 定義 XPath
    zh_name_xpath = "//label[text()='中文品名']/following-sibling::span[1]/text()"
    en_name_xpath = "//label[text()='英文品名']/following-sibling::span[1]/text()"
    code_xpath = "//label[text()='許可證號']/following-sibling::span[1]/text()"
    category_xpath = "//label[text()='藥品類別']/following-sibling::span[1]/text()"
    type_xpath = "//label[text()='劑型']/following-sibling::span[1]/text()"
    expire_date_xpath = "normalize-space(//label[text()='有效日期']/following-sibling::span[1]/text())"
    company_xpath = "normalize-space(//label[text()='申請商名稱']/following-sibling::span[1]/text())"
    info_name_xpath = "//div[@class='toggle-all']//div[@class='toggle']//span[@class='title-name']/text()"
    info_dict = {}
    for key in html.xpath(info_name_xpath):
        info_part = f"//span[text()='{key}']/ancestor::div[@class='toggle']//div[@class='toggle-inner']/div"
        elements = html.xpath(info_part)
        html_text = "".join(
            [etree.tostring(element, encoding='unicode') for element in elements])
        markdown_content = md(html_text).replace("\xa0", " ").strip()
        # 清除 | | |+ 後 清除blank lines
        cleaned_markdown = re.sub(r'^\|\s*\|(\s*\|)+$', "", markdown_content, flags=re.MULTILINE)
        cleaned_markdown = re.sub(r"\n\s*\n", "\n", cleaned_markdown)
        matches = list(re.finditer(r'\n(\|\s*---\s*)+', cleaned_markdown))
        result = cleaned_markdown
        # 遍歷所有匹配部分，從最後一個匹配開始，替換後續匹配為空字符串
        for i in range(len(matches) - 1, 0, -1):  # 跳過第一個匹配
            match = matches[i]
            start, end = match.span()
            result = result[:start] + '' + result[end:]
        cleaned_markdown = result

        info_dict[key] = cleaned_markdown

    # 提取 XPath 結果
    zh_name = sanitize_filename(''.join(html.xpath(zh_name_xpath)).strip())
    en_name = ''.join(html.xpath(en_name_xpath)).strip()
    code = ''.join(html.xpath(code_xpath)).strip()
    category = ''.join(html.xpath(category_xpath)).strip()
    company = ''.join(html.xpath(company_xpath)).strip()
    type_ = ''.join(html.xpath(type_xpath)).strip()
    expire_date = ''.join(html.xpath(expire_date_xpath)).strip()
    # 構建 Markdown 內容
    markdown_content = f"""
## 中文品名
{zh_name}
## 英文品名
{en_name}
## 許可證號
{code}
## 藥品類別
{category}
## 劑型
{type_}
## 有效日期
{expire_date}
## 申請商名稱
{company}
"""
    if not info_dict:
        print("仿單不存在，因跳轉到其他頁面")
        return

    for key, info in info_dict.items():
        markdown_content += f"\n## {key}\n{info}\n"

    file_name = f"{code}-{zh_name}.md"
    for key, value in info_dict.items():
        if key.find("適應症") != -1 or key.find("用途") != -1:
            text = re.split(r'[\n。]', value)[0]
            cleaned_text = re.sub(r'[ \|\-]', '', text)[:40]
            file_name = f"{code}-{zh_name}-{cleaned_text}.md"
            break

    # 使用中文品名作為 Markdown 檔名
    file_path = os.path.join(folder_name, management, file_name)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # 儲存 Markdown 檔案
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(markdown_content)

    print(f"資料已保存至 {file_name}")


# 定義字典
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


def main():
    while True:
        print("你正在抓取電子仿單")
        print("選擇操作模式：")
        print("1. 範圍抓取")
        print("2. 單次抓取")
        mode = input("請輸入選擇 (1 或 2): ")

        print("選擇仿單證別")
        print(options)
        category = int(input("請輸入一個數字 (1-27): "))

        if mode == '1':
            try:
                start = int(input("請輸入起始代碼: "))
                end = int(input("請輸入結束代碼: "))
                delay = float(input("請輸入每次抓取的延遲時間（秒）: "))

                for i in range(start, end + 1):
                    code = f'{i:06d}'  # 將數字格式化為六位數
                    scrape_one_page(code, management=options[category])
                    time.sleep(delay)  # 延遲抓取
            except ValueError:
                print("請輸入有效的數字範圍和延遲時間。")
        elif mode == '2':
            code = input("請輸入要抓取的代碼 (六位數): ")
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
