import streamlit as st
import requests
import json

st.set_page_config(
    page_title="SSHS 겹강/수업 분반 조회기",
    page_icon="🏫",
    layout="wide"
)

CLASSES_API_URL = "https://sshs.app/api/gyeopgang/classes"
STUDENTS_API_URL = "https://sshs.app/api/gyeopgang/students"

@st.cache_data(ttl=300)
def fetch_raw_data():
    """두 API로부터 원본 JSON 데이터를 가져옵니다."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r_students = requests.get(STUDENTS_API_URL, headers=headers, timeout=10)
        r_classes = requests.get(CLASSES_API_URL, headers=headers, timeout=10)
        
        return r_students.json(), r_classes.json(), None
    except Exception as e:
        return None, None, str(e)

students_raw, classes_raw, error_msg = fetch_raw_data()

st.title("🏫 SSHS 수업 및 분반별 수강생 조회")

if error_msg:
    st.error(f"API 요청 실패: {error_msg}")
    st.stop()

# ----------------- 1. 학생 매핑 테이블 구축 -----------------
# 학생 데이터가 리스트인지, dict인지, 혹은 {'students': [...]} 형태인지 모두 대응
student_map = {}

def extract_students(raw):
    s_list = []
    if isinstance(raw, list):
        s_list = raw
    elif isinstance(raw, dict):
        # 딕셔너리 내부의 리스트 필드 탐색
        for k, v in raw.items():
            if isinstance(v, list):
                s_list = v
                break
        if not s_list:
            # 단순 { "24001": "홍길동" } 매핑 형태일 경우
            return {str(k).strip(): str(v).strip() for k, v in raw.items()}
            
    mapping = {}
    for s in s_list:
        if isinstance(s, dict):
            # 가능한 ID/학번 필드
            sid = s.get("id") or s.get("student_id") or s.get("code") or s.get("number") or s.get("sn") or s.get("studentId")
            # 가능한 이름 필드
            name = s.get("name") or s.get("student_name") or s.get("studentName") or s.get("realname")
            if sid and name:
                mapping[str(sid).strip()] = str(name).strip()
        elif isinstance(s, (list, tuple)) and len(s) >= 2:
            mapping[str(s[0]).strip()] = str(s[1]).strip()
    return mapping

student_map = extract_students(students_raw)

# ----------------- 2. 수업 데이터 파싱 -----------------
classes_list = []
if isinstance(classes_raw, list):
    classes_list = classes_raw
elif isinstance(classes_raw, dict):
    for k, v in classes_raw.items():
        if isinstance(v, list):
            classes_list = v
            break

def find_student_list(item):
    """아이템 내에서 학생 목록(list)에 해당하는 필드를 자동으로 찾습니다."""
    # 1. 흔히 쓰이는 키 우선 탐색
    candidate_keys = [
        "students", "members", "student_list", "studentList", "roster", 
        "takes", "enrolled", "people", "student_ids", "studentIds", "users", "list"
    ]
    for key in candidate_keys:
        if key in item and isinstance(item[key], list):
            return item[key]
            
    # 2. 키 이름이 달라도 리스트 타입인 필드 자동 탐색
    for key, value in item.items():
        if isinstance(value, list) and key not in ["times", "schedule", "periods"]:
            return value
    return []

parsed_classes = []
for c in classes_list:
    if not isinstance(c, dict):
        continue
    
    # 과목명 찾기
    subject = (
        c.get("name") or c.get("subject") or c.get("subject_name") or 
        c.get("title") or c.get("course") or c.get("subjectName") or "과목명 미상"
    )
    
    # 분반 찾기
    section = (
        c.get("class") or c.get("section") or c.get("division") or 
        c.get("room") or c.get("class_num") or c.get("classNum") or c.get("group") or "기본분반"
    )
    
    # 수강생 목록 추출
    raw_s_list = find_student_list(c)
    
    # 학번 -> 이름 매핑
    converted_students = []
    for s in raw_s_list:
        if isinstance(s, dict):
            # 학생 정보가 객체 형태로 들어있는 경우
            sid = str(s.get("id") or s.get("student_id") or s.get("code") or s.get("number") or "")
            sname = s.get("name") or s.get("student_name") or student_map.get(sid, sid)
            converted_students.append(f"{sname} ({sid})" if sid and sname != sid else str(sname or sid))
        else:
            sid_str = str(s).strip()
            name = student_map.get(sid_str)
            if name:
                converted_students.append(f"{name} ({sid_str})")
            else:
                converted_students.append(sid_str)

    parsed_classes.append({
        "subject": str(subject),
        "section": str(section),
        "students": converted_students,
        "count": len(converted_students)
    })

# ----------------- 3. UI 시각화 -----------------
all_subjects = sorted(list(set(c["subject"] for c in parsed_classes)))

if not all_subjects:
    st.warning("수업 데이터를 파싱하지 못했습니다. 아래 디버그 정보를 확인하세요.")
else:
    col_search, col_stats = st.columns([3, 1])
    with col_search:
        selected_subject = st.selectbox("🔍 조회할 과목을 선택하세요", options=all_subjects)

    if selected_subject:
        filtered = [c for c in parsed_classes if c["subject"] == selected_subject]
        
        with col_stats:
            total_students = sum(c["count"] for c in filtered)
            st.metric(label="총 수강 인원", value=f"{total_students}명", delta=f"{len(filtered)}개 분반")

        st.divider()

        # 분반별 카드 출력 (한 줄에 3개씩)
        cols_per_row = 3
        for i in range(0, len(filtered), cols_per_row):
            row_items = filtered[i:i + cols_per_row]
            cols = st.columns(cols_per_row)
            for idx, sec in enumerate(row_items):
                with cols[idx]:
                    with st.container(border=True):
                        st.subheader(f"📌 {sec['section']}")
                        st.caption(f"수강 인원: **{sec['count']}명**")
                        st.write("---")
                        if sec["students"]:
                            st.write(" • ".join(sec["students"]))
                        else:
                            st.info("수강생 없음")

# ----------------- 4. 디버깅 도구 (접이식) -----------------
with st.expander("🛠️ API 원본 데이터 구조 확인 (디버그용)"):
    st.write("### 1. 학생 API 응답 샘플 (상위 2개)")
    st.json(students_raw[:2] if isinstance(students_raw, list) else students_raw)
    st.write("### 2. 수업 API 응답 샘플 (상위 2개)")
    st.json(classes_raw[:2] if isinstance(classes_raw, list) else classes_raw)
