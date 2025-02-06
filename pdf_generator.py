import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import Color
from constants import EMPLOYEE_AREAS,STORE_COLORS, WEEKDAY_JA, SATURDAY_BG_COLOR, SUNDAY_BG_COLOR, EMPLOYEES, HOLIDAY_BG_COLOR
from io import BytesIO
from utils import parse_shift  # parse_shift関数をutils.pyからインポート
from datetime import datetime
from reportlab.lib.enums import TA_CENTER
from constants import HOLIDAY_BG_COLOR, KANOYA_BG_COLOR, KAGOKITA_BG_COLOR, DARK_GREY_TEXT_COLOR, SPECIAL_SHIFT_TYPES,RECRUIT_BG_COLOR
import jpholiday

# グローバルスコープでスタイルを定義
styles = getSampleStyleSheet()

title_style = ParagraphStyle('Title', 
                             parent=styles['Heading1'], 
                             fontName='NotoSansJP-Bold', 
                             fontSize=16, 
                             textColor=colors.HexColor("#373737"))

normal_style = ParagraphStyle('Normal', 
                              parent=styles['Normal'], 
                              fontName='NotoSansJP', 
                              fontSize=7, 
                              alignment=TA_CENTER, 
                              textColor=colors.HexColor("#373737"))

bold_style = ParagraphStyle('Bold', 
                            parent=normal_style, 
                            fontName='NotoSansJP-Bold', 
                            fontSize=8, 
                            textColor=colors.white)

bold_style2 = ParagraphStyle('Bold2', 
                             parent=normal_style, 
                             fontName='NotoSansJP-Bold', 
                             fontSize=7, 
                             textColor=colors.HexColor("#595959"))

header_style = ParagraphStyle('Header', 
                              parent=bold_style, 
                              fontSize=10,
                              textColor=colors.white)

special_shift_style = ParagraphStyle('SpecialShift', 
                                     parent=bold_style2, 
                                     textColor=colors.HexColor("#595959"))

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))

def format_shift_for_individual_pdf(shift_type, times, stores):
    """シフトの種類に応じたParagraphオブジェクトのリストを返す"""
    # NaN値や空の値の処理
    if pd.isna(shift_type) or shift_type == '-':
        return [Paragraph('-', bold_style2)]
    
    # 基本シフトタイプの処理
    if shift_type in ['AM', 'PM', '1日']:
        return [Paragraph(f'<b>{shift_type}</b>', bold_style2)]
    
    # 特別シフトタイプとその他の処理
    if shift_type in SPECIAL_SHIFT_TYPES or isinstance(shift_type, str) and shift_type.startswith('その他'):
        # 背景色の設定
        bg_color = (HOLIDAY_BG_COLOR if shift_type == '休み' 
                   else KANOYA_BG_COLOR if shift_type == '鹿屋' 
                   else KAGOKITA_BG_COLOR if shift_type == 'かご北'
                   else RECRUIT_BG_COLOR if shift_type == 'リクルート' or shift_type.startswith('その他')
                   else None)
        
        # その他の内容を含む表示テキストの設定
        if isinstance(shift_type, str) and shift_type.startswith('その他'):
            parts = shift_type.split(',', 1)
            content = parts[1] if len(parts) > 1 else ''
            display_text = f'その他: {content}' if content else 'その他'
        else:
            display_text = shift_type
        
        special_style = ParagraphStyle(
            'SpecialShift', 
            parent=bold_style2, 
            textColor=colors.HexColor(DARK_GREY_TEXT_COLOR),
            backColor=colors.HexColor(bg_color)
        )
        return [Paragraph(f'<b>{display_text}</b>', special_style)]
    
    # 時間と店舗の情報を含むシフトの処理
    formatted_shifts = []
    if times and stores:
        for time, store in zip(times, stores):
            color = STORE_COLORS.get(store, "#000000")
            formatted_shifts.append(
                Paragraph(f'<font color="{color}"><b>{time}@{store}</b></font>', bold_style2)
            )
        return formatted_shifts
    
    # デフォルトケース
    return [Paragraph(str(shift_type), bold_style2)]
