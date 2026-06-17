import streamlit as st
import datetime
import gspread
from google.oauth2 import service_account

st.set_page_config(layout="wide", page_title="테스트 모드")

# 1. 데이터를 확실하게 넣었어 (KeyError 절대 안 남)
def get_mock_data():
    return [
        {'name': '삼성전자', 'close': 70000, 'target': 73150},
        {'name': 'SK하이닉스', 'close': 150000, 'target': 156750}
    ]

st.title("🧪 테스트 모드: 강제 데이터 주입")

# 데이터 생성 버튼
if st.button("🚀 강제 데이터 생성"):
    st.session_state['results'] = get_mock_data()
    st.success("데이터 생성 완료!")

# 데이터 출력 (아까 에러 났던 그 부분!)
if 'results' in st.session_state:
    for r in st.session_state['results']:
        # name, close, target 키가 있는지 확실히 확인
        st.write(f"📌 {r.get('name', '이름없음')} | 진입가: {r.get('close', 0):,}원 | 목표가: {r.get('target', 0):,}원")

# 2. 구글 시트 저장 (테스트)
if st.button("💾 구글 시트 저장 테스트"):
    if 'results' not in st.session_state:
        st.error("데이터를 먼저 생성해주세요!")
    else:
        try:
            # 1. 인증 정보 확인
            if "gsheets" not in st.secrets:
                st.error("Secrets에 [gsheets] 설정이 없습니다.")
                st.stop()
            
            # 2. 인증
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gsheets"], 
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            client = gspread.authorize(creds)
            
            # 3. 시트 열기
            sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
            
            # 4. 데이터 저장
            rows = [[str(datetime.date.today()), r['name'], f"{r['close']:,}원"] for r in st.session_state['results']]
            sheet.append_rows(rows)
            st.success("🎉 저장 성공! 이제 진짜 해결됐어!")
            
        except Exception as e:
            st.error(f"저장 실패 이유: {type(e).__name__} | 내용: {repr(e)}")
