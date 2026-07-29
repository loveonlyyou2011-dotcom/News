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

# Padlet 스타일을 위한 커스텀 CSS
st.markdown("""
<style>
    .stApp {
        background-color: #f4f5f8;
    }
    .news-card {
        background-color: white;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border: 1px solid #e5e7eb;
        border-top: 5px solid #4CAF50;
        transition: transform 0.2s, box-shadow 0.2s;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }
    .news-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.12);
    }
    .news-image {
        width: 100%;
        height: 150px;
        object-fit: cover;
        background-color: #f3f4f6;
    }
    .news-content {
        padding: 16px;
        display: flex;
        flex-direction: column;
        flex-grow: 1;
    }
    .news-title {
        font-size: 15px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 8px;
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
        font-size: 13px;
        color: #4b5563;
        margin-bottom: 12px;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .news-meta {
        font-size: 11px;
        color: #6b7280;
        margin-top: auto;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 1px solid #f3f4f6;
        padding-top: 10px;
    }
    .column-header {
        background-color: #e5e7eb;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
        margin-bottom: 15px;
        color: #374151;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- AI 및 크롤링 헬퍼 함수 -----------------
def extract_article_text(url):
    """주어진 URL에서 뉴스 본문 텍스트를 추출합니다 (리디렉션 및 크롤링 방지 우회 강화)."""
    try:
        # 1. 봇 차단을 우회하기 위한 강력한 브라우저 헤더 설정
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://news.google.com/'
        }
        
        # 세션을 사용하여 리디렉션 및 쿠키 유지
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10, allow_redirects=True)
        response.encoding = response.apparent_encoding # 한글 깨짐 방지
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 2. 구글 뉴스 리디렉션 페이지(메타 태그 자동 이동) 우회 처리
        meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
        if meta_refresh:
            redirect_url = meta_refresh.get('content', '').split('url=')[-1].strip("'\" ")
            if redirect_url:
                response = session.get(redirect_url, headers=headers, timeout=10, allow_redirects=True)
                response.encoding = response.apparent_encoding
                soup = BeautifulSoup(response.text, 'html.parser')
        
        # a 태그 리디렉션 우회 (구글 뉴스의 "계속하려면 클릭" 페이지 처리)
        if "news.google.com" in response.url or "consent.google.com" in response.url:
            a_tag = soup.find('a', href=True)
            if a_tag and 'http' in a_tag['href']:
                response = session.get(a_tag['href'], headers=headers, timeout=10, allow_redirects=True)
                response.encoding = response.apparent_encoding
                soup = BeautifulSoup(response.text, 'html.parser')

        # 3. 실제 기사 본문 텍스트 추출 (p 태그 위주)
        paragraphs = soup.find_all('p')
        text_chunks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        
        # 본문이 p태그가 아닌 div 등에 있는 특이한 언론사를 위한 2차 추출(Fallback)
        if len(text_chunks) < 3: 
            article_divs = soup.find_all('div', id=re.compile(r'(article|content|news)', re.I)) or \
                           soup.find_all('div', class_=re.compile(r'(article|content|news)', re.I))
            for div in article_divs:
                text = div.get_text(separator=' ', strip=True)
                if len(text) > 100:
                    text_chunks.append(text)

        # 문장들을 하나로 합치고 불필요한 공백 제거
        final_text = ' '.join(text_chunks)
        final_text = re.sub(r'\s+', ' ', final_text) 
        
        # 텍스트가 너무 짧으면(기사를 못 가져왔다면) 실패 처리
        if len(final_text) < 150:
            return None
            
        return final_text[:3500] # API 토큰 제한 방지 (최대 3500자 반환)
    except Exception as e:
        # 에러 발생 시 로그를 남기지 않고 조용히 None 반환
        return None

def get_ai_summary(text, key):
    """Gemini API를 사용하여 텍스트를 3줄로 요약합니다."""
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"다음 뉴스 기사 본문을 읽고, 일반인도 이해하기 쉽게 핵심 내용만 정확하게 3줄로 요약해줘. 각 줄은 불릿기호(-)로 시작하게 해줘:\n\n{text}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"요약 실패 (API 키 오류 또는 한도 초과): {str(e)}"
# --------------------------------------------------------

@st.cache_data(ttl=60) 
def get_news(query, max_items=10):
    """구글 뉴스 RSS를 통해 해당 키워드의 최신 뉴스를 가져옵니다."""
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
            
        published = entry.published if hasattr(entry, 'published') else "시간 정보 없음"
        
        # 기본 이미지와 기본 요약값 설정
        image_url = None
        summary = "관련 기사 상세 내용은 제목을 클릭하여 확인하세요."
        
        # RSS description에서 요약과 이미지 추출 (정교화)
        if hasattr(entry, 'description'):
            soup = BeautifulSoup(entry.description, 'html.parser')
            
            # 기사 자체의 이미지 추출 시도
            img_tag = soup.find('img')
            if img_tag and img_tag.get('src'):
                image_url = img_tag['src']
            
            # 구글 뉴스 RSS 특유의 잡음(제목 중복, 출처 중복 등) 제거
            raw_text = soup.get_text(separator=' ', strip=True)
            clean_text = raw_text.replace(title, "").replace(clean_title, "").replace(source, "").strip()
            clean_text = re.sub(r'^(.*?)[—|-]\s*', '', clean_text)
            
            if len(clean_text) > 15:
                summary = clean_text[:80] + "..."
        
        # 기사 내 이미지가 없을 경우, 제목(clean_title)을 시드로 고정 랜덤 이미지 생성
        if not image_url:
            seed = hashlib.md5(clean_title.encode('utf-8')).hexdigest()
            # picsum.photos를 사용하여 다채로운 배경 이미지 적용
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

# 사이드바 설정
with st.sidebar:
    st.title("⚙️ 설정")
    
    st.write("🤖 **AI 요약 기능 활성화**")
    api_key = st.text_input("Gemini API Key 입력", type="password", help="발급받은 구글 Gemini API 키를 입력하세요.")
    if not api_key:
        st.info("🔑 키를 입력하면 뉴스 3줄 요약 버튼이 활성화됩니다.")
        
    st.divider()
    
    st.write("원하시는 주제와 새로고침 주기를 설정하세요.")
    refresh_minutes = st.slider("자동 새로고침 주기 (분)", min_value=1, max_value=60, value=5, step=1)
    
    st.divider()
    
    # 기본 주제와 사용자 정의 키워드
    all_topics = ["시사", "정치", "경제", "연예", "스포츠", "주식", "IT/과학", "부동산"]
    selected_topics = st.multiselect("표시할 주제 선택", all_topics, default=["시사", "정치", "경제", "연예", "스포츠"])
    
    st.divider()
    st.write("✨ 원하는 키워드를 직접 입력해보세요.")
    custom_keyword = st.text_input("사용자 정의 키워드 추가", placeholder="예: 올림픽, 인공지능, 애플")

final_topics = list(selected_topics)
if custom_keyword and custom_keyword.strip() not in final_topics:
    final_topics.append(custom_keyword.strip())

# 자동 새로고침 설정 (밀리초 단위)
refresh_interval = refresh_minutes * 60 * 1000
st_autorefresh(interval=refresh_interval, key="data_refresh")

# 메인 화면
st.markdown(f"<h2>📰 실시간 종합 뉴스 대시보드 <span style='font-size:16px; font-weight:normal; color:gray;'>(마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})</span></h2>", unsafe_allow_html=True)

if not final_topics:
    st.warning("사이드바에서 하나 이상의 주제를 선택하거나 키워드를 입력해주세요.")
else:
    cols = st.columns(len(final_topics))
    
    # 열(컬럼) 반복문
    for i, topic in enumerate(final_topics):
        with cols[i]:
            st.markdown(f"<div class='column-header'>{topic}</div>", unsafe_allow_html=True)
            news_items = get_news(topic, max_items=15)
            
            with st.container(height=800, border=False):
                if not news_items:
                    st.info("뉴스를 불러오지 못했습니다.")
                else:
                    # 행(기사) 반복문
                    for j, item in enumerate(news_items):
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
                        
                        # --- AI 요약 버튼 및 결과 표시 영역 ---
                        if api_key:
                            # 기사 URL을 기반으로 고유 ID 생성
                            article_id = hashlib.md5(item['link'].encode('utf-8')).hexdigest()
                            session_key = f"ai_summary_{article_id}"
                            
                            # 이미 요약된 결과가 있다면 바로 출력
                            if session_key in st.session_state:
                                st.info(st.session_state[session_key])
                            else:
                                # [핵심] 버튼 Key 중복 에러 방지: i(컬럼순서) + j(기사순서) + article_id 결합
                                btn_key = f"btn_{i}_{j}_{article_id}"
                                if st.button("✨ 이 기사 AI 3줄 요약", key=btn_key, use_container_width=True):
                                    with st.spinner("원문을 읽고 요약 중입니다..."):
                                        content = extract_article_text(item['link'])
                                        if content:
                                            summary_result = get_ai_summary(content, api_key)
                                            # 요약 결과를 세션에 저장하여 재로딩시 유지
                                            st.session_state[session_key] = summary_result
                                            st.rerun() 
                                        else:
                                            st.warning("🚫 해당 언론사의 크롤링 방지 설정으로 인해 본문을 가져올 수 없습니다.")
                        st.write("") # 카드 간의 간격 조정
                        # --------------------------------------

st.markdown("<hr><p style='text-align:center; color:gray; font-size:12px;'>Data provided by Google News RSS. Not for commercial use.</p>", unsafe_allow_html=True)
