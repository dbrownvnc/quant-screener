
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener", layout="wide")

# v8.0: 한글 종목명 조회 기능 추가
st.title("📈 AI 퀀트 종목 발굴기")

with st.expander("✨ 앱 소개 및 사용법 (v8.0)"):
    st.markdown('''
    **AI 퀀트 종목 발굴기는 다음 로직에 따라 매수 타이밍에 근접한 종목을 찾아냅니다.**

    **알고리즘 로직:**
    1.  **추세 필터:** 200일 이동평균선 위에 있는 \'상승 추세\' 종목을 대상으로 분석
    2.  **타이밍 포착:** 볼린저 밴드 하단 및 RSI 과매도 시그널을 종합하여 신호 생성
    3.  **리스크 관리:** ATR(변동성) 기반으로 종목별 동적 손절 라인 자동 계산
    ---
    **v8.0 변경점:**
    1.  **🇰🇷 한글 종목명 지원:** 한국 주식 분석 시, 영문명 대신 네이버 금융의 한글 종목명을 표시하여 가독성을 높였습니다.
    2.  **UI/UX 유지:** 이전 버전의 모든 UI(컬럼명, 폰트 스타일 등)는 그대로 유지됩니다.
    ''')

# --- 종목명 가져오기 (v8.0 한글 종목명 지원) ---
@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    # 1. 한국 주식인 경우, 네이버 금융에서 한글 종목명 우선 조회
    if ticker.upper().endswith(('.KS', '.KQ')):
        try:
            code = ticker.split('.')[0]
            url = f"https://m.stock.naver.com/domestic/stock/{code}/total"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # <title> 태그에서 종목명 추출 (예: <title>삼성전자 : 네이버 증권</title>)
            title_start = response.text.find('<title>') + len('<title>')
            title_end = response.text.find(' : 네이버 증권</title>')
            
            if title_start != -1 and title_end != -1:
                name = response.text[title_start:title_end].strip()
                if name: return name
        except Exception:
            pass # 한글 종목명 조회 실패 시 아래 yfinance 로직으로 넘어감

    # 2. (미국 주식 or 한글명 조회 실패 시) yfinance로 종목명 조회
    try:
        stock = yf.Ticker(ticker)
        name = stock.fast_info.get('shortName')
        if name and name != ticker: return name
        info = stock.info
        name = info.get('shortName') or info.get('longName')
        if name and name != ticker: return name
        return ticker
    except Exception:
        return ticker

# --- jsonbin.io 및 Secrets 설정 ---
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]
JSONBIN_API_KEY = next((st.secrets.get(key) for key in api_key_names), None)
JSONBIN_BIN_ID = next((st.secrets.get(key) for key in bin_id_names), None)

if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
    st.error("⚠️ [설정 오류] `JSONBIN_API_KEY` 또는 `JSONBIN_BIN_ID`를 찾을 수 없습니다.")
    st.code('''# Streamlit Cloud의 Secrets에 아래와 같이 키를 추가하세요.\nJSONBIN_API_KEY="YOUR_KEY"\nJSONBIN_BIN_ID="YOUR_ID"''', language='toml')
    st.stop()

JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
HEADERS = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}

# --- 데이터 로드/저장 함수 ---
@st.cache_data(ttl=300)
def load_watchlist_from_jsonbin():
    try:
        response = requests.get(f"{JSONBIN_URL}/latest", headers=HEADERS)
        response.raise_for_status()
        return response.json().get('record', {}).get('watchlist', [])
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return []

def save_watchlist_to_jsonbin(watchlist_data):
    try:
        requests.put(JSONBIN_URL, headers=HEADERS, json={'watchlist': watchlist_data}).raise_for_status()
        st.cache_data.clear()
        return True
    except requests.exceptions.RequestException:
        return False

# --- 세션 상태 초기화 ---
if 'watchlist_loaded' not in st.session_state:
    st.session_state.watchlist = load_watchlist_from_jsonbin()
    st.session_state.watchlist_loaded = True

# --- 사이드바 UI (v7.6 구조) ---
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)

watchlist_str = ", ".join(st.session_state.watchlist)
# ... (프리셋 내용은 이전과 동일하게 유지) ...
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

run_analysis_button = st.sidebar.button("🚀 AI 퀀트 분석 시작!", type="primary")

st.sidebar.divider()
st.sidebar.subheader("🛡️ 리스크 관리 설정")
stop_loss_mode = st.sidebar.radio("손절가 계산 방식", ("ATR 기반 (권장)", "고정 비율 (%)"), index=0)
if stop_loss_mode == "고정 비율 (%)":
    stop_loss_pct = st.sidebar.slider("손절 비율 (%)", 1.0, 10.0, 3.0, 0.5)
    atr_multiplier = 0
