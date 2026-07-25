import streamlit as st
import pandas as pd
import plotly.express as px
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

st.set_page_config(page_title="공공 개발 산출물 저장소", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 1. DB 연동 (구글 시트 & 로컬 하이브리드)
# ==========================================
def load_data():
    local_data = {"users_db": {"admin": "password1234"}, "repository": []}
    
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            local_data = pickle.load(f)
            
    st.session_state['db_mode'] = "Local File"
    
    try:
        from streamlit_gsheets import GSheetsConnection
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            st.session_state['db_mode'] = "Google Sheets"
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            try:
                users_df = conn.read(worksheet="Users", usecols=[0,1], ttl=0)
                if not users_df.empty:
                    users_df = users_df.dropna(subset=['ID'])
                    local_data['users_db'] = dict(zip(users_df['ID'].astype(str), users_df['Password'].astype(str)))
            except: pass
                
            try:
                repo_df = conn.read(worksheet="Repository", ttl=0)
                if not repo_df.empty:
                    repo_df = repo_df.dropna(subset=['id'])
                    sheet_repo = repo_df.to_dict('records')
                    
                    merged_repo = []
                    for s_item in sheet_repo:
                        try:
                            if pd.isna(s_item['feedbacks']): s_item['feedbacks'] = []
                            else: s_item['feedbacks'] = ast.literal_eval(str(s_item['feedbacks']))
                        except:
                            s_item['feedbacks'] = []
                            
                        matching_local = next((l for l in local_data['repository'] if str(l['id']) == str(s_item['id'])), None)
                        if matching_local and 'file_data' in matching_local:
                            s_item['file_data'] = matching_local['file_data']
                        else:
                            s_item['file_data'] = b''
                        
                        merged_repo.append(s_item)
                    local_data['repository'] = merged_repo
            except: pass
    except Exception as e:
        pass

    return local_data

def save_data(data):
    with open(DATA_FILE, "wb") as f:
        pickle.dump(data, f)
        
    if st.session_state.get('db_mode') == "Google Sheets":
        try:
            from streamlit_gsheets import GSheetsConnection
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            users_df = pd.DataFrame(list(data['users_db'].items()), columns=['ID', 'Password'])
            conn.update(worksheet="Users", data=users_df)
            
            if data['repository']:
                repo_df = pd.DataFrame(data['repository'])
                if 'file_data' in repo_df.columns:
                    repo_df = repo_df.drop(columns=['file_data'])
                repo_df['feedbacks'] = repo_df['feedbacks'].apply(lambda x: str(x))
                conn.update(worksheet="Repository", data=repo_df)
        except Exception as e:
            pass

if 'app_data' not in st.session_state:
    st.session_state['app_data'] = load_data()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

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
    .stApp { background-color: #f8fafc; color: #1e293b; }
    .metric-card { background-color: white; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); }
    .panel-card { background-color: white; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 15px; height: 100%; box-shadow: 0 1px 2px rgba(0,0,0,0.02); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 및 회원가입 화면
# ==========================================
def show_login_page():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("<br><br><br>", unsafe_allow_html=True)
        col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
        with col_logo2: st.image(LOGO_IMAGE, use_container_width=True)
            
        st.markdown("<h2 style='text-align: center; margin-top: 10px;'>공공 개발 산출물 저장소</h2>", unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)
        
        tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
        
        with tab_login:
            user_id = st.text_input("ID 또는 이메일", key="login_id")
            password = st.text_input("패스워드", type="password", key="login_pw")
            st.write("<br>", unsafe_allow_html=True)
            if st.button("로그인", use_container_width=True):
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
            if st.button("계정 생성하기", use_container_width=True):
                users_db = st.session_state['app_data']['users_db']
                if new_id in users_db: st.error("이미 사용 중인 아이디입니다.")
                elif new_pw != new_pw_check: st.error("비밀번호가 불일치합니다.")
                else:
                    st.session_state['app_data']['users_db'][new_id] = new_pw
                    save_data(st.session_state['app_data'])
                    st.success("계정 생성 완료. 로그인해 주세요.")

# ==========================================
# 4. 메인 대시보드 화면
# ==========================================
def show_main_page():
    now = datetime.now()
    if now > st.session_state['last_activity'] + timedelta(minutes=AUTO_LOGOUT_MINUTES):
        st.query_params.clear()
        st.session_state['logged_in'] = False
        st.rerun()

    col_title, col_ui = st.columns([6, 4])
    
    with col_title:
        st.markdown(f"### 공공 개발 산출물 저장소(공공 GitLab) 프로젝트 현황 - 환영합니다, **{st.session_state.get('user_id', '사용자')}**님")
    
    with col_ui:
        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1.2, 1])
        with ctrl_col1:
            if st.button("로그아웃", use_container_width=True):
                st.query_params.clear()
                st.session_state['logged_in'] = False
                st.rerun()
        with ctrl_col2:
            st.markdown(f"<div style='background-color:#475569; color:white; text-align:center; padding:8px 0; font-family:monospace; font-weight:bold; font-size:14px;' id='realtime-timer'>--:--</div>", unsafe_allow_html=True)
            inject_timer_js()
        with ctrl_col3:
            if st.button("연장", use_container_width=True):
                st.session_state['last_activity'] = datetime.now()
                st.rerun()

    repo_data = st.session_state['app_data']['repository']
    total_projects = len(repo_data)
    unique_authors = len(set([p['author'] for p in repo_data]))

    is_admin = (st.session_state.get('user_id') == 'admin')
    if is_admin:
        tab1, tab2, tab3 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소", "계정 관리"])
    else:
        tab1, tab2 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소"])

    # ---------------- 탭 1: 대시보드 현황 ----------------
    with tab1:
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: st.markdown(f"<div class='metric-card'><div style='font-size: 12px; color: #64748b; font-weight: bold;'>전체 프로젝트</div><div style='font-size: 26px; font-weight: bold; color: #0f172a;'>{total_projects}</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>공개 프로젝트 기준</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='metric-card'><div style='font-size: 12px; color: #64748b; font-weight: bold;'>월간 프로젝트</div><div style='font-size: 26px; font-weight: bold; color: #0f172a;'>{total_projects}</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>최근 30일 활동</div></div>", unsafe_allow_html=True)
        with m3: st.markdown("<div class='metric-card'><div style='font-size: 12px; color: #64748b; font-weight: bold;'>전체 이슈</div><div style='font-size: 26px; font-weight: bold; color: #0f172a;'>0</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>진행중 0 / 완료 0</div></div>", unsafe_allow_html=True)
        with m4: st.markdown("<div class='metric-card'><div style='font-size: 12px; color: #64748b; font-weight: bold;'>Star</div><div style='font-size: 26px; font-weight: bold; color: #0f172a;'>0</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>좋아요 사용자</div></div>", unsafe_allow_html=True)
        with m5: st.markdown(f"<div class='metric-card'><div style='font-size: 12px; color: #64748b; font-weight: bold;'>프로젝트 담당자</div><div style='font-size: 26px; font-weight: bold; color: #0f172a;'>{unique_authors}</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>참여 개발자 수</div></div>", unsafe_allow_html=True)

        st.write("<br>", unsafe_allow_html=True)

        chart_col1, chart_col2, chart_col3 = st.columns([5, 3, 2])

        with chart_col1:
            st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
            st.markdown("##### 프로젝트 활동 현황")
            if repo_data:
                dates = pd.date_range(end=datetime.today(), periods=7).strftime("%m-%d").tolist()
                trend_df = pd.DataFrame({
                    "일자": dates,
                    "커밋 수": [12, 18, 5, 25, 40, 30, total_projects * 5],
                    "업데이트된 프로젝트": [2, 4, 1, 6, 10, 8, total_projects]
                })
                fig = px.bar(trend_df, x="일자", y="커밋 수", title="", labels={'일자': '', '커밋 수': ''})
                fig.update_traces(marker_color='#3b82f6')
                fig.update_layout(height=240, margin=dict(l=20, r=20, t=10, b=20))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("시각화할 프로젝트 데이터가 부족합니다.")
            st.markdown("</div>", unsafe_allow_html=True)

        with chart_col2:
            st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
            st.markdown("##### 분야별 프로젝트 분포")
            pie_df = pd.DataFrame({
                "분야": ["공공행정", "재난안전", "보건복지", "기타"],
                "비율": [58.6, 20.7, 10.3, 10.4]
            })
            fig_pie = px.pie(pie_df, values='비율', names='분야', hole=0.6)
            fig_pie.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with chart_col3:
            st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
            st.markdown("##### 활동 요약 (최근 7일)")
            st.write("---")
            st.markdown(f"**커밋 수:** {total_projects * 4}건")
            st.markdown("**이슈 생성:** 0건")
            st.markdown(f"**업데이트된 프로젝트:** {total_projects}건")
            st.markdown("</div>", unsafe_allow_html=True)

        st.write("<br>", unsafe_allow_html=True)
        st.markdown("##### 최근 활동 프로젝트")
        
        if not repo_data:
            st.info("등록된 프로젝트가 없습니다.")
        else:
            cols = st.columns(min(len(repo_data), 4))
            for idx, item in enumerate(repo_data[-4:]):
                with cols[idx % len(cols)]:
                    st.markdown(f"""
                        <div style="background-color: white; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; height: 180px; display: flex; flex-direction: column; justify-content: space-between;">
                            <div>
                                <span style="font-size: 11px; color: #64748b;">공공행정 | {item['author']}</span>
                                <h6 style="margin: 5px 0; color: #0f172a; font-weight: bold;">{item['title']}</h6>
                                <p style="font-size: 12px; color: #475569; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">{item['desc']}</p>
                            </div>
                            <div style="font-size: 11px; color: #94a3b8; border-top: 1px solid #f1f5f9; padding-top: 8px;">
                                등록일: {item['date']}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

    # ---------------- 탭 2: 산출물 커뮤니티 및 저장소 ----------------
    with tab2:
        st.markdown("### 산출물 업로드 및 피드백")
        with st.expander("새로운 산출물(결과물) 업로드 하기", expanded=False):
            with st.form("upload_form", clear_on_submit=True):
                proj_name = st.text_input("프로젝트 명")
                proj_desc = st.text_area("산출물 설명")
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
                    else: st.error("프로젝트 명과 파일을 모두 첨부해 주세요.")

        st.markdown("---")
        st.markdown("### 커뮤니티 저장소 현황")

        if not repo_data:
            st.info("아직 공유된 산출물이 없습니다.")
        else:
            for item in reversed(repo_data):
                with st.container():
                    col_info, col_action = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"#### {item['title']}")
                        st.markdown(f"**공유자:** {item['author']} | **등록일:** {item['date']}")
                        st.write(item['desc'])
                    with col_action:
                        if item.get('file_data'):
                            st.download_button(label="파일 다운로드", data=item['file_data'], file_name=item['filename'], mime="application/octet-stream", key=f"dl_{item['id']}")
                        else:
                            st.button("다운로드 만료됨", disabled=True, key=f"dl_{item['id']}")
                    
                    current_user = st.session_state.get('user_id')
                    if current_user == item['author'] or current_user == 'admin':
                        with st.expander("산출물 관리 (수정/삭제)"):
                            with st.form(f"edit_form_{item['id']}"):
                                edit_title = st.text_input("프로젝트 명 수정", value=item['title'])
                                edit_desc = st.text_area("설명 수정", value=item['desc'])
                                c_col1, c_col2 = st.columns(2)
                                update_btn = c_col1.form_submit_button("내용 수정")
                                delete_btn = c_col2.form_submit_button("산출물 삭제")
                                
                                if update_btn:
                                    item['title'] = edit_title
                                    item['desc'] = edit_desc
                                    save_data(st.session_state['app_data'])
                                    st.success("수정되었습니다.")
                                    st.rerun()
                                if delete_btn:
                                    st.session_state['app_data']['repository'] = [p for p in repo_data if p['id'] != item['id']]
                                    save_data(st.session_state['app_data'])
                                    st.success("삭제되었습니다.")
                                    st.rerun()

                    if item.get('file_data'):
                        file_ext = item['filename'].split('.')[-1].lower()
                        if file_ext in ['py', 'txt', 'csv']:
                            with st.expander(f"파일 미리보기 ({item['filename']})"):
                                try: st.code(item['file_data'].decode('utf-8'), language='python' if file_ext == 'py' else 'text')
                                except: st.error("텍스트로 미리볼 수 없는 인코딩입니다.")

                    with st.expander(f"피드백 및 토론 ({len(item['feedbacks'])}건)"):
                        for fb in item['feedbacks']:
                            st.markdown(f"<div style='background-color:#f1f5f9; padding:8px; border-radius:4px; margin-bottom:5px;'><b style='color:#0f172a;'>{fb['user']}</b> ({fb['time']}): {fb['text']}</div>", unsafe_allow_html=True)
                        
                        fb_input = st.text_input("의견을 남겨주세요", key=f"fb_in_{item['id']}")
                        if st.button("피드백 등록", key=f"fb_btn_{item['id']}"):
                            if fb_input:
                                item['feedbacks'].append({"user": st.session_state.get('user_id', '익명'), "time": datetime.now().strftime("%Y-%m-%d %H:%M"), "text": fb_input})
                                save_data(st.session_state['app_data'])
                                st.rerun()
                st.markdown("---")

    # ---------------- 탭 3: 계정 관리 (관리자 전용) ----------------
    if is_admin:
        with tab3:
            st.markdown("### 시스템 계정 관리")
            st.caption("관리자(admin) 계정으로 접속하여 생성된 전체 사용자를 조회하고 관리할 수 있습니다.")
            
            users_db = st.session_state['app_data']['users_db']
            users_df = pd.DataFrame(list(users_db.items()), columns=['사용자 ID', '비밀번호'])
            st.dataframe(users_df, use_container_width=True, hide_index=True)
            
            st.markdown("#### 사용자 계정 삭제")
            target_user = st.selectbox("삭제할 사용자 선택", options=[u for u in users_db.keys() if u != 'admin'])
            if st.button("선택 계정 삭제"):
                if target_user in st.session_state['app_data']['users_db']:
                    del st.session_state['app_data']['users_db'][target_user]
                    save_data(st.session_state['app_data'])
                    st.success(f"사용자 [{target_user}] 계정이 삭제되었습니다.")
                    st.rerun()

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
    st.markdown("<div style='background-color: #f1f5f9; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #e2e8f0;'><h4 style='color: #0f172a; margin-bottom: 5px;'>AI 서정 실험실</h4><p style='font-size: 13px; color: #64748b;'>대학 직원이 현장의 불편을 AI로 해결하는 실험 공간</p><div style='font-size: 22px; padding: 10px 0; color: #2563eb; font-weight: bold;'>Data & AI</div><p style='font-size: 11px; font-weight: bold; color: #64748b; margin-top: 5px;'>AI로 더 다정한 세상을 만들게요</p></div>", unsafe_allow_html=True)

if not st.session_state['logged_in']:
    show_login_page()
else:
    show_main_page()