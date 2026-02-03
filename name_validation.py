
import yfinance as yf

# app.py에 추가된 get_stock_name 함수를 그대로 가져와 테스트합니다.
def get_stock_name(ticker):
    """
    yfinance의 fast_info와 info를 순차적으로 사용하여 종목명을 가져옵니다.
    1. stock.fast_info에서 'shortName'을 먼저 시도합니다. (가장 빠름)
    2. 실패 시, stock.info에서 'shortName' 또는 'longName'을 시도합니다. (느리지만 정보가 많음)
    3. 모든 시도가 실패하면 원본 티커를 반환합니다.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # 1차 시도: 빠르고 가벼운 fast_info 사용
        name = stock.fast_info.get('shortName')
        if name and name != ticker:
            return name
        
        # 2차 시도: 더 많은 정보가 있는 info 사용
        info = stock.info
        name = info.get('shortName') or info.get('longName')
        if name and name != ticker:
            return name
            
        return ticker # 모든 시도 실패 시 티커 반환
    except Exception:
        return ticker # API 호출 중 예외 발생 시 티커 반환

# --- 검증할 티커 목록 ---
test_cases = {
    "미국 주식 (정상)": "NVDA",
    "코스피 (정상)": "005930.KS",
    "코스닥 (정상)": "247540.KQ",
    "존재하지 않는 티커": "NONEXISTENTTICKER",
    "API가 이름을 못찾는 경우(기존 문제)": "GOOGL", # 간혹 shortName이 티커와 동일하게 오는 경우
}

print("--- v7.3 종목명 조회 기능 검증 시작 ---")
all_passed = True

for case, ticker in test_cases.items():
    print(f"\n[테스트 케이스: {case}]")
    print(f"> 입력 티커: {ticker}")
    
    result_name = get_stock_name(ticker)
    
    print(f"> 반환된 이름: {result_name}")
    
    # 검증 로직
    if case == "존재하지 않는 티커":
        if result_name == ticker:
            print("✅ 통과: 존재하지 않는 티커에 대해 입력값을 그대로 반환했습니다.")
        else:
            print(f"❌ 실패: 예상과 다른 값 '{result_name}'을 반환했습니다.")
            all_passed = False
    else:
        if result_name != ticker and result_name is not None:
            print("✅ 통과: 성공적으로 정식 종목명을 가져왔습니다.")
        else:
            print(f"❌ 실패: 종목명을 가져오지 못하고 티커 '{result_name}'를 그대로 반환했습니다.")
            all_passed = False

print("\n--- 검증 요약 ---")
if all_passed:
    print("🎉 모든 검증 통과! 종목명 조회 기능이 안정적으로 작동합니다.")
else:
    print("🔥 일부 검증 실패. 코드나 네트워크 상태를 다시 확인해주세요.")
