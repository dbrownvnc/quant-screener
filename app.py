
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener", layout="wide")

# v7.0: ATR 기반 동적 손절 로직 추가
st.title("📈 AI 퀀트 종목 발굴기 (v7.0)")
st.markdown("""
**알고리즘 로직:**
1.  **추세 필터:** 200일 이동평균선 위에 있는 '상승 추세' 종목을 대상으로 분석
2.  **거래량 필터:** 20일 평균 거래량 대비 현재 거래량의 급증 여부 확인
3.  **타이밍 포착:** 볼린저 밴드 하단 터치 및 RSI 과매도 시그널 확인
4.  **리스크 관리:** ATR(변동성)을 기반으로 종목별 손절 라인 자동 계산
---
**v7.0 변경점:**
1.  **ATR 기반 동적 손절매:** 종목의 변동성에 맞춰 손절 라인을 자동으로 조절하는 기능을 추가하여 리스크 관리를 고도화했습니다. (권장)
2.  **리스크 관리 UI 개선:** 사이드바에서 'ATR 기반' 또는 '고정 비율' 손절 방식을 직접 선택할 수 있습니다.
3.  **안정성 유지:** v6.2의 MultiIndex 오류 수정, 분석 로직, Secrets 관리 기능은 모두 그대로 유지됩니다.
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

# --- 사이드바 UI 수정 (손절 설정 고도화) ---
st.sidebar.divider()
st.sidebar.subheader("🛡️ 리스크 관리 설정")
stop_loss_mode = st.sidebar.radio(
    "손절가 계산 방식",
    ("ATR 기반 (권장)", "고정 비율 (%)"),
    index=0,
    help="ATR: 종목의 변동성에 따라 자동으로 손절폭을 조절합니다.\n고정 비율: 모든 종목에 동일한 퍼센트를 적용합니다."
)

if stop_loss_mode == "고정 비율 (%)":
    stop_loss_pct = st.sidebar.slider("손절 비율 (%)", 1.0, 10.0, 3.0, 0.5)
    atr_multiplier = 0  # 사용 안 함
else:
    atr_multiplier = st.sidebar.slider("ATR 배수 (k)", 1.0, 5.0, 2.0, 0.1, help="보통 2.0~3.0을 사용합니다. 수치가 클수록 손절폭이 넓어집니다.")
    stop_loss_pct = 0  # 사용 안 함

# --- 분석 함수 수정 (ATR 로직 추가) ---
def analyze_dataframe(ticker, df, stop_loss_mode, stop_val, market):
    try:
        # 1. 기술적 지표 생성
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)  # 2. ATR 지표 추가

        df.dropna(inplace=True)
        if df.empty: return {"티커": ticker, "신호": "오류", "오류 원인": "데이터 정제 후 비어있음"}

        # 3. 컬럼 매핑
        bbl_col = next((col for col in df.columns if col.startswith('BBL')), None)
        sma_col = next((col for col in df.columns if col.startswith('SMA_200')), None)
        atr_col = next((col for col in df.columns if col.startswith('ATRr')), None)

        if not bbl_col or not sma_col or not atr_col:
            return {"티커": ticker, "신호": "오류", "오류 원인": "핵심 지표 컬럼 생성 실패"}

        latest = df.iloc[-1]
        close = latest['close']
        ma200 = latest[sma_col]
        rsi = latest['RSI_14']
        bb_lower = latest[bbl_col]
        atr_value = latest[atr_col]

        # --- 손절가 계산 로직 (핵심 수정) ---
        currency_format = "{:,.0f}" if market == '한국 증시 (Korea)' else "{:,.2f}"
        currency_symbol = "₩" if market == '한국 증시 (Korea)' else "$"

        if stop_loss_mode == "ATR 기반 (권장)":
            loss_price = close - (atr_value * stop_val)
            loss_pct_display = round(((close - loss_price) / close) * 100, 2)
            loss_info = f"{currency_symbol}{currency_format.format(loss_price)} (-{loss_pct_display}%)"
        else:  # 고정 비율
            loss_price = close * (1 - stop_val / 100)
            loss_info = f"{currency_symbol}{currency_format.format(loss_price)} (-{stop_val}%)"

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
            "추세": trend, "RSI": rsi, "거래량": volume_signal, "손절가": loss_info,
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
                df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0).str.lower()
                else:
                    df.columns = df.columns.str.lower()

                if df.empty or len(df) < 200: continue

                # --- 호출 부분 수정 ---
                target_val = atr_multiplier if stop_loss_mode == "ATR 기반 (권장)" else stop_loss_pct
                analysis_result = analyze_dataframe(ticker, df.copy(), stop_loss_mode, target_val, market_choice)

                if "오류" in analysis_result.get("신호", ""): error_results.append(analysis_result)
                else: ok_results.append(analysis_result)

            except Exception as e:
                error_results.append({"티커": ticker, "신호": "오류", "오류 원인": str(e)})
            progress_bar.progress((i + 1) / len(tickers), text=f"[{ticker}] 분석 완료")

        progress_bar.empty()

        if ok_results:
            st.subheader("📊 분석 결과")
            res_df = pd.DataFrame(ok_results)
            # 점수 기반 정렬
            score_map = {"🔥 강력 매수": 0, "✅ 매수 고려": 1, "관망": 2}
            res_df['score'] = res_df['신호'].map(score_map).fillna(3)
            res_df = res_df.sort_values('score').drop(columns='score').reset_index(drop=True)
            
            # 통화 형식 적용
            price_format = "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}"
            st.dataframe(res_df.style.format(
                {"현재가": price_format, "RSI": "{:.1f}"}
            ), use_container_width=True, hide_index=True)

        if error_results:
            st.subheader("⚠️ 분석 실패 목록")
            st.dataframe(pd.DataFrame(error_results), use_container_width=True, hide_index=True)
