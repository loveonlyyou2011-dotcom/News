import streamlit as st
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import re
from bs4 import BeautifulSoup

# 페이지 기본 설정 (가로로 넓게 쓰기 위해 wide 모드 적용)
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

# Padlet 스타일을 위한 커스텀 CSS
st.markdown("""
<style>
    /* 배경색 약간 회색으로 설정 (패들렛 느낌) */
    .stApp {
        background-color: #f4f5f8;
    }
    
    .news-card {
        background-color: white;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border: 1px solid #e5e7eb;
        border-top: 5px solid #4CAF50; /* 패들렛처럼 상단 포인트 바 형태로 변경 */
        transition: transform 0.2s, box-shadow 0.2s;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }
    
    .news-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.12);
    }
    
    /* 썸네일 이미지 영역 */
    .news-image {
        width: 100%;
        height: 150px;
        object-fit: cover;
        background-color: #f3f4f6;
    }

    /* 카드 내부 컨텐츠 영역 */
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

    /* 요약 텍스트 스타일 */
    .news-summary {
        font-size: 13px;
        color: #4b5563;
        margin-bottom: 12px;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2; /* 최대 2줄까지만 표시하고 넘어가면 ... 처리 */
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    .news-meta {
        font-size: 11px;
        color: #6b7280;
        margin-top: auto; /* 하단으로 밀어내기 */
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 1px solid #f3f4f6;
        padding-top: 10px;
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

@st.cache_data(ttl=60) 
def get_news(query, max_items=10):
    """구글 뉴스 RSS를 통해 해당 키워드의 최신 뉴스를 가져옵니다."""
    # 구글 뉴스 한국어 RSS URL
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    
    # 주제별 맞춤형 고품질 기본 이미지 (Unsplash 사진 ID)
    topic_images = {
        "시사": "1585829365295-ab7cd400c167",     # 신문/뉴스룸
        "정치": "1540914946210-6de8b560cb9a",     # 마이크
        "경제": "1611974789855-9c2a0a7236a3",     # 차트
        "연예": "1470229722913-7c090be1fb98",     # 콘서트/조명
        "스포츠": "1461896836934-ffe607ba8211",   # 육상 트랙
        "주식": "1590283603385-17ffb3a77196",     # 트레이딩 화면
        "IT/과학": "1518770660439-4636190af475",  # 회로/기술
        "부동산": "1560518883-ce09059eeffa"      # 고층 건물
    }
    
    # 선택된 주제에 맞는 이미지가 없으면 사용할 범용 이미지
    default_img_id = "1495020689067-958852a7765e" 
    img_id = topic_images.get(query, default_img_id)
    default_image_url = f"https://images.unsplash.com/photo-{img_id}?w=400&h=200&fit=crop"
    
    news_list = []
    for entry in feed.entries[:max_items]:
        # HTML 태그 제거 및 데이터 정제
        title = entry.title
        link = entry.link
        
        # 출처 분리
        if " - " in title:
            title_parts = title.rsplit(" - ", 1)
            clean_title = title_parts[0]
            source = title_parts[1]
        else:
            clean_title = title
            source = "알 수 없음"
            
        published = entry.published if hasattr(entry, 'published') else "시간 정보 없음"
        
        # BeautifulSoup을 사용하여 요약 텍스트 추출
        summary = "관련 기사 상세 내용은 제목을 클릭하여 확인하세요."
        if hasattr(entry, 'description'):
            soup = BeautifulSoup(entry.description, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            # 구글 뉴스 RSS는 제목이 설명에 중복 기재되므로, 일정 길이 이상일 때만 요약으로 간주
            if len(text) > len(clean_title) + 5:
                summary = text[:80] + "..." # 80자까지만 자르기
        
        news_list.append({
            "title": clean_title,
            "link": link,
            "source": source,
            "published": published,
            "image": default_image_url, # RSS 자체 썸네일 대신 주제별 고화질 이미지 적용
            "summary": summary
        })
    return news_list

# 사이드바 설정
with st.sidebar:
    st.title("⚙️ 설정")
    st.write("원하시는 주제와 새로고침 주기를 설정하세요.")
    
    # 시간 설정 버튼 (슬라이더 활용)
    refresh_minutes = st.slider("자동 새로고침 주기 (분)", min_value=1, max_value=60, value=5, step=1)
    
    st.divider()
    
    # 주제 설정 (에러 수정: all_topics 리스트에 '경제' 추가)
    all_topics = ["시사", "정치", "경제", "연예", "스포츠", "주식", "IT/과학", "부동산"]
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

st.markdown("<hr><p style='text-align:center; color:gray; font-size:12px;'>Data provided by Google News RSS. Not for commercial use.</p>", unsafe_allow_html=True)
