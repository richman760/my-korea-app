import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import gspread
from google.oauth2 import service_account

st.set_page_config(layout="wide", page_title="🇰🇷 최종 안정화 스캐너")

# 1. 초기화
if 'ticker_list' not in st.session_state: st.session_state['ticker_list'] = None
if 'results' not in st.session_state: st.session_state['results'] = []

# 2. 로직: 한국_퀀트.py의 핵심 기능
def run_backtest(ticker_code):
    try:
        df = fdr.DataReader(ticker_code, '2005-01-01')
        if len(df) < 250: return None
        df['MA20'] = df['Close'].rolling(20).mean()
        df['STD20'] = df['Close'].rolling(20).std()
        df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
        df['RSI'] = 100 - (100 / (1 + (df['Close'].diff().clip(0).rolling(14).mean() / (-df['Close'].diff().clip(upper=0).rolling(14).mean() + 1e-9))))
        df['Vol_MA5'] = df['Volume'].rolling(5).mean()
        df['Signal'] = (df['RSI'].rolling(3).min() <= 35) & (df['Close'] >= df['BB_Lower'] * 0.98) & (df['Volume'] > df['Vol_MA5'])
        if not df['Signal'].iloc[-1]: return None
        return {'name': '종목명', 'close': int(df['Close'].iloc[-1]), 'target': int(df['Close'].iloc[-1] * 1.045)}
    except: return None

# 3. UI
st.title("🚀 최종 안정화 퀀트 스캐너")

# [핵심] 리스트 불러오기를 버튼으로 분리해서 에러 방지
if st.button("1. 종목 리스트 불러오기"):
    with st.spinner('KRX 서버 연결 중...'):
        try:
            # KRX 한번에 가져오기 부담스러우면 코스피/코스닥 분리 시도
            df = fdr.StockListing('KOSPI')
            st.session_state['ticker_list'] = df[['Code', 'Name']].to_dict('records')
            st.success(f"{len(st.session_state['ticker_list'])}개 종목 로드 완료!")
        except Exception as e:
            st.error(f"연결 실패: {e}. 잠시 후 다시 시도하세요.")

if st.session_state['ticker_list']:
    if st.button("2. 퀀트 스캔 시작"):
        st.session_state['results'] = []
        with st.spinner('스캔 중...'):
            for stock in st.session_state['ticker_list'][:100]: # 테스트 위해 100개만
                res = run_backtest(stock['Code'])
                if res:
                    res['name'] = stock['Name']
                    st.session_state['results'].append(res)
        st.write("스캔 완료!")

# 결과 출력
for r in st.session_state['results']:
    st.write(f"📌 {r['name']} | 진입: {r['close']:,}원 | 목표: {r['target']:,}원")

# 저장
if st.button("💾 구글 시트 저장"):
    try:
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gsheets"], scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        sheet = gspread.authorize(creds).open_by_url(st.secrets["sheet_url"]).sheet1
        sheet.append_rows([[str(datetime.date.today()), r['name'], f"{r['close']:,}원"] for r in st.session_state['results']])
        st.success("저장 성공!")
    except Exception as e: st.error(f"저장 실패: {e}")