def generate_help_table_pdf(data, year, month, area=None):
    buffer = io.BytesIO()
    # ページサイズを少し大きくする
    custom_page_size = (landscape(A4)[0] * 1.2, landscape(A4)[1] * 1.1)
    doc = SimpleDocTemplate(buffer, pagesize=custom_page_size, rightMargin=5*mm, leftMargin=5*mm, topMargin=10*mm, bottomMargin=10*mm)
    elements = []

    pdfmetrics.registerFont(TTFont('NotoSansJP', 'NotoSansJP-VariableFont_wght.ttf'))
    pdfmetrics.registerFont(TTFont('NotoSansJP-Bold', 'NotoSansJP-Bold.ttf'))

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', 
                                 parent=styles['Heading1'], 
                                 fontName='NotoSansJP-Bold', 
                                 fontSize=16, 
                                 textColor=colors.HexColor("#373737"))

    normal_style = ParagraphStyle('Normal', 
                                  parent=styles['Normal'], 
                                  fontName='NotoSansJP', 
                                  fontSize=8,  # フォントサイズを少し大きく
                                  alignment=TA_CENTER, 
                                  textColor=colors.HexColor("#373737"))

    bold_style = ParagraphStyle('Bold', 
                                parent=normal_style, 
                                fontName='NotoSansJP-Bold', 
                                fontSize=8,  # フォントサイズを少し大きく
                                textColor=colors.HexColor("#373737"))

    header_style = ParagraphStyle('Header', 
                                  parent=bold_style, 
                                  fontSize=9,  # ヘッダーのフォントサイズを調整
                                  textColor=colors.white)

    start_date = pd.Timestamp(year, month, 16)
    end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    next_month_start = pd.Timestamp(year, month, 1) + pd.DateOffset(months=1)

    date_ranges = [
        (start_date, next_month_start - pd.Timedelta(days=1)),
        (next_month_start, end_date)
    ]

    # エリアに基づいて従業員リストを取得
    if area and area in EMPLOYEE_AREAS:
        employees = EMPLOYEE_AREAS[area]
        title_prefix = f"{area} "
    else:
        employees = EMPLOYEES
        title_prefix = ""

    for i, (range_start, range_end) in enumerate(date_ranges):
        if i > 0:
            elements.append(PageBreak())

        title = Paragraph(f"{title_prefix}{range_start.strftime('%Y年%m月%d日')}～{range_end.strftime('%Y年%m月%d日')} ヘルプ表", title_style)
        elements.append(title)
        elements.append(Spacer(1, 5*mm))

        filtered_data = data[(data.index >= range_start) & (data.index <= range_end)]

        table_data = [
            [
                Paragraph(f'<font color="white"><b>日付</b></font>', header_style),
                Paragraph(f'<font color="white"><b>曜日</b></font>', header_style)
            ] + [Paragraph(f'<font color="white"><b>{emp}</b></font>', header_style) for emp in employees]
        ]

        for date, row in filtered_data.iterrows():
            weekday = WEEKDAY_JA.get(date.strftime('%a'), date.strftime('%a'))
            date_str = date.strftime('%Y-%m-%d')
            employee_shifts = [format_shift_for_pdf(row[emp]) for emp in employees]
            table_data.append([Paragraph(f'<b>{date_str}</b>', bold_style), Paragraph(f'<b>{weekday}</b>', bold_style)] + employee_shifts)

        # 列幅を調整（日付と曜日は固定幅、従業員列は均等に分配）
        available_width = custom_page_size[0] - 10*mm  # マージンを考慮
        date_width = 45*mm  # 日付列の幅
        weekday_width = 25*mm  # 曜日列の幅
        remaining_width = available_width - date_width - weekday_width - 10*mm  # 余白を考慮
        employee_width = remaining_width / len(employees)  # 従業員列の幅を均等に分配
        
        col_widths = [date_width, weekday_width] + [employee_width] * len(employees)
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'NotoSansJP-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),  # パディングを少し増やす
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#373737")),
        ])

        # 土日祝日の背景色
        for i, (date, row) in enumerate(filtered_data.iterrows(), start=1):
            if date.strftime('%a') == 'Sun' or jpholiday.is_holiday(date):
                table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(HOLIDAY_BG_COLOR))
            elif date.strftime('%a') == 'Sat':
                table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(SATURDAY_BG_COLOR))

        table.setStyle(table_style)
        elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer


