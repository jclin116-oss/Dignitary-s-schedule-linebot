import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import urllib3
import re

# 關閉 SSL 憑證警告資訊
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與佈局
st.set_page_config(page_title="國家政要公開行程", layout="wide")

st.title("總統府、行政院、經濟部國家政要公開行程")
st.caption("u272260-115-6-23")

# --- 側邊欄配置 ---
st.sidebar.header("📅 設定日期")
target_date = st.sidebar.date_input("選擇日期", datetime.today())
start_search = st.sidebar.button("開始同步並篩選資料", type="primary")

# 定義轄區關鍵字
JURISDICTION_KEYWORDS = ["基隆", "雙溪", "貢寮", "老梅", "石門", "瑞芳", "萬里", "金山", "汐止", "平溪", "三芝", "石碇", "慈護宮", "拱北殿", "靈鷲山", "勸濟堂", "慶安宮"]

# ==================== 1. 總統府解析邏輯 ====================
def parse_president_schedule(scraped_date):
    date_str = scraped_date.strftime("%Y-%m-%d")
    base_url = f"https://www.president.gov.tw/Page/37?FDate={date_str}&EDate={date_str}"
    
    roc_year_str = f"{scraped_date.year - 1911}年"
    month_str = f"{scraped_date.month}月"
    day_str = f"{scraped_date.day}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    parsed_data = {
        "總統": {"時間": [], "行程內容": []},
        "副總統": {"時間": [], "行程內容": []}
    }

    try:
        res = requests.get(base_url, headers=headers, timeout=15, verify=False)
        if res.status_code == 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")
            body = soup.find("body")
            
            if body:
                raw_text = body.get_text(separator="\n", strip=True)
                lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
                
                in_target_section = False
                current_role = None
                i = 0
                
                while i < len(lines):
                    if i + 3 < len(lines) and lines[i].endswith("年") and lines[i+1].endswith("月") and lines[i+3] == "日":
                        if lines[i] == roc_year_str and lines[i+1] == month_str and lines[i+2] == day_str:
                            in_target_section = True
                            i += 4
                            if i < len(lines) and lines[i].startswith("星期"):
                                i += 1
                            continue
                        else:
                            if in_target_section:
                                break
                            i += 4
                            continue
                    
                    if in_target_section:
                        if lines[i] in parsed_data.keys():
                            current_role = lines[i]
                            i += 1
                            
                            while i < len(lines):
                                if i + 3 < len(lines) and lines[i].endswith("年") and lines[i+1].endswith("月") and lines[i+3] == "日":
                                    break
                                if lines[i] in ["總統", "副總統", "總統府"]:
                                    break
                                    
                                line = lines[i]
                                if line == "無公開行程":
                                    parsed_data[current_role]["時間"].append("-")
                                    parsed_data[current_role]["行程內容"].append("無公開行程")
                                    i += 1
                                elif re.match(r"^\d{2}:\d{2}", line):
                                    time_val = line
                                    if i + 1 < len(lines):
                                        next_line = lines[i+1]
                                        is_separator = (next_line in ["總統", "副總統", "總統府"] or 
                                                        re.match(r"^\d{2}:\d{2}", next_line) or 
                                                        (next_line.endswith("年") and i + 4 < len(lines) and lines[i+2].endswith("月")))
                                        if not is_separator:
                                            parsed_data[current_role]["時間"].append(time_val)
                                            parsed_data[current_role]["行程內容"].append(next_line)
                                            i += 2
                                            continue
                                    parsed_data[current_role]["時間"].append(time_val)
                                    parsed_data[current_role]["行程內容"].append("")
                                    i += 1
                                else:
                                    i += 1
                        else:
                            i += 1
                    else:
                        i += 1
    except Exception:
        pass

    final_rows = []
    for role in ["總統", "副總統"]:
        times = parsed_data[role]["時間"]
        contents = parsed_data[role]["行程內容"]
        
        if len(times) > 1 and "-" in times:
            idx = times.index("-")
            times.pop(idx)
            contents.pop(idx)
            
        if times and contents:
            for t, c in zip(times, contents):
                final_rows.append({
                    "機關": "總統府",
                    "類別/官階": role,
                    "行程內容": c if c else "公開行程",
                    "時間": t
                })
        else:
            final_rows.append({
                "機關": "總統府",
                "類別/官階": role,
                "行程內容": "無公開行程",
                "時間": "-"
            })
            
    return final_rows


