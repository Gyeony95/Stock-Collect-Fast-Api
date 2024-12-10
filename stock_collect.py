from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
import dart_fss as dart
import datetime
import logging
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시
    scheduler.start()
    logger.info("스케줄러 시작됨")
    yield
    # 종료 시
    scheduler.shutdown()
    logger.info("스케줄러 종료됨")

app = FastAPI(lifespan=lifespan)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DART API 키 설정 (나중에 입력)
DART_API_KEY = "YOUR_API_KEY_HERE"

# 관심 있는 종목 코드 리스트
STOCK_CODES = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035720",  # 카카오
    # 원하는 종목 코드를 추가하세요
]

def collect_dart_data():
    """DART에서 데이터를 수집하는 함수"""
    try:
        # DART API 초기화
        dart.set_api_key(DART_API_KEY)
        
        current_time = datetime.datetime.now()
        logger.info(f"데이터 수집 시작: {current_time}")
        
        for stock_code in STOCK_CODES:
            try:
                # 기업 정보 가져오기
                company = dart.get_corp_info(stock_code)
                
                # 최근 공시 정보 가져오기 (최근 7일)
                bgn_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y%m%d')
                end_date = datetime.datetime.now().strftime('%Y%m%d')
                
                disclosures = dart.filings.search(
                    corp_code=company.corp_code,
                    bgn_de=bgn_date,
                    end_de=end_date
                )
                
                # 여기에 원하는 데이터 처리 로직을 추가하세요
                logger.info(f"종목 코드 {stock_code}의 최근 공시 개수: {len(disclosures)}")
                
                # 데이터 처리 예시:
                for disclosure in disclosures:
                    logger.info(f"공시 제목: {disclosure.report_nm}")
                    # 추가적인 데이터 처리...
                
            except Exception as e:
                logger.error(f"종목 코드 {stock_code} 처리 중 오류 발생: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {str(e)}")

# 스케줄러 설정
scheduler = BackgroundScheduler()
scheduler.add_job(collect_dart_data, 'cron', hour=9, minute=0)  # 매일 오전 9시에 실행

@app.get("/")
async def root():
    """서버 상태 확인용 엔드포인트"""
    return {"status": "running"}

@app.get("/run-collection")
async def run_collection():
    """수동으로 데이터 수집을 실행하는 엔드포인트"""
    collect_dart_data()
    return {"status": "collection started"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
