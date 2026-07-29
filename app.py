import streamlit as st
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import re
from bs4 import BeautifulSoup
import hashlib

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
        
        # 이미지 & 요약 텍스트 추출 로직 개선
        image_url = None
        summary = "기사 원문에서 자세한 내용을 확인하세요."
        
        if hasattr(entry, 'description'):
            soup = BeautifulSoup(entry.description, 'html.parser')
            
            # 1. 구글 뉴스 본문 내 썸네일 이미지 추출 시도
            img_tag = soup.find('img')
            if img_tag and img_tag.get('src'):
                image_url = img_tag['src']
            
            # 2. 요약 텍스트 추출 (순수 텍스트만)
            text = soup.get_text(separator=' ', strip=True)
            
            # 구글 뉴스는 RSS description에 제목과 출처가 반복되므로 이를 제거
            clean_text = text.replace(title, "").replace(clean_title, "").replace(source, "").strip()
            
            # 특수기호나 날짜 등 불필요한 앞부분 찌꺼기 제거 (예: "2026. 7. 29. — ")
            clean_text = re.sub(r'^(.*?)[—|-]\s*', '', clean_text)
            
            # 의미 있는 요약 내용이 남아있다면 반영 (너무 짧으면 무시)
            if len(clean_text) > 15:
                summary = clean_text[:80] + "..." # 80자까지만 자르기
        
        # 3. 이미지가 없는 경우, 기사 제목을 바탕으로 고유한 랜덤 썸네일 할당
        if not image_url:
            # 기사 제목을 해시(Hash)값으로 변환하여 동일한 기사는 항상 동일한 이미지를 갖도록 고정
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

# 사이드바 설정
with st.sidebar:
    st.title("⚙️ 설정")
    st.write("원하시는 주제와 새로고침 주기를 설정하세요.")
    
    # 시간 설정 버튼 (슬라이더 활용)
    refresh_minutes = st.slider("자동 새로고침 주기 (분)", min_value=1, max_value=60, value=5, step=1)
    
    st.divider()
    
    # 주제 설정 
    all_topics = ["시사", "정치", "경제", "연예", "스포츠", "주식", "IT/과학", "부동산"]
    selected_topics = st.multiselect("기본 주제 선택", all_topics, default=["시사", "정치", "경제", "연예"])
    
    st.divider()
    st.write("✨ 원하는 키워드를 직접 입력해보세요.")
    custom_keyword = st.text_input("사용자 정의 키워드 추가", placeholder="예: 인공지능, 올림픽, 금리")

# 최종적으로 화면에 표시할 주제 리스트 통합
final_topics = list(selected_topics)
if custom_keyword and custom_keyword.strip() not in final_topics:
    final_topics.append(custom_keyword.strip())

# 자동 새로고침 적용 (밀리초 단위로 변환)
refresh_interval = refresh_minutes * 60 * 1000
st_autorefresh(interval=refresh_interval, key="data_refresh")

# 메인 헤더
st.markdown(f"<h2>📰 실시간 종합 뉴스 대시보드 <span style='font-size:16px; font-weight:normal; color:gray;'>(마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})</span></h2>", unsafe_allow_html=True)

if not final_topics:
    st.warning("사이드바에서 하나 이상의 주제를 선택하거나 키워드를 입력해주세요.")
else:
    # 패들렛 스타일을 위한 컬럼 생성 (선택한 주제 수만큼 컬럼 분할)
    cols = st.columns(len(final_topics))
    
    # 각 컬럼별로 주제 할당 및 뉴스 렌더링
    for i, topic in enumerate(final_topics):
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
                        
                        # --- AI 요약 버튼 및 결과 표시 영역 ---
                        if api_key:
                            # 기사별 고유 ID 생성 (제목 기반)
                            article_id = hashlib.md5(item['title'].encode('utf-8')).hexdigest()
                            session_key = f"ai_summary_{article_id}"
                            
                            # 1. 이미 요약을 요청했던 기사라면 파란색 알림창으로 내용 바로 표시
                            if session_key in st.session_state:
                                st.info(st.session_state[session_key])
                            # 2. 아직 요약 전이라면 요약 버튼 표시
                            else:
                                if st.button("✨ 이 기사 AI 3줄 요약", key=f"btn_{article_id}", use_container_width=True):
                                    with st.spinner("원문을 읽고 요약 중입니다..."):
                                        content = extract_article_text(item['link'])
                                        if content:
                                            summary_result = get_ai_summary(content, api_key)
                                            # 요약 결과를 세션에 저장
                                            st.session_state[session_key] = summary_result
                                            st.rerun() # 화면을 즉시 새로고침하여 결과 표시
                                        else:
                                            st.warning("🚫 해당 언론사의 보안(크롤링 방지) 설정으로 본문을 가져올 수 없습니다.")
                        st.write("") # 카드 간 약간의 띄어쓰기 여백 추가
                        # --------------------------------------

st.markdown("<hr><p style='text-align:center; color:gray; font-size:12px;'>Data provided by Google News RSS. Not for commercial use.</p>", unsafe_allow_html=True)