def format_shift_for_pdf(shift):
    if pd.isna(shift) or shift == '-':
        return Paragraph('-', normal_style)
    
    if shift == '休み':
        return Paragraph('<b>休み</b>', ParagraphStyle('Holiday', 
                                                      parent=bold_style, 
                                                      textColor=colors.HexColor("#373737"),
                                                      backColor=colors.HexColor(HOLIDAY_BG_COLOR)))
    if shift == '鹿屋':
        return Paragraph('<b>鹿屋</b>', ParagraphStyle('Kanoya', 
                                                      parent=bold_style, 
                                                      textColor=colors.HexColor("#373737"),
                                                      backColor=colors.HexColor(KANOYA_BG_COLOR)))
    if shift == 'かご北':
        return Paragraph('<b>かご北</b>', ParagraphStyle('Kagokita', 
                                                        parent=bold_style, 
                                                        textColor=colors.HexColor("#373737"),
                                                        backColor=colors.HexColor(KAGOKITA_BG_COLOR)))
    if shift == 'リクルート':
        return Paragraph('<b>リクルート</b>', ParagraphStyle('Recruit', 
                                                        parent=bold_style, 
                                                        textColor=colors.HexColor("#373737"),
    
                                                        backColor=colors.HexColor(RECRUIT_BG_COLOR)))
    # その他の処理を追加
    if isinstance(shift, str) and shift.startswith('その他'):
        other_style = ParagraphStyle('Other', 
                                    parent=bold_style, 
                                    textColor=colors.HexColor("#373737"),
                                    backColor=colors.HexColor(RECRUIT_BG_COLOR))
        if ',' in shift:
            _, content = shift.split(',', 1)
            return Paragraph(f'<b>その他: {content}</b>', other_style)
        return Paragraph('<b>その他</b>', other_style)
    
    shift_parts = shift.split(',')
    shift_type = shift_parts[0]
    formatted_parts = []

    shift_type_color = "#595959" if shift_type in ['AM可', 'PM可', '1日可'] else "#373737"
    formatted_parts.append(Paragraph(f'<font color="{shift_type_color}"><b>{shift_type}</b></font>', bold_style))
    
    for part in shift_parts[1:]:
        if '@' in part:
            time, store = part.split('@')
            color = STORE_COLORS.get(store, "#373737")
            formatted_parts.append(Paragraph(f'<font color="{color}"><b>{time}@{store}</b></font>', bold_style))
        else:
            formatted_parts.append(Paragraph(f'<b>{part}</b>', bold_style))
    
    return formatted_parts

def generate_individual_pdf(data, employee, year, month):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=10*mm, leftMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)
    elements = []

    pdfmetrics.registerFont(TTFont('NotoSansJP', 'NotoSansJP-VariableFont_wght.ttf'))
    pdfmetrics.registerFont(TTFont('NotoSansJP-Bold', 'NotoSansJP-Bold.ttf'))

    title = Paragraph(f"{employee}さん {year}年{month}月 シフト表", title_style)
    elements.append(title)
    elements.append(Spacer(1, 10))

    start_date = pd.Timestamp(year, month, 16)
    end_date = start_date + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    filtered_data = data[(data.index >= start_date) & (data.index <= end_date)]

    max_shifts = max(len(str(shift).split(',')) - 1 for shift in filtered_data if not pd.isna(shift))
    
    col_widths = [20*mm, 15*mm] + [30*mm] * max_shifts
    
    table_data = [['日付', '曜日'] + [f'シフト{i+1}' for i in range(max_shifts)]]
    
    for date, shift in filtered_data.items():
        weekday = WEEKDAY_JA[date.strftime('%a')]
        shift_parts = str(shift).split(',') if pd.notna(shift) else ['-']
        shift_type = shift_parts[0]
        times_stores = [part.strip().split('@') for part in shift_parts[1:] if '@' in part]
        times, stores = zip(*times_stores) if times_stores else ([], [])
        formatted_shifts = format_shift_for_individual_pdf(shift_type, times, stores)
        row = [date.strftime('%m/%d'), weekday] + formatted_shifts + [''] * (max_shifts - len(formatted_shifts))
        table_data.append(row)

    t = Table(table_data, colWidths=col_widths)
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), 'NotoSansJP'),
        ('FONTNAME', (0, 0), (-1, 0), 'NotoSansJP-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
    ])

    for i, row in enumerate(table_data[1:], start=1):
        date = pd.to_datetime(filtered_data.index[i-1])
        if '日' in row[1] or jpholiday.is_holiday(date):
            style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(HOLIDAY_BG_COLOR))
        elif '土' in row[1]:
            style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(SATURDAY_BG_COLOR))

        for j, cell in enumerate(row[2:], start=2):
            if isinstance(cell, list) and len(cell) > 0 and isinstance(cell[0], Paragraph):
                if '休み' in cell[0].text:
                    style.add('BACKGROUND', (j, i), (j, i), colors.HexColor(HOLIDAY_BG_COLOR))
                elif '鹿屋' in cell[0].text:
                    style.add('BACKGROUND', (j, i), (j, i), colors.HexColor(KANOYA_BG_COLOR))
                elif 'かご北' in cell[0].text:
                    style.add('BACKGROUND', (j, i), (j, i), colors.HexColor(KAGOKITA_BG_COLOR))
                elif 'リクルート' in cell[0].text:
                    style.add('BACKGROUND', (j, i), (j, i), colors.HexColor(RECRUIT_BG_COLOR))

    t.setStyle(style)
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