# ==================== 2. 行政院解析邏輯 ====================
def parse_taiwan_date(date_text):
    if not date_text:
        return None
    try:
        month_match = re.search(r'(\d+)\s*月', date_text)
        day_match = re.search(r'(\d+)\s*日', date_text)
        year_match = re.search(r'(\d+)\s*年', date_text)
        
        if month_match and day_match and year_match:
            month = int(month_match.group(1))
            day = int(day_match.group(1))
            tw_year = int(year_match.group(1))
            ad_year = tw_year + 1911
            return f"{ad_year}-{month:02d}-{day:02d}"
    except Exception:
        pass
    return None

def get_ey_data(url, title, target_date_str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    scraped_data = []

    try:
        res = requests.get(url, headers=headers, timeout=15, verify=False)
        if res.status_code == 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")
            outer_blocks = soup.find_all(class_="timeline_block")
            
            for block in outer_blocks:
                date_tag = block.find(class_=["timeline-date", "newsDate"])
                if not date_tag:
                    continue
                    
                raw_date_text = date_tag.get_text(separator=' ', strip=True)
                parsed_date_str = parse_taiwan_date(raw_date_text)
                
                if parsed_date_str != target_date_str:
                    continue
                
                content_tag = block.find(class_="timeline-content")
                if content_tag:
                    lines = [line.strip() for line in content_tag.get_text(separator="\n", strip=True).split("\n") if line.strip()]
                    if lines:
                        first_line = lines[0]
                        time_match = re.match(r'^([上下]午\d+:\d+(?:~\d+:\d+)?|上午|下午)', first_line)
                        
                        if time_match:
                            time_str = time_match.group(1)
                            content_str = " ".join(lines).replace(time_str, "", 1).strip()
                        else:
                            time_str = "-"
                            content_str = " ".join(lines)
                            
                        scraped_data.append({
                            "機關": "行政院",
                            "類別/官階": title,
                            "行程內容": content_str,
                            "時間": time_str
                        })
    except Exception:
        pass
        
    if not scraped_data:
        scraped_data.append({
            "機關": "行政院",
            "類別/官階": title,
            "行程內容": "無公開行程",
            "時間": "-"
        })
        
    return scraped_data


# ==================== 3. 經濟部解析邏輯 ====================
def get_moea_schedule(url, target_date_str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.moea.gov.tw/"
    }

    categories_status = {
        "部長": [],
        "次長": []
    }
    
    target_date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")

    try:
        res = requests.get(url, headers=headers, timeout=15, verify=False)
        if res.status_code == 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")
            date_tags = soup.find_all(id=re.compile(r'lblDate_S_'))
            
            for d_tag in date_tags:
                date_text = d_tag.get_text(strip=True)
                day_container = d_tag.find_parent(class_=re.compile(r'sch_day|divchs|divchs_items'))
                if not day_container:
                    day_container = d_tag.parent.parent
                
                year_tag = day_container.find(class_="sch_year")
                year_text = year_tag.get_text(strip=True) if year_tag else str(target_date_obj.year)
                
                month_match = re.search(r'(\d+)\s*月', date_text)
                day_match = re.search(r'(\d+)\s*日', date_text)
                
                if month_match and day_match:
                    m = int(month_match.group(1))
                    d = int(day_match.group(1))
                    y = int(year_text)
                    current_date_str = f"{y}-{m:02d}-{d:02d}"
                else:
                    continue
                
                if current_date_str != target_date_str:
                    continue
                
                sch_blocks = day_container.find_all(class_="divSch")
                if not sch_blocks:
                    sibling = day_container.find_next_sibling()
                    while sibling and "divSch" in sibling.get("class", []):
                        sch_blocks.append(sibling)
                        sibling = sibling.find_next_sibling()
                
                for block in sch_blocks:
                    kind_tag = block.find(class_="minister-kind")
                    title = kind_tag.get_text(strip=True) if kind_tag else None
                    
                    if not title or title not in categories_status:
                        continue
                    
                    title_tag = block.find(class_="sch-title")
                    if not title_tag:
                        continue
                    
                    title_text = title_tag.get_text(strip=True)
                    
                    if "本日無公開行程" in title_text:
                        continue
                    
                    time_match = re.match(r'^(\d+:\d+\s*[APMpm]+|[上下]午\s*\d+:\d+)', title_text)
                    if time_match:
                        time_str = time_match.group(1)
                        content_str = title_text.replace(time_str, "", 1).strip()
                    else:
                        time_str = "-"
                        content_str = title_text
                    
                    place_tag = block.find(class_="sch-place")
                    place_str = place_tag.get_text(strip=True).replace("地點：", "").strip() if place_tag else "-"
                    
                    if place_str and place_str != "-":
                        content_str = f"{content_str}（地點：{place_str}）"
                    
                    categories_status[title].append({"時間": time_str, "行程內容": content_str})
                        
    except Exception:
        pass
        
    final_rows = []
    for cat in ["部長", "次長"]:
        data_list = categories_status[cat]
        if data_list:
            for item in data_list:
                final_rows.append({
                    "機關": "經濟部",
                    "類別/官階": cat,
                    "行程內容": item["行程內容"],
                    "時間": item["時間"]
                })
        else:
            final_rows.append({
                "機關": "經濟部",
                "類別/官階": cat,
                "行程內容": "無公開行程",
                "時間": "-"
            })
            
    return final_rows


# ==================== 4. 主畫面控制中心 ====================
if start_search:
    date_str = target_date.strftime("%Y-%m-%d")
    all_consolidated_data = []
    
    with st.spinner(f"⚡ 正在跨單位同步 {date_str} 的特定政要公開行程..."):
        try:
            president_data = parse_president_schedule(target_date)
            all_consolidated_data.extend(president_data)
        except Exception as e:
            st.error(f"總統/副總統行程抓取失敗: {e}")
            
        try:
            ey_urls = {
                "院長": "https://www.ey.gov.tw/Page/278197D37F0FCDA",
                "副院長": "https://www.ey.gov.tw/Page/EE0A18CCA0C9BC4",
                "秘書長": "https://www.ey.gov.tw/Page/98C9B1D4B4F70B85"
            }
            for title, url in ey_urls.items():
                ey_data = get_ey_data(url, title, date_str)
                all_consolidated_data.extend(ey_data)
        except Exception as e:
            st.error(f"行政院政要行程抓取失敗: {e}")
            
        try:
            moea_url = "https://www.moea.gov.tw/Mns/populace/news/MinisterSchedule.aspx?menu_id=42225"
            moea_data = get_moea_schedule(moea_url, date_str)
            all_consolidated_data.extend(moea_data)
        except Exception as e:
            st.error(f"經濟部政要行程抓取失敗: {e}")
            
        df_final = pd.DataFrame(all_consolidated_data)
        
        st.success(f"📊 查詢成功！已完成 {date_str} 的特定政要行程搜尋。")
        
        display_cols = ["機關", "類別/官階", "行程內容", "時間"]
        df_final = df_final[display_cols]
        
        # 顯示處理後總表
        st.dataframe(df_final, use_container_width=True, hide_index=True)
        
        # ---- 轄區關鍵字比對邏輯 ----
        st.subheader("🔍 基隆區處轄區到訪檢視")
        
        matched_records = []
        for index, row in df_final.iterrows():
            content = str(row["行程內容"])
            # 找出行程內容中有包含哪些轄區關鍵字
            found_keywords = [kw for kw in JURISDICTION_KEYWORDS if kw in content]
            
            if found_keywords:
                matched_records.append({
                    "機關": row["機關"],
                    "類別/官階": row["類別/官階"],
                    "行程內容": row["行程內容"],
                    "時間": row["時間"],
                    "觸發關鍵字": "、".join(found_keywords)
                })
        
        if matched_records:
            df_matched = pd.DataFrame(matched_records)
            st.error(f"⚠️ 注意：偵測到當日有政要即將前往基隆區處轄區！")
            st.dataframe(df_matched[["機關", "類別/官階", "觸發關鍵字", "行程內容", "時間"]], use_container_width=True, hide_index=True)
        else:
            st.success("✅ 經比對，當日無核心政要前往基隆區處轄區（基隆、雙溪、貢寮、老梅、石門、瑞芳、萬里、金山、汐止）的公開行程。")
        
       # 下載 CSV (修正 Excel 開啟亂碼問題)
        csv_data = df_final.to_csv(index=False, encoding="utf-8-sig")
        
        st.download_button(
            label="📥 匯出政要行程表為 CSV",
            data=csv_data.encode('utf-8-sig'),  # 關鍵修正：確保加上 BOM 的二進位資料完整寫入
            file_name=f"特定政要公開行程表_{date_str}.csv",
            mime="text/csv"
        )
else:
    st.info("💡 請於左側設定抓取日期後，點擊「開始同步並篩選資料」按鈕。")
    
# ==================== 5. 自動化執行與 LINE 通知 (GitHub Actions 用) ====================
def send_line_notification(message):
    import os
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")
    
    if not token or not user_id:
        print("未設定 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID，跳過發送。")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            print("LINE 通知發送成功！")
        else:
            print(f"LINE 發送失敗，狀態碼：{res.status_code}, 回應：{res.text}")
    except Exception as e:
        print(f"LINE 發送異常: {e}")

# 判定是否在 GitHub Actions 環境執行（非點擊 Streamlit 按鈕時觸發）
if __name__ == "__main__" and not start_search:
    from datetime import timezone, timedelta
    
    # 強制修正為台灣時區 (UTC+8)
    tz_taiwan = timezone(timedelta(hours=8))
    today_obj = datetime.now(tz_taiwan)
    date_str = today_obj.strftime("%Y-%m-%d")
    
    print(f"=== 開始執行每日政要行程自動監控 ({date_str}) ===")
    
    auto_consolidated_data = []
    
    # 1. 總統府
    try:
        auto_consolidated_data.extend(parse_president_schedule(today_obj))
    except Exception as e:
        print(f"總統府抓取失敗: {e}")
        
    # 2. 行政院
    try:
        ey_urls = {
            "院長": "https://www.ey.gov.tw/Page/278197D37F0FCDA",
            "副院長": "https://www.ey.gov.tw/Page/EE0A18CCA0C9BC4",
            "秘書長": "https://www.ey.gov.tw/Page/98C9B1D4B4F70B85"
        }
        for title, url in ey_urls.items():
            auto_consolidated_data.extend(get_ey_data(url, title, date_str))
    except Exception as e:
        print(f"行政院抓取失敗: {e}")
        
    # 3. 經濟部
    try:
        moea_url = "https://www.moea.gov.tw/Mns/populace/news/MinisterSchedule.aspx?menu_id=42225"
        auto_consolidated_data.extend(get_moea_schedule(moea_url, date_str))
    except Exception as e:
        print(f"經濟部抓取失敗: {e}")

    # 4. 比對轄區關鍵字
    auto_matched = []
    for row in auto_consolidated_data:
        content = str(row.get("行程內容", ""))
        found_keywords = [kw for kw in JURISDICTION_KEYWORDS if kw in content]
        if found_keywords:
            auto_matched.append({
                "機關": row["機關"],
                "官階": row["類別/官階"],
                "行程": row["行程內容"],
                "時間": row["時間"],
                "關鍵字": "、".join(found_keywords)
            })

# 5. 組裝訊息（無論有無行程都發送）
    if auto_matched:
        msg = f"⚠️【政要公開行程監控日報】{date_str}\n偵測到當日有政要前往基隆區處轄區！\n\n"
        for item in auto_matched:
            msg += f"• [{item['機關']}] {item['官階']}\n  觸發關鍵字：{item['關鍵字']}\n  時間：{item['時間']}\n  內容：{item['行程']}\n\n"
    else:
        msg = f"【政要公開行程監控日報】{date_str}\n經自動化比對，當日無核心政要前往基隆區處轄區公開行程，系統運作正常，手動查詢介面：https://h5rxs9rxdlzmuxffk8f2vg.streamlit.app/。"

    # 6. 發送 LINE 通知
    send_line_notification(msg)
