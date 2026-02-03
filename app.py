
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener", layout="wide")

# v3.10로 버전 업데이트
st.title("📈 AI 퀀트 종목 발굴기 (v3.10 - 버그 수정)")
st.markdown(""" 
**알고리즘 로직:**
1. **추세 필터:** 200일 이동평균선 위에 있는 '상승 추세' 종목을 대상으로 분석
2. **거래량 필터:** 20일 평균 거래량 대비 현재 거래량의 급증 여부 확인
3. **타이밍 포착:** 볼린저 밴드 하단 터치 및 RSI 과매도 시그널 확인
4. **리스크 관리:** 설정된 손절 라인 자동 계산
---
**v3.10 변경점:** 디버그 모드에서 발생하는 `SyntaxError` 버그를 수정했습니다.
""")

# --- 사이드바 설정 ---
st.sidebar.header("⚙️ 설정 (Settings)")
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)

# --- 종목 선택 UI ---
if market_choice == '한국 증시 (Korea)':
    presets = {
        "주요 기술주": "005930, 000660, 035420, 035720", "주요 자동차주": "005380, 000270",
        "주요 배터리주": "373220, 006400, 051910",
    }
    caption = "💡 종목 코드 입력 (예: 005930)"
    preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
    tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)
else: # 미국 증시
    presets = {
        "주요 기술주": "NVDA, AAPL, MSFT, GOOGL, AMD", "주요 성장주": "TSLA, PLTR, MSTR",
        "주요 ETF": "SPY, QQQ, TQQQ",
    }
    caption = "💡 티커 입력 (예: NVDA, TSLA)"
    preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
    tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)

st.sidebar.caption(caption)
stop_loss_pct = st.sidebar.slider("손절가 비율 (%)", 1.0, 10.0, 3.0, 0.5)
debug_mode = st.sidebar.checkbox("상세 디버깅 모드")


# --- 분석 함수 ---
def analyze_dataframe(ticker, df, stop_loss_pct):
    try:
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)

        required_indicators = ['SMA_200', 'RSI_14', 'BBL_20_2.0', 'BBU_20_2.0']

        if 'volume' in df.columns:
            df['volume_ma20'] = df['volume'].rolling(window=20).mean()
            required_indicators.append('volume_ma20')

        missing_indicators = [col for col in required_indicators if col not in df.columns]
        if missing_indicators:
            return {"티커": ticker, "신호": "오류", "오류 원인": f"지표 계산 실패: {missing_indicators}"}

        df.dropna(inplace=True)
        if df.empty:
            return {"티커": ticker, "신호": "오류", "오류 원인": "데이터 정제 후 비어있음"}

        latest = df.iloc[-1]
        close, ma200, rsi, bb_lower, bb_upper = latest[['close', 'SMA_200', 'RSI_14', 'BBL_20_2.0', 'BBU_20_2.0']]
        
        volume_signal = "N/A"
        if 'volume' in df.columns and 'volume_ma20' in latest and latest['volume_ma20'] > 0:
            vol = latest['volume']
            vol_avg = latest['volume_ma20']
            volume_signal = "급증" if vol > vol_avg * 1.5 else "보통"
        
        trend = "상승" if close > ma200 else "하락"
        signal = "관망"
        if close > ma200:
            if close <= bb_lower and rsi < 35:
                signal = "🔥 강력 매수"
            elif close <= bb_lower * 1.03 and rsi < 45:
                signal = "✅ 매수 고려"
        if close >= bb_upper and rsi > 65:
            signal = "🔻 이익 실현"

        stop_price = close * (1 - (stop_loss_pct / 100))

        return {
            "티커": ticker, "신호": signal, "현재가": close,
            "추세": trend, "RSI": rsi, "거래량": volume_signal, "손절가": stop_price,
        }
    except KeyError as e:
        return {"티커": ticker, "신호": "오류", "오류 원인": f"분석에 필요한 열({e})을 찾을 수 없습니다."}
    except Exception as e:
        return {"티커": ticker, "신호": "오류", "오류 원인": f"분석 로직 오류: {str(e)}"}

# --- 실행 버튼 및 결과 표시 ---
if st.sidebar.button("🚀 AI 퀀트 분석 시작!"):
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = [f"{t}.KS" for t in tickers_raw] if market_choice == '한국 증시 (Korea)' else tickers_raw

    if not tickers:
        st.warning("분석할 종목이 없습니다. 티커를 입력해주세요.")
    else:
        ok_results, error_results = [], []
        error_dfs = {}
        
        progress_bar = st.progress(0, text="분석 시작...")

        for i, ticker in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers), text=f"[{ticker}] 데이터 다운로드 중...")
            
            original_df = None
            try:
                df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
                if debug_mode:
                    original_df = df.copy()

                if isinstance(df.columns, pd.MultiIndex):
                    level0_cols = [str(col).lower() for col in df.columns.get_level_values(0)]
                    if 'open' in level0_cols or 'close' in level0_cols:
                        df.columns = df.columns.get_level_values(0)
                    else:
                        df.columns = df.columns.get_level_values(1)

                df.columns = [str(col).lower() for col in df.columns]

                if df.empty:
                    raise ValueError("데이터 없음 (티커를 확인해주세요)")

                required_cols = ['open', 'high', 'low', 'close']
                for col in required_cols + ['volume']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    raise ValueError(f"필수 OHLC 데이터 부족: {missing_cols}. 사용 가능한 열: {list(df.columns)}")

                if df['close'].count() < 200:
                    raise ValueError(f"데이터 부족 (유효한 'close' 데이터가 {df['close'].count()}개로, 200개 미만)")

                progress_bar.progress((i + 1) / len(tickers), text=f"[{ticker}] 기술 지표 분석 중...")
                analysis_result = analyze_dataframe(ticker, df.copy(), stop_loss_pct)
                
                if analysis_result.get('신호') == '오류':
                    error_results.append(analysis_result)
                    # ❗️ 핵심 수정 (v3.10): "is not in None" -> "is not None" 구문 오류 수정
                    if debug_mode and original_df is not None:
                        error_dfs[ticker] = original_df
                else:
                    ok_results.append(analysis_result)

            except Exception as e:
                 error_results.append({"티커": ticker, "신호": "오류", "오류 원인": str(e)})
                 if debug_mode and original_df is not None:
                     error_dfs[ticker] = original_df

        progress_bar.empty()

        if ok_results:
            st.subheader("📊 분석 결과")
            res_df = pd.DataFrame(ok_results)
            res_df['score'] = res_df['신호'].map({"🔥 강력 매수":0, "✅ 매수 고려":1, "관망":2, "🔻 이익 실현":3, "오류": 4})
            res_df = res_df.sort_values(by="score").drop(columns=['score'])
            st.dataframe(res_df.style.format(
                {"현재가": "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}",
                 "손절가": "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}",
                 "RSI": "{:.1f}"}
            ), use_container_width=True, hide_index=True)

        if error_results:
            st.subheader("⚠️ 분석 실패 목록")
            error_df = pd.DataFrame(error_results)[['티커', '오류 원인']]
            st.dataframe(error_df, use_container_width=True, hide_index=True)
            
            if debug_mode and error_dfs:
                st.subheader("🐞 디버깅: 원본 데이터")
                for ticker_key, df_val in error_dfs.items():
                    with st.expander(f"'{ticker_key}'의 원본 데이터 보기"):
                        st.dataframe(df_val)

        if not ok_results and not error_results:
            st.warning("분석 결과가 없습니다. 티커를 확인하거나 다른 종목을 시도해보세요.")
