
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json
import re

# --- 페이지 설정 ---
st.set_page_config(page_title="Pro Quant Screener", layout="wide")

st.title("📈 AI 프로 퀀트 스크리너 (v9.1 - UI 복원)")

with st.expander("✨ v9.1 업그레이드 내용"):
    st.markdown('''
    **v9.1은 v9.0의 강력한 분석 엔진을 유지하면서, v8.5의 편리한 UI를 복원했습니다.**

    1.  **📊 피봇(Pivot) 지지/저항:** 전일 데이터를 기반으로 **1차 목표가(저항선)**를 계산합니다.
    2.  **🏆 종합 스코어링:** 추세, 모멘텀 등을 종합하여 **100점 만점**으로 종목의 매력도를 평가합니다.
    3.  **❤️ 상세 프리셋 복원:** v8.5의 상세하고 풍부한 **종목 프리셋**을 다시 가져왔습니다.
    4.  **🛡️ 손절 옵션 복원:** **ATR 기반** 또는 **고정 비율** 손절 방식을 선택할 수 있습니다.
    ''')

# --- 종목명 가져오기 (v8.5 로직 유지) ---
@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    hotfix_map = {"005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "373220.KS": "LG에너지솔루션"}
    if ticker.upper() in hotfix_map: return hotfix_map[ticker.upper()]
    
    if ticker.upper().endswith(('.KS', '.KQ')):
        try:
            code = ticker.split('.')[0]
            url = f"https://ac.finance.naver.com/ac?q={code}&q_enc=euc-kr&t_opts=2"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=2)
            items = response.json().get('items', [])
            if items and items[0]:
                 for item in items[0]:
                    if isinstance(item, list) and len(item) > 1 and item[0] == code:
                        name = item[1]
                        if re.search(r'[\uac00-\ud7a3]', name):
                            return name
        except: pass

    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={ticker}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        response.raise_for_status()
        data = response.json()
        quotes = data.get('quotes', [])
        for quote in quotes:
            if quote.get('symbol') == ticker.upper():
                name = quote.get('longname') or quote.get('shortname')
                if name: return name
    except Exception: pass

    try:
        stock = yf.Ticker(ticker)
        name = stock.info.get('longName') or stock.info.get('shortName')
        if name: return name
    except Exception: pass

    return ticker

# --- JSONBin 설정 (기존 유지) ---
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]
JSONBIN_API_KEY = next((st.secrets.get(key) for key in api_key_names), None)
JSONBIN_BIN_ID = next((st.secrets.get(key) for key in bin_id_names), None)
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
HEADERS = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}

@st.cache_data(ttl=300)
def load_watchlist():
    try: return requests.get(f"{JSONBIN_URL}/latest", headers=HEADERS).json()['record'].get('watchlist', [])
    except: return []

def save_watchlist(data):
    try: 
        requests.put(JSONBIN_URL, headers=HEADERS, json={'watchlist': data})
        st.cache_data.clear()
        return True
    except: return False

if 'watchlist_loaded' not in st.session_state:
    st.session_state.watchlist = load_watchlist()
    st.session_state.watchlist_loaded = True

# --- UI 설정 (v8.5 복원) ---
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)
watchlist_str = ", ".join(st.session_state.watchlist)

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

