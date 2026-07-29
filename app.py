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
from PIL import Image

# 페이지 설정
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

# CSS 스타일링 (모바일 반응형 & 디자인)
st.markdown("""
<style>
    .stApp { background-color: #F8FAFC; }
    .main-title { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 900; font-size: 2.5rem; text-align: center; margin-bottom: 20px; }
    .news-card { background: white; border-radius: 12px; padding: 15px; margin-bottom: 15px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .news-card:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.1); }
    .ticker-wrap { background: #0f172a; color: #f8fafc; padding: 10px; border-radius: 8px; margin-bottom: 25px; white-space: nowrap; overflow: hidden; font-weight: bold; }
    @media (max-width: 768px) { .stColumn { width: 100% !important; } }
</style>
""", unsafe_allow_html=True)

# ----------------- 크롤링 & AI 함수 -----------------
def extract_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        session = requests.Session()
        res = session.get(url, headers=headers, timeout=8, allow_redirects=True)
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # 주요 기사 본문 영역 찾기
        selectors = ['div.newsct_article', 'div.article_view', 'div.dic_area', 'article', 'div.article-body']
        for s in selectors:
            content = soup.select_one(s)
            if content: return content.get_text(separator=' ', strip=True)[:2500]
        
        paragraphs = soup.find_all('p')
        return ' '.join([p.get_text() for p in paragraphs if len(p.get_text()) > 50])[:2500]
    except: return None

def get_ai_summary(content, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(f"뉴스 기사 본문을 3줄로 요약해줘: {content}")
        return res.text
    except Exception as e: return f"요약 실패: {str(e)}"

# ----------------- 메인 로직 -----------------
# 1. 자동 새로고침 설정 (사이드바에서 받음)
st_autorefresh(interval=300000, key="datarefresh") # 5분마다

with st.sidebar:
    st.title("⚙️ 설정")
    api_key = st.text_input("Gemini API Key", type="password")
    refresh_time = st.slider("자동 새로고침(분)", 1, 60, 5)
    
    st.subheader("📌 주제/키워드 설정")
    if "keywords" not in st.session_state: st.session_state.keywords = ["시사", "경제"]
    
    # 키워드 관리 로직
    new_keys = []
    for i in range(len(st.session_state.keywords)):
        val = st.text_input(f"키워드 {i+1}", value=st.session_state.keywords[i], key=f"k_{i}")
        if val: new_keys.append(val)
    if len(new_keys) < 10 and (not new_keys or new_keys[-1] != ""):
        new_keys.append("")
    st.session_state.keywords = new_keys
    
    st.divider()
    # QR 코드 생성 (현재 주소 기준)
    st.write("📱 모바일 접속 QR")
    qr = qrcode.make("https://share.streamlit.io/") # 실제 배포 주소로 수정
    st.image(qr.get_image(), width=150)

st.markdown("<h1 class='main-title'>🌐 Live News Desk</h1>", unsafe_allow_html=True)

# 뉴스 티커
final_topics = [k for k in st.session_state.keywords if k]
if final_topics:
    st.markdown(f"<div class='ticker-wrap'>📢 { ' | '.join(final_topics) } 실시간 뉴스 업데이트 중...</div>", unsafe_allow_html=True)

# 뉴스 카드 레이아웃 (반응형 그리드)
cols = st.columns(min(len(final_topics), 3) if final_topics else 1)

for i, topic in enumerate(final_topics):
    col = cols[i % 3]
    with col:
        st.subheader(f"📌 {topic}")
        url = f"https://news.google.com/rss/search?q={topic}&hl=ko&gl=KR&ceid=KR:ko"
        entries = feedparser.parse(url).entries[:4]
        
        for j, item in enumerate(entries):
            with st.container():
                st.markdown(f"<div class='news-card'><b>{item.title}</b><br><a href='{item.link}'>🔗 기사 바로가기</a></div>", unsafe_allow_html=True)
                if api_key and st.button("✨ 요약", key=f"btn_{i}_{j}_{hash(item.title)}"):
                    with st.spinner("AI 분석 중..."):
                        content = extract_article_text(item.link) or item.summary
                        if content: st.success(get_ai_summary(content, api_key))
                        else: st.warning("🚫 본문 접근 차단됨 (제목을 클릭하세요)")
