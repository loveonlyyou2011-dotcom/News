import os
import streamlit as st
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import time
import re
import hashlib
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
import requests
from google import genai
import qrcode

from googlenewsdecoder import gnewsdecoder

# ----------------- 페이지 설정 & 프리미엄 CSS -----------------
st.set_page_config(page_title="실시간 뉴스 대시보드", page_icon="📰", layout="wide")

st.markdown("""
<style>
    :root {
        --bg: #F1F5F9; --card-bg: #ffffff; --card-border: #e2e8f0;
        --text-main: #0f172a; --text-sub: #64748b;
        --summary-bg: #f0fdf4; --summary-border: #22c55e; --summary-text: #166534;
        --placeholder-bg: linear-gradient(135deg, #e2e8f0, #f8fafc);
        --brand: #6366f1;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --bg: #0a0f1c; --card-bg: #131b2e; --card-border: #232f47;
            --text-main: #e5e7eb; --text-sub: #94a3b8;
            --summary-bg: #052e1b; --summary-border: #22c55e; --summary-text: #86efac;
            --placeholder-bg: linear-gradient(135deg, #1f2937, #111827);
            --brand: #818cf8;
        }
    }
    .stApp {
        background:
            radial-gradient(circle at 15% 0%, rgba(99,102,241,0.10), transparent 40%),
            radial-gradient(circle at 85% 10%, rgba(236,72,153,0.08), transparent 35%),
            var(--bg);
    }
    .main-title {
        background: linear-gradient(135deg, #4f46e5 0%, #ec4899 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 900; font-size: 2.6rem; text-align: center; margin-bottom: 2px; letter-spacing: -0.5px;
    }
    .main-subtitle { text-align:center; color: var(--text-sub); margin-bottom: 22px; font-size: 0.95rem; }

    /* 상단 실시간 티커: 좌우로 끊김없이 흐르는 마퀴 애니메이션 */
    .ticker-wrap {
        background: linear-gradient(135deg, #0f172a, #1e1b4b);
        border-radius: 10px; margin-bottom: 26px; overflow: hidden;
        box-shadow: 0 4px 12px rgba(0,0,0,0.18); position: relative;
    }
    .ticker-track {
        display: inline-flex; white-space: nowrap; padding: 13px 0;
        animation: ticker-scroll 22s linear infinite;
    }
    .ticker-wrap:hover .ticker-track { animation-play-state: paused; }
    .ticker-item { color: #f8fafc; font-weight: 700; padding-right: 70px; }
    @keyframes ticker-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }

    @keyframes card-in { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

    .news-card {
        background: var(--card-bg); border-radius: 18px; padding: 16px; margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(15,23,42,0.06); transition: transform 0.25s ease, box-shadow 0.25s ease;
        border: 1px solid var(--card-border); border-left: 4px solid var(--accent, var(--card-border));
        animation: card-in 0.35s ease both;
    }
    .news-card:hover { transform: translateY(-4px); box-shadow: 0 14px 28px rgba(15,23,42,0.12); }
    .topic-badge {
        padding: 8px 18px; border-radius: 999px; font-weight: 800; font-size: 1.05rem;
        display: inline-block; margin-bottom: 15px; letter-spacing: -0.2px;
    }
    .news-title { margin-top:0; font-size:1.08rem; line-height:1.4; color: var(--text-main); font-weight: 700; }
    .news-meta { font-size:0.8rem; color: var(--text-sub); margin-bottom:10px; }
    .news-link { text-decoration:none; color: var(--brand); font-weight:700; font-size: 0.92rem; }
    .news-img { width: 100%; height: 180px; object-fit: cover; border-radius: 12px; margin-bottom: 12px; border: 1px solid var(--card-border); }
    .news-img-placeholder {
        width: 100%; height: 180px; border-radius: 12px; margin-bottom: 12px; border: 1px solid var(--card-border);
        display: flex; align-items: center; justify-content: center; background: var(--placeholder-bg);
    }
    .favicon-icon { width: 44px; height: 44px; border-radius: 10px; }
    .summary-box {
        background-color: var(--summary-bg); border-left: 4px solid var(--summary-border);
        padding: 12px; border-radius: 4px; margin-top: 15px; font-size: 0.95rem; color: var(--summary-text); line-height: 1.5;
    }

    /* 버튼을 좀 더 트렌디한 알약 모양으로 */
    .stButton > button {
        border-radius: 999px !important; font-weight: 600 !important;
        border: 1px solid var(--card-border) !important; transition: all .18s ease !important;
    }
    .stButton > button:hover { border-color: var(--brand) !important; color: var(--brand) !important; transform: translateY(-1px); }

    @media (max-width: 768px) { .stColumn { width: 100% !important; display: block; } }
</style>
""", unsafe_allow_html=True)