else:
    atr_multiplier = st.sidebar.slider("ATR 배수 (k)", 1.0, 5.0, 2.0, 0.1, help="수치가 클수록 손절폭이 넓어집니다.")
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
        bbl_col = next((c for c in df.columns if c.startswith('BBL')), None)
        sma_col = next((c for c in df.columns if c.startswith('SMA_200')), None)
        atr_col = next((c for c in df.columns if c.startswith('ATRr')), None)
        if not all([bbl_col, sma_col, atr_col]): return {"티커": ticker, "신호": "지표 생성 실패"}
        latest = df.iloc[-1]
        close, atr_value = latest['close'], latest[atr_col]
        currency = "₩" if market == '한국 증시 (Korea)' else "$"
        fmt = ",.0f" if market == '한국 증시 (Korea)' else ",.2f"
        if stop_loss_mode == "ATR 기반 (권장)":
            loss_price = close - (atr_value * stop_val)
            loss_pct = round(((close - loss_price) / close) * 100, 2)
            loss_info = f"{currency}{format(loss_price, fmt)} (-{loss_pct}%)"
        else:
            loss_price = close * (1 - stop_val / 100)
            loss_info = f"{currency}{format(loss_price, fmt)} (-{stop_val}%)"
        vol_signal = "N/A"
        if 'volume' in df.columns and df['volume'].rolling(20).mean().iloc[-1] > 0:
            vol_avg = df['volume'].rolling(20).mean().iloc[-1]
            vol_signal = "급증" if latest['volume'] > vol_avg * 1.5 else "보통"
        trend = "상승" if close > latest[sma_col] else "하락"
        signal = "관망"
        if trend == "상승":
            if close <= latest[bbl_col] and latest['RSI_14'] < 35: signal = "🔥 강력 매수"
            elif close <= latest[bbl_col] * 1.03 and latest['RSI_14'] < 45: signal = "✅ 매수 고려"
        return {"티커": ticker, "신호": signal, "현재가": close, "추세": trend, "RSI": latest['RSI_14'], "거래량": vol_signal, "손절가": loss_info}
    except Exception as e:
        return {"티커": ticker, "신호": "분석 오류", "오류 원인": str(e)}

# --- 실행 로직 ---
if run_analysis_button:
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = [f"{t}.KS" if market_choice == '한국 증시 (Korea)' and '.' not in t else t for t in tickers_raw]
    if not tickers:
        st.warning("분석할 종목이 없습니다.")
    else:
        ok_results, error_results = [], []
        progress_bar = st.progress(0, text="분석 시작...")
        for i, ticker in enumerate(tickers):
            stock_name = get_stock_name(ticker)
            progress_bar.progress((i + 1) / len(tickers), f"[{i+1}/{len(tickers)}] {stock_name} ({ticker}) 분석 중...")
            try:
                df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
                if df.empty and market_choice == '한국 증시 (Korea)' and ticker.endswith(".KS"):
                    retry_ticker = ticker.replace(".KS", ".KQ")
                    df = yf.download(retry_ticker, period="1y", progress=False, auto_adjust=True)
                    if not df.empty:
                        ticker, stock_name = retry_ticker, get_stock_name(retry_ticker)
                if df.empty or len(df) < 200:
                    error_results.append({"티커": ticker, "종목명": stock_name, "신호": "데이터 부족"})
                    continue
                df.columns = df.columns.get_level_values(0).str.lower() if isinstance(df.columns, pd.MultiIndex) else df.columns.str.lower()
                target_val = atr_multiplier if stop_loss_mode == "ATR 기반 (권장)" else stop_loss_pct
                res = analyze_dataframe(ticker, df.copy(), stop_loss_mode, target_val, market_choice)
                res["종목명"] = stock_name
                (ok_results if "오류" not in res.get("신호", "") else error_results).append(res)
            except Exception as e:
                error_results.append({"티커": ticker, "종목명": stock_name, "신호": "다운로드 실패", "오류 원인": str(e)})
        progress_bar.empty()
        
        if ok_results:
            st.subheader("📊 분석 결과")
            res_df = pd.DataFrame(ok_results)
            
            # 1. 신호별 정렬 (강력 매수 우선)
            res_df = res_df.sort_values(by='신호', key=lambda s: s.map({"🔥 강력 매수": 0, "✅ 매수 고려": 1, "관망": 2}).fillna(3))
            
            # 2. 표시할 컬럼 정의
            display_cols = ['티커', '종목명', '신호', '현재가', '손절가', '추세', 'RSI', '거래량']
            cols_to_show = [col for col in display_cols if col in res_df.columns]
            
            # 3. 📱 모바일 최적화 (폰트 사이즈 축소)
            formats = {
                "현재가": "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}", 
                "RSI": "{:.1f}"
            }
            
            styler = res_df[cols_to_show].style.format(formats)
            styler.set_properties(**{'font-size': '12px', 'text-align': 'center'})
            styler.set_table_styles([{'selector': 'th', 'props': [('font-size', '12px')]}])

            # 4. 결과 출력
            st.dataframe(styler, use_container_width=True, hide_index=True)

        if error_results:
            st.subheader("⚠️ 처리 실패/제외 목록")
            err_df = pd.DataFrame(error_results)
            error_display_cols = ['티커', '종목명', '신호', '오류 원인']
            err_cols_to_show = [col for col in error_display_cols if col in err_df.columns]
            
            err_styler = err_df[err_cols_to_show].style.set_properties(**{'font-size': '12px'})
            st.dataframe(err_styler, use_container_width=True, hide_index=True)


# --- 사이드바 하단: 관심종목 관리 ---
st.sidebar.divider()
st.sidebar.subheader("❤️ 관심종목 관리 (Cloud)")
with st.sidebar.expander("관심종목 목록 보기/편집"):
    new_ticker = st.text_input("티커 추가", placeholder="예: NVDA, 005930").upper()
    if st.button("➕ 추가"):
        if new_ticker and new_ticker not in st.session_state.watchlist:
            new_list = st.session_state.watchlist + [new_ticker]
            if save_watchlist_to_jsonbin(new_list):
                st.session_state.watchlist = new_list
                st.rerun()

    for ticker_to_remove in st.session_state.watchlist[:]:
        col1, col2 = st.columns([0.8, 0.2])
        col1.markdown(f"- {ticker_to_remove}")
        if col2.button("🗑️", key=f"del_{ticker_to_remove}", help=f"{ticker_to_remove} 삭제"):
            new_list = [t for t in st.session_state.watchlist if t != ticker_to_remove]
            if save_watchlist_to_jsonbin(new_list):
                st.session_state.watchlist = new_list
                st.rerun()
