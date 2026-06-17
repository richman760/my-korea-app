import streamlit as st
import datetime
import gspread
from google.oauth2 import service_account

st.set_page_config(layout="wide", page_title="🧪 테스트 모드")

# 1. 가짜 데이터 생성 (KRX 접속 안 함!)
def get_dummy_data():
    return [
        {'Code': '005930', 'Name': '삼성전자', 'close': 70000, 'target': 73150},
        {'Code': '000660', 'Name': 'SK하이닉스', 'close': 150000, 'target': 156750}
    ]

# 2. 화면 구성
st.title("🧪 구글 시트 저장 테스트 모드")
if 'mock_results' not in st.session_state: st.session_state['mock_results'] = []

if st.button("🚀 가짜 데이터 생성"):
    st.session_state['mock_results'] = get_dummy_data()
    st.write("가짜 데이터 생성 완료!")

# 결과 출력
for r in st.session_state['mock_results']:
    st.write(f"📌 {r['name']} | 진입가: {r['close']:,}원 | 목표가: {r['target']:,}원")

# 3. 저장 로직 (에러 상세 추적)
if st.session_state['mock_results'] and st.button("💾 구글 시트 저장 테스트"):
    try:
        # 서비스 계정 인증
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gsheets"], 
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        
        # 시트 열기
        sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
        
        # 데이터 저장
        rows = [[str(datetime.date.today()), r['name'], f"{r['close']:,}원"] for r in st.session_state['mock_results']]
        sheet.append_rows(rows)
        st.success("🎉 저장 완료! 이제 문제가 해결됐어!")
        
    except Exception as e:
        # 에러가 나면 힌트를 더 확실하게 보여줘
        st.error(f"저장 실패 이유: {type(e).__name__} | 상세 내용: {repr(e)}")
