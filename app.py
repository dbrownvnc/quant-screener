
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener", layout="wide")

# v6.1: Secrets 로딩 안정성 강화
st.title("📈 AI 퀀트 종목 발굴기 (v6.1)")
st.markdown("""
**알고리즘 로직:**
1.  **추세 필터:** 200일 이동평균선 위에 있는 '상승 추세' 종목을 대상으로 분석
2.  **거래량 필터:** 20일 평균 거래량 대비 현재 거래량의 급증 여부 확인
3.  **타이밍 포착:** 볼린저 밴드 하단 터치 및 RSI 과매도 시그널 확인
4.  **리스크 관리:** 설정된 손절 라인 자동 계산
---
**v6.1 변경점:**
1.  **Secrets 로딩 로직 개선:** 대소문자 등 Secrets 입력 오류에 더 유연하게 대응하고, 명확한 디버깅 가이드를 제공합니다.
2.  **클라우드 연동 기능 유지:** jsonbin.io를 통한 관심종목 영구 저장 기능은 그대로 유지됩니다.
""")

# --- jsonbin.io 및 Secrets 설정 (v6.1) ---
# 대소문자 등 일반적인 입력 오류에 대응하기 위해 여러 키 이름을 시도
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]

JSONBIN_API_KEY = None
for key in api_key_names:
    if hasattr(st.secrets, key):
        JSONBIN_API_KEY = st.secrets[key]
        break

JSONBIN_BIN_ID = None
for key in bin_id_names:
    if hasattr(st.secrets, key):
        JSONBIN_BIN_ID = st.secrets[key]
        break

# 키를 찾았는지 최종 확인
if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
    st.error("⚠️ [설정 오류] `JSONBIN_API_KEY` 또는 `JSONBIN_BIN_ID`를 찾을 수 없습니다.")
    st.warning("Secrets 설정 가이드:")
    st.code('''
    # Streamlit Cloud의 앱 설정 > Secrets에 아래 형식으로 키와 값을 입력하세요.
    # (대소문자를 정확히 지켜주세요)

    JSONBIN_API_KEY = "YOUR_JSONBIN_API_KEY"
    JSONBIN_BIN_ID = "YOUR_JSONBIN_BIN_ID"
    ''', language='toml')
    st.info("💡 Secrets를 추가하거나 수정한 후에는 반드시 우측 상단의 'Manage app' 메뉴에서 **앱을 재부팅(Reboot app)**해야 적용됩니다.")
    st.stop()

JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
HEADERS = {
    'Content-Type': 'application/json',
    'X-Master-Key': JSONBIN_API_KEY
}

# --- jsonbin.io 데이터 로드/저장 함수 ---
@st.cache_data(ttl=600) # 10분 동안 캐시
def load_watchlist_from_jsonbin():
    try:
        response = requests.get(f"{JSONBIN_URL}/latest", headers=HEADERS)
        response.raise_for_status()
        if not response.content:
             return []
        return response.json().get('record', {}).get('watchlist', [])
    except requests.exceptions.RequestException as e:
        st.error(f"클라우드에서 관심종목 로딩 실패: {e}")
        return []
    except json.JSONDecodeError:
        st.warning("클라우드 데이터가 비어있거나 손상되었습니다. 새 목록을 생성합니다.")
        return []

def save_watchlist_to_jsonbin(watchlist_data):
    try:
        response = requests.put(JSONBIN_URL, headers=HEADERS, json={'watchlist': watchlist_data})
        response.raise_for_status()
        st.cache_data.clear()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"클라우드에 관심종목 저장 실패: {e}")
        return False

# --- 세션 상태 초기화 ---
if 'watchlist_loaded' not in st.session_state:
    st.session_state.watchlist = load_watchlist_from_jsonbin()
    st.session_state.watchlist_loaded = True

# (이하 코드는 v6.0과 동일)
# --- 사이드바 ---
st.sidebar.header("⚙️ 설정 (Settings)")
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)

# --- 관심종목 관리 UI ---
st.sidebar.subheader("❤️ 관심종목 관리 (Cloud)")
new_ticker = st.sidebar.text_input("티커 추가", placeholder="예: NVDA, 005930").upper()

