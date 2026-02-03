import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json
import re

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener v9.0", layout="wide")

st.title("📈 AI 퀀트 종목 발굴기 (v9.0 - 지지/저항 기반)")

with st.expander("✨ 앱 소개 및 v9.0 변경점"):
    st.markdown('''
    **AI 퀀트 종목 발굴기는 기술적 분석 지표를 종합하여 매수 타이밍에 근접한 종목을 찾아냅니다.**

    **v9.0 핵심 로직:**
    1.  **추세 필터:** 200일 이동평균선을 기반으로 '상승 추세'에 있는 종목을 선별합니다.
    2.  **타이밍 포착 (신호 강화):**
        *   단순 과매도 지표(RSI, 볼린저밴드)를 넘어, **피봇 지지선(S1)** 및 **최근 전저점(Swing Low)**을 함께 분석합니다.
        *   여러 지지 조건이 중첩되는 구간에서 신호를 발생시켜 신뢰도를 높였습니다. (예: `🔥 강력 매수 (볼린저 하단, 피봇 지지)`)
    3.  **거래량 분석:** 거래량 급증 시, 상승 에너지를 동반하는 **양봉 거래량**인지 하락 신호인 **음봉 거래량**인지를 구분합니다.
    4.  **리스크 관리 (손절가 개선):** 기존의 ATR, 고정비율 방식에 더해, 핵심 지지선인 **"피봇 1차 지지선(S1) 이탈 시"**를 손절 기준으로 추가했습니다.
    ''')

# --- 핵심 분석 함수 (v9.0) ---

@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    hotfix_map = {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스",
        "373220.KS": "LG에너지솔루션", "373220.KQ": "LG에너지솔루션"
    }
    if ticker.upper() in hotfix_map:
        return hotfix_map[ticker.upper()]
    try:
        if ".KS" in ticker or ".KQ" in ticker:
            code = ticker.split(".")[0]
            url = f"https://ac.finance.naver.com/ac?q={code}&q_enc=euc-kr&t_opts=2"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
            items = response.json().get('items', [])
            if items and items[0]:
                for item in items[0]:
                    if isinstance(item, list) and len(item) > 1 and item[0] == code:
                        return item[1]
    except Exception: pass
    try:
        stock = yf.Ticker(ticker)
        name = stock.info.get('longName') or stock.info.get('shortName')
        if name: return name
    except Exception: pass
    return ticker

def get_pivot_points(df):
    if len(df) < 2: return 0, 0
    last = df.iloc[-2] # 전일 데이터 기준
    high, low, close = last['high'], last['low'], last['close']
    pivot = (high + low + close) / 3
    s1 = (2 * pivot) - high
    r1 = (2 * pivot) - low
    return s1, r1

# --- jsonbin.io 및 Secrets 설정 ---
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]
JSONBIN_API_KEY = next((st.secrets.get(key) for key in api_key_names), None)
JSONBIN_BIN_ID = next((st.secrets.get(key) for key in bin_id_names), None)

if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
    st.error("⚠️ [설정 오류] Secrets 설정을 확인해주세요.")
    st.stop()

JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
HEADERS = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}

@st.cache_data(ttl=300)
def load_watchlist_from_jsonbin():
    try:
        response = requests.get(f"{JSONBIN_URL}/latest", headers=HEADERS)
        response.raise_for_status()
        return response.json().get('record', {}).get('watchlist', [])
    except Exception: return []

def save_watchlist_to_jsonbin(watchlist_data):
    try:
        requests.put(JSONBIN_URL, headers=HEADERS, json={'watchlist': watchlist_data}).raise_for_status()
        st.cache_data.clear()
        return True
    except Exception: return False

# --- 세션 초기화 ---
if 'watchlist_loaded' not in st.session_state:
    st.session_state.watchlist = load_watchlist_from_jsonbin()
    st.session_state.watchlist_loaded = True

# --- 사이드바 UI (v9.0) ---
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)
watchlist_str = ", ".join(st.session_state.watchlist)

# 프리셋 (한국)
if market_choice == '한국 증시 (Korea)':
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "💾 반도체 (삼성/HBM/소부장)": "005930,000660,042700,000020,028300.KQ,058470.KQ,403870.KQ,095340.KQ,005290,088800.KQ",
        "🔋 2차전지 (셀/양극재/전해질)": "373220,006400,051910,003670,247540.KQ,086520.KQ,066970.KQ,005070,277810.KQ",
        "⚡ 전력설비 & 원전 (AI수혜)": "267250,024110,010120,000720,086280,034020,052690,005860",
        "💉 바이오 (비만/신약/CMO)": "207940,068270,196170.KQ,000100,326030,214150.KQ,000250,028300.KQ,096530.KQ",
        "🛡️ 방산 & 조선 (수출 주도)": "012450,064350,079550,042660,005490,329180,010140,042670,004270",
        "🚗 자동차 & 부품 (저PBR)": "005380,000270,012330,003550,009900,023160,002980",
        "💄 K-뷰티 & 푸드 (수출)": "271560,192820,243070,097950,003230,280360,090430,278470",
        "🏦 금융지주 & 밸류업": "105560,055550,086790,032830,316140,000810,138040,071050",
        "📱 네카오 & 게임 & 엔터": "035420,035720,251270,036570,005940,293490,006360,352820,122870.KQ"
    }
    caption = "💡 종목 코드 입력 (예: 005930, 247540.KQ)"
