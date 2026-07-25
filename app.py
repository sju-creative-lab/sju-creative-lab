import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pickle
import os
import ast
import streamlit.components.v1 as components

# ==========================================
# 0. 공통 설정
# ==========================================
LOGO_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/1/19/Emblem_of_South_Korea.svg"
DATA_FILE = "app_data.pkl"
AUTO_LOGOUT_MINUTES = 30  # 자동 로그아웃 시간(분)

st.set_page_config(page_title="공공 GitHub 저장소", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 1. DB 연동 (구글 시트 & 로컬 하이브리드)
# ==========================================
def load_data():
    local_data = {"users_db": {"admin": "password1234"}, "repository": []}
    
    # 1. 로컬 데이터 먼저 불러오기 (파일 데이터 복구용)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            local_data = pickle.load(f)
            
    st.session_state['db_mode'] = "Local File"
    
    # 2. 구글 시트 연동 시도 (텍스트 데이터 완벽 보존용)
    try:
        from streamlit_gsheets import GSheetsConnection
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            st.session_state['db_mode'] = "Google Sheets"
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            # Users 시트 불러오기
            try:
                users_df = conn.read(worksheet="Users", usecols=[0,1], ttl=0)
                if not users_df.empty:
                    users_df = users_df.dropna(subset=['ID'])
                    local_data['users_db'] = dict(zip(users_df['ID'].astype(str), users_df['Password'].astype(str)))
            except: pass
                
            # Repository 시트 불러오기
            try:
                repo_df = conn.read(worksheet="Repository", ttl=0)
                if not repo_df.empty:
                    repo_df = repo_df.dropna(subset=['id'])
                    sheet_repo = repo_df.to_dict('records')
                    
                    merged_repo = []
                    for s_item in sheet_repo:
                        # 피드백 문자열을 리스트로 복구
                        try:
                            if pd.isna(s_item['feedbacks']): s_item['feedbacks'] = []
                            else: s_item['feedbacks'] = ast.literal_eval(str(s_item['feedbacks']))
                        except:
                            s_item['feedbacks'] = []
                            
                        # 로컬에 남아있는 실제 파일 바이트(Bytes) 매칭
                        matching_local = next((l for l in local_data['repository'] if str(l['id']) == str(s_item['id'])), None)
                        if matching_local and 'file_data' in matching_local:
                            s_item['file_data'] = matching_local['file_data']
                        else:
                            s_item['file_data'] = b'' # 서버 재부팅으로 파일 지워짐 표시
                        
                        merged_repo.append(s_item)
                    local_data['repository'] = merged_repo
            except: pass
    except Exception as e:
        print("DB Load Error:", e)

    return local_data

def save_data(data):
    # 1. 로컬에 전체 저장 (파일 포함)
    with open(DATA_FILE, "wb") as f:
        pickle.dump(data, f)
        
    # 2. 구글 시트에 텍스트 동기화 (파일 제외)
    if st.session_state.get('db_mode') == "Google Sheets":
        try:
            from streamlit_gsheets import GSheetsConnection
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            # Users 저장
            users_df = pd.DataFrame(list(data['users_db'].items()), columns=['ID', 'Password'])
            conn.update(worksheet="Users", data=users_df)
            
            # Repository 저장
            if data['repository']:
                repo_df = pd.DataFrame(data['repository'])
                if 'file_data' in repo_df.columns:
                    repo_df = repo_df.drop(columns=['file_data'])
                repo_df['feedbacks'] = repo_df['feedbacks'].apply(lambda x: str(x))
                conn.update(worksheet="Repository", data=repo_df)
        except Exception as e:
            print("DB Save Error:", e)

if 'app_data' not in st.session_state:
    st.session_state['app_data'] = load_data()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# 새로고침 방어
if not st.session_state['logged_in'] and "user_session" in st.query_params:
    st.session_state['logged_in'] = True
    st.session_state['user_id'] = st.query_params["user_session"]
    st.session_state['last_activity'] = datetime.now()

# ==========================================
# 2. 커스텀 CSS & 자바스크립트 타이머
# ==========================================
def inject_timer_js():
    expiry_time = st.session_state['last_activity'] + timedelta(minutes=AUTO_LOGOUT_MINUTES)
    expiry_timestamp = expiry_time.timestamp() * 1000
    components.html(f"""
        <script>
        const expiry = {expiry_timestamp};
        setInterval(function() {{
            const now = new Date().getTime();
            const distance = expiry - now;
            const elem = window.parent.document.getElementById('realtime-timer');
            if (distance < 0) {{
                if(elem) elem.innerHTML = "00:00";
            }} else {{
                const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                const s = Math.floor((distance % (1000 * 60)) / 1000);
                if(elem) elem.innerHTML = (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
            }}
        }}, 1000);
        </script>
    """, height=0)

st.markdown("""
    <style>
    .timer-container { display: flex; align-items: center; justify-content: flex-end; background-color: transparent; height: 40px; margin-top: 10px; }
    div[data-testid="column"] { padding: 0 !important; }
    .timer-display { background-color: #5c7e82; color: #d4f1f4; padding: 8px 15px; font-family: monospace; font-size: 16px; font-weight: bold; display: flex; align-items: center; justify-content: center; height: 38px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 및 회원가입 화면
# ==========================================
def show_login_page():
    st.markdown("<style>.stApp { background-color: #121216; color: white; } div.stButton > button { background-color: #5c8ae6; color: white; border: none; width: 100%; border-radius: 5px; padding: 10px; }</style>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("<br><br><br>", unsafe_allow_html=True)
        col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
        with col_logo2: st.image(LOGO_IMAGE, use_container_width=True)
            
        st.markdown("<h2 style='color: white; text-align: center; margin-top: 10px;'>공공 GitHub 저장소</h2>", unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)
        
        tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
        
        with tab_login:
            user_id = st.text_input("ID 또는 이메일", key="login_id")
            password = st.text_input("패스워드", type="password", key="login_pw")
            st.write("<br>", unsafe_allow_html=True)
            if st.button("로그인"):
                users_db = st.session_state['app_data']['users_db']
                if user_id in users_db and users_db[user_id] == password:
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = user_id
                    st.session_state['last_activity'] = datetime.now()
                    st.query_params["user_session"] = user_id
                    st.rerun()
                else: st.error("아이디가 존재하지 않거나 비밀번호가 틀렸습니다.")
                    
        with tab_signup:
            new_id = st.text_input("새 ID", key="signup_id")
            new_pw = st.text_input("새 패스워드", type="password", key="signup_pw")
            new_pw_check = st.text_input("패스워드 확인", type="password", key="signup_pw_chk")
            if st.button("계정 생성하기"):
                users_db = st.session_state['app_data']['users_db']
                if new_id in users_db: st.error("이미 사용 중인 아이디입니다.")
                elif new_pw != new_pw_check: st.error("비밀번호가 불일치합니다.")
                else:
                    st.session_state['app_data']['users_db'][new_id] = new_pw
                    save_data(st.session_state['app_data'])
                    st.success("계정 생성 완료! 로그인해주세요.")

# ==========================================
# 4. 메인 대시보드 화면
# ==========================================
def show_main_page():
    now = datetime.now()
    if now > st.session_state['last_activity'] + timedelta(minutes=AUTO_LOGOUT_MINUTES):
        st.query_params.clear()
        st.session_state['logged_in'] = False
        st.rerun()

    st.markdown("<style>.stApp { background-color: #f5f6f8; color: #333; } .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 15px;}</style>", unsafe_allow_html=True)

    col_title, col_ui = st.columns([7, 3])
    
    with col_title:
        st.markdown(f"### 공공 개발 산출물 저장소(공공 GitHub) 프로젝트 현황 - 환영합니다, **{st.session_state.get('user_id', '사용자')}**님!")
        if st.session_state['db_mode'] == "Google Sheets": st.caption("🟢 DB: 구글 스프레드시트 영구 보존 모드")
        else: st.caption("🟡 DB: 로컬 임시 저장 모드 (구글 시트 미연결)")
    
    with col_ui:
        ucol1, ucol2, ucol3 = st.columns([1, 1, 1])
        with ucol1:
            if st.button("로그아웃", use_container_width=True):
                st.query_params.clear()
                st.session_state['logged_in'] = False
                st.rerun()
        with ucol2:
            st.markdown(f"<div class='timer-display' id='realtime-timer'>--:--</div>", unsafe_allow_html=True)
            inject_timer_js()
        with ucol3:
            if st.button("연장", use_container_width=True):
                st.session_state['last_activity'] = datetime.now()
                st.rerun()

    repo_data = st.session_state['app_data']['repository']
    total_projects = len(repo_data)
    unique_authors = len(set([p['author'] for p in repo_data]))

    tab1, tab2 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소"])

    with tab1:
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: st.markdown(f"<div class='metric-card'><div style='font-size: 14px; color: #666; font-weight: bold;'>전체 프로젝트</div><div style='font-size: 32px; font-weight: bold; color: #111;'>{total_projects}</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='metric-card'><div style='font-size: 14px; color: #666; font-weight: bold;'>월간 프로젝트</div><div style='font-size: 32px; font-weight: bold; color: #111;'>{total_projects}</div></div>", unsafe_allow_html=True)
        with m3: st.markdown("<div class='metric-card'><div style='font-size: 14px; color: #666; font-weight: bold;'>전체 이슈</div><div style='font-size: 32px; font-weight: bold; color: #111;'>0</div></div>", unsafe_allow_html=True)
        with m4: st.markdown("<div class='metric-card'><div style='font-size: 14px; color: #666; font-weight: bold;'>Star</div><div style='font-size: 32px; font-weight: bold; color: #111;'>0</div></div>", unsafe_allow_html=True)
        with m5: st.markdown(f"<div class='metric-card'><div style='font-size: 14px; color: #666; font-weight: bold;'>프로젝트 담당자</div><div style='font-size: 32px; font-weight: bold; color: #111;'>{unique_authors}</div></div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("### 산출물 업로드 및 피드백")
        with st.expander("새로운 산출물(결과물) 업로드 하기", expanded=False):
            with st.form("upload_form", clear_on_submit=True):
                proj_name = st.text_input("프로젝트 명", placeholder="예: 자동 요약 봇")
                proj_desc = st.text_area("산출물 설명", placeholder="어떤 문제를 해결하는지 설명해주세요.")
                uploaded_file = st.file_uploader("산출물 파일 첨부", type=['zip', 'pdf', 'py', 'csv', 'txt', 'xlsx'])
                
                if st.form_submit_button("저장소에 배포하기"):
                    if proj_name and uploaded_file:
                        new_item = {
                            "id": len(repo_data) + 1,
                            "title": proj_name,
                            "desc": proj_desc,
                            "author": st.session_state.get('user_id', '익명'),
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "filename": uploaded_file.name,
                            "file_data": uploaded_file.read(),
                            "feedbacks": []
                        }
                        st.session_state['app_data']['repository'].append(new_item)
                        save_data(st.session_state['app_data'])
                        st.success("성공적으로 공유되었습니다.")
                        st.rerun()
                    else: st.error("프로젝트 명과 파일을 모두 첨부해주세요.")

        st.markdown("---")
        st.markdown("### 커뮤니티 저장소 현황")

        if not repo_data:
            st.info("아직 공유된 산출물이 없습니다.")
        else:
            for item in reversed(repo_data):
                with st.container():
                    col_info, col_action = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"#### 📦 {item['title']}")
                        st.markdown(f"**공유자:** {item['author']} | **등록일:** {item['date']}")
                        st.write(item['desc'])
                    with col_action:
                        # 파일 유실(서버 재부팅) 시 예외 처리
                        if item.get('file_data'):
                            st.download_button(label=f"💾 {item['filename']} 다운로드", data=item['file_data'], file_name=item['filename'], mime="application/octet-stream", key=f"dl_{item['id']}")
                        else:
                            st.button("🚫 다운로드 만료됨", disabled=True, key=f"dl_{item['id']}")
                    
                    if item.get('file_data'):
                        file_ext = item['filename'].split('.')[-1].lower()
                        if file_ext in ['py', 'txt', 'csv']:
                            with st.expander(f"👀 '{item['filename']}' 파일 내용 미리보기"):
                                try: st.code(item['file_data'].decode('utf-8'), language='python' if file_ext == 'py' else 'text')
                                except: st.error("텍스트로 미리볼 수 없는 인코딩입니다.")

                    with st.expander(f"💬 피드백 및 토론 ({len(item['feedbacks'])}건)"):
                        for fb in item['feedbacks']:
                            st.markdown(f"<div style='background-color:#f0f2f6; padding:10px; border-radius:5px; margin-bottom:5px;'><b style='color:#3b82f6;'>{fb['user']}</b> ({fb['time']}): {fb['text']}</div>", unsafe_allow_html=True)
                        
                        fb_input = st.text_input("의견을 남겨주세요", key=f"fb_in_{item['id']}")
                        if st.button("피드백 등록", key=f"fb_btn_{item['id']}"):
                            if fb_input:
                                item['feedbacks'].append({"user": st.session_state.get('user_id', '익명'), "time": datetime.now().strftime("%Y-%m-%d %H:%M"), "text": fb_input})
                                save_data(st.session_state['app_data'])
                                st.rerun()
                st.markdown("---")

    with st.sidebar:
        col_side1, col_side2, col_side3 = st.columns([1, 2, 1])
        with col_side2: st.image(LOGO_IMAGE, use_container_width=True)
        st.markdown("<h3 style='text-align:center;'>AI 서정 실험실</h3>", unsafe_allow_html=True)
        st.markdown("---")
        st.selectbox("분야", ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"])
        st.selectbox("정렬 기준", ["최근 활동순", "별점 높은순", "이슈 많은순"])
        st.text_input("검색어", placeholder="프로젝트 검색...")
        cb1, cb2 = st.columns(2)
        cb1.button("검색", use_container_width=True)
        cb2.button("초기화", use_container_width=True)
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<div style='background-color: #e6f0ff; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #cce0ff;'><h4 style='color: #0055ff; margin-bottom: 5px;'>AI 서정 실험실</h4><p style='font-size: 13px; color: #555;'>대학 직원이 현장의 불편을 AI로 해결하는 실험 공간</p><div style='font-size: 24px; padding: 10px 0; color: #0055ff; font-weight: bold;'>Data & AI</div><p style='font-size: 12px; font-weight: bold; color: #0055ff; margin-top: 10px;'>AI로 더 다정한 세상을 만들게요</p></div>", unsafe_allow_html=True)

if not st.session_state['logged_in']: show_login_page()
else: show_main_page()