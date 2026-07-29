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
import base64

# ----------------- 페이지 설정 & 프리미엄 CSS -----------------
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8FAFC; }
    .main-title { 
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); 
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
        font-weight: 900; font-size: 2.5rem; text-align: center; margin-bottom: 20px; 
    }
    .ticker-wrap { 
        background: #0f172a; color: #f8fafc; padding: 12px; border-radius: 8px; 
        margin-bottom: 25px; white-space: nowrap; overflow: hidden; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
    }
    .news-card { 
        background: white; border-radius: 16px; padding: 15px; margin-bottom: 20px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.3s ease; border: 1px solid #e2e8f0; 
    }
    .news-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
    .topic-badge { 
        background-color: #e0f2fe; color: #0369a1; padding: 8px 18px; 
        border-radius: 20px; font-weight: bold; font-size: 1.1rem; display: inline-block; margin-bottom: 15px; 
    }
    /* 썸네일 비율 및 둥글기 최적화 */
    .news-img { width: 100%; height: 180px; object-fit: cover; border-radius: 12px; margin-bottom: 12px; border: 1px solid #f1f5f9; }
    .summary-box { 
        background-color: #f0fdf4; border-left: 4px solid #22c55e; 
        padding: 12px; border-radius: 4px; margin-top: 15px; font-size: 0.95rem; color: #166534; line-height: 1.5;
    }
    @media (max-width: 768px) { .stColumn { width: 100% !important; display: block; } }
</style>
""", unsafe_allow_html=True)

# ----------------- 스마트 크롤링 및 이미지 추출 -----------------

def decode_google_news_url(url):
    """구글 뉴스 RSS 링크 안에 숨겨진 진짜 언론사 URL을 해독합니다."""
    try:
        match = re.search(r'(?:articles|read)/([^?]+)', url)
        if match:
            b64_str = match.group(1)
            b64_str += '=' * (4 - len(b64_str) % 4) # Base64 패딩 맞추기
            decoded_bytes = base64.urlsafe_b64decode(b64_str)
            decoded_str = decoded_bytes.decode('latin1', errors='ignore')
            
            urls = re.findall(r'(https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s\x00-\x1f"\']*)?)', decoded_str)
            for u in urls:
                if 'news.google.com' not in u:
                    return u
    except: pass
    return url

@st.cache_data(ttl=1800, show_spinner=False)
def get_real_url_and_image(google_url):
    """실제 기사 주소와 실제 썸네일 이미지를 추출합니다."""
    real_url = decode_google_news_url(google_url)
    img_url = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=400&q=80" # 기본 배경
    
    # 1. 만약 해독에 실패했다면 접속해서 추적
    if real_url == google_url:
        try:
            res1 = requests.get(google_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            soup1 = BeautifulSoup(res1.text, 'html.parser')
            for a in soup1.find_all('a', href=True):
                if a['href'].startswith('http') and 'google' not in a['href']:
                    real_url = a['href']
                    break
        except: pass

    # 2. 뚫어낸 '진짜 URL(KBS, 다음 등)'에 접속해서 썸네일(og:image) 가져오기
    if real_url and 'google' not in real_url:
        try:
            res = requests.get(real_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            og_img = soup.find('meta', property='og:image')
            
            if og_img and og_img.get('content'):
                val = og_img['content']
                # 구글 기본 로고가 아닌 경우에만 썸네일로 인정
                if 'ssl.gstatic.com' not in val and 'googleusercontent' not in val:
                    if val.startswith('//'): img_url = 'https:' + val
                    elif val.startswith('/'):
                        parsed = urllib.parse.urlparse(real_url)
                        img_url = f"{parsed.scheme}://{parsed.netloc}{val}"
                    else: img_url = val
        except: pass
            
    return real_url, img_url

def extract_article_text(real_url):
    """실제 URL에서 뉴스 본문을 추출합니다."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(real_url, headers=headers, timeout=8)
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
    
    new_keys = []
    for i, k in enumerate(st.session_state.keywords):
        val = st.text_input(f"키워드 {i+1}", value=k, key=f"kw_{i}")
        if val.strip(): new_keys.append(val.strip())
            
    if len(new_keys) < 10: new_keys.append("")
        
    if new_keys != st.session_state.keywords:
        st.session_state.keywords = new_keys
        st.rerun()

    final_topics = [k for k in st.session_state.keywords if k.strip()]
    
    st.divider()
    st.subheader("📱 모바일 접속 QR")
    try:
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
    
    num_cols = min(len(final_topics), 4)
    cols = st.columns(num_cols if num_cols > 0 else 1)
    
    for i, topic in enumerate(final_topics):
        col = cols[i % num_cols]
        with col:
            st.markdown(f"<div class='topic-badge'>📌 {topic}</div>", unsafe_allow_html=True)
            
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(topic)}&hl=ko&gl=KR&ceid=KR:ko"
            feed = feedparser.parse(url)
            
            for j, item in enumerate(feed.entries[:5]):
                # 💡 마법이 일어나는 부분: 진짜 기사 주소와 실제 썸네일을 가져옴
                real_url, actual_img_url = get_real_url_and_image(item.link)
                
                with st.container():
                    st.markdown("<div class='news-card'>", unsafe_allow_html=True)
                    
                    card_html = f"""
                        <img src='{actual_img_url}' class='news-img'>
                        <h4 style='margin-top:0; font-size:1.1rem; line-height:1.4;'>{item.title}</h4>
                        <p style='font-size:0.8rem; color:#64748b; margin-bottom:10px;'>{item.published}</p>
                        <a href='{real_url}' target='_blank' style='text-decoration:none; color:#3b82f6; font-weight:bold;'>🔗 원문 기사 읽기</a>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    if api_key:
                        if st.button("✨ 이 기사 AI 3줄 요약", key=f"btn_{i}_{j}_{hash(item.title)}", use_container_width=True):
                            with st.spinner("본문을 분석 중입니다..."):
                                # 진짜 주소를 넘겨주기 때문에 크롤링 차단을 거의 완벽하게 회피함
                                article_text = extract_article_text(real_url)
                                
                                if not article_text:
                                    fallback_text = BeautifulSoup(item.summary, "html.parser").get_text(separator=" ", strip=True)
                                    article_text = fallback_text
                                    st.warning("🚫 보안 설정으로 서두를 요약합니다.")
                                
                                if article_text:
                                    summary_result = get_ai_summary(article_text, api_key)
                                    st.markdown(f"<div class='summary-box'><b>[AI 요약]</b><br>{summary_result}</div>", unsafe_allow_html=True)
                                else:
                                    st.error("요약할 텍스트를 추출하지 못했습니다.")
                    
                    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("👈 왼쪽 사이드바에서 표시할 주제/키워드를 입력해 주세요.")
