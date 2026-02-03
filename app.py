
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener", layout="wide")

# v7.1: 프리셋 업데이트 및 코스닥 자동 지원
st.title("📈 AI 퀀트 종목 발굴기 (v7.1)")
st.markdown("""
**알고리즘 로직:**
1.  **추세 필터:** 200일 이동평균선 위에 있는 '상승 추세' 종목을 대상으로 분석
2.  **거래량 필터:** 20일 평균 거래량 대비 현재 거래량의 급증 여부 확인
3.  **타이밍 포착:** 볼린저 밴드 하단 터치 및 RSI 과매도 시그널 확인
4.  **리스크 관리:** ATR(변동성)을 기반으로 종목별 손절 라인 자동 계산
---
**v7.1 변경점:**
1.  **시장 주도주 프리셋:** AI, 반도체, 비만치료제 등 최신 트렌드를 반영한 미국/한국 주도주 목록으로 프리셋을 대폭 업데이트했습니다.
2.  **코스닥 자동 지원:** 한국 증시 분석 시, 코스피(.KS) 조회 실패 시 코스닥(.KQ)으로 자동 재시도하는 안정적인 로직을 도입했습니다.
""")

# --- jsonbin.io 및 Secrets 설정 ---
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]

JSONBIN_API_KEY = next((st.secrets[key] for key in api_key_names if hasattr(st.secrets, key)), None)
JSONBIN_BIN_ID = next((st.secrets[key] for key in bin_id_names if hasattr(st.secrets, key)), None)

if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
    st.error("⚠️ [설정 오류] `JSONBIN_API_KEY` 또는 `JSONBIN_BIN_ID`를 찾을 수 없습니다.")
    st.code('''
    # Streamlit Cloud의 앱 설정 > Secrets에 아래 형식으로 키를 입력하세요.
    JSONBIN_API_KEY = "YOUR_JSONBIN_API_KEY"
    JSONBIN_BIN_ID = "YOUR_JSONBIN_BIN_ID"
    ''', language='toml')
    st.info("💡 Secrets를 추가/수정한 후에는 반드시 우측 상단의 'Manage app' 메뉴에서 **앱을 재부팅(Reboot app)**해야 적용됩니다.")
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
        return []

def save_watchlist_to_jsonbin(watchlist_data):
    try:
        response = requests.put(JSONBIN_URL, headers=HEADERS, json={'watchlist': watchlist_data})
        response.raise_for_status()
        st.cache_data.clear()
        return True
    except requests.exceptions.RequestException:
        return False

# --- 세션 상태 초기화 ---
if 'watchlist_loaded' not in st.session_state:
    st.session_state.watchlist = load_watchlist_from_jsonbin()
    st.session_state.watchlist_loaded = True

# --- 사이드바 UI ---
st.sidebar.header("⚙️ 설정 (Settings)")
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)

# --- 관심종목 UI ---
st.sidebar.subheader("❤️ 관심종목 관리 (Cloud)")
new_ticker = st.sidebar.text_input("티커 추가", placeholder="예: NVDA, 005930").upper()
if st.sidebar.button("➕ 추가") and new_ticker and new_ticker not in st.session_state.watchlist:
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

# --- 종목 선택 UI (프리셋 업데이트) ---
watchlist_str = ", ".join(st.session_state.watchlist)

if market_choice == '한국 증시 (Korea)':
    presets = {
        "관심종목 (Cloud)": watchlist_str,
        "💾 반도체 (삼성/하이닉스/HBM)": "005930,000660,042700,000020,028300,005290,005980,088800",
        "🔋 2차전지 & 에코프로 형제": "373220,006400,051910,003670,247540,086520,005070,066970",
        "💉 바이오 (비만/신약/CMO)": "207940,068270,000100,128940,196170,326030,214150,000250",
        "🚗 자동차 & 부품": "005380,000270,012330,003550,009900,002980",
        "🛡️ 방산 & 조선 (수출 주도)": "012450,064350,042660,005490,329180,010140,042670",
        "💡 전력설비 & 원전": "267250,024110,000720,086280,034020,052690",
        "💄 화장품 & 푸드 (K-수출)": "271560,192820,243070,097950,003230,280360",
        "🏦 금융지주 & 밸류업": "105560,055550,086790,032830,316140,000810",
        "📱 네카오 & 게임": "035420,035720,251270,036570,005940,293490"
    }
    caption = "💡 종목 코드 입력 (예: 005930, 247540)"