else:
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "👑 매그니피센트 7 (빅테크)": "NVDA,AAPL,MSFT,GOOGL,AMZN,META,TSLA",
        "🤖 AI 반도체 & 하드웨어": "NVDA,AMD,AVGO,TSM,MU,INTC,QCOM,AMAT,LRCX,ARM,SMCI,DELL,VRT,PSTG",
        "💾 AI 소프트웨어 & 보안": "PLTR,SNOW,CRWD,PANW,FTNT,ADBE,CRM,NOW,ORCL,IBM,MDB,DDOG",
        "💊 비만치료제 & 헬스케어": "LLY,NVO,VRTX,REGN,AMGN,PFE,MRK,JNJ,UNH,ABBV,ISRG,SYK",
        "💰 비트코인 & 핀테크": "MSTR,COIN,HOOD,MARA,CLSK,JPM,V,MA,BLK,PYPL,SQ,AFRM",
        "⚡ 전력 & 에너지 (데이터센터)": "VST,CEG,NRG,GE,ET,XOM,CVX,NEE,SO,DUK",
        "🚗 전기차 & 자율주행": "TSLA,RIVN,LCID,F,GM,UBER,LYFT,ON,MBLY",
        "🛡️ 우주 & 방산": "LMT,RTX,GD,BA,NOC,AXON,RKLB,PL,KTOS",
        "🛍️ 소비재 & 리테일": "COST,WMT,TGT,KO,PEP,MCD,SBUX,NKE,LULU,CMG,HD,LOW",
        "💎 배당성장 & 리츠 (월배당)": "SCHD,O,JEPI,JEPQ,MAIN,VNQ,DGRO,VIG",
        "📈 3배 레버리지 (야수의 심장)": "TQQQ,SQQQ,SOXL,SOXS,FNGU,BULZ,NVDL,TSLL,CONL,MSTX"
    }
    caption = "💡 티커 입력 (예: NVDA, TSLA)"

preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)
st.sidebar.caption(caption)

run_analysis_button = st.sidebar.button("🚀 AI 퀀트 분석 시작!", type="primary")

st.sidebar.divider()
st.sidebar.subheader("🛡️ 리스크 관리 (손절)")
stop_loss_mode = st.sidebar.radio("계산 방식", ("ATR 기반 (권장)", "고정 비율 (%)"), horizontal=True)

if stop_loss_mode == "고정 비율 (%)":
    stop_loss_pct = st.sidebar.slider("손절 비율 (%)", 1.0, 10.0, 3.0, 0.5)
    atr_multiplier = 0
else:
    atr_multiplier = st.sidebar.slider("ATR 배수 (k)", 1.0, 5.0, 2.0, 0.1)
    stop_loss_pct = 0

