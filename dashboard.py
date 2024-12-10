import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# 데이터베이스 연결
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/dart_db')
engine = create_engine(DATABASE_URL)

st.set_page_config(page_title="DART 모니터링 대시보드", layout="wide")

st.title("DART 공시 모니터링 대시보드")

# 날짜 필터
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("시작일", datetime.now() - timedelta(days=30))
with col2:
    end_date = st.date_input("종료일", datetime.now())

# 공시 데이터 조회
query = text("""
    SELECT company_name, disclosure_date, disclosure_title, disclosure_type
    FROM stock_data
    WHERE disclosure_date BETWEEN :start_date AND :end_date
    ORDER BY disclosure_date DESC
""")

df_disclosures = pd.read_sql(
    query,
    engine,
    params={"start_date": start_date, "end_date": end_date}
)

# 재무데이터 조회
query_financial = text("""
    SELECT company_name, date, revenue, operating_profit, net_income
    FROM financial_data
    WHERE date BETWEEN :start_date AND :end_date
    ORDER BY date DESC
""")

df_financial = pd.read_sql(
    query_financial,
    engine,
    params={"start_date": start_date, "end_date": end_date}
)

# 시각화
st.header("공시 현황")
fig_disclosures = px.bar(
    df_disclosures.groupby('company_name').size().reset_index(name='count'),
    x='company_name',
    y='count',
    title="기업별 공시 건수"
)
st.plotly_chart(fig_disclosures)

st.header("재무 현황")
for metric in ['revenue', 'operating_profit', 'net_income']:
    fig = px.line(
        df_financial,
        x='date',
        y=metric,
        color='company_name',
        title=f"기업별 {metric.replace('_', ' ').title()}"
    )
    st.plotly_chart(fig)

# 상세 데이터 테이블
st.header("최근 공시 목록")
st.dataframe(df_disclosures) 