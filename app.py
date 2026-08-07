import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import pickle
import os
import ast
import base64
import traceback
import math
import time
import streamlit.components.v1 as components

# ==========================================
# 0. 공통 설정
# ==========================================
LOGO_IMAGE = "sj_signature04.png"
DATA_FILE = "app_data.pkl"
AUTO_LOGOUT_MINUTES = 30
KST = timezone(timedelta(hours=9))
PAGE_SIZE = 10

st.set_page_config(page_title="교육혁신처 AI Creative Lab 산출물 저장소", layout="wide", initial_sidebar_state="expanded")


def now_kst():
    return datetime.now(KST)


def safe_show_logo(width=None, use_container_width=False):
    try:
        if os.path.exists(LOGO_IMAGE):
            if width:
                st.image(LOGO_IMAGE, width=width)
            else:
                st.image(LOGO_IMAGE, use_container_width=use_container_width)
        else:
            st.markdown(
                "<div style='text-align:center; padding:14px; border:1px dashed var(--border); "
                "border-radius:12px; color:var(--muted-foreground); font-size:12px;'>"
                "로고 이미지를 찾을 수 없습니다.<br>저장소에 파일을 업로드해 주세요."
                "</div>",
                unsafe_allow_html=True
            )
    except Exception as e:
        st.markdown(
            f"<div style='text-align:center; padding:14px; border:1px dashed var(--border); "
            f"border-radius:12px; color:var(--muted-foreground); font-size:12px;'>"
            f"로고 이미지를 불러오는 중 오류가 발생했습니다: {type(e).__name__}"
            f"</div>",
            unsafe_allow_html=True
        )


# ==========================================
# 1. DB 연동 (구글 시트 & 로컬 하이브리드)
# ==========================================
def load_data():
    local_data = {
        "users_db": {
            "admin": {"password": "password1234", "dept": "시스템관리자", "manager": "관리자", "approved": True, "role": "admin", "survey_completed": True}
        },
        "repository": [],
        "categories": ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"],
        "deleted_ids": [],
        "survey": []
    }

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            loaded = pickle.load(f)
            if isinstance(loaded, dict):
                local_data.update(loaded)

    if 'deleted_ids' not in local_data or local_data['deleted_ids'] is None:
        local_data['deleted_ids'] = []
    deleted_ids_set = set(local_data['deleted_ids'])

    if 'survey' not in local_data or local_data['survey'] is None:
        local_data['survey'] = []

    migrated_users = {}
    for uid, uval in local_data.get('users_db', {}).items():
        if uid in deleted_ids_set:
            continue
        if isinstance(uval, str):
            is_admin_account = (uid == "admin")
            migrated_users[uid] = {
                "password": uval,
                "dept": "시스템관리자" if is_admin_account else "",
                "manager": "관리자" if is_admin_account else "",
                "approved": True,
                "role": "admin" if is_admin_account else "user",
                "survey_completed": True if is_admin_account else False
            }
        elif isinstance(uval, dict):
            uval.setdefault("dept", "")
            uval.setdefault("manager", "")
            uval["approved"] = True
            uval.setdefault("role", "admin" if uid == "admin" else "user")
            uval.setdefault("survey_completed", True if uid == "admin" else False)
            if uid == "admin":
                uval["role"] = "admin"
                uval["survey_completed"] = True
            migrated_users[uid] = uval
    if "admin" not in migrated_users:
        migrated_users["admin"] = {"password": "password1234", "dept": "시스템관리자", "manager": "관리자", "approved": True, "role": "admin", "survey_completed": True}
    local_data['users_db'] = migrated_users

    for item in local_data.get('repository', []):
        if 'issues' not in item or item['issues'] is None:
            item['issues'] = []
        item.setdefault('completed_at', None)

    if 'timeline_log' not in local_data or local_data['timeline_log'] is None:
        local_data['timeline_log'] = []

    local_users_before_merge = dict(local_data['users_db'])
    local_repo_before_merge = list(local_data['repository'])
    local_categories_before_merge = list(local_data.get('categories', []))

    st.session_state['db_mode'] = "Local File"
    st.session_state['gsheets_debug_log'] = []
    st.session_state['gsheets_full_traceback'] = []

    def _log(msg, level="info"):
        st.session_state['gsheets_debug_log'].append((level, msg))

    def _fmt_err(e, tag):
        full_tb = traceback.format_exc()
        st.session_state['gsheets_full_traceback'].append((tag, full_tb))
        return f"[{type(e).__name__}] {str(e) if str(e) else '(메시지 없음, 아래 전체 traceback 확인)'}"

    try:
        from streamlit_gsheets import GSheetsConnection
        _log("streamlit_gsheets 패키지 import 성공")

        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            _log("st.secrets에 [connections.gsheets] 설정 발견 -> Google Sheets 모드로 전환 시도")
            st.session_state['db_mode'] = "Google Sheets"
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                _log("st.connection 객체 생성 성공")
            except Exception as e_conn:
                _log(f"[오류] st.connection 생성 자체가 실패했습니다: {_fmt_err(e_conn, 'connection_create')}", "error")
                conn = None

            if conn is not None:
                try:
                    users_df = conn.read(worksheet="Users", ttl=0)
                    _log(f"Users 시트 읽기 성공: {len(users_df)}행, 컬럼={list(users_df.columns)}")
                    required_cols = {'ID', 'Password'}
                    if not users_df.empty and required_cols.issubset(set(users_df.columns)):
                        users_df = users_df.dropna(subset=['ID'])
                        merged_users = {}
                        for _, row in users_df.iterrows():
                            uid = str(row['ID'])
                            if uid in deleted_ids_set:
                                continue
                            pw = str(row['Password'])
                            dept = str(row['Dept']) if 'Dept' in users_df.columns and pd.notna(row.get('Dept')) else ""
                            manager = str(row['Manager']) if 'Manager' in users_df.columns and pd.notna(row.get('Manager')) else ""
                            role_raw = str(row.get('Role')).strip().lower() if 'Role' in users_df.columns and pd.notna(row.get('Role')) else "user"
                            role = "admin" if role_raw == "admin" else "user"
                            approved = True
                            survey_completed = bool(row.get('SurveyCompleted', False)) if 'SurveyCompleted' in users_df.columns and pd.notna(row.get('SurveyCompleted')) else False
                            
                            if uid == "admin":
                                role = "admin"
                                survey_completed = True
                            merged_users[uid] = {"password": pw, "dept": dept, "manager": manager, "approved": approved, "role": role, "survey_completed": survey_completed}

                        for uid, uinfo in local_users_before_merge.items():
                            if uid in deleted_ids_set:
                                continue
                            if uid not in merged_users:
                                merged_users[uid] = uinfo
                            else:
                                merged_users[uid]["approved"] = True
                                if uinfo.get("role") == "admin":
                                    merged_users[uid]["role"] = "admin"

                        for uid in list(merged_users.keys()):
                            if uid in deleted_ids_set:
                                del merged_users[uid]
                        if "admin" not in merged_users:
                            merged_users["admin"] = {"password": "password1234", "dept": "시스템관리자", "manager": "관리자", "approved": True, "role": "admin", "survey_completed": True}
                        else:
                            merged_users["admin"]["approved"] = True
                            merged_users["admin"]["role"] = "admin"
                            merged_users["admin"]["survey_completed"] = True
                        local_data['users_db'] = merged_users
                        _log(f"Users 병합 완료: 총 {len(merged_users)}건 (승인 절차 폐지로 전원 승인 처리)")
                    else:
                        _log("[안내] Users 시트가 비어있거나 'ID'/'Password' 헤더가 없습니다. 로컬 기본값을 사용합니다.")
                except Exception as e_users:
                    _log(f"[오류] Users 시트 읽기 실패: {_fmt_err(e_users, 'users_read')}", "error")

                try:
                    repo_df = conn.read(worksheet="Repository", ttl=0)
                    _log(f"Repository 시트 읽기 성공: {len(repo_df)}행, 컬럼={list(repo_df.columns)}")

                    if not repo_df.empty and 'id' in repo_df.columns:
                        repo_df = repo_df.dropna(subset=['id'])
                        sheet_repo = repo_df.to_dict('records')

                        final_repo = []
                        for s_item in sheet_repo:
                            s_id_str = str(s_item['id'])
                            try:
                                if pd.isna(s_item.get('feedbacks')):
                                    s_item['feedbacks'] = []
                                else:
                                    s_item['feedbacks'] = ast.literal_eval(str(s_item['feedbacks']))
                            except Exception:
                                s_item['feedbacks'] = []

                            try:
                                if pd.isna(s_item.get('issues')):
                                    s_item['issues'] = []
                                else:
                                    s_item['issues'] = ast.literal_eval(str(s_item['issues']))
                            except Exception:
                                s_item['issues'] = []

                            if pd.isna(s_item.get('completed_at')) or str(s_item.get('completed_at')) in ('', 'None', 'nan'):
                                s_item['completed_at'] = None

                            matching_local = next((l for l in local_repo_before_merge if str(l['id']) == s_id_str), None)
                            if matching_local and 'file_data' in matching_local:
                                s_item['file_data'] = matching_local['file_data']
                            else:
                                s_item['file_data'] = b''

                            final_repo.append(s_item)

                        local_data['repository'] = final_repo
                        _log(f"Repository 로드 완료(시트 기준): 총 {len(final_repo)}건")
                    else:
                        local_data['repository'] = []
                except Exception as e_repo:
                    _log(f"[오류] Repository 시트 읽기 실패: {_fmt_err(e_repo, 'repo_read')}", "error")

                try:
                    cat_df = conn.read(worksheet="Categories", ttl=0)
                    if not cat_df.empty and 'category' in cat_df.columns:
                        cat_list = cat_df['category'].dropna().astype(str).tolist()
                        if "전체" not in cat_list:
                            cat_list.insert(0, "전체")
                        local_data['categories'] = cat_list
                    else:
                        local_data['categories'] = local_categories_before_merge
                except Exception as e_cat:
                    local_data['categories'] = local_categories_before_merge
                    
                try:
                    survey_df = conn.read(worksheet="survey", ttl=0)
                    if not survey_df.empty:
                        local_data['survey'] = survey_df.to_dict('records')
                    else:
                        local_data['survey'] = []
                except Exception as e_sv:
                    local_data['survey'] = local_data.get('survey', [])
                    _log(f"[안내] survey 시트를 찾을 수 없습니다: {_fmt_err(e_sv, 'survey_read')}", "warn")

                try:
                    timeline_df = conn.read(worksheet="TimelineLog", ttl=0)
                    if not timeline_df.empty:
                        local_data['timeline_log'] = timeline_df.to_dict('records')
                except Exception as e_tl:
                    pass
        else:
            _log("st.secrets에 [connections.gsheets] 설정이 없습니다 -> Local File 모드로 동작합니다.")
    except Exception as e:
        _log(f"[오류] Google Sheets 연동 초기화 자체가 실패했습니다: {_fmt_err(e, 'init')}", "error")

    return local_data


