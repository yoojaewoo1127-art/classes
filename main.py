import streamlit as st
import requests

# 페이지 기본 설정
st.set_page_config(
    page_title="SSHS 겹강/수업 분반 조회기",
    page_icon="🏫",
    layout="wide"
)

CLASSES_API_URL = "https://sshs.app/api/gyeopgang/classes"
STUDENTS_API_URL = "https://sshs.app/api/gyeopgang/students"

@st.cache_data(ttl=300)
def fetch_api_data():
    """API로부터 학생 및 수업 데이터를 가져옵니다."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r_students = requests.get(STUDENTS_API_URL, headers=headers, timeout=10)
        r_classes = requests.get(CLASSES_API_URL, headers=headers, timeout=10)
        
        r_students.raise_for_status()
        r_classes.raise_for_status()
        
        return r_students.json(), r_classes.json(), None
    except Exception as e:
        return None, None, str(e)

students_raw, classes_raw, error_msg = fetch_api_data()

st.title("🏫 SSHS 수업 및 분반별 수강생 조회")

if error_msg:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {error_msg}")
    st.stop()

# ----------------- 1. 학생(교번 -> 이름) 매핑 딕셔너리 구성 -----------------
student_map = {}

def build_student_map(data):
    mapping = {}
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                # 가능한 교번/학번 필드 모두 탐색
                sid = (
                    item.get("id") or item.get("student_id") or item.get("studentId") or 
                    item.get("code") or item.get("number") or item.get("sn") or 
                    item.get("user_id") or item.get("userId")
                )
                # 가능한 이름 필드 탐색
                name = (
                    item.get("name") or item.get("student_name") or item.get("studentName") or 
                    item.get("realname") or item.get("user_name")
                )
                if sid is not None and name is not None:
                    sid_str = str(sid).strip()
                    mapping[sid_str] = str(name).strip()
                    # 숫자인 경우 앞자리 0 제거 버전/0 채운 버전도 함께 매핑
                    if sid_str.isdigit():
                        mapping[str(int(sid_str))] = str(name).strip()
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                mapping[str(item[0]).strip()] = str(item[1]).strip()
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                sid = v.get("id") or v.get("student_id") or k
                name = v.get("name") or v.get("student_name")
                if sid and name:
                    mapping[str(sid).strip()] = str(name).strip()
            else:
                mapping[str(k).strip()] = str(v).strip()
    return mapping

student_map = build_student_map(students_raw)

def get_student_display_name(raw_student):
    """학생 객체/교번을 받아 '이름 (교번)' 또는 '이름'으로 변환"""
    if isinstance(raw_student, dict):
        sid = (
            raw_student.get("id") or raw_student.get("student_id") or 
            raw_student.get("code") or raw_student.get("number")
        )
        name = raw_student.get("name") or raw_student.get("student_name")
        sid_str = str(sid).strip() if sid is not None else ""
        
        # 이름이 비어있으면 매핑 테이블 조회
        if not name and sid_str:
            name = student_map.get(sid_str, student_map.get(str(int(sid_str)) if sid_str.isdigit() else "", sid_str))
            
        if name and sid_str and name != sid_str:
            return f"{name} ({sid_str})"
        return str(name or sid_str)
    else:
        sid_str = str(raw_student).strip()
        # 매핑 조회 (문자열 그대로 or 정수형)
        name = student_map.get(sid_str)
        if not name and sid_str.isdigit():
            name = student_map.get(str(int(sid_str)))
            
        if name:
            return f"{name} ({sid_str})"
        return sid_str

# ----------------- 2. 수업 데이터 파싱 -----------------
classes_list = classes_raw if isinstance(classes_raw, list) else []
if isinstance(classes_raw, dict):
    for k, v in classes_raw.items():
        if isinstance(v, list):
            classes_list = v
            break

def format_section_name(class_item):
    """class_id 등을 기반으로 'N분반' 형태로 정규화"""
    cid = (
        class_item.get("class_id") or class_item.get("classId") or 
        class_item.get("class") or class_item.get("section") or 
        class_item.get("division") or class_item.get("room")
    )
    if cid is None:
        return "1분반"
    
    cid_str = str(cid).strip()
    # 이미 '분반'이나 '반'이 붙어있다면 그대로 반환
    if "반" in cid_str:
        return cid_str
    # 숫자 형태면 'N분반'으로 생성
    return f"{cid_str}분반"

def extract_students(class_item):
    """수강생 목록 추출"""
    keys = ["students", "members", "student_list", "studentList", "roster", "takes", "student_ids", "studentIds", "users", "list"]
    for k in keys:
        if k in class_item and isinstance(class_item[k], list):
            return class_item[k]
    # 리스트 타입 필드 자동 탐색
    for k, v in class_item.items():
        if isinstance(v, list) and k not in ["times", "schedule", "periods", "rooms"]:
            return v
    return []

parsed_classes = []
for item in classes_list:
    if not isinstance(item, dict):
        continue
        
    subject = (
        item.get("name") or item.get("subject") or item.get("subject_name") or 
        item.get("title") or item.get("course") or item.get("subjectName") or "과목명 미상"
    )
    section_name = format_section_name(item)
    raw_students = extract_students(item)
    
    # 학생 이름 변환
    named_students = [get_student_display_name(s) for s in raw_students]
    
    parsed_classes.append({
        "subject": str(subject).strip(),
        "section": section_name,
        "students": named_students,
        "count": len(named_students)
    })

# 과목별 그룹화 및 총 인원 계산
subject_summary = {}
for c in parsed_classes:
    sub = c["subject"]
    if sub not in subject_summary:
        subject_summary[sub] = {"total_students": 0, "sections": []}
    subject_summary[sub]["total_students"] += c["count"]
    subject_summary[sub]["sections"].append(c)

all_subjects = sorted(list(subject_summary.keys()))

# ----------------- 3. UI 렌더링 -----------------
if not all_subjects:
    st.warning("조회 가능한 수업 데이터가 없습니다.")
else:
    # 드롭다운 옵션에 총 인원 및 분반 수 표시
    subject_options = {
        f"{sub}  (총 {subject_summary[sub]['total_students']}명 / {len(subject_summary[sub]['sections'])}개 분반)": sub
        for sub in all_subjects
    }
    
    col_search, col_stats = st.columns([3, 1])
    with col_search:
        selected_label = st.selectbox(
            "🔍 조회할 과목을 검색하거나 선택하세요",
            options=list(subject_options.keys())
        )
        selected_subject = subject_options[selected_label]

    with col_stats:
        curr_data = subject_summary[selected_subject]
        st.metric(
            label=f"[{selected_subject}] 총 수강 인원",
            value=f"{curr_data['total_students']}명",
            delta=f"{len(curr_data['sections'])}개 분반"
        )

    st.divider()

    # 분반별 카드 그리드 출력 (한 줄에 3개씩)
    sections_list = curr_data["sections"]
    cols_per_row = 3
    
    for i in range(0, len(sections_list), cols_per_row):
        row_sections = sections_list[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        
        for idx, sec in enumerate(row_sections):
            with cols[idx]:
                with st.container(border=True):
                    st.subheader(f"📌 {sec['section']}")
                    st.caption(f"수강 인원: **{sec['count']}명**")
                    st.write("---")
                    
                    if sec["students"]:
                        # 가독성을 위해 불릿 기호로 정렬
                        st.markdown(" • " + " • ".join(sec["students"]))
                    else:
                        st.info("배정된 학생이 없습니다.")

# ----------------- 4. 디버그 및 확인용 (접이식) -----------------
with st.expander("🛠️ API 원본 데이터 샘플 확인"):
    st.write("**1. 학생 API 데이터 샘플:**")
    st.json(students_raw[:3] if isinstance(students_raw, list) else students_raw)
    st.write("**2. 수업 API 데이터 샘플:**")
    st.json(classes_raw[:3] if isinstance(classes_raw, list) else classes_raw)
