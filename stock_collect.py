from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import dart_fss as dart
import datetime
import logging
import os
from dotenv import load_dotenv
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from models import SessionLocal, StockData, FinancialData, ManagedStock
from datetime import datetime, timedelta
from sqlalchemy.sql import text
from fastapi.background import BackgroundTasks

# .env 파일 로드
load_dotenv()

app = FastAPI()

# 템플릿과 정적 파일 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 비번호 설정
PASSWORD = os.getenv('ADMIN_PASSWORD')

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

def get_managed_stocks(db):
    stocks = db.query(ManagedStock).filter(ManagedStock.is_active == True).all()
    return {stock.stock_code: stock.company_name for stock in stocks}

@app.get("/manage")
async def manage_page(request: Request, _=Depends(verify_login)):
    """종목 관리 페이지"""
    db = SessionLocal()
    try:
        # 활성화된 종목만 조회
        stocks = db.query(ManagedStock)\
            .filter(ManagedStock.is_active == True)\
            .all()
        stocks_dict = {stock.stock_code: stock.company_name for stock in stocks}
        return templates.TemplateResponse(
            "manage.html", 
            {"request": request, "stocks": stocks_dict}
        )
    finally:
        db.close()

@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """로그�� 처리"""
    if password == PASSWORD:
        request.session["logged_in"] = True
        return RedirectResponse(url="/manage", status_code=303)
    raise HTTPException(status_code=401, detail="잘못된 비밀번호입니다")

