import streamlit as st
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import re
from bs4 import BeautifulSoup
import hashlib
import requests
import google.generativeai as genai
import qrcode
from io import BytesIO

# 페이지 설정
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

# CSS 스타일링
st.markdown("""
<style>
    .stApp { background-color: #F8FAFC; }
    .main-title { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 900; }
    .news-card { background: white; border-radius: 16px; padding: 15px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .ticker-wrap { background: #0f172a; color: white; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
    @media (max-width: 768px) { .stColumn { width: 100% !important; } }
</style>
""", unsafe_allow_html=True)

# 크롤링 강화 로직
def extract_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
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

# 사이드바 설정
with st.sidebar:
    st.title("⚙️ 설정")
    api_key = st.text_input("Gemini API Key", type="password")
    
    # QR 코드 생성
    qr = qrcode.make(st.query_params.get("url", "https://share.streamlit.io/")) # 배포 주소로 수정 필요
    buf = BytesIO()
    qr.save(buf, format="PNG")
    st.image(buf, caption="모바일에서 접속하세요", width=150)
    
    # 키워드 입력창 관리
    if "keywords" not in st.session_state: st.session_state.keywords = [""]
    
    for i in range(len(st.session_state.keywords)):
        st.session_state.keywords[i] = st.text_input(f"키워드 {i+1}", value=st.session_state.keywords[i], key=f"k_{i}")
    
    # 마지막 칸이 채워지면 새로운 칸 추가
    if st.session_state.keywords[-1] != "" and len(st.session_state.keywords) < 10:
        st.session_state.keywords.append("")
        st.rerun()
    # 텍스트가 지워지면 중간 빈칸 제거
    elif len(st.session_state.keywords) > 1 and st.session_state.keywords[-2] == "":
        st.session_state.keywords.pop()
        st.rerun()

# 뉴스 수집 로직 (폴백 포함)
def get_news(query):
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    return feed.entries[:5]

# 대시보드 렌더링
st.markdown("<h1 class='main-title'>🌐 Live News Desk</h1>", unsafe_allow_html=True)

final_topics = [k for k in st.session_state.keywords if k] or ["시사", "경제"]
cols = st.columns(len(final_topics))

for i, topic in enumerate(final_topics):
    with cols[i]:
        st.subheader(f"📌 {topic}")
        for item in get_news(topic):
            with st.container():
                st.markdown(f"**[{item.source.title if 'source' in item else '뉴스'}]** [{item.title}]({item.link})", unsafe_allow_html=True)
                if st.button("✨ 요약", key=f"sum_{topic}_{item.title}"):
                    with st.spinner("분석 중..."):
                        content = extract_article_text(item.link) or item.summary
                        if api_key:
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            res = model.generate_content(f"3줄 요약: {content}")
                            st.info(res.text)
                        else:
                            st.warning("API 키를 입력하세요.")