def save_data(data):
    with open(DATA_FILE, "wb") as f:
        pickle.dump(data, f)

    if st.session_state.get('db_mode') == "Google Sheets":
        core_save_failed = False
        try:
            from streamlit_gsheets import GSheetsConnection
            conn = st.connection("gsheets", type=GSheetsConnection)

            deleted_ids_set = set(data.get('deleted_ids', []))

            try:
                latest_users_df = conn.read(worksheet="Users", ttl=0)
            except Exception:
                latest_users_df = pd.DataFrame(columns=["ID", "Password", "Dept", "Manager", "Approved", "Role", "SurveyCompleted"])

            latest_users = {}
            if not latest_users_df.empty and {'ID', 'Password'}.issubset(set(latest_users_df.columns)):
                for _, row in latest_users_df.dropna(subset=['ID']).iterrows():
                    uid = str(row['ID'])
                    if uid in deleted_ids_set:
                        continue
                    role_raw = str(row.get('Role')).strip().lower() if 'Role' in latest_users_df.columns and pd.notna(row.get('Role')) else "user"
                    latest_users[uid] = {
                        "password": str(row['Password']),
                        "dept": str(row['Dept']) if 'Dept' in latest_users_df.columns and pd.notna(row.get('Dept')) else "",
                        "manager": str(row['Manager']) if 'Manager' in latest_users_df.columns and pd.notna(row.get('Manager')) else "",
                        "approved": True,
                        "role": "admin" if (role_raw == "admin" or uid == "admin") else "user",
                        "survey_completed": bool(row.get('SurveyCompleted', False)) if 'SurveyCompleted' in latest_users_df.columns and pd.notna(row.get('SurveyCompleted')) else False
                    }

            final_users = dict(latest_users)
            for uid, uinfo in data['users_db'].items():
                if uid in deleted_ids_set:
                    continue
                final_users[uid] = uinfo
            for uid in list(final_users.keys()):
                if uid in deleted_ids_set:
                    del final_users[uid]
            if "admin" not in final_users:
                final_users["admin"] = {"password": "password1234", "dept": "시스템관리자", "manager": "관리자", "approved": True, "role": "admin", "survey_completed": True}
            else:
                final_users["admin"]["role"] = "admin"
                final_users["admin"]["approved"] = True
                final_users["admin"]["survey_completed"] = True

            data['users_db'] = final_users

            users_rows = []
            for uid, uinfo in final_users.items():
                users_rows.append({
                    "ID": uid,
                    "Password": uinfo.get("password", ""),
                    "Dept": uinfo.get("dept", ""),
                    "Manager": uinfo.get("manager", ""),
                    "Approved": bool(uinfo.get("approved", True)),
                    "Role": uinfo.get("role", "user"),
                    "SurveyCompleted": bool(uinfo.get("survey_completed", False))
                })
            users_df = pd.DataFrame(users_rows, columns=["ID", "Password", "Dept", "Manager", "Approved", "Role", "SurveyCompleted"])

            try:
                conn.update(worksheet="Users", data=users_df)
            except Exception as e_u:
                core_save_failed = True
                raise e_u

            if data['repository']:
                repo_df = pd.DataFrame(data['repository'])
                if 'file_data' in repo_df.columns:
                    repo_df = repo_df.drop(columns=['file_data'])
                repo_df['feedbacks'] = repo_df['feedbacks'].apply(lambda x: str(x))
                if 'issues' in repo_df.columns:
                    repo_df['issues'] = repo_df['issues'].apply(lambda x: str(x))
                if 'completed_at' not in repo_df.columns:
                    repo_df['completed_at'] = None
                try:
                    conn.update(worksheet="Repository", data=repo_df)
                except Exception as e_r:
                    core_save_failed = True
                    raise e_r
            else:
                empty_df = pd.DataFrame(columns=['id', 'title', 'category', 'desc', 'author', 'date', 'filename', 'feedbacks', 'issues', 'completed_at'])
                try:
                    conn.update(worksheet="Repository", data=empty_df)
                except Exception as e_r2:
                    core_save_failed = True
                    raise e_r2

            cat_list = data.get('categories', [])
            cat_df = pd.DataFrame({"category": cat_list})
            try:
                conn.update(worksheet="Categories", data=cat_df)
            except Exception as e_c:
                core_save_failed = True
                raise e_c

            try:
                if data.get('survey'):
                    survey_df = pd.DataFrame(data['survey'])
                else:
                    survey_df = pd.DataFrame(columns=['부서명', '담당자 성명', '업무명', '관리 매체', '주 사용자', '업무주기', '1회 소요시간', '연계 부서', '개선 필요사항', '제출일', 'User_ID'])
                conn.update(worksheet="survey", data=survey_df)
            except Exception as e_sv:
                core_save_failed = True
                raise e_sv

            try:
                if data.get('timeline_log'):
                    timeline_df = pd.DataFrame(data['timeline_log'])
                else:
                    timeline_df = pd.DataFrame(columns=['id', 'title', 'category', 'author', 'started_at', 'completed_at', 'duration_hours'])
                conn.update(worksheet="TimelineLog", data=timeline_df)
            except Exception as e_tl:
                pass

            st.session_state['last_save_status'] = "success"
        except Exception as e:
            full_tb = traceback.format_exc()
            st.session_state.setdefault('gsheets_full_traceback', []).append(("save_data", full_tb))
            err_txt = f"[{type(e).__name__}] {str(e) if str(e) else '(메시지 없음)'}"
            st.session_state.setdefault('gsheets_debug_log', []).append(("error", f"[오류] save_data 중 Google Sheets 쓰기 실패: {err_txt}"))
            if core_save_failed:
                st.session_state['last_save_status'] = "fail"
                st.error(f"[주의] 구글 시트 저장에 실패했습니다! 변경사항이 시트에 반영되지 않았을 수 있습니다. 오류: {err_txt}")
            else:
                st.session_state['last_save_status'] = "success"
    else:
        st.session_state['last_save_status'] = "local_only"


if 'app_data' not in st.session_state:
    st.session_state['app_data'] = load_data()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if 'filter_reset_counter' not in st.session_state:
    st.session_state['filter_reset_counter'] = 0

_reset_suffix = st.session_state['filter_reset_counter']
_cat_key = f"filter_category_{_reset_suffix}"
_sort_key = f"filter_sort_{_reset_suffix}"
_kw_key = f"filter_keyword_{_reset_suffix}"

if 'repo_page' not in st.session_state:
    st.session_state['repo_page'] = 1
if 'dashboard_page' not in st.session_state:
    st.session_state['dashboard_page'] = 1

if 'pending_signup' not in st.session_state:
    st.session_state['pending_signup'] = None
if 'show_signup_confirm' not in st.session_state:
    st.session_state['show_signup_confirm'] = False


def get_display_name(user_id):
    users_db = st.session_state['app_data'].get('users_db', {})
    uinfo = users_db.get(user_id, {})
    dept = (uinfo.get('dept') or '').strip()
    manager = (uinfo.get('manager') or '').strip()
    if manager:
        return manager
    elif dept:
        return dept
    else:
        return user_id


def get_user_dept(user_id):
    users_db = st.session_state['app_data'].get('users_db', {})
    uinfo = users_db.get(user_id, {})
    dept = (uinfo.get('dept') or '').strip()
    return dept if dept else "기타"


def is_user_admin(user_id):
    if user_id == 'admin':
        return True
    users_db = st.session_state['app_data'].get('users_db', {})
    uinfo = users_db.get(user_id, {})
    return uinfo.get('role') == 'admin'


def ensure_category_exists(dept_name):
    cats = st.session_state['app_data'].get('categories', [])
    if dept_name and dept_name not in cats:
        cats.append(dept_name)
        st.session_state['app_data']['categories'] = cats


def record_timeline_completion(item):
    try:
        started = datetime.strptime(item['date'], "%Y-%m-%d %H:%M")
    except Exception:
        started = None
    completed = now_kst().replace(tzinfo=None)

    duration_hours = None
    if started is not None:
        duration_hours = round((completed - started).total_seconds() / 3600, 1)

    st.session_state['app_data'].setdefault('timeline_log', []).append({
        "id": item['id'],
        "title": item['title'],
        "category": item.get('category', '일반'),
        "author": item.get('author', ''),
        "started_at": item['date'],
        "completed_at": completed.strftime("%Y-%m-%d %H:%M"),
        "duration_hours": duration_hours
    })


def finalize_signup(pending):
    st.session_state['app_data']['users_db'][pending['id']] = {
        "password": pending['pw'],
        "dept": pending['dept'],
        "manager": pending['manager'],
        "approved": True,
        "role": "user",
        "survey_completed": False
    }
    if pending['id'] in st.session_state['app_data'].get('deleted_ids', []):
        st.session_state['app_data']['deleted_ids'].remove(pending['id'])
    ensure_category_exists(pending['dept'])
    save_data(st.session_state['app_data'])
    return st.session_state.get('last_save_status') != "fail"


# ==========================================
# 2. 커스텀 CSS & 자바스크립트 타이머
# ==========================================
def inject_timer_js():
    if 'last_activity' not in st.session_state:
        return
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


