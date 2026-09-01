import streamlit as st
import requests
import pandas as pd

# 페이지 기본 설정
st.set_page_config(
    page_title="SSHS 겹강/수업 분반 조회기",
    page_icon="🏫",
    layout="wide"
)

# API 엔드포인트
CLASSES_API_URL = "https://sshs.app/api/gyeopgang/classes"
STUDENTS_API_URL = "https://sshs.app/api/gyeopgang/students"

@st.cache_data(ttl=600)  # 10분간 캐싱
def load_data():
    """API로부터 학생 및 수업 데이터를 받아와 매핑 테이블을 생성합니다."""
    try:
        # 1. 학생 데이터 가져오기 (교번/학번 -> 이름 매핑)
        res_students = requests.get(STUDENTS_API_URL, timeout=10)
        res_students.raise_for_status()
        students_data = res_students.json()
        
        # 학생 매핑 딕셔너리 생성 (다양한 JSON 구조에 유연하게 대응)
        # 예: [{'id': '2024001', 'name': '홍길동'}, ...] 또는 {'2024001': '홍길동'}
        student_map = {}
        if isinstance(students_data, list):
            for s in students_data:
                if isinstance(s, dict):
                    sid = str(s.get("id") or s.get("student_id") or s.get("code") or s.get("number", ""))
                    name = s.get("name") or s.get("student_name", "")
                    if sid and name:
                        student_map[sid] = name
        elif isinstance(students_data, dict):
            student_map = {str(k): str(v) for k, v in students_data.items()}

        # 2. 수업 데이터 가져오기
        res_classes = requests.get(CLASSES_API_URL, timeout=10)
        res_classes.raise_for_status()
        classes_data = res_classes.json()

        return student_map, classes_data

    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return {}, []

def parse_student_name(student_entry, student_map):
    """학번 또는 데이터로부터 '이름(학번)' 형식으로 반환"""
    sid = str(student_entry).strip()
    name = student_map.get(sid, sid)  # 매핑 실패 시 기존 번호 그대로 노출
    return f"{name} ({sid})" if name != sid else sid

# ----------------- UI 및 인터랙션 -----------------
st.title("🏫 SSHS 수업 및 분반별 수강생 조회")
st.caption("과목명을 검색하여 분반별 수강생 명단을 한눈에 확인하세요.")

with st.spinner("최신 학사 데이터를 불러오는 중..."):
    student_map, classes_data = load_data()

if not classes_data:
    st.warning("수업 데이터를 가져올 수 없거나 목록이 비어있습니다.")
    st.stop()

# 수업 데이터 구조 정규화
# 지원 구조: [{ 'subject': '물리학', 'section': 'A반', 'students': ['24001', '24002'] }, ...]
normalized_classes = []
for item in classes_data:
    if isinstance(item, dict):
        subject = item.get("name") or item.get("subject") or item.get("subject_name") or item.get("title", "과목명 미정")
        section = item.get("class") or item.get("section") or item.get("division") or item.get("room") or "기본분반"
        raw_students = item.get("students") or item.get("members") or item.get("student_list") or []
        
        # 교번 -> 이름 변환
        named_students = [parse_student_name(s, student_map) for s in raw_students]
        
        normalized_classes.append({
            "subject": str(subject),
            "section": str(section),
            "students": named_students,
            "count": len(named_students)
        })

# 전체 과목 리스트 추출
all_subjects = sorted(list(set(c["subject"] for c in normalized_classes)))

# 사이드바/상단 검색 필터
col_search, col_stats = st.columns([3, 1])
with col_search:
    selected_subject = st.selectbox(
        "🔍 조회할 과목을 선택하거나 검색하세요",
        options=all_subjects,
        index=0 if all_subjects else None
    )

if selected_subject:
    # 선택된 과목의 분반 필터링
    filtered_sections = [c for c in normalized_classes if c["subject"] == selected_subject]
    
    with col_stats:
        total_students = sum(c["count"] for c in filtered_sections)
        st.metric(label="총 수강 인원", value=f"{total_students}명", delta=f"{len(filtered_sections)}개 분반")

    st.divider()

    # 분반별 카드 렌더링 (최대 3~4열 Grid)
    num_sections = len(filtered_sections)
    cols_per_row = 3
    
    for row_start in range(0, num_sections, cols_per_row):
        row_sections = filtered_sections[row_start:row_start + cols_per_row]
        cols = st.columns(len(row_sections))
        
        for idx, sec in enumerate(row_sections):
            with cols[idx]:
                # 사각형 컨테이너 카드
                with st.container(border=True):
                    st.subheader(f"📌 {sec['section']}")
                    st.caption(f"수강생: **{sec['count']}명**")
                    
                    if sec["students"]:
                        # 뱃지/태그 형태로 보기 쉽게 나열
                        st.write("---")
                        # 학생 이름을 칩 형태로 가독성 있게 표시
                        student_chips = " • ".join(sec["students"])
                        st.markdown(f"**명단:**\n\n{student_chips}")
                    else:
                        st.info("배정된 학생이 없습니다.")
