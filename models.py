from sqlalchemy import Column, Integer, String, DateTime, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/dart_db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class StockData(Base):
    __tablename__ = "stock_data"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String, index=True)
    company_name = Column(String)
    disclosure_date = Column(DateTime, index=True)
    disclosure_title = Column(String)
    disclosure_type = Column(String)
    url = Column(String)

class FinancialData(Base):
    __tablename__ = "financial_data"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String, index=True)
    company_name = Column(String)
    date = Column(DateTime, index=True)
    revenue = Column(Float)
    operating_profit = Column(Float)
    net_income = Column(Float)

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine) 