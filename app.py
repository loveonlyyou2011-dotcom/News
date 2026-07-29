import streamlit as st
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import re
from bs4 import BeautifulSoup
import hashlib
import requests
import google.generativeai as genai

# 페이지 기본 설정 (반응형을 위해 layout="wide" 유지, 모바일 자동 최적화)
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

st.markdown("""
<style>
    /* 전체 배경색 및 기본 폰트 */
    .stApp {
        background-color: #F8FAFC;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    
    /* 상단 타이틀 (모바일 반응형 크기 조절) */
    .main-title {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 2.5rem;
        margin-bottom: 5px;
    }
    
    /* 실시간 뉴스 티커 영역 */
    .ticker-wrap {
        width: 100%;
        background-color: #0f172a;
        height: 44px;
        border-radius: 10px;
        overflow: hidden;
        position: relative;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 30px;
        display: flex;
        align-items: center;
    }
    .ticker-title {
        background-color: #ef4444;
        color: white;
        font-weight: 800;
        padding: 0 16px;
        height: 100%;
        display: flex;
        align-items: center;
        z-index: 10;
        font-size: 0.9rem;
        white-space: nowrap;
        box-shadow: 2px 0 5px rgba(0,0,0,0.2);
    }
    .ticker-content {
        white-space: nowrap;
        animation: ticker 40s linear infinite;
        padding-left: 100%;
        color: #f8fafc;
        font-size: 0.95rem;
    }
    .ticker-content:hover {
        animation-play-state: paused;
    }
    @keyframes ticker {
        0% { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }
    .ticker-content span {
        margin-right: 50px;
    }
    .ticker-content span strong {
        color: #fbbf24; 
    }

    /* 패들렛 스타일 뉴스 카드 (모바일 100% 너비 대응) */
    .news-card {
        background-color: white;
        border-radius: 16px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        margin-bottom: 20px;
        border: 1px solid #e2e8f0;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
        display: flex;
        flex-direction: column;
        width: 100%;
    }
    .news-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 25px rgba(0,0,0,0.1);
        border-color: #cbd5e1;
    }
    .news-image {
        width: 100%;
        height: 160px;
        object-fit: cover;
        background-color: #f1f5f9;
        border-bottom: 1px solid #f1f5f9;
    }
    .news-content {
        padding: 18px;
        display: flex;
        flex-direction: column;
        flex-grow: 1;
    }
    .news-title {
        font-size: 16px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 10px;
        line-height: 1.4;
    }
    .news-title a {
        color: inherit;
        text-decoration: none;
    }
    .news-title a:hover {
        color: #2563eb;
        text-decoration: underline;
    }
    .news-summary {
        font-size: 13.5px;
        color: #475569;
        margin-bottom: 15px;
        line-height: 1.6;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .news-meta {
        font-size: 11.5px;
        color: #94a3b8;
        margin-top: auto;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 1px dashed #e2e8f0;
        padding-top: 12px;
    }
    
    /* 뱃지 스타일 컬럼 헤더 */
    .column-header {
        background-color: white;
        padding: 12px;
        border-radius: 12px;
        text-align: center;
        font-weight: 800;
        font-size: 16px;
        margin-bottom: 20px;
        color: #1e293b;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #e2e8f0;
        border-bottom: 4px solid #3b82f6;
    }

    /* 모바일 및 태블릿 반응형 처리 (미디어 쿼리) */
    @media (max-width: 768px) {
        .main-title { font-size: 1.8rem; }
        .ticker-title { font-size: 0.8rem; padding: 0 10px; }
        .ticker-content { font-size: 0.85rem; }
        .news-title { font-size: 15px; }
        .column-header { font-size: 15px; margin-top: 20px; }
    }
</style>
""", unsafe_allow_html=True)