else: # 프리셋 (미국)
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "👑 매그니피센트 7": "NVDA,AAPL,MSFT,GOOGL,AMZN,META,TSLA",
        "🤖 AI & 반도체": "NVDA,AMD,AVGO,TSM,MU,INTC,QCOM,AMAT,LRCX,ARM,SMCI,DELL",
        "💾 S/W & 보안": "PLTR,SNOW,CRWD,PANW,FTNT,ADBE,CRM,NOW,ORCL,MDB,DDOG",
        "💊 헬스케어 (비만)": "LLY,NVO,VRTX,REGN,AMGN,PFE,MRK,JNJ,UNH,ABBV",
        "💰 핀테크 (비트코인)": "MSTR,COIN,HOOD,MARA,CLSK,JPM,V,MA,PYPL,SQ,AFRM",
        "⚡ 에너지 (전력)": "VST,CEG,NRG,GE,ET,XOM,CVX,NEE,SO,DUK",
        "🚗 자동차": "TSLA,RIVN,LCID,F,GM,UBER,LYFT,ON,MBLY",
        "🛡️ 방산 & 우주": "LMT,RTX,GD,BA,NOC,AXON,RKLB,PL,KTOS",
        "📈 3배 레버리지": "TQQQ,SQQQ,SOXL,SOXS,FNGU,BULZ,NVDL,TSLL,CONL"
    }
    caption = "💡 티커 입력 (예: NVDA, TSLA)"

preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)
st.sidebar.caption(caption)
run_analysis_button = st.sidebar.button("🚀 AI 퀀트 분석 시작!", type="primary")

st.sidebar.divider()
st.sidebar.subheader("🛡️ 리스크 관리 (손절)")
stop_loss_mode = st.sidebar.radio("계산 방식", ("ATR 기반 (권장)", "피봇 지지선 (S1) 기준", "고정 비율 (%)"), horizontal=True, index=0)

atr_multiplier, stop_loss_pct = 0, 0
if stop_loss_mode == "ATR 기반 (권장)":
    atr_multiplier = st.sidebar.slider("ATR 배수 (k)", 1.0, 5.0, 2.0, 0.1)
elif stop_loss_mode == "고정 비율 (%)":
    stop_loss_pct = st.sidebar.slider("손절 비율 (%)", 1.0, 10.0, 3.0, 0.5)

# --- 분석 로직 (v9.0) ---
def analyze_dataframe(ticker, df, stop_loss_mode, market, **kwargs):
    try:
        # 1. 지표 계산
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        df.dropna(inplace=True)
        if df.empty: return {"티커": ticker, "신호": "데이터 부족"}

        cols = df.columns
        bbl_col = next((c for c in cols if 'BBL' in str(c)), None)
        sma_col = next((c for c in cols if 'SMA_200' in str(c)), None)
        atr_col = next((c for c in cols if 'ATRr' in str(c)), None)
        if not all([bbl_col, sma_col, atr_col]): return {"티커": ticker, "신호": "지표 생성 실패"}

        latest = df.iloc[-1]
        close = latest['close']
        currency = "₩" if market == '한국 증시 (Korea)' else "$"

        # 2. 지지/저항 레벨 산출
        s1, r1 = get_pivot_points(df)
        swing_low_20d = df['low'].tail(20).min()

        # 3. 신호 로직 강화
        score, reasons = 0, []
        if close <= latest[bbl_col] * 1.01:
            score += 1; reasons.append("볼린저 하단")
        if s1 > 0 and close <= s1 * 1.02:
            score += 1; reasons.append("피봇 지지")
        if close <= swing_low_20d * 1.03:
            score += 1; reasons.append("전저점 근접")
        
        rsi = latest['RSI_14']
        if rsi < 35: score += 1
        
        trend = "상승" if close > latest[sma_col] else "하락"
        signal = "관망"
        if trend == "상승":
            if score >= 2:
                signal = f"🔥 강력 매수 ({', '.join(reasons)})" if reasons else "🔥 강력 매수"
            elif score == 1 and rsi < 45:
                signal = f"✅ 매수 고려 ({reasons[0]})" if reasons else "✅ 매수 고려"

        # 4. 거래량 필터 강화
        vol_signal = "보통"
        if 'volume' in df.columns and len(df) > 20:
            vol_avg_20 = df['volume'].rolling(20).mean().iloc[-1]
            if vol_avg_20 > 0 and latest['volume'] > vol_avg_20 * 1.5:
                vol_signal = "⬆️ 양봉 급증" if close > latest['open'] else "⬇️ 음봉 급증"

        # 5. 손절가 계산 방식 변경
        loss_info = "N/A"
        if stop_loss_mode == "ATR 기반 (권장)":
            loss_price = close - (latest[atr_col] * kwargs.get('atr_multiplier', 2.0))
            loss_info = f"{currency}{loss_price:,.0f} (-{round(((close - loss_price) / close) * 100, 1)}%)"
        elif stop_loss_mode == "피봇 지지선 (S1) 기준":
            if s1 > 0: loss_info = f"{currency}{s1:,.0f} (피봇 S1)"
            else: loss_info = "계산 불가"
        else: # 고정 비율
            loss_price = close * (1 - kwargs.get('stop_loss_pct', 3.0) / 100)
            loss_info = f"{currency}{loss_price:,.0f} (-{kwargs.get('stop_loss_pct', 3.0)}%)"

        return {
            "티커": ticker, "신호": signal, "현재가": close, "손절가": loss_info,
            "지지(S1)": s1, "저항(R1)": r1, "RSI": rsi, "추세": trend, "거래량": vol_signal
        }
    except Exception as e:
        return {"티커": ticker, "신호": "분석 오류", "오류 원인": str(e)}


