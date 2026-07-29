import streamlit as st
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import re
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
import qrcode
import urllib.parse

# ----------------- 페이지 설정 & 프리미엄 CSS -----------------
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

st.markdown("""
<style>
    /* 전체 배경 및 폰트 */
    .stApp { background-color: #F8FAFC; }
    
    /* 메인 타이틀 */
    .main-title { 
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); 
        -webkit-background-clip: text; 
        -webkit-text-fill-color: transparent; 
        font-weight: 900; 
        font-size: 2.5rem; 
        text-align: center; 
        margin-bottom: 20px; 
    }
    
    /* 실시간 뉴스 티커(전광판) */
    .ticker-wrap { 
        background: #0f172a; color: #f8fafc; padding: 12px; border-radius: 8px; 
        margin-bottom: 25px; white-space: nowrap; overflow: hidden; 
        font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
    }
    
    /* 패들렛 스타일 뉴스 카드 */
    .news-card { 
        background: white; border-radius: 16px; padding: 15px; margin-bottom: 20px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.3s ease; 
        border: 1px solid #e2e8f0; 
    }
    .news-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
    
    /* 둥근 뱃지 스타일 컬럼 헤더 */
    .topic-badge { 
        background-color: #e0f2fe; color: #0369a1; padding: 8px 18px; 
        border-radius: 20px; font-weight: bold; font-size: 1.1rem; 
        display: inline-block; margin-bottom: 15px; 
    }
    
    /* 썸네일 이미지 */
    .news-img { width: 100%; height: 180px; object-fit: cover; border-radius: 12px; margin-bottom: 12px; }
    
    /* AI 요약 박스 */
    .summary-box { 
        background-color: #f0fdf4; border-left: 4px solid #22c55e; 
        padding: 12px; border-radius: 4px; margin-top: 15px; 
        font-size: 0.95rem; color: #166534; line-height: 1.5;
    }
    
    /* 모바일 반응형 (Grid Chunking) */
    @media (max-width: 768px) {
        .stColumn { width: 100% !important; display: block; }
    }
</style>
""", unsafe_allow_html=True)

# ----------------- AI 및 크롤링 헬퍼 함수 -----------------
def extract_article_text(url):
    """뉴스 본문 추출 (우회 로직 포함)"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://news.google.com/'
        }
        session = requests.Session()
        res = session.get(url, headers=headers, timeout=10, allow_redirects=True)
        
        # 구글 리디렉션 뚫기
        for _ in range(2):
            if "news.google.com" in res.url or "consent.google.com" in res.url:
                soup = BeautifulSoup(res.text, 'html.parser')
                meta = soup.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'refresh'})
                if meta and 'url=' in meta.get('content', '').lower():
                    next_url = re.split('url=', meta['content'], flags=re.IGNORECASE)[-1].strip("'\" ")
                    res = session.get(next_url, headers=headers, timeout=10)
                    continue
                a_tag = soup.find('a', href=True)
                if a_tag and a_tag['href'].startswith('http'):
                    res = session.get(a_tag['href'], headers=headers, timeout=10)
                    continue
                break
                
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        
        target_selectors = [('div', 'dic_area'), ('div', 'articeBody'), ('div', 'article_view'), ('div', 'newsct_article'), ('article', '')]
        text_chunks = []
        
        for tag, name in target_selectors:
            element = soup.find(tag, id=name) or soup.find(tag, class_=name) if name else soup.find(tag)
            if element:
                text_chunks = [p.get_text(strip=True) for p in element.find_all(['p', 'div']) if len(p.get_text(strip=True)) > 20]
                if text_chunks: break
                
        if not text_chunks:
            text_chunks = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 30]

        final_text = re.sub(r'\s+', ' ', ' '.join(text_chunks)).strip()
        return final_text[:3000] if len(final_text) > 100 else None
    except:
        return None

def get_ai_summary(text, api_key):
    """Gemini AI 요약"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(f"다음 뉴스 기사를 핵심만 3줄로 요약해줘:\n\n{text}")
        return res.text
    except Exception as e:
        return f"요약 중 오류 발생: {str(e)}"

# ----------------- 사이드바 설정 -----------------
if 'keywords' not in st.session_state:
    st.session_state.keywords = ["시사", "경제", "IT/과학", "스포츠"]

