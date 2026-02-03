
# verify_names.py
import sys
import asyncio

# Streamlit 앱의 get_stock_name 함수를 직접 임포트하여 테스트합니다.
# 이는 실제 앱과 동일한 코드를 테스트하기 위함입니다.
from app import get_stock_name

async def run_test(ticker, expected_name_contains):
    """개별 티커에 대한 테스트를 비동기적으로 실행하고 결과를 반환합니다."""
    # get_stock_name은 @st.cache_data 데코레이터 때문에 직접 await 할 수 없으므로,
    # 실제 앱과 유사하게 동기적으로 호출합니다.
    # asyncio.to_thread를 사용해 block이 될 수 있는 I/O 작업을 별도 스레드에서 실행합니다.
    # 실제 Streamlit 환경에서는 이 함수가 정상적으로 동작하지만,
    # 스크립트 환경에서는 데코레이터를 모방하기 위해 이와 같이 실행합니다.
    try:
        # st.cache_data는 내부적으로 thread-local context를 사용하므로, 
        # 일반 비동기 방식으로는 테스트하기 어렵습니다. 
        # 여기서는 함수의 순수 로직만 테스트하기 위해 직접 호출합니다.
        # 실제 앱에서는 Streamlit의 런타임이 캐싱을 관리합니다.
        
        # NOTE: Streamlit의 @st.cache_data는 직접적인 비동기 호출을 지원하지 않습니다.
        # 이 스크립트는 함수의 로직 자체를 검증하는 데 중점을 둡니다.
        name = get_stock_name(ticker)
        
        # 예상 결과 문자열을 포함하는지 확인 (대소문자 무시)
        is_correct = expected_name_contains.lower() in name.lower()
        status = "✅ 통과" if is_correct else f"❌ 실패 (예상: '{expected_name_contains}', 실제: '{name}')"
        print(f"- 테스트: '{ticker}' -> '{name}' [{status}]")
        return is_correct
    except Exception as e:
        status = f"💥 오류: {e}"
        print(f"- 테스트: '{ticker}' -> {status}")
        return False

def main():
    """테스트 케이스를 정의하고 실행 결과를 요약합니다."""
    print("--- (v8.2) 종목명 조회 기능 자동 검증 시작 ---")
    
    test_cases = {
        # --- 1. 한국 주식 (정상 케이스) ---
        "005930.KS": "삼성전자",
        "000660.KS": "SK하이닉스",
        "373220.KQ": "LG에너지솔루션", # 코스닥
        
        # --- 2. 미국 주식 (정상 케이스) ---
        "NVDA": "NVIDIA",
        "AAPL": "Apple",
        "GOOGL": "Alphabet",
        "TSLA": "Tesla",

        # --- 3. 예외 케이스 ---
        "invalidticker": "invalidticker",     # 존재하지 않는 티커
        "000000.KS": "000000.KS",         # 존재하지 않는 종목 코드
        "aApL": "Apple",                  # 대소문자 혼용
    }

    results = []
    for ticker, expected in test_cases.items():
        # 이벤트 루프 없이 간단한 동기 방식으로 실행합니다.
        results.append(run_test_sync(ticker, expected))

    print("\n--- 검증 결과 요약 ---")
    if all(results):
        print(f"✅ 모든 {len(results)}개 테스트 케이스 통과! 조회 기능이 안정적으로 동작합니다.")
    else:
        failures = results.count(False)
        print(f"❌ {failures}개의 테스트 케이스 실패. 코드 검토가 필요합니다.")
    print("----------------------")

def run_test_sync(ticker, expected_name_contains):
    """개별 티커에 대한 테스트를 동기적으로 실행하고 결과를 반환합니다."""
    try:
        name = get_stock_name(ticker)
        is_correct = expected_name_contains.lower() in name.lower()
        status = "✅ 통과" if is_correct else f"❌ 실패 (예상: '{expected_name_contains}', 실제: '{name}')"
        print(f"- 테스트: '{ticker}' -> '{name}' [{status}]")
        return is_correct
    except Exception as e:
        status = f"💥 오류: {e}"
        print(f"- 테스트: '{ticker}' -> {status}")
        return False

if __name__ == "__main__":
    main()
