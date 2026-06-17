import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(layout="wide", page_title="🇰🇷 한국 퀀트 스캐너")

# 1. 숫자 -> 한글 변환
def number_to_korean(n):
    if n == 0: return "0원"
    if n < 10000: return f"{n:,}원"
    man = n // 10000
    remainder = n % 10000
    result = f"{man:,}만"
    if remainder > 0: result += f"{remainder:,}"
    return result + "원"

# 2. 기억력 장치
if 'found_list' not in st.session_state:
    st.session_state['found_list'] = []

# 3. 퀀트 로직
def run_backtest_for_stock(ticker_code):
    try:
        df = fdr.DataReader(ticker_code, '2005-01-01')
        if len(df) < 250: return None
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD20'] = df['Close'].rolling(window=20).std()
        df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
        df['RSI'] = 100 - (100 / (1 + (df['Close'].diff().where(df['Close'].diff()>0, 0).rolling(14).mean() / (-df['Close'].diff().where(df['Close'].diff()<0, 0).rolling(14).mean() + 1e-9))))
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        df['Signal'] = (df['RSI'].rolling(window=3).min() <= 35) & (df['Close'] >= df['BB_Lower'] * 0.98) & (df['Volume'] > df['Vol_MA5'])
        if not df['Signal'].iloc[-1]: return None
        return {'name': fdr.StockListing('KRX').set_index('Code').loc[ticker_code, 'Name'], 'today_close': int(df['Close'].iloc[-1]), 'target_val': int(df['Close'].iloc[-1] * 1.045)}
    except: return None

# 4. 사이드바
st.sidebar.title("💰 매매 설정")
budget = st.sidebar.number_input("투자 가능 자산 (원)", value=10000000, step=1000000)
st.sidebar.caption(f"현재 설정: {number_to_korean(budget)}")

# 5. 스캔 버튼
if st.button("🚀 스캔 시작"):
    st.session_state['found_list'] = []
    with st.spinner('종목 스캔 중...'):
        try:
            tickers = fdr.StockListing('KRX')['Code'].tolist()[:300]
            for code in tickers:
                res = run_backtest_for_stock(code)
                if res: st.session_state['found_list'].append(res)
        except Exception as e: st.error(f"데이터 에러: {e}")

# 6. 결과 출력
for res in st.session_state['found_list']:
    with st.expander(f"📌 {res['name']}", expanded=True):
        st.text(f"종목명: {res['name']} | 진입가: {res['today_close']:,}원")
        shares = budget // res['today_close']
        profit = (res['target_val'] - res['today_close']) * shares
        st.markdown(f"**💰 {budget:,}원 투입 시 예상 수익: +{profit:,}원 ({shares:,}주)**")

# 7. 구글 시트 저장 (에러 상세 보기용)
if st.session_state['found_list'] and st.button("💾 구글 시트에 저장하기"):
    try:
        # Secrets 확인
        if "gsheets" not in st.secrets: raise Exception("Secrets 설정에 [gsheets] 항목이 없습니다.")
        creds_dict = dict(st.secrets["gsheets"])
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
        
        rows = [[str(datetime.date.today()), r['name'], f"{r['today_close']:,}원", f"{r['target_val']:,}원", f"{budget:,}원"] for r in st.session_state['found_list']]
        sheet.append_rows(rows)
        st.success("저장 완료!")
    except Exception as e:
        st.error(f"상세 에러: {type(e).__name__} / 메시지: {str(e)}")