# --- 실행 로직 ---
if run_analysis_button:
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = []
    for t in tickers_raw:
        if market_choice == '한국 증시 (Korea)' and not (t.endswith('.KS') or t.endswith('.KQ')):
             tickers.append(f"{t}.KS")
        else:
             tickers.append(t)

    if not tickers:
        st.warning("분석할 종목이 없습니다.")
    else:
        ok_results, error_results = [], []
        bar = st.progress(0, "분석 준비 중...")
        
        for i, ticker in enumerate(tickers):
            stock_name = get_stock_name(ticker)
            bar.progress((i)/len(tickers), f"[{stock_name}] 데이터 분석 중...")
            try:
                df = yf.download(ticker, period="1y", progress=False)
                if df.empty and ".KS" in ticker: # 코스닥 재시도
                    retry_ticker = ticker.replace(".KS", ".KQ")
                    df_kq = yf.download(retry_ticker, period="1y", progress=False)
                    if not df_kq.empty:
                        df, ticker, stock_name = df_kq, retry_ticker, get_stock_name(retry_ticker)
                
                df.columns = df.columns.str.lower()
                if df.empty or len(df) < 100:
                    error_results.append({"티커": ticker, "종목명": stock_name, "신호": "데이터 부족"})
                    continue

                res = analyze_dataframe(ticker, df, stop_loss_mode, market_choice, atr_multiplier=atr_multiplier, stop_loss_pct=stop_loss_pct)
                res["종목명"] = stock_name
                if "오류" in res.get("신호", ""): error_results.append(res)
                else: ok_results.append(res)
                    
            except Exception as e:
                error_results.append({"티커": ticker, "종목명": stock_name, "신호": "실패", "오류 원인": str(e)})
        bar.empty()

        # --- 결과 출력 (v9.0) ---
        if ok_results:
            st.success(f"✅ 분석 완료! ({len(ok_results)}개 종목)")
            res_df = pd.DataFrame(ok_results)
            
            # 신호 레벨에 따라 정렬
            signal_order = {'🔥': 0, '✅': 1, '관': 2}
            res_df['sort_key'] = res_df['신호'].apply(lambda x: signal_order.get(x[0], 99))
            res_df = res_df.sort_values(by='sort_key')
            
            # 출력 컬럼 정의
            currency_format = "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}"
            cols = ["티커", "종목명", "신호", "현재가", "손절가", "지지(S1)", "저항(R1)", "RSI", "거래량", "추세"]
            final_df = res_df[[c for c in cols if c in res_df.columns]]
            
            styler = final_df.style.format({
                "현재가": currency_format, "지지(S1)": currency_format, "저항(R1)": currency_format, "RSI": "{:.1f}"
            })
            styler.set_properties(**{'font-size': '13px', 'text-align': 'center'})
            styler.set_table_styles([{'selector': 'th', 'props': [('font-size', '13px'), ('text-align', 'center')]}])
            
            st.dataframe(styler, use_container_width=True, hide_index=True)

        if error_results:
            st.warning("⚠️ 분석 실패/제외 목록")
            st.dataframe(pd.DataFrame(error_results), hide_index=True)

# --- 관심종목 관리 ---
st.sidebar.divider()
st.sidebar.subheader("❤️ 관심종목 관리")
with st.sidebar.expander("목록 편집"):
    new_t = st.text_input("추가", placeholder="예: 005930").upper()
    if st.button("➕ 저장"):
        if new_t and new_t not in st.session_state.watchlist:
            new_l = st.session_state.watchlist + [new_t]
            if save_watchlist_to_jsonbin(new_l):
                st.session_state.watchlist = new_l; st.rerun()
    
    for t in st.session_state.watchlist:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(f"- {t}")
        if c2.button("X", key=f"d_{t}"):
            new_l = [x for x in st.session_state.watchlist if x != t]
            if save_watchlist_to_jsonbin(new_l):
                st.session_state.watchlist = new_l; st.rerun()