with st.sidebar:
    st.title("⚙️ 설정")
    api_key = st.text_input("🔑 Gemini API Key", type="password")
    refresh_time = st.slider("자동 새로고침 주기(분)", 1, 60, 5)
    
    st.divider()
    st.subheader("🔍 키워드 설정 (최대 10개)")
    
    # 입력창 자동 조절 로직 (스마트 UI)
    new_keys = []
    for i, k in enumerate(st.session_state.keywords):
        val = st.text_input(f"키워드 {i+1}", value=k, key=f"kw_{i}")
        if val.strip():
            new_keys.append(val.strip())
            
    # 마지막에 항상 1개의 빈 칸 유지 (최대 10개 미만일 때)
    if len(new_keys) < 10:
        new_keys.append("")
        
    if new_keys != st.session_state.keywords:
        st.session_state.keywords = new_keys
        st.rerun()

    final_topics = [k for k in st.session_state.keywords if k.strip()]
    
    st.divider()
    st.subheader("📱 모바일 접속 QR")
    try:
        # 사용자 배포 URL로 QR 생성
        app_url = "https://pl6iapp7sjwpgkkwvr4gf4.streamlit.app/"
        qr = qrcode.make(app_url)
        st.image(qr.get_image(), use_container_width=True)
        st.caption("스마트폰 카메라로 스캔하세요.")
    except Exception as e:
        st.error("QR코드 생성 실패")

# ----------------- 메인 대시보드 영역 -----------------
st_autorefresh(interval=refresh_time * 60 * 1000, key="data_refresh")

st.markdown("<h1 class='main-title'>🌐 실시간 종합 뉴스 대시보드</h1>", unsafe_allow_html=True)

if final_topics:
    st.markdown(f"<div class='ticker-wrap'>🔥 실시간 주요뉴스: {' | '.join(final_topics)} ...업데이트 중</div>", unsafe_allow_html=True)
    
    # 모바일 및 데스크탑 대응 (한 줄에 최대 4개씩 자동 줄바꿈)
    num_cols = min(len(final_topics), 4)
    cols = st.columns(num_cols if num_cols > 0 else 1)
    
    for i, topic in enumerate(final_topics):
        col = cols[i % num_cols] # 4개를 넘어가면 아래로 자동 배치됨
        with col:
            st.markdown(f"<div class='topic-badge'>📌 {topic}</div>", unsafe_allow_html=True)
            
            # 구글 뉴스 RSS 파싱
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(topic)}&hl=ko&gl=KR&ceid=KR:ko"
            feed = feedparser.parse(url)
            
            for j, item in enumerate(feed.entries[:5]): # 각 주제별 5개 기사
                # 제목 기반 고유 시드로 썸네일 중복 방지 (Picsum 이미지)
                seed = hash(item.title) % 10000
                img_url = f"https://picsum.photos/seed/{seed}/400/200"
                
                with st.container():
                    st.markdown("<div class='news-card'>", unsafe_allow_html=True)
                    
                    # 이미지와 제목을 HTML로 예쁘게 배치
                    card_html = f"""
                        <img src='{img_url}' class='news-img'>
                        <h4 style='margin-top:0; font-size:1.1rem; line-height:1.4;'>{item.title}</h4>
                        <p style='font-size:0.8rem; color:#64748b; margin-bottom:10px;'>{item.published}</p>
                        <a href='{item.link}' target='_blank' style='text-decoration:none; color:#3b82f6; font-weight:bold;'>🔗 원문 기사 읽기</a>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    # AI 요약 버튼 및 로직
                    if api_key:
                        if st.button("✨ 이 기사 AI 3줄 요약", key=f"btn_{i}_{j}_{hash(item.title)}", use_container_width=True):
                            with st.spinner("본문을 분석 중입니다..."):
                                article_text = extract_article_text(item.link)
                                
                                # 하이브리드 폴백: 본문을 못 긁어오면 RSS Summary 텍스트라도 사용
                                if not article_text:
                                    fallback_text = BeautifulSoup(item.summary, "html.parser").get_text(separator=" ", strip=True)
                                    article_text = fallback_text
                                    st.warning("🚫 보안 설정으로 본문 접근이 차단되어 기사 서두를 요약합니다.")
                                
                                if article_text:
                                    summary_result = get_ai_summary(article_text, api_key)
                                    st.markdown(f"<div class='summary-box'><b>[AI 요약]</b><br>{summary_result}</div>", unsafe_allow_html=True)
                                else:
                                    st.error("요약할 텍스트를 추출하지 못했습니다.")
                    
                    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("👈 왼쪽 사이드바에서 표시할 주제/키워드를 입력해 주세요.")