# ==========================================
# 2-1. 디자인 토큰 & 전역 스타일
# ==========================================
def inject_design_system():
    st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --background: #FFFFFF;
        --foreground: #0F172A;
        --muted: #F1F5F9;
        --muted-foreground: #64748B;
        --accent: #0052FF;
        --accent-secondary: #4D7CFF;
        --accent-foreground: #FFFFFF;
        --border: #E2E8F0;
        --card: #FFFFFF;
        --ring: #0052FF;

        --font-display: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        --font-body: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        --font-mono: 'JetBrains Mono', 'Pretendard', monospace;

        --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
        --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
        --shadow-lg: 0 10px 15px rgba(0,0,0,0.08);
        --shadow-xl: 0 20px 25px rgba(0,0,0,0.1);
        --shadow-accent: 0 4px 14px rgba(0,82,255,0.25);
        --shadow-accent-lg: 0 8px 24px rgba(0,82,255,0.35);
    }

    html, body, .stApp, [class*="css"] {
        font-family: var(--font-body) !important;
    }

    html {
        background-color: var(--background) !important;
    }
    html::before {
        content: "";
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        z-index: -1;
        background-image:
            radial-gradient(circle at 15% 20%, rgba(0,82,255,0.07) 0%, transparent 45%),
            radial-gradient(circle at 85% 30%, rgba(77,124,255,0.07) 0%, transparent 45%),
            radial-gradient(circle at 50% 85%, rgba(0,82,255,0.05) 0%, transparent 50%);
        background-repeat: no-repeat;
        background-size: 200% 200%;
        animation: bgFloat 22s ease-in-out infinite;
    }
    @keyframes bgFloat {
        0%   { background-position: 0% 0%, 100% 0%, 50% 100%; }
        50%  { background-position: 30% 30%, 70% 40%, 60% 70%; }
        100% { background-position: 0% 0%, 100% 0%, 50% 100%; }
    }

    .stApp {
        color: var(--foreground);
        background-color: transparent !important;
    }
    [data-testid="stSidebar"] {
        background-color: transparent !important;
    }
    [data-testid="stSidebar"] > div {
        background-color: transparent !important;
    }
    [data-testid="stHeader"] {
        background-color: transparent !important;
    }

    h1, h2, h3 {
        font-family: var(--font-display) !important;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: var(--foreground);
    }
    h4, h5, h6 {
        font-family: var(--font-display) !important;
        font-weight: 700;
        letter-spacing: -0.01em;
    }
    code, .mono-label {
        font-family: var(--font-mono) !important;
    }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 8px; }

    .gradient-text {
        background: linear-gradient(to right, var(--accent), var(--accent-secondary));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        display: inline-block;
    }

    .metric-card {
        background-color: var(--card);
        padding: 20px;
        border-radius: 16px;
        border: 1px solid var(--border);
        margin-bottom: 15px;
        box-shadow: var(--shadow-md);
        transition: box-shadow 0.3s ease-out, transform 0.3s ease-out;
    }
    .metric-card:hover {
        box-shadow: var(--shadow-lg);
        transform: translateY(-3px);
    }
    .metric-card .label { font-size: 12px; color: var(--muted-foreground); font-weight: bold; }
    .metric-card .value { font-size: 28px; font-weight: 800; color: var(--foreground); }
    .metric-card .sub { font-size: 11px; color: var(--muted-foreground); margin-top: 4px; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px !important;
        box-shadow: var(--shadow-md);
        transition: box-shadow 0.3s ease-out;
        background-color: var(--card) !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: var(--shadow-lg);
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.login-hero-inner) {
        border-radius: 24px !important;
        box-shadow: var(--shadow-xl) !important;
        padding: 12px 24px 24px 24px !important;
        animation: fadeInUp 0.7s ease-out;
        margin-top: 24px;
        background-color: var(--card) !important;
    }
    .login-hero-inner { position: relative; }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.repo-card-inner) {
        border-radius: 18px !important;
        box-shadow: var(--shadow-sm) !important;
        padding: 20px 22px !important;
        margin-bottom: 18px;
        animation: fadeInUp 0.5s ease-out;
        border: 1px solid var(--border) !important;
        transition: box-shadow 0.25s ease-out, transform 0.25s ease-out;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.repo-card-inner):hover {
        box-shadow: var(--shadow-accent) !important;
        transform: translateY(-2px);
    }
    .repo-card-inner { position: relative; }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.board-wrapper-marker) {
        border-radius: 16px !important;
        box-shadow: var(--shadow-sm) !important;
        padding: 18px 20px !important;
        border: 1px solid var(--border) !important;
        background-color: var(--card) !important;
    }
    .board-wrapper-marker { position: relative; }

    .repo-title-row {
        display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
        margin-bottom: 10px;
    }
    .repo-title { font-size: 19px; font-weight: 800; color: var(--foreground); margin: 0; }

    .repo-meta-row {
        display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
        margin: 0 0 12px 0;
    }
    .repo-cat-badge {
        font-family: var(--font-mono); font-size: 11px; color: var(--accent);
        background: rgba(0,82,255,0.08); padding: 3px 10px; border-radius: 999px;
        border: 1px solid rgba(0,82,255,0.2);
    }
    .repo-author-badge {
        font-size: 12px; color: var(--muted-foreground);
    }
    .repo-desc { font-size: 13px; color: var(--muted-foreground); margin: 4px 0 4px 0; }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }

    div[data-testid="stImage"] {
        background: transparent !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    div[data-testid="stImage"] img {
        display: block;
        margin: 0 auto;
        background: transparent !important;
    }

    #realtime-timer-badge {
        background: linear-gradient(135deg, var(--foreground), #1e293b);
        color: white;
        text-align: center;
        padding: 8px 0;
        font-family: var(--font-mono);
        font-weight: 600;
        font-size: 13px;
        border-radius: 8px;
        box-shadow: var(--shadow-sm);
        letter-spacing: 0.05em;
    }

    .sidebar-brand-card {
        background: linear-gradient(160deg, var(--muted), var(--card));
        padding: 22px;
        border-radius: 16px;
        text-align: center;
        border: 1px solid var(--border);
        box-shadow: var(--shadow-sm);
    }
    .sidebar-brand-card .tag {
        font-family: var(--font-mono);
        font-size: 18px;
        font-weight: 700;
        padding: 8px 0;
        background: linear-gradient(to right, var(--accent), var(--accent-secondary));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }

    .issue-badge-open {
        display: inline-block; font-size: 11px; font-family: var(--font-mono);
        background: rgba(234,88,12,0.1); color: #C2410C; border: 1px solid rgba(234,88,12,0.3);
        padding: 2px 10px; border-radius: 999px;
    }
    .issue-badge-done {
        display: inline-block; font-size: 11px; font-family: var(--font-mono);
        background: rgba(22,163,74,0.1); color: #15803D; border: 1px solid rgba(22,163,74,0.3);
        padding: 2px 10px; border-radius: 999px;
    }
    .role-badge-admin {
        display: inline-block; font-size: 11px; font-family: var(--font-mono);
        background: rgba(0,82,255,0.1); color: var(--accent); border: 1px solid rgba(0,82,255,0.3);
        padding: 2px 10px; border-radius: 999px;
    }
    .role-badge-user {
        display: inline-block; font-size: 11px; font-family: var(--font-mono);
        background: var(--muted); color: var(--muted-foreground); border: 1px solid var(--border);
        padding: 2px 10px; border-radius: 999px;
    }
    .proj-status-progress {
        display: inline-block; font-size: 11px; font-family: var(--font-mono);
        background: rgba(234,88,12,0.1); color: #C2410C; border: 1px solid rgba(234,88,12,0.3);
        padding: 2px 10px; border-radius: 999px; white-space: nowrap;
    }
    .proj-status-done {
        display: inline-block; font-size: 11px; font-family: var(--font-mono);
        background: rgba(22,163,74,0.1); color: #15803D; border: 1px solid rgba(22,163,74,0.3);
        padding: 2px 10px; border-radius: 999px; white-space: nowrap;
    }

    .confirm-row {
        display: flex; justify-content: space-between; padding: 10px 0;
        border-bottom: 1px solid var(--border); font-size: 14px;
    }
    .confirm-row .k { color: var(--muted-foreground); font-weight: 600; }
    .confirm-row .v { color: var(--foreground); font-weight: 700; }

    div[data-testid="stButton"] > button {
        border-radius: 10px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease-out !important;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-1px);
        color: var(--accent) !important;
    }
    div[data-testid="stButton"] > button:active {
        transform: scale(0.98);
    }
    div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(to right, var(--accent), var(--accent-secondary)) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease-out !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        filter: brightness(1.08);
        box-shadow: var(--shadow-accent-lg);
        transform: translateY(-1px);
    }
    div[data-testid="stFormSubmitButton"] > button:active {
        transform: scale(0.98);
    }
    div[data-baseweb="tab-list"] { gap: 6px; }
    button[data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        font-weight: 500;
    }
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {
        border-radius: 10px !important;
        border: 1px solid var(--border) !important;
        background-color: var(--card) !important;
        color: var(--foreground) !important;
    }
    div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px rgba(0,82,255,0.25) !important;
    }
    div[data-testid="stTextInput"] input::placeholder, div[data-testid="stTextArea"] textarea::placeholder {
        color: var(--muted-foreground) !important;
        opacity: 0.7 !important;
    }
    hr { border-color: var(--border) !important; }

    .board-table { width: 100%; border-collapse: collapse; background-color: var(--card); }
    .board-table th {
        text-align: left; font-size: 12px; color: var(--muted-foreground);
        border-bottom: 2px solid var(--border); padding: 10px 8px;
        font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.05em;
    }
    .board-table td {
        padding: 12px 8px; border-bottom: 1px solid var(--border); font-size: 14px; color: var(--foreground);
        vertical-align: middle;
    }
    .board-table tr:hover td { background-color: var(--muted); }
    .board-dept-badge {
        font-family: var(--font-mono); font-size: 11px; color: var(--accent);
        background: rgba(0,82,255,0.08); padding: 2px 8px; border-radius: 999px;
        border: 1px solid rgba(0,82,255,0.2); white-space: nowrap;
    }
    </style>
    """, unsafe_allow_html=True)


inject_design_system()


# ==========================================
# 2-2. 회원가입 확인 모달
# ==========================================
def _render_signup_confirm_body():
    pending = st.session_state.get('pending_signup')
    if not pending:
        return

    st.markdown("입력하신 회원가입 정보가 맞는지 다시 한번 확인해 주세요.")
    st.write("")
    st.markdown(f"""
        <div class='confirm-row'><span class='k'>부서명</span><span class='v'>{pending['dept']}</span></div>
        <div class='confirm-row'><span class='k'>담당자명</span><span class='v'>{pending['manager']}</span></div>
        <div class='confirm-row'><span class='k'>아이디</span><span class='v'>{pending['id']}</span></div>
    """, unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("다시 입력하기", key="signup_confirm_cancel", use_container_width=True):
            st.session_state['pending_signup'] = None
            st.session_state['show_signup_confirm'] = False
            st.rerun()
    with c2:
        if st.button("완료", key="signup_confirm_done", use_container_width=True, type="primary"):
            with st.spinner("계정을 안전하게 생성하고 있습니다. 잠시만 기다려주세요..."):
                time.sleep(1.5)
                ok = finalize_signup(pending)
            
            st.session_state['pending_signup'] = None
            st.session_state['show_signup_confirm'] = False
            if ok:
                st.session_state['signup_success_msg'] = f"[{pending['id']}] 계정이 생성되었습니다. 바로 로그인하실 수 있습니다."
            st.rerun()


if hasattr(st, "dialog"):
    @st.dialog("회원가입 정보 확인")
    def show_signup_confirm_dialog():
        _render_signup_confirm_body()
elif hasattr(st, "experimental_dialog"):
    @st.experimental_dialog("회원가입 정보 확인")
    def show_signup_confirm_dialog():
        _render_signup_confirm_body()
else:
    def show_signup_confirm_dialog():
        st.markdown("---")
        with st.container(border=True):
            st.markdown("#### 회원가입 정보 확인")
            _render_signup_confirm_body()


# ==========================================
# 3. 로그인 및 회원가입 화면
# ==========================================
def show_login_page():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<div class='login-hero-inner'>", unsafe_allow_html=True)

            _, logo_col, _ = st.columns([1, 1.2, 1])
            with logo_col:
                safe_show_logo(width=200)

            st.markdown("""
                <div style='text-align:center; margin-top:14px;'>
                    <h2 style='text-align: center; margin-top: 4px;'>
                        교육혁신처 AI Creative Lab <span class='gradient-text'>산출물 저장소</span>
                    </h2>
                    <p style='text-align:center; color:var(--muted-foreground); font-size:14px; margin-top:-6px;'>
                        대학 구성원의 개발 산출물을 안전하게 공유하고 관리하세요
                    </p>
                </div>
            """, unsafe_allow_html=True)
            st.write("<br>", unsafe_allow_html=True)

            tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

            with tab_login:
                with st.form("login_form"):
                    user_id = st.text_input("ID 또는 이메일", key="login_id", placeholder="예: hongildong")
                    password = st.text_input("패스워드", type="password", key="login_pw", placeholder="비밀번호를 입력하세요")
                    st.write("<br>", unsafe_allow_html=True)
                    login_submit = st.form_submit_button("로그인", use_container_width=True)

                if login_submit:
                    users_db = st.session_state['app_data']['users_db']
                    user_info = users_db.get(user_id)
                    if user_info is None or user_info.get("password") != password:
                        st.error("아이디가 존재하지 않거나 비밀번호가 틀렸습니다.")
                    elif not user_info.get("approved", True):
                        st.warning("아직 관리자 승인이 완료되지 않은 계정입니다. 관리자에게 문의해 주세요.")
                    else:
                        st.session_state['logged_in'] = True
                        st.session_state['user_id'] = user_id
                        st.session_state['last_activity'] = now_kst()
                        st.rerun()

            with tab_signup:
                if st.session_state.get('signup_success_msg'):
                    st.success(st.session_state['signup_success_msg'])
                    st.session_state['signup_success_msg'] = None

                with st.form("signup_form"):
                    new_dept = st.text_input("부서명", key="signup_dept", placeholder="예: 교육혁신처")
                    new_manager = st.text_input("담당자명", key="signup_manager", placeholder="예: 홍길동")
                    new_id = st.text_input("새 ID", key="signup_id", placeholder="예: hongildong01")
                    new_pw = st.text_input("새 패스워드", type="password", key="signup_pw", placeholder="영문/숫자 조합 8자 이상 권장")
                    new_pw_check = st.text_input("패스워드 확인", type="password", key="signup_pw_chk", placeholder="비밀번호를 한번 더 입력하세요")
                    signup_submit = st.form_submit_button("계정 생성하기", use_container_width=True)

                if signup_submit:
                    users_db = st.session_state['app_data']['users_db']
                    if not new_dept.strip() or not new_manager.strip() or not new_id.strip() or not new_pw.strip():
                        st.error("부서명, 담당자명, 아이디, 비밀번호는 모두 필수 입력 항목입니다.")
                    elif new_id in users_db:
                        st.error("이미 사용 중인 아이디입니다.")
                    elif new_pw != new_pw_check:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        st.session_state['pending_signup'] = {
                            "dept": new_dept.strip(),
                            "manager": new_manager.strip(),
                            "id": new_id.strip(),
                            "pw": new_pw
                        }
                        st.session_state['show_signup_confirm'] = True
                        st.rerun()

    if st.session_state.get('show_signup_confirm') and st.session_state.get('pending_signup'):
        show_signup_confirm_dialog()


# ==========================================
# 3-1. 부서별 자동화 현황조사 팝업 및 폼 화면
# ==========================================
def _render_survey_success_body():
    st.markdown("제출이 정상적으로 완료되었습니다.<br><br>보내주신 내용을 꼼꼼히 검토하여 개선 업무를 선정한 뒤, 담당자 1:1 미팅 일정을 메신저를 통해 개별 안내해 드릴 예정입니다.", unsafe_allow_html=True)
    st.write("")
    if st.button("확인하였습니다", use_container_width=True, type="primary"):
        st.session_state['show_survey_success'] = False
        
        # 확인 버튼 클릭 시 프로덕트 투어 플래그를 활성화하여 다음 화면에서 실행되도록 트리거
        st.session_state['tour_trigger'] = True
        st.rerun()

if hasattr(st, "dialog"):
    @st.dialog("제출 완료 안내")
    def show_survey_success_dialog():
        _render_survey_success_body()
elif hasattr(st, "experimental_dialog"):
    @st.experimental_dialog("제출 완료 안내")
    def show_survey_success_dialog():
        _render_survey_success_body()
else:
    def show_survey_success_dialog():
        st.markdown("---")
        with st.container(border=True):
            st.markdown("#### 제출 완료 안내")
            _render_survey_success_body()


def show_survey_page():
    user_id = st.session_state['user_id']
    users_db = st.session_state['app_data'].get('users_db', {})
    uinfo = users_db.get(user_id, {})

    st.markdown("### 부서별 자동화 대상 업무 현황조사")
    st.markdown("""
    <div style='background-color: #FFF3CD; padding: 15px; border-radius: 8px; border: 1px solid #FFEEBA; margin-bottom: 20px; color: #856404;'>
        <b>1. 단순반복성 업무나 자동화가 필요한 업무를 중심으로 작성해 주시기 바랍니다.</b><br>
        ※ 작성 관련 문의: 원격교육지원센터 임현기(내선5203)
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("survey_form"):
        c1, c2 = st.columns(2)
        with c1:
            dept = st.text_input("부서명", value=uinfo.get('dept', ''))
        with c2:
            manager = st.text_input("담당자 성명", value=uinfo.get('manager', ''))

        task_name = st.text_input("업무명", placeholder="예: 멀티스튜디오 예약관리")
        media = st.text_input("관리 매체 (통합정보시스템, 별도 엑셀관리 등)", placeholder="예: 별도 엑셀대장 관리")

        c3, c4 = st.columns(2)
        with c3:
            main_user = st.text_input("주 사용자", placeholder="예: 담당직원 및 각 학과 조교")
        with c4:
            freq = st.text_input("업무주기 (주당)", placeholder="예: 주 3회 이상")

        c5, c6 = st.columns(2)
        with c5:
            time_spent = st.text_input("1회 소요시간", placeholder="예: 30분")
        with c6:
            linked_dept = st.text_input("연계 부서", placeholder="예: 각 학과")

        improvement = st.text_area("개선 필요사항", placeholder="- 엑셀에 입력하는 과정에서 오타 발생\n- 수기입력에 행정력 소모 심함\n- 기존 이용내역에 대한 통계 등 누적자료 분석 어려움")

        submitted = st.form_submit_button("현황조사 제출 완료하기", use_container_width=True, type="primary")

        if submitted:
            if not task_name.strip():
                st.error("업무명은 필수 입력 항목입니다.")
            else:
                with st.spinner("현황조사 데이터를 시스템에 기록하고 있습니다. 잠시만 기다려주세요..."):
                    time.sleep(1.5)
                    survey_data = {
                        "부서명": dept,
                        "담당자 성명": manager,
                        "업무명": task_name,
                        "관리 매체": media,
                        "주 사용자": main_user,
                        "업무주기": freq,
                        "1회 소요시간": time_spent,
                        "연계 부서": linked_dept,
                        "개선 필요사항": improvement,
                        "제출일": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                        "User_ID": user_id
                    }
                    st.session_state['app_data'].setdefault('survey', []).append(survey_data)
                    st.session_state['app_data']['users_db'][user_id]['survey_completed'] = True
    
                    save_data(st.session_state['app_data'])
                if st.session_state.get('last_save_status') != "fail":
                    st.session_state['show_survey_success'] = True
                    st.rerun()

    if st.session_state.get('show_survey_success', False):
        show_survey_success_dialog()
        
    st.write("<br><br>", unsafe_allow_html=True)
    
    _, bottom_logo_col, _ = st.columns([4, 1.5, 4])
    with bottom_logo_col:
        safe_show_logo(use_container_width=True)