ACCENT_COLORS = ["#6366f1", "#ec4899", "#f59e0b", "#22c55e", "#06b6d4", "#ef4444", "#a855f7", "#14b8a6"]


def accent_for(index: int) -> str:
    return ACCENT_COLORS[index % len(ACCENT_COLORS)]

# 이미지가 전혀 없을 때 쓰는 순수 로컬 플레이스홀더 (외부 이미지 요청 없이 즉시 렌더링됨)
NO_IMAGE_SVG = "data:image/svg+xml;utf8," + urllib.parse.quote(
    "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='220'>"
    "<rect width='100%' height='100%' fill='#cbd5e1'/>"
    "<text x='50%' y='50%' font-size='42' text-anchor='middle' dominant-baseline='middle'>📰</text></svg>"
)

# ----------------- URL 디코딩 / 썸네일 추출 -----------------
# 구글이 뉴스 링크 인코딩 방식을 계속 바꾸기 때문에, 직접 base64를 해독하는 대신
# 이 변화에 맞춰 유지보수되는 googlenewsdecoder 라이브러리를 사용한다.

def decode_google_news_url(google_url: str) -> str:
    try:
        result = gnewsdecoder(google_url, interval=1)
        if result and result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception:
        pass
    return google_url


# 실패 결과를 오래 캐싱하면 한 번 실패한 기사가 한동안 계속 실패로 보이므로
# 성공/실패의 캐시 수명을 분리한다.
@st.cache_data(ttl=180, show_spinner=False)
def _resolve_real_url(google_url: str):
    real_url = decode_google_news_url(google_url)
    ok = bool(real_url) and "news.google.com" not in real_url
    return real_url, ok


