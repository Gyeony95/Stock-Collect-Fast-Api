from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from apscheduler.schedulers.background import BackgroundScheduler
import dart_fss as dart
import datetime
import logging
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

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

# 템플릿과 정적 파일 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 비밀번호 설정
PASSWORD = os.getenv('ADMIN_PASSWORD')

# 종목 관리를 위한 전역 변수
STOCK_CODES = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035720": "카카오",
}

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DART API 키 설정
DART_API_KEY = os.getenv('DART_API_KEY')
if not DART_API_KEY:
    raise ValueError("DART_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")

@app.get("/manage")
async def manage_page(request: Request):
    """종목 관리 페이지"""
    return templates.TemplateResponse(
        "manage.html", 
        {"request": request, "stocks": STOCK_CODES}
    )

@app.post("/login")
async def login(password: str = Form(...)):
    """로그인 처리"""
    if password == PASSWORD:
        return RedirectResponse(url="/manage", status_code=303)
    raise HTTPException(status_code=401, detail="잘못된 비밀번호입니다")

@app.post("/add-stock")
async def add_stock(stock_name: str = Form(...)):
    """종목 추가"""
    try:
        # dart-fss로 종목 검색
        corps = dart.get_corp_list().find_by_corp_name(stock_name, exactly=False)
        if corps:
            corp = corps[0]  # 첫 번째 검색 결과 사용
            STOCK_CODES[corp.stock_code] = corp.corp_name
            return {"success": True, "code": corp.stock_code, "name": corp.corp_name}
        return {"success": False, "error": "종목을 찾을 수 없습니다"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/remove-stock/{stock_code}")
async def remove_stock(stock_code: str):
    """종목 제거"""
    if stock_code in STOCK_CODES:
        del STOCK_CODES[stock_code]
        return {"success": True}
    return {"success": False, "error": "존재하지 않는 종목 코드입니다"}

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