# ==========================================
# 3-2. 인터랙티브 프로덕트 투어 기능 (Driver.js 주입)
# ==========================================
def run_product_tour():
    """
    화면 내 요소를 직접 하이라이트하며 설명해주는 인터랙티브 투어 자바스크립트를 삽입합니다.
    """
    components.html("""
    <script>
    const parentDoc = window.parent.document;
    
    // CSS 로드 확인 및 주입
    if (!parentDoc.getElementById('driver-css')) {
        const link = parentDoc.createElement('link');
        link.id = 'driver-css';
        link.rel = 'stylesheet';
        link.href = 'https://cdn.jsdelivr.net/npm/driver.js@1.0.1/dist/driver.css';
        parentDoc.head.appendChild(link);
    }

    function startTour() {
        const driver = window.parent.driver.js.driver;
        const driverObj = driver({
          showProgress: true,
          nextBtnText: '다음',
          prevBtnText: '이전',
          doneBtnText: '완료',
          allowClose: true,
          steps: [
            {
                element: parentDoc.querySelector('[data-testid="stSidebar"]'),
                popover: {
                    title: '1. 사이드바 검색 및 필터',
                    description: '원하는 산출물을 부서별로 필터링하거나 검색어를 통해 빠르게 찾아볼 수 있습니다.',
                    side: 'right',
                    align: 'start'
                }
            },
            {
                element: parentDoc.querySelector('div[data-baseweb="tab-list"]'),
                popover: {
                    title: '2. 주요 기능 이동 탭',
                    description: '대시보드 현황 화면과 산출물을 직접 등록하고 조회할 수 있는 커뮤니티 공간을 자유롭게 오갈 수 있습니다.',
                    side: 'bottom',
                    align: 'start'
                }
            },
            {
                element: parentDoc.querySelector('.metric-card'),
                popover: {
                    title: '3. 현황 통계 요약',
                    description: '현재 시스템에 등록된 전체 산출물, 진행 중인 이슈 현황, 참여 담당자 수를 한눈에 파악할 수 있습니다.',
                    side: 'bottom',
                    align: 'start'
                }
            }
          ]
        });
        
        // Streamlit 렌더링 지연시간을 고려하여 약간 딜레이 후 실행
        setTimeout(() => driverObj.drive(), 800);
    }

    // JS 로드 확인 및 주입 후 투어 시작
    if (!parentDoc.getElementById('driver-js')) {
        const script = parentDoc.createElement('script');
        script.id = 'driver-js';
        script.src = 'https://cdn.jsdelivr.net/npm/driver.js@1.0.1/dist/driver.js.iife.js';
        script.onload = startTour;
        parentDoc.body.appendChild(script);
    } else {
        startTour();
    }
    </script>
    """, height=0, width=0)


