import streamlit as st
import feedparser
import requests
import google.generativeai as genai

from newspaper import Article
from streamlit_autorefresh import st_autorefresh
from bs4 import BeautifulSoup
from io import BytesIO
import qrcode

# -------------------------------------------------
# PAGE
# -------------------------------------------------

st.set_page_config(
    page_title="Live News Dashboard",
    page_icon="📰",
    layout="wide"
)

st_autorefresh(interval=300000, key="refresh")

# -------------------------------------------------
# CSS
# -------------------------------------------------

st.markdown("""
<style>

.stApp{
background:#eef2f7;
}

.card{
background:white;
padding:15px;
border-radius:15px;
margin-bottom:18px;
box-shadow:0 3px 8px rgba(0,0,0,.08);
}

.card img{
border-radius:12px;
}

.news-title{
font-size:20px;
font-weight:bold;
margin-bottom:10px;
}

.summary{
background:#f5f7fb;
padding:10px;
border-radius:10px;
}

</style>
""",unsafe_allow_html=True)

# -------------------------------------------------
# SIDEBAR
# -------------------------------------------------

with st.sidebar:

    st.title("⚙️ 설정")

    api_key=st.text_input(
        "Gemini API",
        type="password"
    )

    if "keywords" not in st.session_state:
        st.session_state.keywords=[
            "경제",
            "AI",
            "반도체"
        ]

    st.divider()

    new=[]

    for i,k in enumerate(st.session_state.keywords):

        v=st.text_input(
            f"키워드{i+1}",
            value=k,
            key=i
        )

        if v!="":
            new.append(v)

    if len(new)<8:
        new.append("")

    st.session_state.keywords=new

    st.divider()

    qr=qrcode.make("https://streamlit.io")

    buf=BytesIO()

    qr.save(buf)

    st.image(buf,width=120)

# -------------------------------------------------
# FUNCTIONS
# -------------------------------------------------

def get_news(keyword):

    url=f"https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"

    news=feedparser.parse(url)

    return news.entries[:5]


def get_image(link):

    try:

        article=Article(link)

        article.download()

        article.parse()

        return article.top_image

    except:

        return None


def get_text(link):

    try:

        article=Article(link)

        article.download()

        article.parse()

        return article.text[:5000]

    except:

        try:

            r=requests.get(link,timeout=10)

            soup=BeautifulSoup(r.text,"html.parser")

            return soup.get_text(" ",strip=True)[:5000]

        except:

            return ""


def ai_summary(text,key):

    if key=="":

        return "Gemini API Key를 입력하세요."

    try:

        genai.configure(api_key=key)

        model=genai.GenerativeModel("gemini-1.5-flash")

        prompt=f"""

아래 뉴스를 한국어로

1. 핵심내용

2. 중요한 사실

3. 전망

3줄로 요약해줘.

{text}

"""

        res=model.generate_content(prompt)

        return res.text

    except Exception as e:

        return str(e)

# -------------------------------------------------

st.title("📰 실시간 뉴스 대시보드")

ticker=" | ".join(
[
f"📢 {k}"
for k in st.session_state.keywords
if k
]
)

st.info(ticker)

topics=[k for k in st.session_state.keywords if k]

cols=st.columns(len(topics))

for idx,topic in enumerate(topics):

    with cols[idx]:

        st.subheader(topic)

        news=get_news(topic)

        for n,item in enumerate(news):

            st.markdown("<div class='card'>",unsafe_allow_html=True)

            img=get_image(item.link)

            if img:

                st.image(
                    img,
                    use_container_width=True
                )

            st.markdown(
                f"<div class='news-title'>{item.title}</div>",
                unsafe_allow_html=True
            )

            st.write(item.get("published",""))

            st.link_button(
                "기사 보기",
                item.link,
                use_container_width=True
            )

            if st.button(
                "✨ AI 3줄 요약",
                key=f"{idx}{n}"
            ):

                with st.spinner("AI 분석중..."):

                    text=get_text(item.link)

                    if text=="":

                        text=item.summary

                    result=ai_summary(
                        text,
                        api_key
                    )

                    st.success(result)

            st.markdown("</div>",unsafe_allow_html=True)
