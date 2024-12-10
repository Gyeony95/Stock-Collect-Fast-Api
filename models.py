from sqlalchemy import Column, Integer, String, DateTime, Float, create_engine, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+pymysql://user:password@localhost:3306/dart_db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class StockData(Base):
    __tablename__ = "stock_data"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String(20), index=True)
    company_name = Column(String(100))
    disclosure_date = Column(DateTime, index=True)
    disclosure_title = Column(String(500))
    disclosure_type = Column(String(100))
    url = Column(String(500))

class FinancialData(Base):
    __tablename__ = "financial_data"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String(20), index=True)
    company_name = Column(String(100))
    date = Column(DateTime, index=True)
    revenue = Column(Float)
    operating_profit = Column(Float)
    net_income = Column(Float)

class ManagedStock(Base):
    __tablename__ = "managed_stocks"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String(20), unique=True, index=True)
    company_name = Column(String(100))
    is_active = Column(Boolean, default=True)  # 종목 활성화 여부
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine) 