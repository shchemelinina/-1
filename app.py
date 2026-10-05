import streamlit as st
import pandas as pd
import time
import requests
from bs4 import BeautifulSoup
import plotly.express as px
from datetime import timedelta
import re

st.set_page_config(page_title="Аналитика БРС", layout="wide")

BASE_URL = "https://rating.unecon.ru/index.php"
CACHE_TTL = timedelta(days=30)
REQUEST_TIMEOUT = 1.5 


@st.cache_data(ttl=CACHE_TTL)
def fetch_programs(year):
    """Динамически парсит доступные направления бакалавриата для выбранного года."""
    programs = []
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        
        # k=1 - строго бакалавриат, f=1 - очная форма
        response = session.get(BASE_URL, params={'y': year, 'k': 1, 'f': 1})
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            prog_filter = soup.find(lambda tag: tag.name == "b" and "Направление" in tag.text)
            
            if prog_filter:
                options_div = prog_filter.find_next('div', class_='options')
                if options_div:
                    for opt in options_div.find_all('a', class_='option'):
                        href = opt.get('href')
                        prog_name = opt.text.strip()
                        # Отсекаем пустые значения или сбросы фильтров, если они есть
                        if prog_name and href and 'p=all' not in href and 'p=none' not in href:
                            programs.append(prog_name)
    except Exception as e:
        st.error(f"Ошибка при получении списка направлений: {e}")
        
    return programs if programs else ["Данные не найдены"]