@app.post("/add-stock")
async def add_stock(stock_name: str = Form(...)):
    """종목 추가"""
    db = SessionLocal()
    try:
        # dart-fss로 종목 검색
        corps = dart.get_corp_list().find_by_corp_name(stock_name, exactly=False)
        if not corps:
            return {"success": False, "error": "종목을 찾을 수 없습니다"}

        corp = corps[0]  # 첫 번째 검색 결과 사용
        
        # 이미 등록된 종목인지 확인
        existing_stock = db.query(ManagedStock)\
            .filter(ManagedStock.stock_code == corp.stock_code)\
            .first()
        
        if existing_stock:
            if existing_stock.is_active:
                return {"success": False, "error": "이미 등록된 종목입니다"}
            # 비활성화된 종목이면 다시 활성화
            existing_stock.is_active = True
            existing_stock.updated_at = datetime.now()
            db.commit()
        else:
            # 새 종목 추가
            new_stock = ManagedStock(
                stock_code=corp.stock_code,
                company_name=corp.corp_name,
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(new_stock)
            db.commit()
        
        return {"success": True, "code": corp.stock_code, "name": corp.corp_name}
    except Exception as e:
        db.rollback()
        logger.error(f"종목 추가 중 오류 발생: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.post("/remove-stock/{stock_code}")
async def remove_stock(stock_code: str):
    """종목 제거"""
    db = SessionLocal()
    try:
        stock = db.query(ManagedStock)\
            .filter(ManagedStock.stock_code == stock_code)\
            .first()
        
        if not stock:
            return {"success": False, "error": "존재하지 않는 종목 코드입니다"}
        
        if not stock.is_active:
            return {"success": False, "error": "이미 제거된 종목입니다"}
        
        # 종목 비활성화
        stock.is_active = False
        stock.updated_at = datetime.now()
        db.commit()
        
        logger.info(f"종목 제거됨: {stock.company_name} ({stock_code})")
        return {"success": True}
    except Exception as e:
        db.rollback()
        logger.error(f"종목 제거 중 오류 발생: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def collect_dart_data():
    """DART에서 데이터를 수집하는 함수"""
    try:
        dart.set_api_key(DART_API_KEY)
        corp_list = dart.get_corp_list()
        current_time = datetime.now()
        logger.info(f"데이터 수집 시작: {current_time}")
        
        db = SessionLocal()
        try:
            # 활성화된 종목 조회
            stocks = db.query(ManagedStock).filter(ManagedStock.is_active == True).all()
            for stock in stocks:
                try:
                    company = corp_list.find_by_stock_code(stock.stock_code)
                    
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
                            stock_code=stock.stock_code,
                            company_name=stock.company_name,
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
                                    stock_code=stock.stock_code,
                                    company_name=stock.company_name,
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
                    logger.error(f"종목 코드 {stock.stock_code} 처리 중 오류 발생: {str(e)}")
                    continue
                    
        finally:
            db.close()
                
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {str(e)}")

@app.get("/")
async def root():
    """서버 상태 확인용 엔드포인트"""
    return {"status": "running"}

@app.get("/run-collection")
async def run_collection():
    """수동으로 데이터 수집을 실행하는 엔드포인트"""
    try:
        collect_dart_data()
        return {"status": "collection started"}
    except Exception as e:
        logger.error(f"데이터 수집 실행 중 오류: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/logout")
async def logout(request: Request):
    """로그아웃"""
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

def collect_single_stock_data(stock_code: str, company_name: str):
    """단일 종목의 데이터를 수집하는 함수"""
    collected_data = {
        "stock_code": stock_code,
        "company_name": company_name,
        "disclosures": [],
        "financials": []
    }
    
    try:
        dart.set_api_key(DART_API_KEY)
        corp_list = dart.get_corp_list()
        db = SessionLocal()
        try:
            company = corp_list.find_by_stock_code(stock_code)
            if not company:
                raise ValueError(f"종목코드 {stock_code} 해당하는 기업을 찾을 수 없습니다.")
            
            # 공시 정보 수집 (최근 1년)
            bgn_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            end_date = datetime.now().strftime('%Y%m%d')
            
            disclosures = dart.filings.search(
                corp_code=company.corp_code,
                bgn_de=bgn_date,
                end_de=end_date
            )
            
            # 공시 데이터 저장
            for disclosure in disclosures:
                disclosure_data = {
                    "date": disclosure.rcept_dt,
                    "title": disclosure.report_nm,
                    "type": disclosure.rm,
                    "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={disclosure.rcp_no}"
                }
                collected_data["disclosures"].append(disclosure_data)
                
                db_disclosure = StockData(
                    stock_code=stock_code,
                    company_name=company_name,
                    disclosure_date=datetime.strptime(disclosure.rcept_dt, '%Y%m%d'),
                    disclosure_title=disclosure.report_nm,
                    disclosure_type=disclosure.rm,
                    url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={disclosure.rcp_no}"
                )
                db.add(db_disclosure)
            
            # 재무제표 데이터 수집
            try:
                # 연결재무제표 시도
                fs = company.extract_fs(bgn_de=(datetime.now() - timedelta(days=365*3)).strftime('%Y%m%d'))
            except dart.errors.NotFoundConsolidated:
                try:
                    # 일반재무제표 시도
                    fs = company.extract_fs(bgn_de=(datetime.now() - timedelta(days=365*3)).strftime('%Y%m%d'), separate=True)
                except Exception as e:
                    logger.warning(f"{company_name}({stock_code}) 일반재무제표 수집 중 오류: {str(e)}")
                    fs = None

            if fs is not None:
                try:
                    statements = fs.show('재무상태표')
                    if statements is not None:
                        for idx, row in statements.iterrows():
                            try:
                                date = datetime.strptime(str(idx.year), '%Y')
                                financial_data = {
                                    "date": date.strftime('%Y-%m-%d'),
                                    "revenue": float(row.get('매출액', 0)),
                                    "operating_profit": float(row.get('영업이익', 0)),
                                    "net_income": float(row.get('당기순이익', 0))
                                }
                                collected_data["financials"].append(financial_data)
                                
                                db_financial = FinancialData(
                                    stock_code=stock_code,
                                    company_name=company_name,
                                    date=date,
                                    revenue=financial_data["revenue"],
                                    operating_profit=financial_data["operating_profit"],
                                    net_income=financial_data["net_income"]
                                )
                                db.add(db_financial)
                            except (ValueError, TypeError) as e:
                                logger.warning(f"재무데이터 처리 중 오류: {str(e)}")
                                continue
                except Exception as e:
                    logger.warning(f"{company_name}({stock_code}) 재무제표 데이터 처리 중 오류: {str(e)}")
            
            db.commit()
            logger.info(f"{company_name}({stock_code}) 데이터 수집 완료")
            # 수집된 데이터 출력
            import json
            print("\n수집된 데이터:")
            print(json.dumps(collected_data, indent=2, ensure_ascii=False))
            
        finally:
            db.close()
                
    except Exception as e:
        logger.error(f"{company_name}({stock_code}) 데이터 수집 중 오류 발생: {str(e)}")
        raise e
    finally:
        collection_status["status"] = "idle"
        collection_status["message"] = ""
        collection_status["collecting_stocks"].discard(stock_code)

# 전역 변수로 수집 상태 관리
collection_status = {"status": "idle", "message": "", "collecting_stocks": set()}

@app.get("/collection-status")
async def get_collection_status():
    """데이터 수집 상태 확인"""
    return collection_status

@app.get("/stock/{stock_code}")
async def stock_detail(request: Request, stock_code: str, background_tasks: BackgroundTasks, _=Depends(verify_login)):
    """종목 상세 정보 페이지"""
    try:
        db = SessionLocal()
        try:
            # 활성화된 종목인지 확인
            stock = db.query(ManagedStock)\
                .filter(ManagedStock.stock_code == stock_code, ManagedStock.is_active == True)\
                .first()
            
            if not stock:
                raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다")
            
            company_name = stock.company_name
            collecting = False
            
            # 데이터 존재 여부 확인 (재무제표 또는 공시 데이터)
            data_exists = db.query(FinancialData)\
                .filter(FinancialData.stock_code == stock_code)\
                .first() is not None or \
                db.query(StockData)\
                .filter(StockData.stock_code == stock_code)\
                .first() is not None
            
            # 데이터가 없고 현재 수집 중이 아닌 경우에만 수집 시작
            if not data_exists and stock_code not in collection_status["collecting_stocks"]:
                collecting = True
                collection_status["status"] = "collecting"
                collection_status["message"] = f"{company_name} 데이터를 수집하고 있습니다..."
                collection_status["collecting_stocks"].add(stock_code)
                # 백그라운드에서 데이터 수집 실행
                background_tasks.add_task(collect_single_stock_data, stock_code, company_name)
            elif stock_code in collection_status["collecting_stocks"]:
                collecting = True

            # 최근 3개년 재무데이터 조회
            yearly_query = text("""
                SELECT date_trunc('year', date) as year,
                       sum(revenue) as revenue,
                       sum(operating_profit) as operating_profit,
                       sum(net_income) as net_income
                FROM financial_data
                WHERE stock_code = :stock_code
                AND date >= current_date - interval '3 years'
                GROUP BY date_trunc('year', date)
                ORDER BY year
            """)
            
            yearly_data = db.execute(yearly_query, {"stock_code": stock_code}).fetchall()
            
            # 최근 분기와 전년 동기 데이터 조회
            quarter_query = text("""
                WITH latest_quarter AS (
                    SELECT date_trunc('quarter', date) as quarter
                    FROM financial_data
                    WHERE stock_code = :stock_code
                    ORDER BY date DESC
                    LIMIT 1
                )
                SELECT date_trunc('quarter', date) as quarter,
                       sum(revenue) as revenue,
                       sum(operating_profit) as operating_profit,
                       sum(net_income) as net_income
                FROM financial_data
                WHERE stock_code = :stock_code
                AND (
                    date_trunc('quarter', date) = (SELECT quarter FROM latest_quarter)
                    OR date_trunc('quarter', date) = (SELECT quarter FROM latest_quarter) - interval '1 year'
                )
                GROUP BY date_trunc('quarter', date)
                ORDER BY quarter
            """)
            
            quarter_data = db.execute(quarter_query, {"stock_code": stock_code}).fetchall()
            
            # 최근 공시 데이터 조회
            disclosures = db.query(StockData)\
                .filter(StockData.stock_code == stock_code)\
                .order_by(StockData.disclosure_date.desc())\
                .limit(10)\
                .all()
            
            # 그래프 데이터 구성
            yearly_traces = [
                {
                    'x': [row.year.strftime('%Y') for row in yearly_data],
                    'y': [row[metric] for row in yearly_data],
                    'type': 'scatter',
                    'mode': 'lines+markers',
                    'name': metric.replace('_', ' ').title()
                }
                for metric in ['revenue', 'operating_profit', 'net_income']
            ]
            
            # 분기 데이터가 있는 경우에만 차트 데이터 생성
            if len(quarter_data) >= 2:
                quarter_traces = [
                    {
                        'x': ['매출액', '영업이익', '순이익'],
                        'y': [quarter_data[-1].revenue, quarter_data[-1].operating_profit, quarter_data[-1].net_income],
                        'type': 'bar',
                        'name': '최근 분기'
                    },
                    {
                        'x': ['매출액', '영업이익', '순이익'],
                        'y': [quarter_data[0].revenue, quarter_data[0].operating_profit, quarter_data[0].net_income],
                        'type': 'bar',
                        'name': '전년 분기'
                    }
                ]
            else:
                quarter_traces = []  # 분기 데이터가 없으면 빈 배열
            
            return templates.TemplateResponse(
                "stock_detail.html",
                {
                    "request": request,
                    "company_name": company_name,
                    "stock_code": stock_code,
                    "yearly_data": {"data": yearly_traces},
                    "quarter_data": {"data": quarter_traces},
                    "disclosures": disclosures,
                    "collecting": collecting
                }
            )
            
        finally:
            db.close()
            
    except Exception as e:
        collection_status["status"] = "idle"  # 오류 발생 시 상태 초기화
        logger.error(f"종목 상세정보 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="서버 오류가 발생했습니다")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
