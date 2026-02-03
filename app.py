import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Chart Screener", layout="wide")

st.title("📈 AI 퀀트 종목 발굴기 (Pro Ver.)")
st.markdown("""
**알고리즘 로직:**
1. **추세 필터:** 200일 이동평균선 위에 있는 종목만 '상승 추세'로 인정
2. **거래량 필터:** 평균 거래량 대비 현재 거래량 급증 여부 확인
3. **진입 타이밍:** 볼린저 밴드 하단 터치 + RSI 과매도 (30 이하)
4. **리스크 관리:** 진입가 대비 -3% 자동 손절가 산출
""")

# --- 사이드바: 설정 ---
st.sidebar.header("설정 (Settings)")
tickers_input = st.sidebar.text_area(
    "분석할 티커 입력 (콤마로 구분)", 
    "NVDA, TSLA, AAPL, MSFT, AMZN, GOOGL, AMD, PLTR, SOXL, TQQQ"
)
stop_loss_pct = st.sidebar.slider("손절가 비율 설정 (%)", 1, 10, 3)

# --- 분석 함수 ---
def analyze_stock(ticker):
    try:
        # 데이터 다운로드 (최근 1년치 - 200일선 계산 위해 충분히)
        df = yf.download(ticker, period="1y", progress=False)
        if len(df) < 200:
            return None # 데이터 부족

        # 1. 기술적 지표 계산
        # 이동평균선
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        
        # 볼린저 밴드
        bb = ta.bbands(df['Close'], length=20, std=2)
        df = pd.concat([df, bb], axis=1) # 데이터프레임 병합

        # RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)

        # 거래량 이동평균 (20일)
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()

        # --- 최신 데이터 추출 ---
        latest = df.iloc[-1]
        close = latest['Close']
        ma200 = latest['MA200']
        rsi = latest['RSI']
        vol = latest['Volume']
        vol_avg = latest['Vol_MA20']
        bb_lower = latest['BBL_20_2.0']
        bb_upper = latest['BBU_20_2.0']

        # 2. 필터링 로직 (Upgrade)
        
        # A. 추세 판단 (Trend Filter)
        trend = "상승세 (Bull)" if close > ma200 else "하락세 (Bear)"
        trend_score = 1 if close > ma200 else 0

        # B. 거래량 판단 (Volume Filter)
        vol_ratio = (vol / vol_avg) * 100 # 평소 대비 거래량 %
        vol_status = "거래량 폭발" if vol_ratio > 150 else "보통"

        # C. 매매 신호 (Signal)
        signal = "관망"
        color = "gray"
        
        # 매수 조건: 상승 추세이고 + 밴드 하단 근처 + RSI 낮음
        if close > ma200: # 장기 상승 추세일 때만 매수 고려 (안전)
            if close <= bb_lower * 1.02 and rsi < 45:
                signal = "🔥 강력 매수 (눌림목)"
                color = "red"
            elif close <= bb_lower * 1.05 and vol_ratio > 120:
                signal = "✅ 매수 고려 (수급 동반)"
                color = "orange"
        
        # 매도 조건: 밴드 상단 근처 + RSI 과열
        if close >= bb_upper * 0.98 and rsi > 70:
            signal = "🔻 이익 실현 (과열)"
            color = "blue"

        # D. 손절가 계산 (Stop Loss)
        stop_price = close * (1 - (stop_loss_pct / 100))

        return {
            "티커": ticker,
            "현재가": round(close, 2),
            "신호": signal,
            "추세(200일)": trend,
            "RSI": round(rsi, 1),
            "거래량 강도": f"{int(vol_ratio)}%",
            "손절가 (Stop)": round(stop_price, 2),
            "color": color # UI 표시용
        }

    except Exception as e:
        return None

# --- 실행 버튼 ---
if st.button("🔍 종목 분석 시작 (Analyze)"):
    ticker_list = [t.strip() for t in tickers_input.split(',')]
    
    results = []
    progress_bar = st.progress(0)
    
    for i, ticker in enumerate(ticker_list):
        data = analyze_stock(ticker)
        if data:
            results.append(data)
        progress_bar.progress((i + 1) / len(ticker_list))
    
    # 결과 출력
    if results:
        res_df = pd.DataFrame(results)
        
        # 스타일링 함수 (조건부 서식)
        def color_signal(val):
            color = 'black'
            if "강력 매수" in val: color = 'red'
            elif "매수 고려" in val: color = 'orange'
            elif "이익 실현" in val: color = 'blue'
            return f'color: {color}; font-weight: bold'

        st.subheader("📊 분석 결과")
        st.dataframe(
            res_df.style.map(color_signal, subset=['신호'])
            .format({"현재가": "${:.2f}", "손절가 (Stop)": "${:.2f}"}),
            use_container_width=True,
            height=500
        )
    else:
        st.warning("유효한 데이터가 없습니다. 티커를 확인해주세요.")