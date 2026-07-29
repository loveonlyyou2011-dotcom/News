import streamlit as st
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import re
from bs4 import BeautifulSoup
import hashlib
import requests
import google.generativeai as genai

# 페이지 기본 설정
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

# 모던하고 세련된 UI를 위한 CSS (애니메이션, 그림자, 티커 추가)
st.markdown("""
<style>
    /* 전체 배경색 및 폰트 */
    .stApp {
        background-color: #F7F9FC;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    }
    
    /* 상단 그라데이션 타이틀 */
    .main-title {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 2.5rem;
        margin-bottom: 5px;
    }
    
    /* 실시간 뉴스 티커 (전광판) 영역 */
    .ticker-wrap {
        width: 100%;
        background-color: #1e293b;
        height: 40px;
        border-radius: 8px;
        overflow: hidden;
        position: relative;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 25px;
        display: flex;
        align-items: center;
    }
    .ticker-title {
        background-color: #ef4444;
        color: white;
        font-weight: bold;
        padding: 0 15px;
        height: 100%;
        display: flex;
        align-items: center;
        z-index: 10;
        font-size: 0.9rem;
        white-space: nowrap;
    }
    .ticker-content {
        white-space: nowrap;
        animation: ticker 40s linear infinite;
        padding-left: 100%;
        color: #f8fafc;
        font-size: 0.95rem;
    }
    @keyframes ticker {
        0% { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }
    .ticker-content span {
        margin-right: 50px;
    }
    .ticker-content span strong {
        color: #fbbf24; /* 카테고리 강조색 */
    }

    /* 패들렛 스타일 뉴스 카드 */
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
    }
    .news-summary {
        font-size: 13.5px;
        color: #475569;
        margin-bottom: 15px;
        line-height: 1.6;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .news-meta {
        font-size: 11px;
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
</style>
""", unsafe_allow_html=True)

def extract_article_text(url):
    """강화된 뉴스 본문 추출 (리디렉션 및 크롤링 방지 완벽 우회)"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://news.google.com/'
        }
        
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        # 3중 리디렉션 추적 (구글 뉴스 우회용)
        for _ in range(3):
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
        
        # 한국 포털 및 언론사 타겟팅 셀렉터
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
        
        if len(final_text) < 150:
            return None
            
        return final_text[:3500] 
    except Exception as e:
        return None

def get_ai_summary(text, key):
    """Gemini API를 통한 3줄 요약 생성"""
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"다음 뉴스 기사 본문을 읽고, 일반인도 이해하기 쉽게 핵심 내용만 정확하게 3줄로 요약해줘. 각 줄은 이모지 없이 불릿기호(-)로 시작해:\n\n{text}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"요약 실패 (API 키 오류 또는 일일 한도 초과): {str(e)}"

@st.cache_data(ttl=60) 
def get_news(query, max_items=10):
    """구글 뉴스 RSS 파싱"""
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
        
        if hasattr(entry, 'description'):
            soup = BeautifulSoup(entry.description, 'html.parser')
            img_tag = soup.find('img')
            if img_tag and img_tag.get('src'):
                image_url = img_tag['src']
            
            raw_text = soup.get_text(separator=' ', strip=True)
            clean_text = raw_text.replace(title, "").replace(clean_title, "").replace(source, "").strip()
            clean_text = re.sub(r'^(.*?)[—|-]\s*', '', clean_text)
            if len(clean_text) > 15:
                summary = clean_text[:80] + "..."
        
        if not image_url:
            # 기사 제목을 시드로 고정 랜덤 이미지 생성 (중복 방지)
            seed = hashlib.md5(clean_title.encode('utf-8')).hexdigest()
            image_url = f"https://picsum.photos/seed/{seed}/400/200"
        
        news_list.append({
            "title": clean_title,
            "link": link,
            "source": source,
            "published": published,
            "image": image_url,
            "summary": summary
        })
    return news_list

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2965/2965306.png", width=60)
    st.title("⚙️ 대시보드 설정")
    
    st.markdown("### 🤖 AI 요약 기능")
    api_key = st.text_input("Gemini API Key 입력", type="password", help="구글 Gemini API 키를 입력하면 3줄 요약이 활성화됩니다.")
    if not api_key:
        st.info("🔑 키를 입력하여 기사 요약 기능을 켜보세요.")
        
    st.divider()
    
    st.markdown("### 🔄 업데이트 설정")
    refresh_minutes = st.slider("자동 새로고침 주기 (분)", min_value=1, max_value=60, value=5, step=1)
    
    st.divider()
    
    st.markdown("### 📌 기본 뉴스 주제")
    all_topics = ["시사", "정치", "경제", "연예", "스포츠", "IT/과학", "부동산", "세계"]
    selected_topics = st.multiselect("표시할 카테고리 선택", all_topics, default=["시사", "정치", "경제", "연예", "스포츠"])
    
    st.divider()
    st.markdown("### ✨ 맞춤형 키워드 모니터링")
    st.caption("입력창에 키워드를 쓰면 아래에 새 칸이 나타납니다. (최대 10개)")
    
    if "num_kw_inputs" not in st.session_state:
        st.session_state.num_kw_inputs = 1
        
    custom_keywords = []
    for i in range(st.session_state.num_kw_inputs):
        kw = st.text_input(f"키워드 {i+1}", key=f"kw_input_{i}", placeholder="예: 올림픽, 테슬라, 비트코인")
        if kw.strip() and kw.strip() not in custom_keywords:
            custom_keywords.append(kw.strip())
                
    last_kw_val = st.session_state.get(f"kw_input_{st.session_state.num_kw_inputs - 1}", "")
    if last_kw_val.strip() != "" and st.session_state.num_kw_inputs < 10:
        st.session_state.num_kw_inputs += 1
        st.rerun()

final_topics = list(selected_topics)
for kw in custom_keywords:
    if kw not in final_topics:
        final_topics.append(kw)

# 자동 새로고침 타이머
st_autorefresh(interval=refresh_minutes * 60 * 1000, key="data_refresh")

if not final_topics:
    st.warning("사이드바에서 하나 이상의 주제를 선택하거나 키워드를 입력해주세요.")
    st.stop()

# 메인 화면 구축을 위해 데이터를 먼저 수집합니다
all_news_data = {topic: get_news(topic, max_items=15) for topic in final_topics}

# 1. 헤더 (타이틀 및 시간)
current_time = datetime.now().strftime('%Y년 %m월 %d일 %H:%M')
st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:baseline;">
        <h1 class="main-title">🌐 Live News Desk</h1>
        <span style="color:#64748b; font-size:14px; font-weight:600;">마지막 업데이트: {current_time}</span>
    </div>
""", unsafe_allow_html=True)

