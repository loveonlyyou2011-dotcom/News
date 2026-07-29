import streamlit as st
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import re

# 페이지 기본 설정 (가로로 넓게 쓰기 위해 wide 모드 적용)
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

# Padlet 스타일을 위한 커스텀 CSS
st.markdown("""
<style>
    /* 배경색 약간 회색으로 설정 (패들렛 느낌) */
    .stApp {
        background-color: #f4f5f8;
    }
    
    /* 뉴스 카드 스타일 */
    .news-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 15px;
        border-left: 5px solid #4CAF50;
        transition: transform 0.2s;
    }
    
    .news-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    .news-title {
        font-size: 16px;
        font-weight: bold;
        color: #1f2937;
        margin-bottom: 8px;
        line-height: 1.4;
    }
    
    .news-title a {
        color: inherit;
        text-decoration: none;
    }
    
    .news-title a:hover {
        color: #3b82f6;
    }
    
    .news-meta {
        font-size: 12px;
        color: #6b7280;
        margin-top: 10px;
        display: flex;
        justify-content: space-between;
    }
    
    /* 컬럼 헤더 스타일 */
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

# 뉴스 가져오기 함수 (캐싱을 통해 무분별한 요청 방지, ttl로 캐시 만료 시간 설정)
@st.cache_data(ttl=60) 
def get_news(query, max_items=10):
    """구글 뉴스 RSS를 통해 해당 키워드의 최신 뉴스를 가져옵니다."""
    # 구글 뉴스 한국어 RSS URL
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    
    news_list = []
    for entry in feed.entries[:max_items]:
        # HTML 태그 제거 및 데이터 정제
        title = entry.title
        link = entry.link
        # 출처 분리 (보통 제목 끝에 ' - 출처' 형식으로 붙음)
        if " - " in title:
            title_parts = title.rsplit(" - ", 1)
            clean_title = title_parts[0]
            source = title_parts[1]
        else:
            clean_title = title
            source = "알 수 없음"
            
        published = entry.published if hasattr(entry, 'published') else "시간 정보 없음"
        
        news_list.append({
            "title": clean_title,
            "link": link,
            "source": source,
            "published": published
        })
    return news_list

# 사이드바 설정
with st.sidebar:
    st.title("⚙️ 설정")
    st.write("원하시는 주제와 새로고침 주기를 설정하세요.")
    
    # 시간 설정 버튼 (슬라이더 활용)
    refresh_minutes = st.slider("자동 새로고침 주기 (분)", min_value=1, max_value=60, value=5, step=1)
    
    st.divider()
    
    # 주제 설정
    all_topics = ["시사", "정치", "연예", "스포츠", "주식", "IT/과학", "부동산"]
    selected_topics = st.multiselect("표시할 주제 선택", all_topics, default=["시사", "정치", "경제", "연예", "스포츠"])

# 자동 새로고침 적용 (밀리초 단위로 변환)
refresh_interval = refresh_minutes * 60 * 1000
st_autorefresh(interval=refresh_interval, key="data_refresh")

# 메인 헤더
st.markdown(f"<h2>📰 실시간 종합 뉴스 대시보드 <span style='font-size:16px; font-weight:normal; color:gray;'>(마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})</span></h2>", unsafe_allow_html=True)

if not selected_topics:
    st.warning("사이드바에서 하나 이상의 주제를 선택해주세요.")
else:
    # 패들렛 스타일을 위한 컬럼 생성 (선택한 주제 수만큼 컬럼 분할)
    cols = st.columns(len(selected_topics))
    
    # 각 컬럼별로 주제 할당 및 뉴스 렌더링
    for i, topic in enumerate(selected_topics):
        with cols[i]:
            # 컬럼 헤더(주제명)
            st.markdown(f"<div class='column-header'>{topic}</div>", unsafe_allow_html=True)
            
            # 실시간 뉴스 가져오기
            news_items = get_news(topic, max_items=15)
            
            # 스크롤 가능한 컨테이너 (옵션: 너무 길어지는 것을 방지)
            with st.container(height=700, border=False):
                if not news_items:
                    st.info("뉴스를 불러오지 못했습니다.")
                else:
                    for item in news_items:
                        # 뉴스 카드 HTML 구성
                        card_html = f"""
                        <div class="news-card">
                            <div class="news-title">
                                <a href="{item['link']}" target="_blank">{item['title']}</a>
                            </div>
                            <div class="news-meta">
                                <span>🏢 {item['source']}</span>
                                <span>🕒 {item['published'][5:16] if len(item['published']) > 16 else item['published']}</span>
                            </div>
                        </div>
                        """
                        st.markdown(card_html, unsafe_allow_html=True)

st.markdown("<hr><p style='text-align:center; color:gray; font-size:12px;'>Data provided by Google News RSS. Not for commercial use.</p>", unsafe_allow_html=True)
