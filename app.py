import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pickle
import os

# ==========================================
# 0. 공통 설정
# ==========================================
LOGO_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/1/19/Emblem_of_South_Korea.svg"
DATA_FILE = "app_data.pkl"
AUTO_LOGOUT_MINUTES = 30  # 자동 로그아웃 시간 설정 (분)

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="공공 GitHub 저장소",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. 데이터베이스 연동 및 세션/URL 파라미터 관리
# ==========================================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            return pickle.load(f)
    return {"users_db": {"admin": "password1234"}, "repository": []}

def save_data(data):
    with open(DATA_FILE, "wb") as f:
        pickle.dump(data, f)

if 'app_data' not in st.session_state:
    st.session_state['app_data'] = load_data()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# [핵심] 새로고침(F5) 방어 로직: URL 파라미터에 저장된 세션 확인
if not st.session_state['logged_in']:
    if "user_session" in st.query_params:
        st.session_state['logged_in'] = True
        st.session_state['user_id'] = st.query_params["user_session"]
        st.session_state['last_activity'] = datetime.now()

# ==========================================
# 3. 로그인 및 회원가입 화면
# ==========================================
def show_login_page():
    st.markdown("""
        <style>
        .stApp { background-color: #121216; color: white; }
        div.stButton > button { background-color: #5c8ae6; color: white; border: none; width: 100%; border-radius: 5px; padding: 10px; }
        div.stButton > button:hover { background-color: #4a75c7; color: white; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("<br><br><br>", unsafe_allow_html=True)
        col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
        with col_logo2:
            st.image(LOGO_IMAGE, use_container_width=True)
            
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
                    # URL 파라미터에 로그인 정보 기록 (새로고침 방어)
                    st.query_params["user_session"] = user_id
                    st.rerun()
                else:
                    st.error("아이디가 존재하지 않거나 비밀번호가 틀렸습니다.")
                    
        with tab_signup:
            new_id = st.text_input("새 ID (사용할 아이디)", key="signup_id")
            new_pw = st.text_input("새 패스워드", type="password", key="signup_pw")
            new_pw_check = st.text_input("패스워드 확인", type="password", key="signup_pw_chk")
            
            if st.button("계정 생성하기"):
                users_db = st.session_state['app_data']['users_db']
                if not new_id or not new_pw:
                    st.warning("아이디와 비밀번호를 모두 입력해주세요.")
                elif new_id in users_db:
                    st.error("이미 사용 중인 아이디입니다.")
                elif new_pw != new_pw_check:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    st.session_state['app_data']['users_db'][new_id] = new_pw
                    save_data(st.session_state['app_data'])
                    st.success(f"'{new_id}' 계정 생성 완료! 로그인 탭에서 접속해주세요.")

# ==========================================
# 4. 메인 대시보드 화면
# ==========================================
def show_main_page():
    # --- 자동 로그아웃 시간 계산 로직 ---
    now = datetime.now()
    last_act = st.session_state.get('last_activity', now)
    elapsed = now - last_act
    remaining_time = timedelta(minutes=AUTO_LOGOUT_MINUTES) - elapsed

    if remaining_time.total_seconds() <= 0:
        st.query_params.clear() # 세션 만료 시 파라미터 삭제
        st.session_state['logged_in'] = False
        st.warning("세션이 만료되어 자동 로그아웃 되었습니다.")
        st.rerun()

    minutes, seconds = divmod(int(remaining_time.total_seconds()), 60)
    time_str = f"{minutes:02d}:{seconds:02d}"

    st.markdown("""
        <style>
        .stApp { background-color: #f5f6f8; color: #333; }
        .st-emotion-cache-1wmy9hl { background-color: white; }
        .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 15px;}
        .metric-title { font-size: 14px; color: #666; font-weight: bold; margin-bottom: 10px;}
        .metric-value { font-size: 32px; font-weight: bold; color: #111; }
        .metric-sub { font-size: 12px; color: #999; }
        .timer-box { background-color: #2b4c50; color: #a3e4d7; padding: 5px 15px; border-radius: 5px; font-weight: bold; font-family: monospace; font-size: 16px; display: inline-block; }
        </style>
    """, unsafe_allow_html=True)

    # --- 상단 헤더 & 로그아웃/연장 타이머 ---
    col_title, col_timer1, col_timer2, col_timer3 = st.columns([6, 1, 1.2, 1])
    
    with col_title:
        st.markdown(f"### 공공 개발 산출물 저장소(공공 GitHub) 프로젝트 현황 - 환영합니다, **{st.session_state.get('user_id', '사용자')}**님!")
    
    with col_timer1:
        if st.button("로그아웃", use_container_width=True):
            st.query_params.clear()
            st.session_state['logged_in'] = False
            st.rerun()
            
    with col_timer2:
        st.markdown(f"<div style='text-align: center;'><span class='timer-box'>{time_str}</span></div>", unsafe_allow_html=True)
        
    with col_timer3:
        if st.button("연장", use_container_width=True):
            st.session_state['last_activity'] = datetime.now()
            st.rerun()

    # --- 실시간 데이터 연동 계산 ---
    repo_data = st.session_state['app_data']['repository']
    total_projects = len(repo_data)
    unique_authors = len(set([p['author'] for p in repo_data]))

    tab1, tab2 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소"])

    # --- [TAB 1] 대시보드 현황 (데이터 연동 반영) ---
    with tab1:
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: st.markdown(f"<div class='metric-card'><div class='metric-title'>전체 프로젝트</div><div class='metric-value'>{total_projects}</div><div class='metric-sub'>공개 프로젝트 기준</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='metric-card'><div class='metric-title'>월간 프로젝트</div><div class='metric-value'>{total_projects}</div><div class='metric-sub'>최근 30일 활동</div></div>", unsafe_allow_html=True)
        with m3: st.markdown("<div class='metric-card'><div class='metric-title'>전체 이슈</div><div class='metric-value'>0</div><div class='metric-sub'>진행중 0 / 완료 0</div></div>", unsafe_allow_html=True)
        with m4: st.markdown("<div class='metric-card'><div class='metric-title'>Star</div><div class='metric-value'>0</div><div class='metric-sub'>좋아요(로그인 사용자)</div></div>", unsafe_allow_html=True)
        with m5: st.markdown(f"<div class='metric-card'><div class='metric-title'>프로젝트 담당자</div><div class='metric-value'>{unique_authors}</div><div class='metric-sub'>참여 개발자 수</div></div>", unsafe_allow_html=True)

        st.write("<br><b>최근 활동 프로젝트</b>", unsafe_allow_html=True)
        
        # 최근 업로드된 프로젝트 5개 렌더링 (없으면 빈칸 렌더링)
        recent_projects = list(reversed(repo_data))[:5]
        cols = st.columns(5)
        
        for i in range(5):
            with cols[i]:
                if i < len(recent_projects):
                    p = recent_projects[i]
                    st.markdown(f"""
                        <div style='background:white; padding:15px; border-radius:10px; height: 220px; border-top: 4px solid #3b82f6; box-shadow: 0 1px 3px rgba(0,0,0,0.1);'>
                            <div style='font-size:12px; color:#666;'>{p['author']} <span style='float:right; color:#3b82f6;'>활성</span></div>
                            <div style='font-size:16px; font-weight:bold; margin: 10px 0;'>{p['title']}</div>
                            <div style='font-size:13px; color:#555; height: 80px; overflow:hidden;'>{p['desc']}</div>
                            <div style='font-size:12px; color:#888; margin-top:10px;'>{p['date'][:10]} 등록</div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                        <div style='background:white; padding:15px; border-radius:10px; height: 220px; border-top: 4px solid #d1d5db; box-shadow: 0 1px 3px rgba(0,0,0,0.1);'>
                            <div style='font-size:12px; color:#999;'>대기중 <span style='float:right; color:#999;'>-</span></div>
                            <div style='font-size:16px; font-weight:bold; margin: 10px 0; color:#999;'>프로젝트 없음</div>
                            <div style='font-size:13px; color:#999; height: 80px; overflow:hidden;'>아직 등록된 프로젝트가 없습니다.</div>
                        </div>
                    """, unsafe_allow_html=True)

    # --- [TAB 2] 커뮤니티 및 저장소 (코드 미리보기 추가) ---
    with tab2:
        st.markdown("### 산출물 업로드 및 피드백")
        
        with st.expander("새로운 산출물(결과물) 업로드 하기", expanded=False):
            with st.form("upload_form", clear_on_submit=True):
                proj_name = st.text_input("프로젝트 명", placeholder="예: 자동 요약 봇")
                proj_desc = st.text_area("산출물 설명", placeholder="어떤 문제를 해결하는지 설명해주세요.")
                uploaded_file = st.file_uploader("산출물 파일 첨부", type=['zip', 'pdf', 'py', 'csv', 'txt'])
                
                if st.form_submit_button("저장소에 배포하기"):
                    if proj_name and uploaded_file:
                        file_data = uploaded_file.read()
                        new_item = {
                            "id": len(st.session_state['app_data']['repository']) + 1,
                            "title": proj_name,
                            "desc": proj_desc,
                            "author": st.session_state.get('user_id', '익명'),
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "filename": uploaded_file.name,
                            "file_data": file_data,
                            "feedbacks": []
                        }
                        st.session_state['app_data']['repository'].append(new_item)
                        save_data(st.session_state['app_data'])
                        st.success("성공적으로 저장소에 공유되었습니다.")
                        st.rerun() # 업로드 즉시 대시보드 반영을 위해 리런
                    else:
                        st.error("프로젝트 명과 파일을 모두 첨부해주세요.")

        st.markdown("---")
        st.markdown("### 커뮤니티 저장소 현황")

        if not repo_data:
            st.info("아직 공유된 산출물이 없습니다. 첫 번째 산출물을 업로드해 보세요.")
        else:
            for item in reversed(repo_data):
                with st.container():
                    col_info, col_action = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"#### {item['title']}")
                        st.markdown(f"**공유자:** {item['author']} | **등록일:** {item['date']}")
                        st.write(item['desc'])
                    with col_action:
                        st.download_button(
                            label=f"💾 {item['filename']} 다운로드",
                            data=item['file_data'],
                            file_name=item['filename'],
                            mime="application/octet-stream",
                            key=f"dl_{item['id']}"
                        )
                    
                    # [핵심] 코드/텍스트 파일 미리보기 기능
                    file_ext = item['filename'].split('.')[-1].lower()
                    if file_ext in ['py', 'txt', 'csv']:
                        with st.expander(f"👀 '{item['filename']}' 파일 내용 미리보기"):
                            try:
                                decoded_text = item['file_data'].decode('utf-8')
                                st.code(decoded_text, language='python' if file_ext == 'py' else 'text')
                            except Exception:
                                st.error("해당 파일은 텍스트 형식으로 미리볼 수 없는 인코딩입니다.")

                    # 피드백 섹션
                    with st.expander(f"💬 피드백 및 토론 ({len(item['feedbacks'])}건)"):
                        for fb in item['feedbacks']:
                            st.markdown(f"<div style='background-color:#f0f2f6; padding:10px; border-radius:5px; margin-bottom:5px;'>"
                                        f"<b style='color:#3b82f6;'>{fb['user']}</b> ({fb['time']}): {fb['text']}</div>", unsafe_allow_html=True)
                        
                        fb_input = st.text_input("의견을 남겨주세요", key=f"fb_in_{item['id']}")
                        if st.button("피드백 등록", key=f"fb_btn_{item['id']}"):
                            if fb_input:
                                item['feedbacks'].append({
                                    "user": st.session_state.get('user_id', '익명'),
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "text": fb_input
                                })
                                save_data(st.session_state['app_data'])
                                st.rerun()
                st.markdown("---")

    # --- 사이드바 ---
    with st.sidebar:
        col_side1, col_side2, col_side3 = st.columns([1, 2, 1])
        with col_side2:
            st.image(LOGO_IMAGE, use_container_width=True)
            
        st.markdown("<h3 style='text-align:center;'>AI 서정 실험실</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.selectbox("분야", ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"])
        st.selectbox("정렬 기준", ["최근 활동순", "별점 높은순", "이슈 많은순"])
        st.text_input("검색어", placeholder="프로젝트 검색...")
        
        cb1, cb2 = st.columns(2)
        cb1.button("검색", use_container_width=True)
        cb2.button("초기화", use_container_width=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='background-color: #e6f0ff; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #cce0ff;'>
                <h4 style='color: #0055ff; margin-bottom: 5px;'>AI 서정 실험실</h4>
                <p style='font-size: 13px; color: #555;'>대학 직원이 현장의 불편을 AI로 해결하는 실험 공간</p>
                <div style='font-size: 24px; padding: 10px 0; color: #0055ff; font-weight: bold;'>Data & AI</div>
                <p style='font-size: 12px; font-weight: bold; color: #0055ff; margin-top: 10px;'>AI로 더 다정한 세상을 만들게요</p>
            </div>
        """, unsafe_allow_html=True)

# ==========================================
# 5. 메인 라우팅
# ==========================================
if not st.session_state['logged_in']:
    show_login_page()
else:
    show_main_page()