else:
    presets = {
        "관심종목 (Cloud)": watchlist_str,
        "👑 매그니피센트 7 (대장주)": "NVDA,AAPL,MSFT,GOOGL,AMZN,META,TSLA",
        "🤖 AI 반도체 & 하드웨어": "NVDA,AMD,AVGO,TSM,MU,INTC,QCOM,AMAT,LRCX,ARM,SMCI,DELL",
        "💾 AI 소프트웨어 & 보안": "PLTR,SNOW,CRWD,PANW,FTNT,ADBE,CRM,NOW,ORCL,IBM",
        "💊 비만치료제 & 바이오": "LLY,NVO,VRTX,REGN,AMGN,PFE,MRK,JNJ,UNH,ABBV",
        "💰 비트코인 & 핀테크": "MSTR,COIN,HOOD,MARA,JPM,V,MA,BLK,PYPL,SQ",
        "⚡ 전력 & 에너지 (AI데이터센터)": "VST,CEG,NRG,GE,ET,XOM,CVX,NEE",
        "🚗 전기차 & 자율주행": "TSLA,RIVN,LCID,F,GM,UBER,LYFT",
        "🛡️ 우주 & 방산": "LMT,RTX,GD,BA,NOC,AXON,RKLB",
        "🛍️ 소비재 & 배당성장": "COST,WMT,TGT,KO,PEP,MCD,SBUX,NKE,LULU,O,SCHD",
        "📈 3배 레버리지 (야수의 심장)": "TQQQ,SOXL,FNGU,BULZ,NVDL,TSLL,CONL"
    }
    caption = "💡 티커 입력 (예: NVDA, TSLA)"

preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)
st.sidebar.caption(caption)

# --- 리스크 관리 UI ---
st.sidebar.divider()
st.sidebar.subheader("🛡️ 리스크 관리 설정")
stop_loss_mode = st.sidebar.radio("손절가 계산 방식", ("ATR 기반 (권장)", "고정 비율 (%)"), index=0)
if stop_loss_mode == "고정 비율 (%)":
    stop_loss_pct = st.sidebar.slider("손절 비율 (%)", 1.0, 10.0, 3.0, 0.5)
    atr_multiplier = 0
else:
    atr_multiplier = st.sidebar.slider("ATR 배수 (k)", 1.0, 5.0, 2.0, 0.1, help="보통 2.0~3.0을 사용합니다. 수치가 클수록 손절폭이 넓어집니다.")
    stop_loss_pct = 0