# ==========================================
# 4. 사이드바 필터가 반영된 저장소 데이터 조회 함수
# ==========================================
def get_filtered_repo():
    repo_data = st.session_state['app_data']['repository']
    cat_filter = st.session_state.get(_cat_key, '전체')
    keyword = st.session_state.get(_kw_key, '').strip().lower()
    sort_option = st.session_state.get(_sort_key, '최근 활동순')

    filtered = list(repo_data)

    if cat_filter and cat_filter != "전체":
        filtered = [p for p in filtered if p.get('category', '') == cat_filter]

    if keyword:
        filtered = [
            p for p in filtered
            if keyword in p.get('title', '').lower() or keyword in p.get('desc', '').lower()
        ]

    if sort_option == "최근 활동순":
        filtered = sorted(filtered, key=lambda p: p.get('date', ''), reverse=True)
    elif sort_option == "이슈 많은순":
        filtered = sorted(filtered, key=lambda p: len(p.get('issues', [])), reverse=True)

    return filtered


def render_pagination(total_items, page_state_key, key_prefix):
    total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
    current_page = st.session_state.get(page_state_key, 1)
    if current_page > total_pages:
        current_page = total_pages
        st.session_state[page_state_key] = current_page

    p1, p2, p3, p4, p5 = st.columns([1, 1, 2, 1, 1])
    with p1:
        if st.button("« 처음", key=f"{key_prefix}_first", use_container_width=True, disabled=(current_page <= 1)):
            st.session_state[page_state_key] = 1
            st.rerun()
    with p2:
        if st.button("‹ 이전", key=f"{key_prefix}_prev", use_container_width=True, disabled=(current_page <= 1)):
            st.session_state[page_state_key] = current_page - 1
            st.rerun()
    with p3:
        st.markdown(f"<div style='text-align:center; padding-top:8px; font-size:13px; color:var(--muted-foreground);'>{current_page} / {total_pages} 페이지 (총 {total_items}건)</div>", unsafe_allow_html=True)
    with p4:
        if st.button("다음 ›", key=f"{key_prefix}_next", use_container_width=True, disabled=(current_page >= total_pages)):
            st.session_state[page_state_key] = current_page + 1
            st.rerun()
    with p5:
        if st.button("마지막 »", key=f"{key_prefix}_last", use_container_width=True, disabled=(current_page >= total_pages)):
            st.session_state[page_state_key] = total_pages
            st.rerun()

    return current_page


def render_board_table(page_items, start_idx):
    table_rows = ""
    for idx, item in enumerate(page_items):
        row_no = start_idx + idx + 1
        issue_cnt = len(item.get('issues', []))
        is_done = bool(item.get('completed_at'))
        status_html = "<span class='proj-status-done'>완료</span>" if is_done else "<span class='proj-status-progress'>진행중</span>"
        manager_name = get_display_name(item['author'])
        table_rows += (
            "<tr>"
            f"<td style='width:40px; color:var(--muted-foreground); font-family:var(--font-mono);'>{row_no}</td>"
            f"<td><span class='board-dept-badge'>{item.get('category', '일반')}</span></td>"
            f"<td style='font-weight:600;'>{item['title']}</td>"
            f"<td style='color:var(--muted-foreground);'>{manager_name}</td>"
            f"<td style='color:var(--muted-foreground); font-family:var(--font-mono); font-size:12px;'>{item['date']}</td>"
            f"<td style='text-align:center;'>{status_html}</td>"
            f"<td style='text-align:center;'>{issue_cnt}</td>"
            "</tr>"
        )
    board_html = (
        "<table class='board-table'>"
        "<thead><tr>"
        "<th>#</th><th>부서</th><th>프로젝트명</th><th>담당자</th><th>등록일</th>"
        "<th style='text-align:center;'>상태</th>"
        "<th style='text-align:center;'>이슈</th>"
        "</tr></thead>"
        f"<tbody>{table_rows}</tbody>"
        "</table>"
    )
    with st.container(border=True):
        st.markdown("<div class='board-wrapper-marker'></div>", unsafe_allow_html=True)
        st.markdown(board_html, unsafe_allow_html=True)


def render_department_timeline():
    repo_data_all = st.session_state['app_data']['repository']
    if not repo_data_all:
        st.info("타임라인을 표시할 산출물이 없습니다.")
        return

    rows = []
    for item in repo_data_all:
        try:
            start_dt = datetime.strptime(item['date'], "%Y-%m-%d %H:%M")
        except Exception:
            continue

        if item.get('completed_at'):
            try:
                end_dt = datetime.strptime(item['completed_at'], "%Y-%m-%d %H:%M")
                status = "완료"
            except Exception:
                end_dt = now_kst().replace(tzinfo=None)
                status = "진행중"
        else:
            end_dt = now_kst().replace(tzinfo=None)
            status = "진행중"

        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(hours=1)

        rows.append({
            "부서": item.get('category', '일반'),
            "프로젝트명": item['title'],
            "시작": start_dt,
            "종료": end_dt,
            "상태": status,
            "담당자": get_display_name(item.get('author', ''))
        })

    if not rows:
        st.info("타임라인을 계산할 수 있는 유효한 등록일 데이터가 없습니다.")
        return

    timeline_df = pd.DataFrame(rows)
    timeline_df = timeline_df.sort_values("시작")

    fig = px.timeline(
        timeline_df, x_start="시작", x_end="종료", y="프로젝트명",
        color="상태",
        color_discrete_map={"완료": "#0052FF", "진행중": "#C7D6FF"},
        hover_data={"부서": True, "담당자": True, "상태": True, "프로젝트명": False}
    )
    fig.update_yaxes(autorange="reversed", title="", categoryorder="array", categoryarray=timeline_df["프로젝트명"].tolist())
    fig.update_xaxes(title="")
    fig.update_traces(marker_line_width=0, opacity=0.95)
    fig.update_layout(
        height=max(220, 46 * len(timeline_df)),
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(family="Pretendard, sans-serif", color="#0F172A", size=12),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        legend_title_text='상태',
        bargap=0.35
    )
    st.plotly_chart(fig, use_container_width=True)

    done_rows = [r for r in rows if r["상태"] == "완료"]
    if done_rows:
        st.markdown("###### 부서별 평균 제작 소요 시간 (완료된 산출물 기준)")
        dur_df = pd.DataFrame([
            {"부서": r["부서"], "소요시간(시간)": round((r["종료"] - r["시작"]).total_seconds() / 3600, 1)}
            for r in done_rows
        ])
        avg_df = dur_df.groupby("부서", as_index=False)["소요시간(시간)"].mean()
        avg_df["소요시간(시간)"] = avg_df["소요시간(시간)"].round(1)
        st.dataframe(avg_df, use_container_width=True, hide_index=True)
    else:
        st.caption("아직 완료 처리된 산출물이 없어 평균 소요 시간을 계산할 수 없습니다. 커뮤니티 저장소 목록에서 산출물을 '완료 처리'해 보세요.")