def extract_article_text(url):
    """뉴스 원문 크롤링 (실패 시 None 반환)"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://news.google.com/'
        }
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=12, allow_redirects=True)
        
        for _ in range(2):
            if "news.google.com" in response.url or "consent.google.com" in response.url:
                soup = BeautifulSoup(response.text, 'html.parser')
                meta = soup.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'refresh'})
                if meta and 'url=' in meta.get('content', '').lower():
                    next_url = re.split('url=', meta['content'], flags=re.IGNORECASE)[-1].strip("'\" ")
                    response = session.get(next_url, headers=headers, timeout=10, allow_redirects=True)
                    continue
                a_tag = soup.find('a', href=True)
                if a_tag and a_tag['href'].startswith('http'):
                    response = session.get(a_tag['href'], headers=headers, timeout=10, allow_redirects=True)
                    continue
                break
            else:
                break

        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        
        target_selectors = [
            ('div', 'dic_area'), ('div', 'articeBody'), ('div', 'newsct_article'), 
            ('div', 'article_view'), ('div', 'news_body'), ('div', 'articleBody'),
            ('div', 'content_body'), ('article', ''), ('div', 'article-body')
        ]
        text_chunks = []
        for tag, name in target_selectors:
            element = soup.find(tag, id=name) or soup.find(tag, class_=name) if name else soup.find(tag)
            if element:
                paragraphs = element.find_all(['p', 'div', 'span'])
                text_chunks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
                if text_chunks:
                    break
        
        if not text_chunks:
            paragraphs = soup.find_all('p')
            text_chunks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]

        final_text = ' '.join(text_chunks)
        final_text = re.sub(r'\s+', ' ', final_text).strip()
        
        if len(final_text) < 100:
            return None
        return final_text[:3500] 
    except Exception:
        return None

def get_ai_summary(text, key):
    """Gemini API 호출"""
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"다음 뉴스 텍스트를 읽고, 핵심 내용만 일반인이 이해하기 쉽게 딱 3줄로 요약해줘. 각 줄은 이모지 없이 불릿기호(-)로 시작할 것:\n\n{text}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"요약 중 오류 발생: API 키가 유효한지 확인해주세요."

@st.cache_data(ttl=60) 
def get_news(query, max_items=10):
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    
    news_list = []
    for entry in feed.entries[:max_items]:
        title = entry.title
        link = entry.link
        
        if " - " in title:
            title_parts = title.rsplit(" - ", 1)
            clean_title = title_parts[0]
            source = title_parts[1]
        else:
            clean_title = title
            source = "알 수 없음"
            
        published = entry.published if hasattr(entry, 'published') else "시간 없음"
        image_url = None
        summary = "관련 기사 상세 내용은 제목을 클릭하여 확인하세요."
        full_raw_text = "" # 봇 차단 시 AI 요약에 사용할 예비용 텍스트
        
        if hasattr(entry, 'description'):
            soup = BeautifulSoup(entry.description, 'html.parser')
            img_tag = soup.find('img')
            if img_tag and img_tag.get('src'):
                image_url = img_tag['src']
            
            raw_text = soup.get_text(separator=' ', strip=True)
            clean_text = raw_text.replace(title, "").replace(clean_title, "").replace(source, "").strip()
            clean_text = re.sub(r'^(.*?)[—|-]\s*', '', clean_text)
            full_raw_text = clean_text # 예비용 저장
            if len(clean_text) > 15:
                summary = clean_text[:80] + "..."
        
        if not image_url:
            seed = hashlib.md5(clean_title.encode('utf-8')).hexdigest()
            image_url = f"https://picsum.photos/seed/{seed}/400/200"
        
        news_list.append({
            "title": clean_title,
            "link": link,
            "source": source,
            "published": published,
            "image": image_url,
            "summary": summary,
            "full_raw_text": full_raw_text # 하이브리드 요약을 위해 추가
        })
    return news_list

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2965/2965306.png", width=60)
    st.title("⚙️ 대시보드 설정")
    
    st.markdown("### 🤖 AI 요약 기능")
    api_key = st.text_input("Gemini API Key 입력", type="password")
    if not api_key:
        st.info("🔑 키를 입력하여 기사 3줄 요약 기능을 켜보세요.")
        
    st.divider()
    refresh_minutes = st.slider("자동 새로고침 주기 (분)", min_value=1, max_value=60, value=5, step=1)
    
    st.divider()
    st.markdown("### 📌 기본 뉴스 주제")
    all_topics = ["시사", "정치", "경제", "연예", "스포츠", "IT/과학", "부동산", "세계"]
    selected_topics = st.multiselect("표시할 카테고리 선택", all_topics, default=["시사", "정치", "경제", "연예"])
    
    st.divider()
    st.markdown("### ✨ 맞춤형 키워드 추가")
    st.caption("텍스트를 입력하면 아래에 새 칸이 생성됩니다.")
    
    if "num_kw_inputs" not in st.session_state:
        st.session_state.num_kw_inputs = 1
        
    custom_keywords = []
    for i in range(st.session_state.num_kw_inputs):
        kw = st.text_input(f"키워드 {i+1}", key=f"kw_input_{i}", placeholder="예: 비트코인, 테슬라")
        if kw.strip() and kw.strip() not in custom_keywords:
            custom_keywords.append(kw.strip())
            
    last_kw_val = st.session_state.get(f"kw_input_{st.session_state.num_kw_inputs - 1}", "")
    
    if last_kw_val.strip() != "" and st.session_state.num_kw_inputs < 10:
        st.session_state.num_kw_inputs += 1
        st.rerun()
        
    if st.session_state.num_kw_inputs > 1 and last_kw_val.strip() == "":
        second_to_last_val = st.session_state.get(f"kw_input_{st.session_state.num_kw_inputs - 2}", "")
        if second_to_last_val.strip() == "":
            st.session_state.num_kw_inputs -= 1
            st.rerun()

final_topics = list(selected_topics)
for kw in custom_keywords:
    if kw not in final_topics:
        final_topics.append(kw)

st_autorefresh(interval=refresh_minutes * 60 * 1000, key="data_refresh")

if not final_topics:
    st.warning("사이드바에서 하나 이상의 주제를 선택하거나 키워드를 입력해주세요.")
    st.stop()

# 메인 데이터 수집
all_news_data = {topic: get_news(topic, max_items=12) for topic in final_topics}

current_time = datetime.now().strftime('%Y년 %m월 %d일 %H:%M')
st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap;">
        <h1 class="main-title">🌐 Live News Desk</h1>
        <span style="color:#64748b; font-size:14px; font-weight:600; margin-bottom:10px;">업데이트: {current_time}</span>
    </div>
""", unsafe_allow_html=True)