@st.cache_data(ttl=21600, show_spinner=False)
def _fetch_thumbnail(real_url: str):
    """실제 언론사 URL에서 og:image를 가져오고, 없으면 파비콘, 그마저 없으면 로컬 플레이스홀더."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(real_url, headers=headers, timeout=6)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            val = og_img["content"]
            if "ssl.gstatic.com" not in val and "googleusercontent" not in val:
                if val.startswith("//"):
                    return "https:" + val, False
                if val.startswith("/"):
                    parsed = urllib.parse.urlparse(real_url)
                    return f"{parsed.scheme}://{parsed.netloc}{val}", False
                return val, False
    except Exception:
        pass

    try:
        domain = urllib.parse.urlparse(real_url).netloc
        if domain:
            return f"https://www.google.com/s2/favicons?sz=128&domain={domain}", True
    except Exception:
        pass
    return NO_IMAGE_SVG, True


def get_real_url_and_image(google_url: str):
    real_url, ok = _resolve_real_url(google_url)
    if not ok:
        return real_url, NO_IMAGE_SVG, True
    img_url, is_placeholder = _fetch_thumbnail(real_url)
    return real_url, img_url, is_placeholder


@st.cache_data(ttl=21600, show_spinner=False)
def extract_article_text(real_url: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(real_url, headers=headers, timeout=8)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")

        target_selectors = [("div", "dic_area"), ("div", "articeBody"), ("div", "article_view"), ("div", "newsct_article"), ("article", "")]
        text_chunks = []
        for tag, name in target_selectors:
            element = (soup.find(tag, id=name) or soup.find(tag, class_=name)) if name else soup.find(tag)
            if element:
                text_chunks = [p.get_text(strip=True) for p in element.find_all(["p", "div"]) if len(p.get_text(strip=True)) > 20]
                if text_chunks:
                    break

        if not text_chunks:
            text_chunks = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 30]

        final_text = re.sub(r"\s+", " ", " ".join(text_chunks)).strip()
        return final_text[:3000] if len(final_text) > 100 else None
    except Exception:
        return None


@st.cache_data(ttl=21600, show_spinner=False)
def get_ai_summary(text: str, api_key: str, model_name: str = "gemini-flash-latest"):
    """Gemini AI 요약 (신규 google-genai SDK 사용, 구 google-generativeai는 지원 종료됨).

    특정 버전(gemini-2.5-flash 등)은 계정/시점에 따라 신규 사용자에게 404로 막히거나
    지원이 종료될 수 있어, 항상 최신 stable flash 모델을 가리키는 별칭인
    gemini-flash-latest를 기본값으로 사용한다.

    실패(레이트리밋, 일시적 서버 과부하 등)를 여기서 삼켜버리면 st.cache_data가
    그 실패 결과를 6시간 동안 캐싱해버리므로, 예외를 그대로 올려서 실패는 캐싱되지 않게 한다.
    """
    client = genai.Client(api_key=api_key)
    res = client.models.generate_content(
        model=model_name,
        contents=f"다음 뉴스 기사를 핵심만 3줄로 요약해줘:\n\n{text}",
    )
    return res.text


def relative_time(entry) -> str:
    try:
        published_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
        diff_min = int((datetime.now() - published_dt).total_seconds() // 60)
        if diff_min < 1:
            return "방금 전"
        if diff_min < 60:
            return f"{diff_min}분 전"
        diff_hour = diff_min // 60
        if diff_hour < 24:
            return f"{diff_hour}시간 전"
        return f"{diff_hour // 24}일 전"
    except Exception:
        return getattr(entry, "published", "")


def dedupe_entries(entries):
    """여러 언론사가 같은 제목(+ 언론사명)으로 우려먹는 기사를 제거."""
    seen = set()
    result = []
    for e in entries:
        norm = re.sub(r"\s*[-|·]\s*[^-|·]{1,20}$", "", e.title).strip()
        key = norm[:24]
        if key in seen:
            continue
        seen.add(key)
        result.append(e)
    return result


def stable_key(*parts) -> str:
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _remove_keyword(idx: int):
    """키워드 삭제 콜백.

    Streamlit의 text_input은 key가 같으면 서버 쪽 기본값(value=)이 바뀌어도 브라우저에
    이미 그려진 입력창의 값을 그대로 들고 있는다. 그래서 중간 키워드를 지워 뒤 항목들의
    인덱스가 당겨지면, 위젯이 새 값이 아니라 이전에 표시하던 값을 계속 보여주는 문제가 생긴다.
    이를 막기 위해 삭제할 때마다 kw_version을 올려서 모든 입력창의 key를 바꾸고,
    강제로 새 위젯을 처음부터 다시 그리게 한다.
    """
    keywords = st.session_state.keywords
    st.session_state.keywords = [k for j, k in enumerate(keywords) if j != idx]
    st.session_state.kw_version = st.session_state.get("kw_version", 0) + 1


# ----------------- 사이드바 설정 -----------------
if "keywords" not in st.session_state:
    st.session_state.keywords = ["시사", "경제", "IT/과학", "스포츠"]
if "kw_version" not in st.session_state:
    st.session_state.kw_version = 0
if "bookmarks" not in st.session_state:
    st.session_state.bookmarks = {}  # key -> {title, url}

try:
    default_api_key = st.secrets.get("GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
except Exception:
    default_api_key = os.environ.get("GEMINI_API_KEY", "")

with st.sidebar:
    st.title("⚙️ 설정")
    api_key = st.text_input("🔑 Gemini API Key", type="password", value=default_api_key,
                             help="배포 환경의 .streamlit/secrets.toml에 GEMINI_API_KEY를 넣어두면 매번 입력하지 않아도 됩니다.")
    refresh_time = st.slider("자동 새로고침 주기(분)", 1, 60, 5)
    per_topic_count = st.slider("토픽당 기사 수", 3, 10, 5)

    st.divider()
    st.subheader("🔍 키워드 설정 (최대 10개)")

    current_keywords = st.session_state.keywords
    kw_ver = st.session_state.kw_version
    updated_keywords = []
    for i, k in enumerate(current_keywords):
        c1, c2 = st.columns([5, 1])
        with c1:
            val = st.text_input(
                f"키워드 {i + 1}", value=k, key=f"kw_input_{kw_ver}_{i}",
                label_visibility="collapsed", placeholder=f"키워드 {i + 1}",
            )
        with c2:
            st.button(
                "✕", key=f"kw_del_{kw_ver}_{i}", use_container_width=True, disabled=not k.strip(),
                on_click=_remove_keyword, args=(i,),
            )
        if val.strip():
            updated_keywords.append(val.strip())

    if len(updated_keywords) < 10:
        updated_keywords.append("")  # 입력 가능한 빈 칸을 항상 마지막에 하나 유지 (개수에 따라 자동으로 늘고 줆)

    if updated_keywords != current_keywords:
        st.session_state.keywords = updated_keywords
        st.rerun()

    final_topics = [k.strip() for k in st.session_state.keywords if k.strip()][:10]

    st.divider()
    st.subheader(f"⭐ 즐겨찾기 ({len(st.session_state.bookmarks)})")
    if st.session_state.bookmarks:
        with st.expander("즐겨찾은 기사 보기"):
            for b in st.session_state.bookmarks.values():
                st.markdown(f"- [{b['title']}]({b['url']})")
    else:
        st.caption("기사 카드의 ⭐ 버튼으로 즐겨찾기를 추가하세요.")

    st.divider()
    st.subheader("📱 모바일 접속 QR")
    try:
        app_url = "https://pl6iapp7sjwpgkkwvr4gf4.streamlit.app/"
        qr = qrcode.make(app_url)
        st.image(qr.get_image(), use_container_width=True)
        st.caption("스마트폰 카메라로 스캔하세요.")
    except Exception:
        st.error("QR코드 생성 실패")

# ----------------- 메인 대시보드 영역 -----------------
st_autorefresh(interval=refresh_time * 60 * 1000, key="data_refresh")

st.markdown("<h1 class='main-title'>🌐 실시간 종합 뉴스 대시보드</h1>", unsafe_allow_html=True)
st.markdown("<p class='main-subtitle'>관심 키워드를 자동으로 추적해서 보여드려요</p>", unsafe_allow_html=True)

if final_topics:
    ticker_text = f"🔥 실시간 주요뉴스&nbsp;&nbsp;&nbsp;{'&nbsp;&nbsp;|&nbsp;&nbsp;'.join(final_topics)}&nbsp;&nbsp;&nbsp;...업데이트 중"
    st.markdown(f"""
        <div class='ticker-wrap'>
            <div class='ticker-track'>
                <span class='ticker-item'>{ticker_text}</span>
                <span class='ticker-item'>{ticker_text}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 토픽마다 따로 로딩 스피너를 띄우면 화면이 산만해지므로, 모든 토픽의 기사를 먼저 모아서
    # 한 번에 병렬로 리졸브하고 로딩 표시도 한 번만 보여준다.
    topic_entries = {}
    all_entries = []
    for topic in final_topics:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(topic)}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(url)
        entries = dedupe_entries(feed.entries)[:per_topic_count]
        topic_entries[topic] = entries
        all_entries.extend(entries)

    unique_links = list(dict.fromkeys(e.link for e in all_entries))
    with st.spinner("최신 기사를 불러오는 중..."):
        with ThreadPoolExecutor(max_workers=16) as executor:
            resolved_list = list(executor.map(get_real_url_and_image, unique_links))
    resolved_map = dict(zip(unique_links, resolved_list))

    num_cols = min(len(final_topics), 4)
    cols = st.columns(num_cols if num_cols > 0 else 1)

    for i, topic in enumerate(final_topics):
        col = cols[i % num_cols]
        accent = accent_for(i)
        with col:
            st.markdown(
                f"<div class='topic-badge' style='background:{accent}22; color:{accent};'>📌 {topic}</div>",
                unsafe_allow_html=True,
            )

            entries = topic_entries[topic]

            for j, item in enumerate(entries):
                real_url, img_url, is_placeholder = resolved_map[item.link]
                key_id = stable_key(topic, item.link, str(j))

                with st.container():
                    st.markdown(f"<div class='news-card' style='--accent:{accent};'>", unsafe_allow_html=True)

                    img_html = (
                        f"<div class='news-img-placeholder'><img src='{img_url}' class='favicon-icon' "
                        f"onerror=\"this.onerror=null;this.src='{NO_IMAGE_SVG}';\"></div>"
                        if is_placeholder else
                        f"<img src='{img_url}' class='news-img' "
                        f"onerror=\"this.onerror=null;this.parentElement.innerHTML='<div class=&quot;news-img-placeholder&quot;><img src=&quot;{NO_IMAGE_SVG}&quot; class=&quot;favicon-icon&quot;></div>';\">"
                    )
                    card_html = f"""
                        {img_html}
                        <h4 class='news-title'>{item.title}</h4>
                        <p class='news-meta'>🕒 {relative_time(item)}</p>
                        <a href='{real_url}' target='_blank' class='news-link'>🔗 원문 기사 읽기</a>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)

                    btn_col1, btn_col2 = st.columns([1, 1])
                    with btn_col1:
                        is_marked = key_id in st.session_state.bookmarks
                        if st.button("⭐ 즐겨찾기" if not is_marked else "✅ 즐겨찾음", key=f"bm_{key_id}", use_container_width=True):
                            if is_marked:
                                st.session_state.bookmarks.pop(key_id, None)
                            else:
                                st.session_state.bookmarks[key_id] = {"title": item.title, "url": real_url}
                            st.rerun()
                    with btn_col2:
                        if api_key:
                            if st.button("✨ AI 3줄 요약", key=f"btn_{key_id}", use_container_width=True):
                                with st.spinner("본문을 분석 중입니다..."):
                                    article_text = extract_article_text(real_url)
                                    if not article_text:
                                        article_text = BeautifulSoup(item.summary, "html.parser").get_text(separator=" ", strip=True)
                                        st.warning("🚫 본문 접근이 막혀 있어 RSS 요약본으로 대체합니다.")
                                    if article_text:
                                        try:
                                            summary_result = get_ai_summary(article_text, api_key)
                                            st.markdown(f"<div class='summary-box'><b>[AI 요약]</b><br>{summary_result}</div>", unsafe_allow_html=True)
                                        except Exception as e:
                                            st.error(f"AI 요약 호출 실패: {e}")
                                    else:
                                        st.error("요약할 텍스트를 추출하지 못했습니다.")

                    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("👈 왼쪽 사이드바에서 표시할 주제/키워드를 입력해 주세요.")
