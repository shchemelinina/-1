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
def fetch_student_data(year, program):
    data = []
    try:
        session = requests.Session()
        
        # маскировка под браузер Chrome, чтобы брс не блокировал
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        
        # запрашиваем страницу (k=1 - бакалавриат, f=1 - очная форма)
        response = session.get(BASE_URL, params={'y': year, 'k': 1, 'f': 1})
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            st.error(f"Сайт БРС недоступен (Код ошибки: {response.status_code})")
            return pd.DataFrame(data, columns=["Год", "Направление", "Группа", "ФИО", "Семестр", "Предмет", "Балл"])

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # словарь для поиска
        program_keywords = {
            "ПМ": "Прикладная математика",
            "БИ": "Бизнес-информатика",
            "Менеджмент": "Менеджмент",
            "Экономика": "Экономика"
        }
        keyword = program_keywords.get(program, program)
        
        # поиск фильтра <b>Направление</b>
        prog_filter = soup.find(lambda tag: tag.name == "b" and "Направление" in tag.text)
        
        if not prog_filter:
            st.error(f"Не найден фильтр направлений для {year} года.")
            with st.expander("Посмотреть HTML-ответ сайта (для отладки)"):
                st.code(soup.prettify()[:1500])
            return pd.DataFrame(data, columns=["Год", "Направление", "Группа", "ФИО", "Семестр", "Предмет", "Балл"])
            
        prog_url = None
        # перебор направлений на сайте и поиск совпадения
        for opt in prog_filter.find_next('div', class_='options').find_all('a', class_='option'):
            if keyword.lower() in opt.text.lower(): 
                prog_url = opt.get('href') 
                break
                
        if not prog_url:
            st.error(f"Направление '{keyword}' не найдено на сайте в {year} году.")
            return pd.DataFrame(data, columns=["Год", "Направление", "Группа", "ФИО", "Семестр", "Предмет", "Балл"])
            
        # переход на страницу выбранного направления
        full_prog_url = prog_url if prog_url.startswith('http') else f"https://rating.unecon.ru/{prog_url}"
        time.sleep(REQUEST_TIMEOUT)
        prog_resp = session.get(full_prog_url)
        prog_resp.encoding = 'utf-8'
        prog_soup = BeautifulSoup(prog_resp.text, 'html.parser')
        
        # сбор групп
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

        # обход каждой группы и её семестров
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
                    
                table = sem_soup.find('table') # ищем таблицу с баллами
                if not table:
                    continue
                
                group_header = sem_soup.find('h3') # вытаскиваем название группы
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
                        col_idx = i + 2 # колонка с оценкой
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

# интерфейс стимлита
st.sidebar.header("Параметры анализа")

years = ["2023", "2024", "2025", "2026"]
programs = ["ПМ", "БИ", "Менеджмент", "Экономика"]

year1 = st.sidebar.selectbox("Год поступления 1", years, index=2)
prog1 = st.sidebar.selectbox("Направление обучения 1", programs, index=0)

year2
