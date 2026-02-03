
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener", layout="wide")

st.title("📈 AI 퀀트 종목 발굴기 (Pro Ver.)")
st.markdown("""
**알고리즘 로직:**
1. **추세 필터:** 200일 이동평균선 위에 있는 종목만 '상승 추세'로 인정
2. **거래량 필터:** 20일 평균 거래량 대비 현재 거래량 급증 여부 확인
3. **진입 타이밍:** 볼린저 밴드 하단 터치 + RSI 과매도 구간 진입
4. **리스크 관리:** 진입가 대비 설정된 % 자동 손절가 산출
""")

# --- 사이드바: 설정 ---
st.sidebar.header("⚙️ 설정 (Settings)")

# --- 시장 선택 ---
market_choice = st.sidebar.radio(
    "시장 선택 (Market)",
    ('미국 증시 (US)', '한국 증시 (Korea)'),
    horizontal=True
)

# --- 종목 선택 ---
if market_choice == '한국 증시 (Korea)':
    presets = {
        "주요 기술주": "005930, 000660, 035420, 035720",
        "주요 자동차주": "005380, 000270",
        "주요 배터리주": "373220, 006400, 051910"
    }
    caption = "💡 종목 코드만 입력하세요 (자동으로 .KS 추가)"
    preset_tickers = presets[st.sidebar.selectbox("종목 프리셋 선택", options=list(presets.keys()))]
else: # 미국 증시
    presets = {
        "주요 기술주": "NVDA, AAPL, MSFT, GOOGL, AMD",
        "주요 성장주": "TSLA, PLTR, SOXL, MSTR",
        "주요 ETF": "SPY, QQQ, DIA"
    }
    caption = "💡 티커를 입력하세요 (예: NVDA, TSLA)"
    preset_tickers = presets[st.sidebar.selectbox("종목 프리셋 선택", options=list(presets.keys()))]


tickers_input = st.sidebar.text_area(
    "분석할 티커 (직접 수정 가능)",
    preset_tickers
)
st.sidebar.caption(caption)
stop_loss_pct = st.sidebar.slider("손절가 비율 설정 (%)", 1, 10, 3)

# --- 분석 함수 (오류 처리 강화) ---
@st.cache_data
def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        
        if df.empty:
            return {"티커": ticker, "신호": "오류", "현재가": 0, "추세(200일)": "데이터 없음", "RSI": 0, "거래량": "실패", "손절가": 0}
        if len(df) < 200:
            return {"티커": ticker, "신호": "오류", "현재가": df.iloc[-1]['Close'], "추세(200일)": "데이터 부족 (200일 미만)", "RSI": 0, "거래량": "실패", "손절가": 0}

        df['MA200'] = ta.sma(df['Close'], length=200)
        bbands = ta.bbands(df['Close'], length=20, std=2)
        df = pd.concat([df, bbands], axis=1)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['Vol_MA20'] = ta.sma(df['Volume'], length=20)

        latest = df.iloc[-1]
        close, ma200, rsi, vol, vol_avg, bb_lower, bb_upper = latest[['Close', 'MA200', 'RSI', 'Volume', 'Vol_MA20', 'BBL_20_2.0', 'BBU_20_2.0']]

        trend = "상승 추세" if close > ma200 else "하락 추세"
        vol_ratio = (vol / vol_avg) if vol_avg > 0 else 0
        volume_signal = "거래량 급증" if vol_ratio > 1.5 else "거래량 보통"

        signal = "관망"
        if close > ma200:
            if close <= bb_lower and rsi < 35:
                signal = "🔥 강력 매수"
            elif close <= bb_lower * 1.03 and rsi < 45:
                signal = "✅ 매수 고려"
        if close >= bb_upper * 0.98 and rsi > 65:
            signal = "🔻 이익 실현"

        stop_price = close * (1 - (stop_loss_pct / 100))

        return {
            "티커": ticker, "신호": signal, "현재가": close,
            "추세(200일)": trend, "RSI": rsi, "거래량": volume_signal, "손절가": stop_price,
        }
    except Exception as e:
        return {"티커": ticker, "신호": "오류", "현재가": 0, "추세(200일)": f"분석 실패: {e}", "RSI": 0, "거래량": "실패", "손절가": 0}

# --- 실행 버튼 ---
if st.sidebar.button("🚀 AI 퀀트 분석 시작!"):
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = [f"{t}.KS" for t in tickers_raw] if market_choice == '한국 증시 (Korea)' else tickers_raw

    if not tickers:
        st.warning("분석할 종목이 없습니다. 티커를 입력해주세요.")
    else:
        results = []
        progress_bar = st.progress(0, text="분석 시작...")
        
        for i, ticker in enumerate(tickers):
            results.append(analyze_stock(ticker))
            progress_bar.progress((i + 1) / len(tickers), text=f"{ticker} 분석 중...")
        
        res_df = pd.DataFrame(results)
        if res_df.empty or all(res_df['신호'] == '오류'):
            st.warning("분석 결과가 없습니다. 티커를 확인하거나 다른 종목을 시도해보세요.")
            st.dataframe(res_df, use_container_width=True, hide_index=True)
        else:
            res_df['signal_score'] = res_df['신호'].map({"🔥 강력 매수": 0, "✅ 매수 고려": 1, "관망": 2, "🔻 이익 실현": 3, "오류": 4})
            res_df = res_df.sort_values(by="signal_score").drop(columns=['signal_score'])
            
            def color_signal(val):
                color = 'grey'
                if "강력 매수" in val: color = 'red'
                elif "매수 고려" in val: color = 'orange'
                elif "이익 실현" in val: color = 'blue'
                elif val == "관망": color = 'black'
                return f'color: {color}; font-weight: bold'

            st.subheader("📊 분석 결과")
            currency_format = "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}"
            st.dataframe(
                res_df.style.map(color_signal, subset=['신호'])
                .format({"현재가": currency_format, "손절가": currency_format, "RSI": "{:.1f}"}, na_rep="-"),
                use_container_width=True,
                hide_index=True,
            )
