from fastapi import FastAPI, Request, Form, HTTPException, Depends
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
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from models import SessionLocal, StockData, FinancialData
from datetime import datetime, timedelta

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

app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

async def verify_login(request: Request):
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=303, detail="/")  # 로그인 페이지로 리다이렉트
    return True

@app.get("/")
async def login_page(request: Request):
    """로그인 페이지"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/manage")
async def manage_page(request: Request, _=Depends(verify_login)):
    """종목 관리 페이지"""
    return templates.TemplateResponse(
        "manage.html", 
        {"request": request, "stocks": STOCK_CODES}
    )

@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """로그인 처리"""
    if password == PASSWORD:
        request.session["logged_in"] = True
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
    try:
        if stock_code in STOCK_CODES:
            company_name = STOCK_CODES[stock_code]  # 로깅을 위해 회사명 저장
            del STOCK_CODES[stock_code]
            logger.info(f"종목 제거됨: {company_name} ({stock_code})")
            return {"success": True}
        logger.warning(f"존재하지 않는 종목 코드: {stock_code}")
        return {"success": False, "error": "존재하지 않는 종목 코드입니다"}
    except Exception as e:
        logger.error(f"종목 제거 중 오류 발생: {str(e)}")
        return {"success": False, "error": str(e)}

def collect_dart_data():
    """DART에서 데이터를 수집하는 함수"""
    try:
        dart.set_api_key(DART_API_KEY)
        current_time = datetime.now()
        logger.info(f"데이터 수집 시작: {current_time}")
        
        db = SessionLocal()
        try:
            for stock_code, company_name in STOCK_CODES.items():
                try:
                    company = dart.get_corp_info(stock_code)
                    
                    # 공시 정보 수집
                    bgn_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
                    end_date = datetime.now().strftime('%Y%m%d')
                    
                    disclosures = dart.filings.search(
                        corp_code=company.corp_code,
                        bgn_de=bgn_date,
                        end_de=end_date
                    )
                    
                    # 공시 데이터 저장
                    for disclosure in disclosures:
                        db_disclosure = StockData(
                            stock_code=stock_code,
                            company_name=company_name,
                            disclosure_date=datetime.strptime(disclosure.date, '%Y-%m-%d'),
                            disclosure_title=disclosure.report_nm,
                            disclosure_type=disclosure.report_tp,
                            url=disclosure.url
                        )
                        db.add(db_disclosure)
                    
                    # 재무제표 데이터 수집 (최근 분기)
                    try:
                        fs = dart.get_financial_statement(company.corp_code, bgn_de=bgn_date)
                        if fs:
                            for statement in fs:
                                db_financial = FinancialData(
                                    stock_code=stock_code,
                                    company_name=company_name,
                                    date=statement['date'],
                                    revenue=statement.get('revenue', 0),
                                    operating_profit=statement.get('operating_profit', 0),
                                    net_income=statement.get('net_income', 0)
                                )
                                db.add(db_financial)
                    
                    except Exception as e:
                        logger.error(f"재무제표 수집 중 오류: {str(e)}")
                    
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"종목 코드 {stock_code} 처리 중 오류 발생: {str(e)}")
                    continue
                    
        finally:
            db.close()
                
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

@app.get("/logout")
async def logout(request: Request):
    """로그아웃"""
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