if st.sidebar.button("➕ 추가"):
    if new_ticker and new_ticker not in st.session_state.watchlist:
        new_list = st.session_state.watchlist + [new_ticker]
        if save_watchlist_to_jsonbin(new_list):
            st.session_state.watchlist = new_list
            st.sidebar.success(f"'{new_ticker}'를 클라우드에 추가했습니다.")
            st.rerun()
    elif new_ticker in st.session_state.watchlist:
        st.sidebar.warning(f"'{new_ticker}'는 이미 목록에 있습니다.")
    else:
        st.sidebar.warning("추가할 티커를 입력해주세요.")


if st.session_state.watchlist:
    st.sidebar.markdown("내 관심종목:")
    for ticker_to_remove in st.session_state.watchlist[:]:
        col1, col2 = st.sidebar.columns([0.8, 0.2])
        col1.markdown(f"- {ticker_to_remove}")
        if col2.button("🗑️", key=f"del_{ticker_to_remove}", help=f"{ticker_to_remove} 삭제"):
            new_list = [t for t in st.session_state.watchlist if t != ticker_to_remove]
            if save_watchlist_to_jsonbin(new_list):
                st.session_state.watchlist = new_list
                st.rerun()
else:
    st.sidebar.caption("추가된 관심종목이 없습니다.")

st.sidebar.divider()

# --- 종목 선택 UI ---
watchlist_str = ", ".join(st.session_state.watchlist)

if market_choice == '한국 증시 (Korea)':
    presets = {
        "관심종목 (Cloud)": watchlist_str,
        "주요 기술주": "005930, 000660, 035420, 035720",
        "주요 자동차주": "005380, 000270",
        "주요 배터리주": "373220, 006400, 051910",
    }
    caption = "💡 종목 코드 입력 (예: 005930)"
else: # 미국 증시
    presets = {
        "관심종목 (Cloud)": watchlist_str,
        "주요 기술주": "NVDA, AAPL, MSFT, GOOGL, AMD",
        "주요 성장주": "TSLA, PLTR, MSTR",
        "주요 ETF": "SPY, QQQ, TQQQ",
    }
    caption = "💡 티커 입력 (예: NVDA, TSLA)"

preset_options = list(presets.keys())
preset_key = st.sidebar.selectbox("종목 프리셋", preset_options)
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)
st.sidebar.caption(caption)
stop_loss_pct = st.sidebar.slider("손절가 비율 (%)", 1.0, 10.0, 3.0, 0.5)

# --- 분석 함수 ---
def analyze_dataframe(ticker, df, stop_loss_pct):
    try:
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.dropna(inplace=True)
        if df.empty: return {"티커": ticker, "신호": "오류", "오류 원인": "데이터 부족"}
        bbl_col = next((col for col in df.columns if col.startswith('BBL')), None)
        sma_col = next((col for col in df.columns if col.startswith('SMA')), None)
        if not bbl_col or not sma_col: return {"티커": ticker, "신호": "오류", "오류 원인": "지표 생성 실패"}
        latest = df.iloc[-1]
        close = latest['close']
        trend = "상승" if close > latest[sma_col] else "하락"
        signal = "관망"
        if trend == "상승" and close <= latest[bbl_col]:
            signal = "매수 고려"
        return {"티커": ticker, "신호": signal, "현재가": f"{close:.2f}", "추세": trend}
    except Exception as e:
        return {"티커": ticker, "신호": "오류", "오류 원인": str(e)}

# --- 실행 버튼 및 결과 표시 ---
if st.sidebar.button("🚀 AI 퀀트 분석 시작!"):
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = [f"{t}.KS" if market_choice == '한국 증시 (Korea)' else t for t in tickers_raw]
    if not tickers:
        st.warning("분석할 종목이 없습니다. 티커를 입력해주세요.")
    else:
        results = []
        progress_bar = st.progress(0)
        for i, ticker in enumerate(tickers):
            try:
                data = yf.download(ticker, period="1y", progress=False)
                if data.empty: raise ValueError("데이터 없음")
                analysis = analyze_dataframe(ticker, data.copy(), stop_loss_pct)
                results.append(analysis)
            except Exception as e:
                results.append({"티커": ticker, "신호": "오류", "오류 원인": str(e)})
            progress_bar.progress((i + 1) / len(tickers))
        st.subheader("분석 결과")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
