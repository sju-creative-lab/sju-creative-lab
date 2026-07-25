import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="공공 GitLab 저장소",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. 세션 상태 초기화 (임시 데이터베이스 역할)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# 사용자 정보 저장소 (기본 관리자 계정 1개 세팅)
if 'users_db' not in st.session_state:
    st.session_state['users_db'] = {'admin': 'password1234'}

if 'repository' not in st.session_state:
    st.session_state['repository'] = []

# ==========================================
# 3. 로그인 및 회원가입 화면
# ==========================================
def show_login_page():
    st.markdown("""
        <style>
        .stApp { background-color: #121216; color: white; }
        div.stButton > button {
            background-color: #5c8ae6; color: white; border: none; width: 100%; border-radius: 5px; padding: 10px;
        }
        div.stButton > button:hover { background-color: #4a75c7; color: white; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='text-align: center;'>
                <img src='https://upload.wikimedia.org/wikipedia/commons/1/19/Emblem_of_South_Korea.svg' width='60'>
                <h2 style='color: white; margin-top: 15px;'>공공 GitLab 저장소</h2>
            </div>
        """, unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)
        
        # 탭을 나누어 로그인과 회원가입 기능 분리
        tab_login, tab_signup = st.tabs(["🔑 로그인", "📝 회원가입"])
        
        # --- [1] 로그인 탭 ---
        with tab_login:
            user_id = st.text_input("ID 또는 이메일", key="login_id")
            password = st.text_input("패스워드", type="password", key="login_pw")
            
            st.write("<br>", unsafe_allow_html=True)
            if st.button("로그인"):
                # 입력한 ID가 DB에 있고, 비밀번호가 일치하는지 확인
                if user_id in st.session_state['users_db'] and st.session_state['users_db'][user_id] == password:
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = user_id
                    st.rerun()
                else:
                    st.error("아이디가 존재하지 않거나 비밀번호가 틀렸습니다.")
                    
        # --- [2] 회원가입 탭 ---
        with tab_signup:
            new_id = st.text_input("새 ID (사용할 아이디)", key="signup_id")
            new_pw = st.text_input("새 패스워드", type="password", key="signup_pw")
            new_pw_check = st.text_input("패스워드 확인", type="password", key="signup_pw_chk")
            
            st.write("<br>", unsafe_allow_html=True)
            if st.button("계정 생성하기"):
                if not new_id or not new_pw:
                    st.warning("아이디와 비밀번호를 모두 입력해주세요.")
                elif new_id in st.session_state['users_db']:
                    st.error("이미 사용 중인 아이디입니다. 다른 아이디를 입력해주세요.")
                elif new_pw != new_pw_check:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    # 새로운 계정을 임시 DB에 저장
                    st.session_state['users_db'][new_id] = new_pw
                    st.success(f"'{new_id}' 계정이 성공적으로 생성되었습니다! '로그인' 탭에서 접속해주세요.")

# ==========================================
# 4. 메인 대시보드 화면 (이전 코드와 동일하므로 내용 유지)
# ==========================================
def show_main_page():
    # ... (기존 대시보드 렌더링 코드 유지) ...
    st.write("로그인 성공! 대시보드 화면입니다.") # (테스트용 간략 표시, 실제는 기존 코드 사용)
    if st.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.rerun()

# ==========================================
# 5. 메인 라우팅
# ==========================================
if not st.session_state['logged_in']:
    show_login_page()
else:
    show_main_page() # 기존 4번 대시보드 코드를 여기에 그대로 연결하시면 됩니다.