@st.cache_data(ttl=CACHE_TTL)
def fetch_student_data(year, program):
    data = []
    try:
        session = requests.Session()
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        
        # k=1 - бакалавриат, f=1 - очная форма
        response = session.get(BASE_URL, params={'y': year, 'k': 1, 'f': 1})
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            st.error(f"Сайт БРС недоступен (Код ошибки: {response.status_code})")
            return pd.DataFrame(data, columns=["Год", "Направление", "Группа", "ФИО", "Семестр", "Предмет", "Балл"])

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Искомое направление теперь передается в исходном виде с сайта
        keyword = program
        
        prog_filter = soup.find(lambda tag: tag.name == "b" and "Направление" in tag.text)
        
        if not prog_filter:
            st.error(f"Не найден фильтр направлений для {year} года.")
            with st.expander("Посмотреть HTML-ответ сайта (для отладки)"):
                st.code(soup.prettify()[:1500])
            return pd.DataFrame(data, columns=["Год", "Направление", "Группа", "ФИО", "Семестр", "Предмет", "Балл"])
            
        prog_url = None
        for opt in prog_filter.find_next('div', class_='options').find_all('a', class_='option'):
            if keyword.lower() == opt.text.strip().lower():
                prog_url = opt.get('href')
                break
                
        if not prog_url:
            st.error(f"Направление '{keyword}' не найдено на сайте в {year} году.")
            return pd.DataFrame(data, columns=["Год", "Направление", "Группа", "ФИО", "Семестр", "Предмет", "Балл"])
            
        full_prog_url = prog_url if prog_url.startswith('http') else f"https://rating.unecon.ru/{prog_url}"
        time.sleep(REQUEST_TIMEOUT)
        prog_resp = session.get(full_prog_url)
        prog_resp.encoding = 'utf-8'
        prog_soup = BeautifulSoup(prog_resp.text, 'html.parser')
        
        group_filter = prog_soup.find(lambda tag: tag.name == "b" and "Группа" in tag.text)
        if not group_filter:
            st.error("Не удалось найти список групп для этого направления.")
            return pd.DataFrame(data, columns=["Год", "Направление", "Группа", "ФИО", "Семестр", "Предмет", "Балл"])
            
        groups = []
        for opt in group_filter.find_next('div', class_='options').find_all('a', class_='option'):
            href = opt.get('href')
            if href and 'g=none' not in href and 'g=all' not in href:
                full_url = href if href.startswith('http') else f"https://rating.unecon.ru/{href}"
                groups.append(full_url)

        for group_url in groups:
            time.sleep(REQUEST_TIMEOUT) 
            group_resp = session.get(group_url)
            group_resp.encoding = 'utf-8'
            group_soup = BeautifulSoup(group_resp.text, 'html.parser')
            
            sem_filter = group_soup.find(lambda tag: tag.name == "b" and "Семестр" in tag.text)
            semester_urls = [group_url] 
            
            if sem_filter:
                options_div = sem_filter.find_next('div', class_='options')
                if options_div:
                    semester_urls = []
                    for a in options_div.find_all('a', class_='option'):
                        href = a.get('href')
                        if href:
                            sem_url = href if href.startswith('http') else f"https://rating.unecon.ru/{href}"
                            semester_urls.append(sem_url)
            
            for sem_url in semester_urls:
                if sem_url != group_url:
                    time.sleep(REQUEST_TIMEOUT)
                    sem_resp = session.get(sem_url)
                    sem_resp.encoding = 'utf-8'
                    sem_soup = BeautifulSoup(sem_resp.text, 'html.parser')
                else:
                    sem_soup = group_soup
                    
                table = sem_soup.find('table')
                if not table:
                    continue
                
                group_header = sem_soup.find('h3')
                group_name = group_header.text.replace('Группа:', '').strip() if group_header else "Неизвестно"
                
                current_sem_filter = sem_soup.find(lambda tag: tag.name == "b" and "Семестр" in tag.text)
                semester_num = 1
                if current_sem_filter:
                    sem_text = current_sem_filter.find_next('div', class_='selected_text').text
                    match = re.search(r'(\d+)', sem_text)
                    if match:
                        semester_num = int(match.group(1))

                thead = table.find('thead')
                if not thead: continue
                
                header_rows = thead.find_all('tr')
                if len(header_rows) < 2: continue
                
                subject_headers = header_rows[1].find_all('th')
                subjects = []
                for th in subject_headers:
                    full_title = th.get('title', th.text)
                    subj_name = full_title.split('(')[0].strip() if '(' in full_title else full_title
                    subjects.append(subj_name)
                    
                tbody = table.find('tbody')
                if not tbody: continue
                
                for row in tbody.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) < 3:
                        continue
                        
                    student_name = cols[1].text.strip()
                    if not student_name:
                        student_name = "информации нет" 
                        
                    for i, subj in enumerate(subjects):
                        col_idx = i + 2
                        if col_idx < len(cols) - 1: 
                            score_text = cols[col_idx].text.strip()
                            score = float(score_text) if score_text.replace('.', '', 1).isdigit() else None
                            
                            if score is not None:
                                data.append({
                                    "Год": year,
                                    "Направление": program,
                                    "Группа": group_name,
                                    "ФИО": student_name,
                                    "Семестр": semester_num,
                                    "Предмет": subj,
                                    "Балл": score
                                })
                
    except Exception as e:
        st.error(f"Ошибка при парсинге данных: {e}")
    
    return pd.DataFrame(data, columns=["Год", "Направление", "Группа", "ФИО", "Семестр", "Предмет", "Балл"])

# Поиск индекса для Прикладной математики по умолчанию
def get_default_prog_index(programs_list):
    for i, p in enumerate(programs_list):
        if "прикладная математика" in p.lower():
            return i
    return 0

# интерфейс стимлита
st.sidebar.header("Параметры анализа")

years = ["2023", "2024", "2025", "2026"]

year1 = st.sidebar.selectbox("Год поступления 1", years, index=2)
programs1 = fetch_programs(year1)
prog1 = st.sidebar.selectbox("Направление обучения 1", programs1, index=get_default_prog_index(programs1))

year2 = st.sidebar.selectbox("Год поступления 2", years, index=1)
programs2 = fetch_programs(year2)
prog2 = st.sidebar.selectbox("Направление обучения 2", programs2, index=get_default_prog_index(programs2))

with st.spinner('Загрузка и парсинг данных...'):
    df_prog1 = fetch_student_data(year1, prog1)
    df_prog2 = fetch_student_data(year2, prog2)

if df_prog1.empty and df_prog2.empty:
    st.warning("Нет данных для отображения. Проверьте правильность HTML-селекторов парсера.")
    st.stop()