# 2. 실시간 주요 헤드라인 티커(전광판) 생성
ticker_items = []
for topic, items in all_news_data.items():
    if items: # 각 주제별 가장 최신 뉴스 1개씩 추출
        ticker_items.append(f"<strong>[{topic}]</strong> {items[0]['title']}")

ticker_text = " &nbsp;&nbsp;&nbsp;✦&nbsp;&nbsp;&nbsp; ".join(ticker_items)

if ticker_items:
    st.markdown(f"""
    <div class="ticker-wrap">
        <div class="ticker-title">🔥 실시간 주요뉴스</div>
        <div class="ticker-content">
            <span>{ticker_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

cols = st.columns(len(final_topics))

for i, topic in enumerate(final_topics):
    with cols[i]:
        # 뱃지 스타일 헤더
        st.markdown(f"<div class='column-header'>{topic}</div>", unsafe_allow_html=True)
        news_items = all_news_data[topic]
        
        with st.container(height=850, border=False):
            if not news_items:
                st.info("뉴스를 불러오지 못했습니다.")
            else:
                for j, item in enumerate(news_items):
                    # 기사 카드 HTML
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
                    
                    # AI 요약 기능 영역
                    if api_key:
                        article_id = hashlib.md5(item['link'].encode('utf-8')).hexdigest()
                        session_key = f"ai_summary_{article_id}"
                        
                        if session_key in st.session_state:
                            st.success(st.session_state[session_key], icon="✨")
                        else:
                            # 고유 버튼 Key: i(컬럼순서) + j(기사순서) + article_id 결합으로 에러 완벽 차단
                            btn_key = f"btn_{i}_{j}_{article_id}"
                            if st.button("✨ 3줄 요약 보기", key=btn_key, use_container_width=True):
                                with st.spinner("본문 분석 중..."):
                                    content = extract_article_text(item['link'])
                                    if content:
                                        summary_result = get_ai_summary(content, api_key)
                                        st.session_state[session_key] = summary_result
                                        st.rerun() 
                                    else:
                                        st.error("보안 설정(봇 차단)으로 인해 원문 요약에 실패했습니다.", icon="🚫")
                    st.write("") # 카드 간 간격

st.markdown("<hr><p style='text-align:center; color:#94a3b8; font-size:12px; margin-top:20px;'>Data provided by Google News RSS. Not for commercial use.</p>", unsafe_allow_html=True)
