import requests
from bs4 import BeautifulSoup
import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time

st.set_page_config(page_title="採用FAQボット", page_icon="🤖")
st.title("採用FAQチャットボット (サイト全体連携版)")

# サイドバーの設定
st.sidebar.markdown("### ⚙️ 設定")
api_key = st.sidebar.text_input("Gemini APIキー", type="password")
target_url = st.sidebar.text_input("読み込ませたい自社のURL", value="https://d4c-creative.com/")

# ==========================================
# サイト全体を巡回（クロール）してテキストを抽出する関数
# ==========================================
EXCLUDE_DIRS = ['/wp/', '/test/', '/resalts/']
MAX_PAGES = 30  # 読み込む最大ページ数（プロトタイプ用）

@st.cache_data(show_spinner=False)
def get_all_text_from_site(base_url):
    if not base_url:
        return ""
    
    visited = set()
    urls_to_visit = [base_url]
    all_text = ""
    base_domain = urlparse(base_url).netloc

    with st.spinner("サイト全体を巡回してデータを読み込んでいます...（数分かかる場合があります）"):
        while urls_to_visit and len(visited) < MAX_PAGES:
            current_url = urls_to_visit.pop(0)

            # 既に訪問済みならスキップ
            if current_url in visited:
                continue

            # 【重要】除外ディレクトリが含まれていたらスキップ
            path = urlparse(current_url).path
            if any(exclude in path for exclude in EXCLUDE_DIRS):
                continue

            visited.add(current_url)

            try:
                # ページの内容を取得
                response = requests.get(current_url, timeout=10)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')
                text = soup.get_text(separator='\n', strip=True)
                
                # 抽出したテキストを合体させる（どのページの情報かも記載する）
                all_text += f"\n\n【ページ: {current_url}】\n{text}"

                # ページ内にあるリンクをすべて探し、次に訪問するリストに追加
                for link in soup.find_all('a', href=True):
                    next_url = urljoin(current_url, link['href']).split('#')[0] # #以降（ページ内ジャンプ）は無視
                    next_domain = urlparse(next_url).netloc
                    
                    # 同じドメイン内で、まだ訪問していない新しいURLなら追加
                    if next_domain == base_domain and next_url not in visited and next_url not in urls_to_visit:
                        urls_to_visit.append(next_url)
                
                # 相手サーバーに負荷をかけないよう、少し待機する（マナー）
                time.sleep(0.5)

            except Exception as e:
                print(f"エラー ({current_url}): {e}")

    return all_text

# ==========================================
# メイン処理
# ==========================================
if api_key and target_url:
    # クローラーを実行してサイト全体のテキストを取得
    web_text = get_all_text_from_site(target_url)
    
    genai.configure(api_key=api_key)
    
    # セッションにモデルとチャット履歴がなければ初期化
    if "chat_session" not in st.session_state:
        SYSTEM_INSTRUCTION = f"""
        あなたは優秀な企業の採用アシスタントです。
        以下の【自社Webサイト全体のデータ】のみを参考にして、求職者からの質問に丁寧な言葉遣いで回答してください。
        データに書かれていない質問には絶対に推測で答えず、「その質問については、お手数ですが面接時に直接採用担当へお問い合わせください」と回答してください。

        【自社Webサイト全体のデータ】
        {web_text}
        """

        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash", # バージョンを修正
            system_instruction=SYSTEM_INSTRUCTION
        )
        
        st.session_state.messages = []
        st.session_state.chat_session = model.start_chat(history=[])

    # 過去のメッセージを画面に描画
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ユーザーからの入力
    if prompt := st.chat_input("質問を入力してください"):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("回答を生成中..."):
                try:
                    response = st.session_state.chat_session.send_message(prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"APIエラーが発生しました: {e}")

elif not api_key:
    st.info("👈 左側のサイドバーにGemini APIキーを入力してください。")