# фильтр скрытых студентов
valid_students_prog1 = df_prog1[df_prog1['ФИО'] != "информации нет"]['ФИО'].unique() if not df_prog1.empty else []
target_student = st.sidebar.selectbox("Целевой студент (для анализа)", valid_students_prog1)

valid_all_students = pd.concat([df_prog1, df_prog2])
valid_all_students = valid_all_students[valid_all_students['ФИО'] != "информации нет"]['ФИО'].unique() if not valid_all_students.empty else []
compare_student = st.sidebar.selectbox("Студент для сравнения", valid_all_students)

# дашборд
st.title("Дашборд аналитики успеваемости БРС")

tab1, tab2, tab3, tab4 = st.tabs([
    "Сравнение групп", 
    "Сравнение направлений", 
    "Студент vs Группа",
    "Сравнение студентов"
])

df_all = pd.concat([df_prog1, df_prog2]).drop_duplicates()

# 1: Сравнение групп 
with tab1:
    st.header("Сравнение академических групп")
    
    groups_list_1 = df_prog1['Группа'].dropna().unique()
    groups_list_2 = df_prog2['Группа'].dropna().unique()
    
    if len(groups_list_1) == 0 or len(groups_list_2) == 0:
        st.info("В одном из выбранных направлений нет доступных групп для сравнения.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            group_a = st.selectbox(f"Первая группа ({prog1} - {year1})", groups_list_1, index=0)
        with col2:
            default_idx2 = 1 if (prog1 == prog2 and year1 == year2 and len(groups_list_2) > 1) else 0
            group_b = st.selectbox(f"Вторая группа ({prog2} - {year2})", groups_list_2, index=default_idx2)
            
        data_g1 = df_all[df_all['Группа'] == group_a]
        data_g2 = df_all[df_all['Группа'] == group_b]
        
        sems1 = set(data_g1['Семестр'].dropna().unique())
        sems2 = set(data_g2['Семестр'].dropna().unique())
        intersecting_sems = sorted(list(sems1.intersection(sems2)))
        
        if not intersecting_sems:
            st.warning("У выбранных групп нет общих завершенных семестров.")
        else:
            st.write(f"**Анализ по общим семестрам:** {', '.join(map(str, intersecting_sems))}")
            
            valid_g1 = data_g1[(data_g1['Семестр'].isin(intersecting_sems)) & (data_g1['Балл'].notna())]
            valid_g2 = data_g2[(data_g2['Семестр'].isin(intersecting_sems)) & (data_g2['Балл'].notna())]
            valid_combined_groups = pd.concat([valid_g1, valid_g2])
            
            avg_sem_groups = valid_combined_groups.groupby(['Семестр', 'Группа'])['Балл'].mean().reset_index()
            
            avg_sem_groups['Семестр'] = avg_sem_groups['Семестр'].astype(str) + " семестр"
            
            fig_sem = px.bar(
                avg_sem_groups, 
                x='Семестр', 
                y='Балл', 
                color='Группа', 
                barmode='group', 
                title="Средняя успеваемость групп по общим семестрам",
                text_auto='.1f', 
                labels={'Балл': 'Средний балл', 'Семестр': 'Период обучения'}
            )
            
            fig_sem.update_yaxes(range=[0, 100])
            st.plotly_chart(fig_sem, use_container_width=True)
            
            subjs1 = set(valid_g1['Предмет'].unique())
            subjs2 = set(valid_g2['Предмет'].unique())
            intersecting_subjs = sorted(list(subjs1.intersection(subjs2)))
            
            if intersecting_subjs:
                subj_data = valid_combined_groups[valid_combined_groups['Предмет'].isin(intersecting_subjs)]
                avg_subj_groups = subj_data.groupby(['Предмет', 'Группа'])['Балл'].mean().reset_index()
                
                fig_subj = px.bar(avg_subj_groups, x='Предмет', y='Балл', color='Группа', barmode='group',
                                  title="Успеваемость по смежным дисциплинам",
                                  labels={'Балл': 'Средний балл'})
                st.plotly_chart(fig_subj, use_container_width=True)
            else:
                st.info("В общих семестрах нет совпадающих дисциплин.")

#  2: Сравнение направлений
with tab2:
    st.header("Сравнение направлений")
    prog_sems1 = set(df_prog1['Семестр'].dropna().unique())
    prog_sems2 = set(df_prog2['Семестр'].dropna().unique())
    prog_intersecting = sorted(list(prog_sems1.intersection(prog_sems2)))
    
    if prog_intersecting:
        valid_prog = df_all[(df_all['Семестр'].isin(prog_intersecting)) & (df_all['Балл'].notna())]
        
        avg_prog_sem = valid_prog.groupby(['Направление', 'Семестр'])['Балл'].mean().reset_index()
        fig_prog = px.line(avg_prog_sem, x='Семестр', y='Балл', color='Направление', markers=True,
                           title="Динамика среднего балла направлений по общим семестрам")
        fig_prog.update_xaxes(type='category')
        st.plotly_chart(fig_prog, use_container_width=True)
    else:
        st.warning("Нет общих семестров для сравнения направлений.")

# 3: Студент vs Группа 
with tab3:
    st.header("Сравнение со средней успеваемостью группы")
    if target_student:
        target_data = df_prog1[(df_prog1['ФИО'] == target_student) & (df_prog1['Балл'].notna())]
        
        if not target_data.empty:
            target_group = target_data['Группа'].iloc[0]
            
            group_data = df_prog1[(df_prog1['Группа'] == target_group) & (df_prog1['Балл'].notna())]
            avg_group = group_data.groupby('Семестр')['Балл'].mean().reset_index()
            avg_group['Субъект'] = f'Среднее ({target_group})'
            
            target_sem_avg = target_data.groupby('Семестр')['Балл'].mean().reset_index()
            target_sem_avg['Субъект'] = target_student
            
            comparison_df = pd.concat([target_sem_avg, avg_group])
            
            fig_vs_group = px.line(comparison_df, x='Семестр', y='Балл', color='Субъект', markers=True,
                                   title=f"Успеваемость: {target_student} против группы")
            fig_vs_group.update_traces(line=dict(width=3))
            fig_vs_group.update_xaxes(type='category')
            st.plotly_chart(fig_vs_group, use_container_width=True)
        else:
            st.warning("Нет данных по оценкам для данного студента.")

# 4: Сравнение студентов
with tab4:
    st.header("Индивидуальное сравнение студентов")
    
    if target_student and compare_student:
        data_s1 = df_all[(df_all['ФИО'] == target_student) & (df_all['Балл'].notna())]
        data_s2 = df_all[(df_all['ФИО'] == compare_student) & (df_all['Балл'].notna())]
        
        col3, col4 = st.columns(2)
        with col3:
            avg1 = data_s1['Балл'].mean() if not data_s1.empty else 0
            st.metric(label=f"Средний балл: {target_student}", value=f"{avg1:.2f}")
        with col4:
            avg2 = data_s2['Балл'].mean() if not data_s2.empty else 0
            st.metric(label=f"Средний балл: {compare_student}", value=f"{avg2:.2f}")
            
        subjs_s1 = set(data_s1['Предмет'].unique())
        subjs_s2 = set(data_s2['Предмет'].unique())
        common_subjs = sorted(list(subjs_s1.intersection(subjs_s2)))
        
        if common_subjs:
            st.subheader("Сравнение по смежным предметам")
            s1_common = data_s1[data_s1['Предмет'].isin(common_subjs)].groupby('Предмет')['Балл'].mean().reset_index()
            s1_common['Студент'] = target_student
            
            s2_common = data_s2[data_s2['Предмет'].isin(common_subjs)].groupby('Предмет')['Балл'].mean().reset_index()
            s2_common['Студент'] = compare_student
            
            common_df = pd.concat([s1_common, s2_common])
            fig_students = px.bar(common_df, x='Предмет', y='Балл', color='Студент', barmode='group',
                                  title="Баллы по пересекающимся дисциплинам")
            st.plotly_chart(fig_students, use_container_width=True)
        else:
            st.info("У выбранных студентов нет общих дисциплин для детального сравнения.")
