import streamlit as st
import pandas as pd
from datetime import datetime
import io
import base64
import asyncio
from database import db
from pdf_generator import generate_help_table_pdf, generate_individual_pdf, generate_store_pdf
from constants import STAFF_AREAS, SHIFT_TYPES, STORE_COLORS, WEEKDAY_JA, AREAS
from utils import parse_shift, format_shifts, update_session_state_shifts, highlight_weekend_and_holiday, highlight_filled_shifts

# 全従業員リストを動的に生成
ALL_EMPLOYEES = [employee for employees in STAFF_AREAS.values() for employee in employees]

@st.cache_data(ttl=3600)
def get_cached_shifts(year, month):
    start_date = pd.Timestamp(year, month, 16)
    end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    return db.get_shifts(start_date, end_date)

async def save_shift_async(date, employee, shift_str):
    await asyncio.to_thread(db.save_shift, date, employee, shift_str)
    
    current_month = date.replace(day=1)
    previous_month = current_month - pd.DateOffset(months=1)
    get_cached_shifts.clear()
    get_cached_shifts(current_month.year, current_month.month)
    get_cached_shifts(previous_month.year, previous_month.month)
    
    st.experimental_rerun()

def initialize_shift_data(year, month):
    if 'shift_data' not in st.session_state or st.session_state.current_year != year or st.session_state.current_month != month:
        start_date = pd.Timestamp(year, month, 16)
        end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
        date_range = pd.date_range(start=start_date, end=end_date)
        st.session_state.shift_data = pd.DataFrame(
            index=date_range,
            columns=ALL_EMPLOYEES,
            data='-'
        )
        st.session_state.current_year = year
        st.session_state.current_month = month

def calculate_shift_count(shift_data):
    def count_shift(shift):
        if pd.isna(shift) or shift == '-':
            return 0
        shift_type = shift.split(',')[0] if ',' in shift else shift
        if shift_type in ['1日可', '鹿屋', 'かご北', 'リクルート']:
            return 1
        elif shift_type in ['AM可', 'PM可']:
            return 0.5
        return 0

    return shift_data.applymap(count_shift).sum()

