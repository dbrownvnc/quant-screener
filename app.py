
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener", layout="wide")

# v6.2: MultiIndex 오류 수정 및 분석 로직 복원
st.title("📈 AI 퀀트 종목 발굴기 (v6.2 - 최종 안정화)")
st.markdown("""
**알고리즘 로직:**
1.  **추세 필터:** 200일 이동평균선 위에 있는 '상승 추세' 종목을 대상으로 분석
2.  **거래량 필터:** 20일 평균 거래량 대비 현재 거래량의 급증 여부 확인
3.  **타이밍 포착:** 볼린저 밴드 하단 터치 및 RSI 과매도 시그널 확인
4.  **리스크 관리:** 설정된 손절 라인 자동 계산
---
**v6.2 변경점:**
1.  **MultiIndex 오류 해결:** `yfinance` 데이터 다운로드 시 발생하는 MultiIndex 컬럼 구조를 안정적으로 처리합니다.
2.  **핵심 분석 로직 복원:** v4.2의 동적 지표 컬럼 탐색 기능을 다시 적용하여 분석 안정성을 확보했습니다.
3.  **Secrets 로딩 안정성 유지:** v6.1의 Secrets 로딩 개선 사항은 그대로 유지됩니다.
""")

# --- jsonbin.io 및 Secrets 설정 (v6.1 로직 유지) ---
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]

JSONBIN_API_KEY = next((st.secrets[key] for key in api_key_names if hasattr(st.secrets, key)), None)
JSONBIN_BIN_ID = next((st.secrets[key] for key in bin_id_names if hasattr(st.secrets, key)), None)

if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
    st.error("⚠️ [설정 오류] `JSONBIN_API_KEY` 또는 `JSONBIN_BIN_ID`를 찾을 수 없습니다.")
    st.warning("Secrets 설정 가이드:")
    st.code('''
    # Streamlit Cloud의 앱 설정 > Secrets에 아래 형식으로 키와 값을 입력하세요.
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

# --- 데이터 로드/저장 함수 ---
@st.cache_data(ttl=300)
def load_watchlist_from_jsonbin():
    try:
        response = requests.get(f"{JSONBIN_URL}/latest", headers=HEADERS)
        response.raise_for_status()
        return response.json().get('record', {}).get('watchlist', [])
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        st.error(f"클라우드 관심종목 로딩 실패. 원인: {e}")
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

# --- 사이드바 UI --- 
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
            st.rerun()

# 관심종목 목록 표시 및 삭제
for ticker_to_remove in st.session_state.watchlist[:]:
    col1, col2 = st.sidebar.columns([0.8, 0.2])
    col1.markdown(f"- {ticker_to_remove}")
    if col2.button("🗑️", key=f"del_{ticker_to_remove}", help=f"{ticker_to_remove} 삭제"):
        new_list = [t for t in st.session_state.watchlist if t != ticker_to_remove]
        if save_watchlist_to_jsonbin(new_list):
            st.session_state.watchlist = new_list
            st.rerun()
st.sidebar.divider()

# --- 종목 선택 UI ---
watchlist_str = ", ".join(st.session_state.watchlist)

if market_choice == '한국 증시 (Korea)':
    presets = {"관심종목 (Cloud)": watchlist_str, "주요 기술주": "005930,000660,035420", "주요 자동차주": "005380,000270"}
    caption = "💡 종목 코드 입력 (예: 005930)"
else:
    presets = {"관심종목 (Cloud)": watchlist_str, "주요 기술주": "NVDA,AAPL,MSFT,GOOGL", "주요 성장주": "TSLA,PLTR,MSTR"}
    caption = "💡 티커 입력 (예: NVDA, TSLA)"

preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)
st.sidebar.caption(caption)
stop_loss_pct = st.sidebar.slider("손절가 비율 (%)", 1.0, 10.0, 3.0, 0.5)

# --- 분석 함수 (v4.2 안정화 로직 복원) ---
def analyze_dataframe(ticker, df, stop_loss_pct):
    try:
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.dropna(inplace=True)
        if df.empty: return {"티커": ticker, "신호": "오류", "오류 원인": "데이터 정제 후 비어있음"}

        bbl_col = next((col for col in df.columns if col.startswith('BBL')), None)
        sma_col = next((col for col in df.columns if col.startswith('SMA_200')), None)
        if not bbl_col or not sma_col: return {"티커": ticker, "신호": "오류", "오류 원인": "핵심 지표 컬럼 탐색 실패"}

        latest = df.iloc[-1]
        close = latest['close']
        ma200 = latest[sma_col]
        rsi = latest['RSI_14']
        bb_lower = latest[bbl_col]
        
        volume_signal = "N/A"
        if 'volume' in df.columns and df['volume'].rolling(20).mean().iloc[-1] > 0:
            vol_avg = df['volume'].rolling(20).mean().iloc[-1]
            if latest['volume'] > vol_avg * 1.5: volume_signal = "급증"
            else: volume_signal = "보통"

        trend = "상승" if close > ma200 else "하락"
        signal = "관망"
        if trend == "상승":
            if close <= bb_lower and rsi < 35: signal = "🔥 강력 매수"
            elif close <= bb_lower * 1.03 and rsi < 45: signal = "✅ 매수 고려"

        return {
            "티커": ticker, "신호": signal, "현재가": close,
            "추세": trend, "RSI": rsi, "거래량": volume_signal, "손절가": close * (1 - stop_loss_pct / 100),
        }
    except Exception as e:
        return {"티커": ticker, "신호": "오류", "오류 원인": f"분석 로직 오류: {e}"}

# --- 실행 버튼 및 결과 표시 ---
if st.sidebar.button("🚀 AI 퀀트 분석 시작!"):
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = [f"{t}.KS" if market_choice == '한국 증시 (Korea)' else t for t in tickers_raw]
    
    if not tickers:
        st.warning("분석할 종목이 없습니다.")
    else:
        ok_results, error_results = [], []
        progress_bar = st.progress(0, text="분석 시작...")

        for i, ticker in enumerate(tickers):
            try:
                # ❗️ MultiIndex 핸들링 로직 적용
                df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0).str.lower()
                else:
                    df.columns = df.columns.str.lower()
                
                if df.empty or len(df) < 200: continue

                analysis_result = analyze_dataframe(ticker, df.copy(), stop_loss_pct)
                if "오류" in analysis_result.get("신호", ""): error_results.append(analysis_result)
                else: ok_results.append(analysis_result)
            
            except Exception as e:
                error_results.append({"티커": ticker, "신호": "오류", "오류 원인": str(e)})
            progress_bar.progress((i + 1) / len(tickers), text=f"[{ticker}] 분석 완료")

        progress_bar.empty()

        if ok_results:
            st.subheader("📊 분석 결과")
            res_df = pd.DataFrame(ok_results).sort_values(by="신호").reset_index(drop=True)
            st.dataframe(res_df.style.format(precision=2), use_container_width=True, hide_index=True)

        if error_results:
            st.subheader("⚠️ 분석 실패 목록")
            st.dataframe(pd.DataFrame(error_results), use_container_width=True, hide_index=True)
