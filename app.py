import streamlit as st
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import re
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
import qrcode
from io import BytesIO

# 페이지 설정
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

# CSS 스타일링 (반응형 및 디자인 업그레이드)
st.markdown("""
<style>
    .stApp { background-color: #F1F5F9; }
    .main-title { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 900; font-size: 3rem; margin-bottom: 20px; }
    .news-card { background: white; border-radius: 15px; padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: transform 0.2s; }
    .news-card:hover { transform: translateY(-5px); box-shadow: 0 8px 12px rgba(0,0,0,0.1); }
    .ticker-wrap { background: #0f172a; color: #f8fafc; padding: 10px; border-radius: 8px; margin-bottom: 25px; overflow: hidden; white-space: nowrap; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 20px; background-color: #3b82f6; color: white; }
    @media (max-width: 768px) { .stColumn { width: 100% !important; } }
</style>
""", unsafe_allow_html=True)

def extract_article_text(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://news.google.com/'
        }
        session = requests.Session()
        res = session.get(url, headers=headers, timeout=10, allow_redirects=True)
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # 주요 포털 및 언론사 본문 선택자
        selectors = ['div.newsct_article', 'div.article_view', 'div.dic_area', 'article', 'div.article-body']
        for s in selectors:
            content = soup.select_one(s)
            if content: return content.get_text(separator=' ', strip=True)[:3000]
        
        paragraphs = soup.find_all('p')
        return ' '.join([p.get_text() for p in paragraphs if len(p.get_text()) > 50])[:3000]
    except:
        return None

def get_ai_summary(content, api_key):
    if not api_key: return "API 키가 설정되지 않았습니다."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(f"뉴스 기사 본문을 3줄로 요약해줘: {content}")
        return res.text
    except Exception as e:
        return f"요약 중 오류 발생: {str(e)}"

with st.sidebar:
    st.title("⚙️ 설정")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    st.subheader("키워드 설정")
    if "keywords" not in st.session_state: st.session_state.keywords = ["시사", "경제"]
    
    # 키워드 입력 관리
    new_keys = []
    for i in range(len(st.session_state.keywords)):
        val = st.text_input(f"키워드 {i+1}", value=st.session_state.keywords[i], key=f"k_{i}")
        if val: new_keys.append(val)
    
    # 마지막 칸 추가
    if len(new_keys) < 10 and (not new_keys or new_keys[-1] != ""):
        new_keys.append("")
    st.session_state.keywords = new_keys
    
    st.divider()
    # QR 코드 생성
    qr_url = "https://share.streamlit.io/" # 배포된 URL로 변경 권장
    qr = qrcode.make(qr_url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    st.image(buf, caption="모바일 접속 QR", width=120)

st.markdown("<h1 class='main-title'>🌐 Live News Desk</h1>", unsafe_allow_html=True)

# 실시간 티커 (상단)
latest_news = [f"📢 {k} 이슈 실시간 업데이트중..." for k in st.session_state.keywords if k]
st.markdown(f"<div class='ticker-wrap'>{' | '.join(latest_news)}</div>", unsafe_allow_html=True)

final_topics = [k for k in st.session_state.keywords if k]
cols = st.columns(len(final_topics) if final_topics else 1)

def get_news(query):
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    return feedparser.parse(url).entries[:5]

for i, topic in enumerate(final_topics):
    with cols[i]:
        st.markdown(f"### 📌 {topic}")
        for j, item in enumerate(get_news(topic)):
            with st.container():
                st.markdown(f"<div class='news-card'><b>{item.title}</b><br><a href='{item.link}'>기사 바로가기</a></div>", unsafe_allow_html=True)
                
                article_id = hash(item.title)
                if st.button("✨ AI 3줄 요약", key=f"btn_{i}_{j}_{article_id}"):
                    with st.spinner("분석 중..."):
                        content = extract_article_text(item.link) or item.summary
                        if content:
                            res = get_ai_summary(content, api_key)
                            st.success(res)
                        else:
                            st.warning("🚫 보안 설정으로 본문 접근이 차단되었습니다. 제목을 클릭해 직접 확인해주세요.")