ticker_items = []
for topic, items in all_news_data.items():
    if items: 
        ticker_items.append(f"<strong>[{topic}]</strong> {items[0]['title']}")

if ticker_items:
    ticker_text = " &nbsp;&nbsp;&nbsp;✦&nbsp;&nbsp;&nbsp; ".join(ticker_items)
    st.markdown(f"""
    <div class="ticker-wrap">
        <div class="ticker-title">🔥 속보</div>
        <div class="ticker-content">
            <span>{ticker_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# 모니터/태블릿 해상도를 고려하여 1줄에 최대 4개 컬럼까지만 배치하고, 넘어가면 다음 줄로 내림
MAX_COLS_PER_ROW = 4 

for row_start in range(0, len(final_topics), MAX_COLS_PER_ROW):
    row_topics = final_topics[row_start:row_start + MAX_COLS_PER_ROW]
    cols = st.columns(len(row_topics)) # Streamlit이 모바일에서는 자동으로 1열 세로 정렬 처리해줌
    
    for col_index, topic in enumerate(row_topics):
        with cols[col_index]:
            st.markdown(f"<div class='column-header'>{topic}</div>", unsafe_allow_html=True)
            news_items = all_news_data[topic]
            
            # 높이 제한을 두어 스크롤 가능하게 만들고, 모바일 대응
            with st.container(height=800, border=False):
                if not news_items:
                    st.info("뉴스를 불러오지 못했습니다.")
                else:
                    for item_idx, item in enumerate(news_items):
                        card_html = f"""
                        <div class="news-card">
                            <img src="{item['image']}" class="news-image" alt="news thumbnail">
                            <div class="news-content">
                                <div class="news-title">
                                    <a href="{item['link']}" target="_blank">{item['title']}</a>
                                </div>
                                <div class="news-summary">
                                    {item['summary']}
                                </div>
                                <div class="news-meta">
                                    <span>🏢 {item['source']}</span>
                                    <span>🕒 {item['published'][5:16] if len(item['published']) > 16 else item['published']}</span>
                                </div>
                            </div>
                        </div>
                        """
                        st.markdown(card_html, unsafe_allow_html=True)
                        
                        if api_key:
                            article_id = hashlib.md5(item['link'].encode('utf-8')).hexdigest()
                            session_key = f"ai_{topic}_{article_id}"
                            
                            if session_key in st.session_state:
                                st.success(st.session_state[session_key], icon="✨")
                            else:
                                btn_key = f"btn_{row_start}_{col_index}_{item_idx}_{article_id}"
                                if st.button("✨ 이 기사 3줄 요약", key=btn_key, use_container_width=True):
                                    with st.spinner("분석 중..."):
                                        # 1. 원문 크롤링 시도
                                        content = extract_article_text(item['link'])
                                        
                                        # 2. 크롤링 성공 시 원문 요약, 실패 시 하이브리드(RSS 서두) 요약
                                        if content and len(content) > 100:
                                            summary_result = get_ai_summary(content, api_key)
                                        else:
                                            fallback_text = item.get('full_raw_text', '')
                                            if len(fallback_text) > 40:
                                                # 원문을 못가져왔을 때의 훌륭한 대안
                                                prompt_text = f"본문 접근이 제한되어 기사 서두를 바탕으로 요약합니다:\n{fallback_text}"
                                                summary_result = get_ai_summary(prompt_text, api_key)
                                                summary_result = f"*(서두 요약본)*\n\n{summary_result}"
                                            else:
                                                summary_result = "🚫 보안 설정으로 본문 접근이 차단되었습니다. 제목을 클릭해 직접 확인해주세요."
                                                
                                        st.session_state[session_key] = summary_result
                                        st.rerun() 
                        st.write("") # 카드 간 여백

st.markdown("<hr><p style='text-align:center; color:#94a3b8; font-size:12px; margin-top:20px;'>Data provided by Google News RSS. Not for commercial use.</p>", unsafe_allow_html=True)