# ==========================================
# 5. 메인 대시보드 화면
# ==========================================
def show_main_page():
    # 투어 트리거가 활성화된 경우 자바스크립트 주입 함수 실행 후 즉시 상태 해제
    if st.session_state.get('tour_trigger', False):
        run_product_tour()
        st.session_state['tour_trigger'] = False

    now = now_kst()
    if 'last_activity' in st.session_state and now > st.session_state['last_activity'] + timedelta(minutes=AUTO_LOGOUT_MINUTES):
        keys_to_clear = ['logged_in', 'user_id', 'last_activity', 'show_survey_success', 'pending_signup', 'tour_trigger']
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        st.session_state['logged_in'] = False
        st.rerun()

    col_title, col_ui = st.columns([5, 5])

    current_user_id = st.session_state.get('user_id', '')
    display_name = get_display_name(current_user_id)

    with col_title:
        st.markdown(f"### 교육혁신처 AI Creative Lab 산출물 저장소(GitHub) <span class='gradient-text'>프로젝트 현황</span>", unsafe_allow_html=True)
        st.caption(f"환영합니다, **{display_name}**님")

    with col_ui:
        r0, r1, r2, r3, r4 = st.columns([1.2, 1, 1, 1, 1.5])
        with r0:
            if st.button("이용 안내", use_container_width=True):
                st.session_state['tour_trigger'] = True
                st.rerun()
        with r1:
            if st.button("로그아웃", use_container_width=True):
                keys_to_clear = ['logged_in', 'user_id', 'last_activity', 'show_survey_success', 'pending_signup', 'tour_trigger']
                for k in keys_to_clear:
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state['logged_in'] = False
                st.rerun()
        with r2:
            st.markdown(f"<div id='realtime-timer-badge'><span id='realtime-timer'>--:--</span></div>", unsafe_allow_html=True)
            inject_timer_js()
        with r3:
            if st.button("연장", use_container_width=True):
                st.session_state['last_activity'] = now_kst()
                st.rerun()
        with r4:
            st.markdown(f"<div style='text-align:right; font-size:12px; color:var(--muted-foreground); padding-top:10px; font-family:var(--font-mono);'>기준일자: {now_kst().strftime('%Y. %m. %d. %H:%M')}</div>", unsafe_allow_html=True)

    repo_data_all = st.session_state['app_data']['repository']
    total_projects = len(repo_data_all)
    unique_authors = len(set([p['author'] for p in repo_data_all])) if repo_data_all else 0

    all_issues = []
    for p in repo_data_all:
        all_issues.extend(p.get('issues', []))
    total_issues = len(all_issues)
    open_issues = len([i for i in all_issues if i.get('status') == '진행중'])
    done_issues = len([i for i in all_issues if i.get('status') == '완료'])

    total_feedbacks = sum(len(p.get('feedbacks', [])) for p in repo_data_all)

    is_admin = is_user_admin(current_user_id)

    if is_admin:
        tab1, tab2, tab3, tab4 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소", "계정 관리", "현황 조사 제출 관리"])
    else:
        tab1, tab2 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소"])

    # ---------------- 탭 1: 대시보드 현황 ----------------
    with tab1:
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"<div class='metric-card'><div class='label'>전체 프로젝트</div><div class='value'>{total_projects}</div><div class='sub'>공개(Public) 프로젝트 기준</div></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-card'><div class='label'>월간 프로젝트</div><div class='value'>{total_projects}</div><div class='sub'>최근 30일 활동</div></div>", unsafe_allow_html=True)
        with m3:
            st.markdown(f"<div class='metric-card'><div class='label'>전체 이슈</div><div class='value'>{total_issues}</div><div class='sub'>진행중 {open_issues} / 완료 {done_issues}</div></div>", unsafe_allow_html=True)
        with m4:
            st.markdown(f"<div class='metric-card'><div class='label'>프로젝트 담당자</div><div class='value'>{unique_authors}</div><div class='sub'>참여 개발자 수</div></div>", unsafe_allow_html=True)

        st.write("<br>", unsafe_allow_html=True)
        chart_col1, chart_col2 = st.columns([6, 4])
        with chart_col1:
            with st.container(border=True):
                st.markdown("##### 프로젝트 활동 현황")
                st.caption("최근 7일간 실제 등록된 산출물 건수")
                if repo_data_all:
                    today = now_kst().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
                    date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]

                    parsed_dates = []
                    for p in repo_data_all:
                        try:
                            d = datetime.strptime(p.get('date', ''), "%Y-%m-%d %H:%M")
                            parsed_dates.append(d.date())
                        except Exception:
                            continue

                    counts = []
                    for d in date_range:
                        counts.append(parsed_dates.count(d.date()))

                    trend_df = pd.DataFrame({
                        "일자": [d.strftime("%Y-%m-%d") for d in date_range],
                        "등록 건수": counts
                    })
                    trend_df["일자"] = pd.to_datetime(trend_df["일자"])

                    fig = px.bar(trend_df, x="일자", y="등록 건수", title="", labels={'일자': '', '등록 건수': ''})
                    fig.update_traces(marker_color='#0052FF', marker_line_width=0)
                    fig.update_xaxes(tickformat="%m-%d")
                    fig.update_layout(
                        height=260, margin=dict(l=20, r=20, t=10, b=20),
                        font=dict(family="Pretendard, sans-serif", color="#0F172A"),
                        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("시각화할 프로젝트 데이터가 부족합니다.")
        with chart_col2:
            with st.container(border=True):
                st.markdown("##### 부서별 프로젝트 분포")
                if repo_data_all:
                    df_repo = pd.DataFrame(repo_data_all)
                    cat_counts = df_repo.get('category', pd.Series(['미분류'] * len(df_repo))).value_counts().reset_index()
                    cat_counts.columns = ['부서', '건수']
                    fig_pie = px.pie(
                        cat_counts, values='건수', names='부서', hole=0.65,
                        color_discrete_sequence=['#0052FF', '#4D7CFF', '#7fa4ff', '#a9c1ff', '#0F172A', '#64748B', '#CBD5E1']
                    )
                    fig_pie.update_layout(
                        height=260, margin=dict(l=10, r=10, t=10, b=10), showlegend=True,
                        font=dict(family="Pretendard, sans-serif", color="#0F172A"),
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("등록된 프로젝트가 없어 부서 분포를 표시할 수 없습니다.")

        st.write("<br>", unsafe_allow_html=True)
        st.markdown("##### 부서별 제작 타임라인")
        st.caption("등록일부터 완료 처리일까지의 제작 소요 기간을 보여줍니다. (저장소에서 삭제된 산출물은 집계에서 제외됩니다)")
        with st.container(border=True):
            render_department_timeline()

        st.write("<br>", unsafe_allow_html=True)
        st.markdown("##### 최근 활동 프로젝트")
        st.caption("좌측 사이드바의 부서/검색어 필터가 이 목록에도 동일하게 적용됩니다.")

        dashboard_filtered = get_filtered_repo()

        if not dashboard_filtered:
            if repo_data_all:
                st.info("사이드바 필터/검색어 조건에 맞는 산출물이 없습니다. 사이드바에서 필터를 초기화해 보세요.")
            else:
                st.info("등록된 산출물 프로젝트가 없습니다. 대시보드 탭 옆 커뮤니티 및 저장소에서 등록해 주세요.")
        else:
            current_dash_page = render_pagination(len(dashboard_filtered), 'dashboard_page', 'dash_bottom')
            start_idx = (current_dash_page - 1) * PAGE_SIZE
            end_idx = start_idx + PAGE_SIZE
            page_items = dashboard_filtered[start_idx:end_idx]

            render_board_table(page_items, start_idx)

    # ---------------- 탭 2: 산출물 커뮤니티 및 저장소 ----------------
    with tab2:
        st.markdown("### 산출물 커뮤니티 및 저장소")
        st.caption("대학 구성원들이 공유한 개발 산출물을 탐색하고, 피드백과 이슈로 함께 개선해 나가는 공간입니다.")

        rm1, rm2, rm3, rm4 = st.columns(4)
        with rm1:
            st.markdown(f"<div class='metric-card'><div class='label'>전체 산출물</div><div class='value'>{total_projects}</div><div class='sub'>커뮤니티 공개 기준</div></div>", unsafe_allow_html=True)
        with rm2:
            st.markdown(f"<div class='metric-card'><div class='label'>참여 담당자</div><div class='value'>{unique_authors}</div><div class='sub'>산출물 공유자 수</div></div>", unsafe_allow_html=True)
        with rm3:
            st.markdown(f"<div class='metric-card'><div class='label'>누적 피드백</div><div class='value'>{total_feedbacks}</div><div class='sub'>커뮤니티 토론 건수</div></div>", unsafe_allow_html=True)
        with rm4:
            st.markdown(f"<div class='metric-card'><div class='label'>전체 이슈</div><div class='value'>{total_issues}</div><div class='sub'>진행중 {open_issues} / 완료 {done_issues}</div></div>", unsafe_allow_html=True)

        st.write("<br>", unsafe_allow_html=True)

        with st.expander("새로운 산출물(결과물) 업로드 하기", expanded=False):
            my_dept = get_user_dept(current_user_id)
            st.info(f"업로드 시 부서는 회원가입 시 등록하신 **[{my_dept}]** 으로 자동 지정됩니다.")
            with st.form("upload_form", clear_on_submit=True):
                proj_name = st.text_input("프로젝트 명", placeholder="예: 학사행정 챗봇 자동응답 시스템")
                proj_desc = st.text_area("산출물 설명", placeholder="예: 학생 문의를 자동으로 분류하고 답변하는 AI 챗봇입니다.")
                uploaded_file = st.file_uploader(
                    "산출물 파일 첨부",
                    type=['zip', 'pdf', 'py', 'csv', 'txt', 'xlsx', 'html']
                )
                st.caption("보안상 업로드된 코드/스크립트 파일을 서버에서 직접 실행하는 기능은 제공하지 않습니다. HTML 파일은 새 창에서 미리보기가 가능합니다.")

                if st.form_submit_button("저장소에 배포하기", use_container_width=True):
                    if proj_name and uploaded_file:
                        with st.spinner("산출물을 저장소에 업로드하는 중입니다..."):
                            existing_ids = [item['id'] for item in repo_data_all] if repo_data_all else [0]
                            new_id = max(existing_ids) + 1 if existing_ids else 1
                            auto_dept = get_user_dept(current_user_id)
                            ensure_category_exists(auto_dept)
                            new_item = {
                                "id": new_id,
                                "title": proj_name,
                                "category": auto_dept,
                                "desc": proj_desc,
                                "author": st.session_state.get('user_id', '익명'),
                                "date": now_kst().strftime("%Y-%m-%d %H:%M"),
                                "filename": uploaded_file.name,
                                "file_data": uploaded_file.read(),
                                "feedbacks": [],
                                "issues": [],
                                "completed_at": None
                            }
                            st.session_state['app_data']['repository'].append(new_item)
                            save_data(st.session_state['app_data'])
                        if st.session_state.get('last_save_status') != "fail":
                            st.success("성공적으로 배포되었습니다.")
                            st.balloons()
                            st.rerun()
                    else:
                        st.error("프로젝트 명과 파일을 모두 첨부해 주세요.")

        st.markdown("---")

        filtered_repo = get_filtered_repo()
        active_filters = []
        if st.session_state.get(_cat_key, '전체') != '전체':
            active_filters.append(f"부서: {st.session_state[_cat_key]}")
        if st.session_state.get(_kw_key, '').strip():
            active_filters.append(f"검색어: '{st.session_state[_kw_key]}'")
        filter_desc = f" ({' / '.join(active_filters)} 적용 중)" if active_filters else ""

        h1, h2 = st.columns([4, 2])
        with h1:
            st.markdown(f"#### 커뮤니티 저장소 목록{filter_desc}")
        with h2:
            st.markdown(f"<div style='text-align:right; padding-top:8px; color:var(--muted-foreground); font-size:13px;'>정렬: {st.session_state.get(_sort_key, '최근 활동순')} · 총 {len(filtered_repo)}건</div>", unsafe_allow_html=True)

        if not filtered_repo:
            if repo_data_all:
                st.info("사이드바 필터/검색어 조건에 맞는 산출물이 없습니다. 사이드바에서 필터를 초기화해 보세요.")
            else:
                st.info("아직 공유된 산출물이 없습니다. 위의 업로드 영역에서 첫 산출물을 공유해 보세요.")
        else:
            for item in filtered_repo:
                with st.container(border=True):
                    st.markdown("<div class='repo-card-inner'>", unsafe_allow_html=True)

                    top_col, action_col = st.columns([5, 2])
                    with top_col:
                        is_done = bool(item.get('completed_at'))
                        status_html = "<span class='proj-status-done'>완료</span>" if is_done else "<span class='proj-status-progress'>진행중</span>"
                        manager_name = get_display_name(item['author'])

                        st.markdown(
                            f"<div class='repo-title-row'>"
                            f"<p class='repo-title'>{item['title']}</p>{status_html}"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        completed_part = f" · 완료 {item['completed_at']}" if is_done else ""
                        st.markdown(f"""
                            <div class='repo-meta-row'>
                                <span class='repo-cat-badge'>{item.get('category', '일반')}</span>
                                <span class='repo-author-badge'>{manager_name} · 등록 {item['date']}{completed_part}</span>
                            </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"<p class='repo-desc'>{item['desc']}</p>", unsafe_allow_html=True)

                    current_user = st.session_state.get('user_id')
                    can_manage = (current_user == item['author'] or is_user_admin(current_user))

                    with action_col:
                        file_ext = item['filename'].split('.')[-1].lower() if item.get('filename') else ''
                        if item.get('file_data'):
                            st.download_button(label="파일 다운로드", data=item['file_data'], file_name=item['filename'], mime="application/octet-stream", key=f"dl_{item['id']}", use_container_width=True)
                        else:
                            st.button("다운로드 만료됨", disabled=True, key=f"dl_{item['id']}", use_container_width=True)

                        if item.get('file_data') and file_ext == 'html':
                            b64 = base64.b64encode(item['file_data']).decode()
                            preview_html = f"""
                                <a href="data:text/html;base64,{b64}" target="_blank"
                                   style="display:block; text-align:center; padding:8px 0; margin-top:6px;
                                          background:var(--foreground); color:var(--background); border-radius:10px;
                                          font-size:14px; text-decoration:none; font-weight:500;">
                                   새 창에서 미리보기
                                </a>
                            """
                            st.markdown(preview_html, unsafe_allow_html=True)

                    if can_manage:
                        m_col1, m_col2, m_col3, m_spacer = st.columns([1.3, 1.3, 1.3, 2.1])
                        with m_col1:
                            edit_toggle_key = f"edit_toggle_{item['id']}"
                            if st.button("내용 수정", key=f"edit_open_{item['id']}", use_container_width=True):
                                st.session_state[edit_toggle_key] = not st.session_state.get(edit_toggle_key, False)
                        with m_col2:
                            if not item.get('completed_at'):
                                if st.button("완료 처리", key=f"complete_{item['id']}", use_container_width=True):
                                    completed_time = now_kst().strftime("%Y-%m-%d %H:%M")
                                    item['completed_at'] = completed_time
                                    record_timeline_completion(item)
                                    save_data(st.session_state['app_data'])
                                    if st.session_state.get('last_save_status') != "fail":
                                        st.success("완료 처리되었습니다. 제작 타임라인에 기록됩니다.")
                                        st.rerun()
                            else:
                                if st.button("완료 취소", key=f"uncomplete_{item['id']}", use_container_width=True):
                                    item['completed_at'] = None
                                    save_data(st.session_state['app_data'])
                                    if st.session_state.get('last_save_status') != "fail":
                                        st.success("완료 상태가 취소되어 다시 진행중으로 표시됩니다.")
                                        st.rerun()
                        with m_col3:
                            if st.button("산출물 삭제", key=f"del_{item['id']}", use_container_width=True):
                                st.session_state['app_data']['repository'] = [
                                    p for p in st.session_state['app_data']['repository'] if str(p['id']) != str(item['id'])
                                ]
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') == "fail":
                                    st.stop()
                                st.success("삭제되었습니다. (해당 산출물은 제작 타임라인 집계에서도 제외됩니다)")
                                st.rerun()

                    if can_manage and st.session_state.get(f"edit_toggle_{item['id']}", False):
                        with st.form(f"edit_form_{item['id']}"):
                            edit_title = st.text_input("프로젝트 명 수정", value=item['title'])
                            edit_desc = st.text_area("설명 수정", value=item['desc'])
                            save_edit_btn = st.form_submit_button("수정 내용 저장")
                            if save_edit_btn:
                                item['title'] = edit_title
                                item['desc'] = edit_desc
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') != "fail":
                                    st.session_state[f"edit_toggle_{item['id']}"] = False
                                    st.success("수정되었습니다.")
                                    st.rerun()

                    st.write("")

                    if item.get('file_data'):
                        if file_ext in ['py', 'txt', 'csv']:
                            with st.expander(f"파일 미리보기 ({item['filename']})"):
                                try:
                                    st.code(item['file_data'].decode('utf-8'), language='python' if file_ext == 'py' else 'text')
                                except Exception:
                                    st.error("텍스트로 미리볼 수 없는 인코딩입니다.")
                        elif file_ext == 'html':
                            with st.expander(f"파일 미리보기 ({item['filename']})"):
                                st.caption("아래는 페이지 내 임베드 미리보기입니다. 전체 화면으로 보려면 위쪽의 '새 창에서 미리보기' 버튼을 이용해 주세요.")
                                try:
                                    components.html(item['file_data'].decode('utf-8'), height=400, scrolling=True)
                                except Exception:
                                    st.error("HTML 미리보기를 렌더링할 수 없습니다.")

                    with st.expander(f"피드백 및 토론 ({len(item['feedbacks'])}건)"):
                        for fb in item['feedbacks']:
                            fb_display_name = get_display_name(fb['user'])
                            st.markdown(f"<div style='background-color:var(--muted); padding:10px 12px; border-radius:8px; margin-bottom:6px; border-left:3px solid var(--accent);'><b style='color:var(--foreground);'>{fb_display_name}</b> <span style='color:var(--muted-foreground); font-size:11px;'>({fb['time']})</span>: {fb['text']}</div>", unsafe_allow_html=True)

                        fb_input = st.text_input("의견을 남겨주세요", key=f"fb_in_{item['id']}", placeholder="예: 좋은 아이디어네요! 이 부분은 이렇게 개선하면 어떨까요?")
                        if st.button("피드백 등록", key=f"fb_btn_{item['id']}"):
                            if fb_input:
                                item['feedbacks'].append({"user": st.session_state.get('user_id', '익명'), "time": now_kst().strftime("%Y-%m-%d %H:%M"), "text": fb_input})
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') != "fail":
                                    st.rerun()

                    item_issues = item.get('issues', [])
                    open_cnt = len([i for i in item_issues if i.get('status') == '진행중'])
                    done_cnt = len([i for i in item_issues if i.get('status') == '완료'])
                    with st.expander(f"이슈 ({len(item_issues)}건 · 진행중 {open_cnt} / 완료 {done_cnt})"):
                        if not item_issues:
                            st.caption("등록된 이슈가 없습니다.")
                        for iss in item_issues:
                            badge_class = "issue-badge-open" if iss.get('status') == '진행중' else "issue-badge-done"
                            iss_author_name = get_display_name(iss.get('author', ''))
                            ic1, ic2, ic3 = st.columns([4.5, 1.1, 1.1])
                            with ic1:
                                st.markdown(
                                    f"<span class='{badge_class}'>{iss.get('status')}</span> "
                                    f"<b>{iss.get('title')}</b> "
                                    f"<span style='color:var(--muted-foreground); font-size:11px;'>· {iss_author_name} · {iss.get('date')}</span>",
                                    unsafe_allow_html=True
                                )
                            with ic2:
                                if can_manage:
                                    toggle_label = "완료 처리" if iss.get('status') == '진행중' else "재오픈"
                                    if st.button(toggle_label, key=f"issue_toggle_{item['id']}_{iss['id']}", use_container_width=True):
                                        iss['status'] = '완료' if iss.get('status') == '진행중' else '진행중'
                                        save_data(st.session_state['app_data'])
                                        if st.session_state.get('last_save_status') != "fail":
                                            st.rerun()
                            with ic3:
                                if is_user_admin(current_user):
                                    if st.button("삭제", key=f"issue_del_{item['id']}_{iss['id']}", use_container_width=True):
                                        item['issues'] = [i for i in item_issues if i['id'] != iss['id']]
                                        save_data(st.session_state['app_data'])
                                        if st.session_state.get('last_save_status') != "fail":
                                            st.success("이슈가 삭제되었습니다.")
                                            st.rerun()

                        new_issue_title = st.text_input("새 이슈 제목", key=f"issue_in_{item['id']}", placeholder="예: 다운로드 버튼 클릭 시 오류 발생")
                        if st.button("이슈 등록", key=f"issue_btn_{item['id']}"):
                            if new_issue_title.strip():
                                existing_issue_ids = [i['id'] for i in item_issues] if item_issues else [0]
                                new_issue_id = max(existing_issue_ids) + 1 if existing_issue_ids else 1
                                item_issues.append({
                                    "id": new_issue_id,
                                    "title": new_issue_title.strip(),
                                    "status": "진행중",
                                    "author": st.session_state.get('user_id', '익명'),
                                    "date": now_kst().strftime("%Y-%m-%d %H:%M")
                                })
                                item['issues'] = item_issues
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') != "fail":
                                    st.rerun()
                            else:
                                st.warning("이슈 제목을 입력해 주세요.")

                    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- 탭 3: 계정 관리 및 부서 설정 (관리자 전용) ----------------
    if is_admin:
        with tab3:
            st.markdown("### 시스템 계정 관리")
            users_db = st.session_state['app_data']['users_db']

            users_rows = []
            for uid, uinfo in users_db.items():
                users_rows.append({
                    "사용자 ID": uid,
                    "부서명": uinfo.get("dept", ""),
                    "담당자명": uinfo.get("manager", ""),
                    "비밀번호": uinfo.get("password", ""),
                    "권한": "관리자" if uinfo.get("role") == "admin" else "일반",
                    "승인 여부": "승인됨" if uinfo.get("approved", True) else "대기중",
                    "조사 제출": "완료" if uinfo.get("survey_completed", False) else "미제출"
                })
            users_df = pd.DataFrame(users_rows)
            st.dataframe(users_df, use_container_width=True, hide_index=True)

            st.markdown("#### 회원가입 승인 대기 목록")
            st.caption("현재는 회원가입 시 자동 승인되므로 이 목록은 비어있는 것이 정상입니다. 과거에 미승인 상태로 남아있던 계정이 있을 경우에만 표시됩니다.")
            pending_users = [uid for uid, uinfo in users_db.items() if not uinfo.get("approved", True)]
            if not pending_users:
                st.info("승인 대기 중인 계정이 없습니다.")
            else:
                for uid in pending_users:
                    uinfo = users_db[uid]
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"**{uid}** ({uinfo.get('dept', '-')} / {uinfo.get('manager', '-')})")
                        with c2:
                            if st.button("승인", key=f"approve_{uid}", use_container_width=True):
                                st.session_state['app_data']['users_db'][uid]["approved"] = True
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') != "fail":
                                    st.success(f"[{uid}] 계정이 승인되었습니다.")
                                    st.rerun()

            st.markdown("---")
            st.markdown("#### 관리자 권한 부여 / 해제")
            st.caption("관리자 권한을 부여받은 계정은 모든 산출물을 수정·삭제하고, 다른 사용자를 삭제하며, 부서 목록을 관리할 수 있게 됩니다. 신중하게 부여해 주세요.")

            non_root_users = [uid for uid in users_db.keys() if uid != 'admin']
            if not non_root_users:
                st.info("권한을 부여할 다른 계정이 없습니다.")
            else:
                for uid in non_root_users:
                    uinfo = users_db[uid]
                    current_role = uinfo.get("role", "user")
                    with st.container(border=True):
                        rc1, rc2, rc3 = st.columns([3, 1.3, 1.3])
                        with rc1:
                            role_badge_class = "role-badge-admin" if current_role == "admin" else "role-badge-user"
                            role_label = "관리자" if current_role == "admin" else "일반 사용자"
                            st.markdown(
                                f"**{uid}** ({uinfo.get('dept', '-')} / {uinfo.get('manager', '-')}) "
                                f"<span class='{role_badge_class}'>{role_label}</span>",
                                unsafe_allow_html=True
                            )
                        with rc2:
                            if current_role != "admin":
                                if st.button("관리자로 지정", key=f"grant_admin_{uid}", use_container_width=True):
                                    st.session_state['app_data']['users_db'][uid]["role"] = "admin"
                                    save_data(st.session_state['app_data'])
                                    if st.session_state.get('last_save_status') != "fail":
                                        st.success(f"[{uid}] 계정에 관리자 권한이 부여되었습니다.")
                                        st.rerun()
                        with rc3:
                            if current_role == "admin":
                                if st.button("권한 해제", key=f"revoke_admin_{uid}", use_container_width=True):
                                    st.session_state['app_data']['users_db'][uid]["role"] = "user"
                                    save_data(st.session_state['app_data'])
                                    if st.session_state.get('last_save_status') != "fail":
                                        st.success(f"[{uid}] 계정의 관리자 권한이 해제되었습니다.")
                                        st.rerun()

            st.markdown("---")
            st.markdown("#### 사용자 계정 삭제")
            target_user = st.selectbox("삭제할 사용자 선택", options=[u for u in users_db.keys() if u != 'admin'])
            if st.button("선택 계정 삭제"):
                if target_user in st.session_state['app_data']['users_db']:
                    del st.session_state['app_data']['users_db'][target_user]
                    if 'deleted_ids' not in st.session_state['app_data']:
                        st.session_state['app_data']['deleted_ids'] = []
                    if target_user not in st.session_state['app_data']['deleted_ids']:
                        st.session_state['app_data']['deleted_ids'].append(target_user)
                    save_data(st.session_state['app_data'])
                    if st.session_state.get('last_save_status') != "fail":
                        st.success(f"사용자 [{target_user}] 계정이 삭제되었습니다.")
                        st.rerun()

            st.markdown("---")
            st.markdown("### 사이드바 [부서] 필터 항목 구성")
            st.caption("이 항목은 구글 스프레드시트의 'Categories' 탭과 연동됩니다. 회원가입 시 입력한 부서명은 자동으로 이 목록에 추가됩니다.")
            current_cats = st.session_state['app_data'].get('categories', ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"])
            st.write("현재 등록된 부서 목록:", current_cats)

            new_cat_input = st.text_input("추가할 새로운 부서명 입력", placeholder="예: 산학협력단")
            if st.button("부서 추가"):
                if new_cat_input and new_cat_input not in current_cats:
                    st.session_state['app_data']['categories'].append(new_cat_input)
                    save_data(st.session_state['app_data'])
                    if st.session_state.get('last_save_status') != "fail":
                        st.success(f"부서 [{new_cat_input}]가 추가되었습니다.")
                        st.rerun()

            rem_cat = st.selectbox("삭제할 부서 선택", options=[c for c in current_cats if c != '전체'])
            if st.button("선택 부서 삭제"):
                if rem_cat in st.session_state['app_data']['categories']:
                    st.session_state['app_data']['categories'].remove(rem_cat)
                    save_data(st.session_state['app_data'])
                    if st.session_state.get('last_save_status') != "fail":
                        st.success(f"부서 [{rem_cat}]가 삭제되었습니다.")
                        st.rerun()

            st.markdown("---")
            st.markdown("### Google Sheets 연동 진단 로그")
            st.caption(f"현재 db_mode: **{st.session_state.get('db_mode', '알 수 없음')}**")
            debug_log = st.session_state.get('gsheets_debug_log', [])
            if debug_log:
                for level, line in debug_log:
                    if level == "error":
                        st.error(line)
                    elif level == "warn":
                        st.warning(line)
                    else:
                        st.info(line)
            else:
                st.write("진단 로그가 없습니다.")

            full_tbs = st.session_state.get('gsheets_full_traceback', [])
            if full_tbs:
                st.markdown("#### 전체 traceback (원인 정밀 확인용)")
                for tag, tb in full_tbs:
                    with st.expander(f"[{tag}] 전체 traceback 보기"):
                        st.code(tb, language="text")

    # ---------------- 탭 4: 현황 조사 제출 내역 (관리자 전용) ----------------
    if is_admin:
        with tab4:
            st.markdown("### 부서별 자동화 대상 업무 현황조사 제출 내역")
            st.caption("회원가입 후 최초 로그인 시 제출받은 현황조사 데이터입니다.")
            
            survey_list = st.session_state['app_data'].get('survey', [])
            
            if not survey_list:
                st.info("아직 제출된 현황조사 데이터가 없습니다.")
            else:
                survey_df = pd.DataFrame(survey_list)
                
                st.markdown(f"**총 제출 건수:** {len(survey_df)}건")
                
                st.dataframe(survey_df, use_container_width=True, hide_index=True)
                
                csv_data = survey_df.to_csv(index=False).encode('utf-8-sig')
                
                st.download_button(
                    label="CSV 파일 다운로드",
                    data=csv_data,
                    file_name=f"자동화대상업무_현황조사_{now_kst().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )


# ==========================================
# 6. 사이드바 구성
# ==========================================
def show_sidebar():
    with st.sidebar:
        col_side1, col_side2, col_side3 = st.columns([1, 2, 1])
        with col_side2:
            safe_show_logo(use_container_width=True)
        st.markdown("<h3 style='text-align:center;'>교육혁신처 AI Creative Lab</h3>", unsafe_allow_html=True)
        st.markdown("---")

        cat_options = st.session_state['app_data'].get('categories', ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"])

        st.selectbox("부서", options=cat_options, key=_cat_key)
        st.selectbox("정렬 기준", ["최근 활동순", "이슈 많은순"], key=_sort_key)
        st.text_input("검색어", placeholder="프로젝트 검색...", key=_kw_key)

        cb1, cb2 = st.columns(2)
        with cb1:
            if st.button("검색", use_container_width=True):
                st.session_state['repo_page'] = 1
                st.session_state['dashboard_page'] = 1
                st.rerun()
        with cb2:
            if st.button("초기화", use_container_width=True):
                st.session_state['filter_reset_counter'] += 1
                st.session_state['repo_page'] = 1
                st.session_state['dashboard_page'] = 1
                st.rerun()

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div class='sidebar-brand-card'>
                <h4 style='color: var(--foreground); margin-bottom: 5px;'>교육혁신처 AI Creative Lab</h4>
                <p style='font-size: 13px; color: var(--muted-foreground);'>대학 직원이 현장의 불편을 AI로 해결하는 실험 공간</p>
                <div class='tag'>Idea to Impact</div>
            </div>
        """, unsafe_allow_html=True)


# ==========================================
# 7. 최종 라우팅
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    show_login_page()
else:
    user_id = st.session_state.get('user_id')
    users_db = st.session_state['app_data'].get('users_db', {})
    uinfo = users_db.get(user_id, {})
    is_completed = uinfo.get('survey_completed', False)

    if st.session_state.get('show_survey_success', False):
        st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
        show_survey_page()
    elif not is_completed:
        st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
        show_survey_page()
    else:
        show_sidebar()
        show_main_page()