# --- 🚀 핵심 분석 로직 (v9.0 유지) ---
def analyze_stock(ticker, df, stop_loss_mode, stop_val, market):
    try:
        # 1. 기술적 지표 계산
        df.ta.sma(length=200, append=True)
        df.ta.sma(length=20, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        
        # 2. 피봇 포인트 계산
        high = df['high'].iloc[-2]
        low = df['low'].iloc[-2]
        close_prev = df['close'].iloc[-2]
        pivot = (high + low + close_prev) / 3
        r1 = (2 * pivot) - low
        s1 = (2 * pivot) - high
        
        df.dropna(inplace=True)
        if df.empty: return None

        latest = df.iloc[-1]
        curr_price = latest['close']
        
        sma200 = latest.get('SMA_200', 0)
        sma20 = latest.get('SMA_20', 0)
        rsi = latest.get('RSI_14', 50)
        bbl = latest.get('BBL_20_2.0', 0)
        atr = latest.get('ATRr_14', 0)
        
        # 3. 손절가 계산 (v8.5 방식 적용)
        if stop_loss_mode == "ATR 기반 (권장)":
            stop_price = curr_price - (atr * stop_val)
        else:
            stop_price = curr_price * (1 - stop_val / 100)

        # 4. 종합 스코어링
        score = 0
        reasons = []
        if curr_price > sma200: 
            score += 20
            reasons.append("장기상승")
        if curr_price > sma20: 
            score += 20
            reasons.append("단기상승")
        dist_to_bbl = (curr_price - bbl) / bbl if bbl > 0 else 0
        if dist_to_bbl < 0.02: 
            score += 20
            reasons.append("밴드하단")
        if rsi < 35: 
            score += 10
            reasons.append("과매도")
        vol_avg = df['volume'].rolling(20).mean().iloc[-1]
        if latest['volume'] > vol_avg * 1.5:
            score += 30
            reasons.append("거래폭발")

        # 5. 신호 판정
        signal = "관망"
        if score >= 70: signal = "🔥 강력 매수"
        elif score >= 50: signal = "✅ 매수 고려"
        
        currency = "₩" if market == '한국 증시 (Korea)' else "$"
        fmt = ",.0f" if market == '한국 증시 (Korea)' else ",.2f"
        
        return {
            "티커": ticker,
            "종목명": "",
            "점수": score,
            "신호": signal,
            "현재가": f"{currency}{format(curr_price, fmt)}",
            "손절가": f"{currency}{format(stop_price, fmt)}",
            "1차저항(목표)": f"{currency}{format(r1, fmt)}",
            "핵심요인": ", ".join(reasons) if reasons else "-",
            "RSI": round(rsi, 1)
        }

    except Exception as e:
        return {"티커": ticker, "신호": "오류", "핵심요인": str(e)}

# --- 메인 실행 ---
if run_analysis_button:
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = []
    for t in tickers_raw:
        if market_choice == '한국 증시 (Korea)' and not (t.endswith('.KS') or t.endswith('.KQ')):
             tickers.append(f"{t}.KS")
        else:
             tickers.append(t)
             
    if not tickers:
        st.warning("분석할 종목을 입력해주세요.")
    else:
        results = []
        bar = st.progress(0, "데이터 수집 중...")
        
        for i, ticker in enumerate(tickers):
            name = get_stock_name(ticker)
            bar.progress((i)/len(tickers), f"[{name}] 분석 중...")
            
            try:
                df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
                if df.empty and market_choice == '한국 증시 (Korea)' and ticker.endswith(".KS"):
                    retry_ticker = ticker.replace(".KS", ".KQ")
                    df = yf.download(retry_ticker, period="1y", progress=False, auto_adjust=True)
                    if not df.empty:
                        ticker = retry_ticker
                        name = get_stock_name(ticker)

                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0).str.lower()
                else: df.columns = df.columns.str.lower()

                if len(df) > 100:
                    stop_val = atr_multiplier if stop_loss_mode.startswith("ATR") else stop_loss_pct
                    res = analyze_stock(ticker, df, stop_loss_mode, stop_val, market_choice)
                    if res:
                        res["종목명"] = name
                        results.append(res)
            except: pass
            
        bar.empty()
        
        if results:
            df_res = pd.DataFrame(results)
            df_res = df_res.sort_values(by="점수", ascending=False)
            st.success(f"분석 완료! ({len(results)}개)")
            st.dataframe(
                df_res.style.background_gradient(subset=['점수'], cmap='RdYlGn', vmin=0, vmax=100)
                .format({'RSI': '{:.1f}'}),
                use_container_width=True,
                hide_index=True
            )
            
            with st.expander("📊 결과 해석 가이드"):
                st.markdown("""
                * **점수:** 100점에 가까울수록 매수 매력도가 높습니다.
                * **손절가:** 이 가격 밑으로 떨어지면 기계적으로 매도하여 손실을 제한하세요.
                * **1차저항(목표):** 단기 목표가입니다. 이 가격 도달 시 분할 매도를 고려하세요.
                * **핵심요인:** 점수에 영향을 미친 주요 기술적 요인입니다.
                """)
                
# --- 관심종목 관리 (기존 유지) ---
st.sidebar.divider()
with st.sidebar.expander("❤️ 관심종목 편집"):
    new_t = st.text_input("추가", placeholder="예: AAPL").upper()
    if st.button("➕ 추가"):
        if new_t and new_t not in st.session_state.watchlist:
            new_l = st.session_state.watchlist + [new_t]
            if save_watchlist(new_l): 
                st.session_state.watchlist = new_l
                st.rerun()
    for t in st.session_state.watchlist:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(f"- {t}")
        if c2.button("X", key=f"d_{t}"):
            new_l = [x for x in st.session_state.watchlist if x != t]
            if save_watchlist(new_l): 
                st.session_state.watchlist = new_l
                st.rerun()