def display_shift_table(selected_year, selected_month):
    st.header('ヘルプ表')
    
    start_date = pd.Timestamp(selected_year, selected_month, 16)
    end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    
    date_range = pd.date_range(start=start_date, end=end_date)
    display_data = st.session_state.shift_data.loc[start_date:end_date].copy()
    
    for date in date_range:
        if date not in display_data.index:
            display_data.loc[date] = '-'
    
    display_data = display_data.sort_index()
    
    display_data['日付'] = display_data.index.strftime('%Y-%m-%d')
    display_data['曜日'] = display_data.index.strftime('%a').map(WEEKDAY_JA)
    
    for employee in ALL_EMPLOYEES:
        if employee not in display_data.columns:
            display_data[employee] = '-'
            
    # エリアごとのタブを作成
    area_tabs = st.tabs(list(STAFF_AREAS.keys()))
    
    for area_tab, (area_name, area_staff) in zip(area_tabs, STAFF_AREAS.items()):
        with area_tab:
            area_display_data = display_data[['日付', '曜日'] + area_staff]
            area_display_data = area_display_data.fillna('-')

            shift_counts = calculate_shift_count(area_display_data[area_staff])

            items_per_page = 15
            total_pages = len(area_display_data) // items_per_page + (1 if len(area_display_data) % items_per_page > 0 else 0)
            
            page_key = f"{area_name}_current_page"
            if page_key not in st.session_state:
                st.session_state[page_key] = 1

            col1, col2, col3 = st.columns([2,3,2])
            with col1:
                if st.button('◀◀ 最初', key=f'first_page_{area_name}'):
                    st.session_state[page_key] = 1
                if st.button('◀ 前へ', key=f'prev_page_{area_name}') and st.session_state[page_key] > 1:
                    st.session_state[page_key] -= 1
            with col2:
                st.write(f'ページ {st.session_state[page_key]} / {total_pages}')
            with col3:
                if st.button('最後 ▶▶', key=f'last_page_{area_name}'):
                    st.session_state[page_key] = total_pages
                if st.button('次へ ▶', key=f'next_page_{area_name}') and st.session_state[page_key] < total_pages:
                    st.session_state[page_key] += 1

            start_idx = (st.session_state[page_key] - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_display_data = area_display_data.iloc[start_idx:end_idx]

            st.markdown("""
            <style>
            table {
                font-size: 16px;
                width: 100%;
            }
            th, td {
                text-align: center;
                padding: 10px;
                white-space: pre-line;
                vertical-align: top;
            }
            th {
                background-color: #f0f0f0;
            }
            .shift-count {
                font-weight: bold;
                background-color: #e6f3ff;
            }
            </style>
            """, unsafe_allow_html=True)

            page_display_data = page_display_data.reset_index(drop=True)
            styled_df = page_display_data.style.format(format_shifts, subset=area_staff)\
                                        .apply(highlight_weekend_and_holiday, axis=1)
            
            st.write(styled_df.hide(axis="index").to_html(escape=False), unsafe_allow_html=True)

            st.markdown(f"### {area_name}のシフト日数")
            shift_count_df = pd.DataFrame([shift_counts], columns=area_staff)
            styled_shift_count = shift_count_df.style.format("{:.1f}")\
                                                 .set_properties(**{'class': 'shift-count'})
            st.write(styled_shift_count.hide(axis="index").to_html(escape=False), unsafe_allow_html=True)

    if st.button("ヘルプ表をPDFでダウンロード"):
        pdf = generate_help_table_pdf(display_data, selected_year, selected_month)
        st.download_button(
            label="ヘルプ表PDFをダウンロード",
            data=pdf,
            file_name=f"全ヘルプスタッフ_{selected_year}_{selected_month}.pdf",
            mime="application/pdf"
        )

def initialize_session_state():
    if 'editing_shift' not in st.session_state:
        st.session_state.editing_shift = False
    if 'current_shift' not in st.session_state:
        st.session_state.current_shift = None

def update_shift_input(current_shift, employee, date):
    initialize_session_state()
    
    if not st.session_state.editing_shift:
        st.session_state.current_shift = current_shift
        st.session_state.editing_shift = True
    
    shift_type, times, stores = parse_shift(st.session_state.current_shift)
    
    new_shift_type = st.selectbox('種類', ['AM可', 'PM可', '1日可', '-', '休み', '鹿屋', 'かご北', 'リクルート'], 
                                 index=['AM可', 'PM可', '1日可', '-', '休み', '鹿屋', 'かご北', 'リクルート'].index(shift_type) 
                                 if shift_type in ['AM可', 'PM可', '1日可', '休み', '鹿屋', 'かご北', 'リクルート'] else 3)
    
    if new_shift_type in ['AM可', 'PM可', '1日可']:
        num_shifts = st.number_input('シフト数', min_value=1, max_value=5, value=len(times) or 1)
        
        new_times = []
        new_stores = []
        for i in range(num_shifts):
            col1, col2, col3 = st.columns(3)
            with col1:
                area_options = list(AREAS.keys())
                current_area = next((area for area, stores_list in AREAS.items() if stores[i] in stores_list), area_options[0]) if i < len(stores) else area_options[0]
                area = st.selectbox(f'エリア {i+1}', area_options, index=area_options.index(current_area), key=f'shift_area_{i}')
                
            with col2:
                store_options = [''] + AREAS[area] if area != 'なし' else ['']
                current_store = stores[i] if i < len(stores) and stores[i] in store_options else ''
                store = st.selectbox(f'店舗 {i+1}', store_options, index=store_options.index(current_store), key=f'shift_store_{i}')
            
            with col3:
                time = st.text_input(f'時間 {i+1}', value=times[i] if i < len(times) else '')
            
            if time:
                new_times.append(time)
                new_stores.append(store)
        
        if new_times:
            new_shift_str = f"{new_shift_type},{','.join([f'{t}@{s}' if s else t for t, s in zip(new_times, new_stores)])}"
        else:
            new_shift_str = new_shift_type
    elif new_shift_type in ['休み', '鹿屋', 'かご北', 'リクルート', '-']:
        new_shift_str = new_shift_type
    
    st.session_state.current_shift = new_shift_str
    return new_shift_str

def display_store_help_requests(selected_year, selected_month):
    st.header('店舗ヘルプ希望')
    
    start_date = pd.Timestamp(selected_year, selected_month, 16)
    end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    
    store_help_requests = db.get_store_help_requests(start_date, end_date)
    
    if store_help_requests.empty:
        st.write("ヘルプ希望はありません。")
    else:
        store_help_requests['日付'] = store_help_requests.index.strftime('%Y-%m-%d')
        store_help_requests['曜日'] = store_help_requests.index.strftime('%a').map(WEEKDAY_JA)
        
        all_stores = [store for stores in AREAS.values() for store in stores]
        for store in all_stores:
            if store not in store_help_requests.columns:
                store_help_requests[store] = '-'
        
        store_help_requests = store_help_requests.reset_index(drop=True)

        area_tabs = [area for area in AREAS.keys() if area != 'なし']
        tabs = st.tabs(area_tabs)
        
        st.markdown("""
        <style>
        table {
            font-size: 14px;
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            text-align: center;
            padding: 8px;
            border: 1px solid #ddd;
        }
        th {
            background-color: #f2f2f2;
        }
        </style>
        """, unsafe_allow_html=True)
        
        for area, tab in zip(area_tabs, tabs):
            with tab:
                area_stores = AREAS[area]
                area_data = store_help_requests[['日付', '曜日'] + area_stores]
                area_data = area_data.fillna('-')

                shift_data = st.session_state.shift_data[
                    (st.session_state.shift_data.index >= start_date) & 
                    (st.session_state.shift_data.index <= end_date)
                ]
                shift_data.index = pd.to_datetime(shift_data.index)

                styled_df = area_data.style.apply(highlight_weekend_and_holiday, axis=1)\
                                        .apply(highlight_filled_shifts, shift_data=shift_data, axis=1)

                st.write(styled_df.to_html(escape=False, index=False), unsafe_allow_html=True)

def load_shift_data(year, month):
    start_date = pd.Timestamp(year, month, 16)
    end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    shifts = db.get_shifts(start_date, end_date)
    
    date_range = pd.date_range(start=start_date, end=end_date)
    full_shifts = pd.DataFrame(index=date_range, columns=ALL_EMPLOYEES, data='-')
    full_shifts.update(shifts)
    
    st.session_state.shift_data = full_shifts
    st.session_state.current_year = year
    st.session_state.current_month = month