# --- 분석 함수 ---
def analyze_dataframe(ticker, df, stop_loss_mode, stop_val, market):
    try:
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        df.dropna(inplace=True)
        if df.empty: return {"티커": ticker, "신호": "데이터 부족"}

        bbl_col = next((col for col in df.columns if col.startswith('BBL')), None)
        sma_col = next((col for col in df.columns if col.startswith('SMA_200')), None)
        atr_col = next((col for col in df.columns if col.startswith('ATRr')), None)
        if not all([bbl_col, sma_col, atr_col]): return {"티커": ticker, "신호": "지표 생성 실패"}

        latest = df.iloc[-1]
        close = latest['close']
        atr_value = latest[atr_col]

        currency_format = "{:,.0f}" if market == '한국 증시 (Korea)' else "{:,.2f}"
        currency_symbol = "₩" if market == '한국 증시 (Korea)' else "$"
        if stop_loss_mode == "ATR 기반 (권장)":
            loss_price = close - (atr_value * stop_val)
            loss_pct_display = round(((close - loss_price) / close) * 100, 2)
            loss_info = f"{currency_symbol}{currency_format.format(loss_price)} (-{loss_pct_display}%)"
        else:
            loss_price = close * (1 - stop_val / 100)
            loss_info = f"{currency_symbol}{currency_format.format(loss_price)} (-{stop_val}%)"

        trend = "상승" if close > latest[sma_col] else "하락"
        signal = "관망"
        if trend == "상승":
            if close <= latest[bbl_col] and latest['RSI_14'] < 35: signal = "🔥 강력 매수"
            elif close <= latest[bbl_col] * 1.03 and latest['RSI_14'] < 45: signal = "✅ 매수 고려"

        return {
            "티커": ticker, "신호": signal, "현재가": close,
            "추세": trend, "RSI": latest['RSI_14'], "손절가": loss_info,
        }
    except Exception as e:
        return {"티커": ticker, "신호": "분석 오류", "오류 원인": str(e)}

# --- 실행 버튼 및 결과 표시 ---
if st.sidebar.button("🚀 AI 퀀트 분석 시작!"):
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = []
    for t in tickers_raw:
        if market_choice == '한국 증시 (Korea)' and '.' not in t:
            tickers.append(f"{t}.KS") # 기본으로 .KS 부여, 루프 내에서 재시도
        else:
            tickers.append(t)

    if not tickers:
        st.warning("분석할 종목이 없습니다.")
    else:
        ok_results, error_results = [], []
        progress_bar = st.progress(0, text="분석 시작...")

        for i, ticker in enumerate(tickers):
            progress_text = f"[{i+1}/{len(tickers)}] {ticker} 분석 중..."
            progress_bar.progress((i + 1) / len(tickers), text=progress_text)
            try:
                df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
                
                # KOSPI(.KS) 조회 실패 시 KOSDAQ(.KQ)으로 재시도
                if df.empty and market_choice == '한국 증시 (Korea)' and ticker.endswith(".KS"):
                    retry_ticker = ticker.replace(".KS", ".KQ")
                    progress_bar.progress((i + 1) / len(tickers), text=f"{ticker} 실패. {retry_ticker}로 재시도...")
                    df = yf.download(retry_ticker, period="1y", progress=False, auto_adjust=True)
                    if not df.empty: ticker = retry_ticker # 성공 시 티커 교체

                if df.empty or len(df) < 200:
                    error_results.append({"티커": ticker, "신호": "데이터 부족"})
                    continue

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0).str.lower()
                else:
                    df.columns = df.columns.str.lower()
                
                target_val = atr_multiplier if stop_loss_mode == "ATR 기반 (권장)" else stop_loss_pct
                analysis_result = analyze_dataframe(ticker, df.copy(), stop_loss_mode, target_val, market_choice)

                if "오류" in analysis_result.get("신호", "") or "실패" in analysis_result.get("신호", ""):
                    error_results.append(analysis_result)
                else:
                    ok_results.append(analysis_result)

            except Exception as e:
                error_results.append({"티커": ticker, "신호": "다운로드 실패", "오류 원인": str(e)})

        progress_bar.empty()

        if ok_results:
            st.subheader("📊 분석 결과")
            res_df = pd.DataFrame(ok_results)
            score_map = {"🔥 강력 매수": 0, "✅ 매수 고려": 1, "관망": 2}
            res_df['score'] = res_df['신호'].map(score_map).fillna(3)
            res_df = res_df.sort_values('score').drop(columns='score').reset_index(drop=True)
            
            price_format = "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}"
            st.dataframe(res_df.style.format(
                {"현재가": price_format, "RSI": "{:.1f}"}
            ), use_container_width=True, hide_index=True)

        if error_results:
            st.subheader("⚠️ 처리 실패/제외 목록")
            st.dataframe(pd.DataFrame(error_results), use_container_width=True, hide_index=True)