def time_to_minutes(time_str):
    if '-' in time_str:
        start_time = time_str.split('-')[0]
    else:
        start_time = time_str
    if '半' in start_time:
        start_time = start_time.replace('半', ':30')
    else:
        start_time += ':00'
    time_obj = datetime.strptime(start_time, '%H:%M')
    return time_obj.hour * 60 + time_obj.minute

def generate_store_pdf(store_data, store_name, year, month):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=18)
    elements = []

    pdfmetrics.registerFont(TTFont('NotoSansJP', 'NotoSansJP-VariableFont_wght.ttf'))
    pdfmetrics.registerFont(TTFont('NotoSansJP-Bold', 'NotoSansJP-Bold.ttf'))

    # スタイルの定義
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', 
                                 parent=styles['Heading1'], 
                                 fontName='NotoSansJP-Bold', 
                                 fontSize=16, 
                                 textColor=colors.HexColor("#373737"))

    normal_style = ParagraphStyle('Normal', 
                                  parent=styles['Normal'], 
                                  fontName='NotoSansJP', 
                                  fontSize=10, 
                                  alignment=TA_CENTER, 
                                  textColor=colors.HexColor("#373737"))

    bold_style = ParagraphStyle('Bold', 
                                parent=normal_style, 
                                fontSize=9,
                                fontName='NotoSansJP-Bold')

    header_style = ParagraphStyle('Header', 
                                  parent=bold_style, 
                                  fontSize=10,
                                  textColor=colors.white)

    # タイトル
    title = Paragraph(f"{year}年{month}月 {store_name}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))

    # 注意書き
    #note = Paragraph("*大田さんは1人のときは18時まで\nそれ以外は17時まで", normal_style)
    #elements.append(note)
    #elements.append(Spacer(1, 12))

    # テーブルデータの準備
    header = ['日にち', '時間', 'ヘルプ担当', '備考']
    data = [[Paragraph(f'<b>{h}</b>', header_style) for h in header]]
    row_colors = [('BACKGROUND', (0, 0), (-1, 0), colors.grey)]  # ヘッダー行の背景色

    for i, (date, row) in enumerate(store_data.iterrows(), start=1):
        day_of_week = WEEKDAY_JA.get(date.strftime('%a'), date.strftime('%a'))
        date_str = f"{date.strftime('%m月%d日')} {day_of_week}"
        shifts = []
        for emp in EMPLOYEES:
            shift = row.get(emp, '-')
            if shift != '-':
                shift_type, shift_times, shift_stores = parse_shift(shift)
                for time, store in zip(shift_times, shift_stores):
                    if store == store_name:
                        shifts.append((time_to_minutes(time), time, emp))
        
        # 時間でソート
        shifts.sort(key=lambda x: x[0])
        
        if shifts:
            time_str = '<br/>'.join([shift[1] for shift in shifts])
            helper_str = '<br/>'.join([shift[2] for shift in shifts])
            time_paragraph = Paragraph(time_str, bold_style)
            helper_paragraph = Paragraph(helper_str, bold_style)
        else:
            time_paragraph = Paragraph('-', normal_style)
            helper_paragraph = Paragraph('-', normal_style)
        
        data.append([Paragraph(date_str, normal_style), time_paragraph, helper_paragraph, ''])

        # 土曜日と日曜日の背景色を設定
        if day_of_week == '日' or jpholiday.is_holiday(date):
            row_colors.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor(HOLIDAY_BG_COLOR)))
        elif day_of_week == '土':
            row_colors.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor(SATURDAY_BG_COLOR)))

    # テーブルの作成
    table = Table(data, colWidths=[80, 80, 80, 80])
    table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'NotoSansJP', 14),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#373737")),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('WORDWRAP', (0, 0), (-1, -1), True),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#373737")),
    ] + row_colors))

    elements.append(table)

    # PDFの生成
    doc.build(elements)

    buffer.seek(0)
    return buffer
#streamlit run main.py
# メイン実行部分（必要に応じて）
if __name__ == "__main__":
    # ここにメインの実行コードを記述
    pass