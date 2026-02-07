import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==========================================
# 1. إعداد الصفحة (لازم تكون أول حاجة)
# ==========================================
st.set_page_config(layout="wide", page_title="لوحة تحكم الكهرباء", page_icon="⚡")

# تنسيق CSS لضبط الاتجاه يمين-يسار
st.markdown("""
<style>
    .main {direction: rtl;}
    h1, h2, h3, h4, p, div {text-align: right; font-family: 'Segoe UI', sans-serif;}
    .stDataFrame {width: 100%;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

# الألوان (نفس كود Colab)
COLOR_MAP = {
    'كشك': '#2E86C1',      # أزرق
    'غرفة': '#E74C3C',     # أحمر
    'هوائي': '#8E44AD',    # بنفسجي
    'مبنى': '#F1C40F'      # أصفر
}

st.sidebar.title("🔍 القائمة الرئيسية")
page = st.sidebar.radio("القسم:", ["المحطات العامة", "الموزعات (517)", "شمال الإسماعيلية"])

# ==========================================
# 2. قسم المحطات العامة (نفس منطق Colab)
# ==========================================
@st.cache_data
def load_stations():
    if os.path.exists('Electricity_Stations_Final_Cleaned.xlsx'):
        df = pd.read_excel('Electricity_Stations_Final_Cleaned.xlsx')
        
        # تنظيف الملاحظات
        if 'ملاحظات' in df.columns: 
            df['ملاحظات'] = df['ملاحظات'].fillna('لا توجد ملاحظات')
        else: 
            df['ملاحظات'] = 'غير متوفر'
            
        # --- الحيلة الذكية (df['العدد'] = 1) ---
        df['العدد'] = 1
        return df
    return None

# ==========================================
# 3. قسم الموزعات (517)
# ==========================================
@st.cache_data
def load_distributors():
    # البحث عن ملف الـ 517 في المجلد الحالي
    files = [f for f in os.listdir('.') if "517" in f and (f.endswith('.xlsx') or f.endswith('.csv'))]
    if not files: return None, None
    
    path = files[0]
    if path.endswith('.csv'): 
        df = pd.read_csv(path).iloc[:, [1, 2, 3, 4]]
    else: 
        df = pd.read_excel(path).iloc[:, [1, 2, 3, 4]]
        
    df.columns = ['القطاع', 'الهندسة', 'مسلسل', 'الموزع']
    df = df.replace('nan', pd.NA).ffill()
    df = df[pd.to_numeric(df['مسلسل'], errors='coerce').notnull()]
    
    df['القطاع'] = df['القطاع'].astype(str).str.strip()
    df['الهندسة'] = df['الهندسة'].astype(str).str.strip()
    
    # --- التركة الذكية (دمج الاسم مع عدد الهندسات) ---
    eng_counts = df.groupby('القطاع')['الهندسة'].nunique()
    df['قطاع_للرسم'] = df['القطاع'].apply(lambda x: f"{x} (هندسات: {eng_counts.get(x, 0)})")
    df['عدد_الموزعات'] = 1
    
    summary = df.groupby('القطاع').agg({'الهندسة': 'nunique', 'الموزع': 'count'}).reset_index()
    summary.columns = ['القطاع', 'عدد الهندسات', 'عدد الموزعات']
    return df, summary

# ==========================================
# 4. منطق شمال الإسماعيلية (Focus here)
# ==========================================
def strict_classify_multi(row, type_cols, col_name):
    # تجميع النص من كافة أعمدة النوع
    combined_type_text = ""
    if type_cols:
        for col in type_cols:
            val = str(row[col])
            if pd.notna(val) and val.strip() != 'nan':
                combined_type_text += val + " "

    # تنظيف النصوص
    type_clean = combined_type_text.strip().replace('أ', 'ا').replace('ة', 'ه')
    name_val = str(row[col_name]).strip() if col_name and pd.notna(row[col_name]) else ''
    name_clean = name_val.replace('أ', 'ا').replace('ة', 'ه')

    # القواعد (نفس Colab)
    if 'غرف' in type_clean: return 'غرفة'
    if 'كشك' in type_clean: return 'كشك'
    if 'هواي' in type_clean or 'علق' in type_clean: return 'هوائي'
    if 'غرف' in name_clean: return 'غرفة' # لو النوع مش واضح نبص في الاسم

    return 'كشك' # الأصل

def process_file_final(file_path, filename):
    try:
        # 1. قراءة ذكية للبداية (نفس كودك بالظبط)
        df_temp = pd.read_excel(file_path, header=None)
        start_row = 0
        
        # البحث في أول 30 سطر
        for idx, row in df_temp.head(30).iterrows():
            row_str = " ".join(row.astype(str).values)
            # نفس الشروط اللي في كود Colab
            if ('اسم' in row_str and 'محول' in row_str) or \
               ('كشك' in row_str and 'غرفة' in row_str) or \
               ('بيان' in row_str) or \
               ('قدرة' in row_str):
                start_row = idx
                break
        
        # القراءة الفعلية
        df = pd.read_excel(file_path, header=start_row)
        df.columns = df.columns.astype(str).str.strip()

        # تحديد الأعمدة
        col_name = next((c for c in df.columns if 'اسم' in c or 'محول' in c or 'بيان' in c or 'عملية' in c), None)
        type_cols = [c for c in df.columns if 'نوع' in c or 'كشك' in c or 'غرف' in c or 'صنف' in c]
        col_cap  = next((c for c in df.columns if 'قدرة' in c or 'kva' in c.lower()), None)

        if col_name:
            # تنظيف البيانات
            df_clean = df.dropna(subset=[col_name]).copy()
            df_clean = df_clean[~df_clean[col_name].astype(str).str.contains('total|اجمالي|عدد', case=False, na=False)]
            df_clean = df_clean[df_clean[col_name].astype(str).str.len() > 1]

            # التصنيف
            df_clean['النوع_النهائي'] = df_clean.apply(lambda x: strict_classify_multi(x, type_cols, col_name), axis=1)

            # القدرة (الحفاظ على الكسور)
            if col_cap:
                df_clean['القدرة_النهائية'] = pd.to_numeric(
                    df_clean[col_cap].astype(str).str.replace(',', '').str.replace(' ', ''),
                    errors='coerce'
                ).fillna(0)
            else:
                df_clean['القدرة_النهائية'] = 0.0

            # --- استخراج اسم الهندسة (هنا التعديل عشان يلقط إسماعيلية ثان) ---
            fname_clean = filename.replace('أ', 'ا').replace('ة', 'ه')
            
            if 'زايد' in fname_clean: dist = 'الشيخ زايد'
            elif 'اول' in fname_clean or '1' in fname_clean: dist = 'إسماعيلية أول'
            # هنا زودت الشروط عشان لو الملف اسمه "2" أو "تاني" يقراه
            elif 'ثان' in fname_clean or '2' in fname_clean or 'تاني' in fname_clean: dist = 'إسماعيلية ثان'
            else: dist = 'غير محدد'

            if 'شركه' in fname_clean: owner = 'ملك الشركة'
            elif 'غير' in fname_clean: owner = 'ملك الغير'
            else: owner = 'غير محدد'
            
            if 'شركه' in fname_clean: owner = 'ملك الشركة' # تأكيد

            return pd.DataFrame({
                'الهندسة': dist,
                'الملكية': owner,
                'اسم المحول': df_clean[col_name],
                'النوع': df_clean['النوع_النهائي'],
                'القدرة': df_clean['القدرة_النهائية']
            })
        return None
    except:
        return None

@st.cache_data
def load_north_files():
    all_dfs = []
    # ملفات النظام اللي لازم نتجاهلها
    excluded_files = ['Electricity_Stations_Final_Cleaned.xlsx', 'requirements.txt', 'app.py', 'README.md', '.git']
    
    # قراءة الملفات في الفولدر الحالي (.)
    files = os.listdir('.')
    
    for f in files:
        # التأكد إنه ملف اكسيل ومش من الملفات المستبعدة ومش ملف مؤقت
        if f.endswith(('.xls', '.xlsx')) and \
           f not in excluded_files and \
           "517" not in f and \
           not f.startswith('~$'):
            
            res = process_file_final(f, f)
            if res is not None: all_dfs.append(res)
            
    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True)
        df['القطاع'] = 'شمال الإسماعيلية'
        return df
    return None

# ==========================================
# 5. الواجهة (التنفيذ الفعلي)
# ==========================================

if page == "المحطات العامة":
    st.header("توزيع المحطات (العدد والملاحظات)")
    df = load_stations()
    if df is not None:
        # Sunburst
        fig1 = px.sunburst(
            df, 
            path=['القطاع', 'المحطة'], 
            values='العدد', 
            height=750,
            hover_data={'ملاحظات': True, 'العدد': True}
        )
        fig1.update_traces(hovertemplate='<b>%{label}</b><br>عدد المحطات: %{value}<br>الملاحظات: %{customdata[0]}')
        st.plotly_chart(fig1, use_container_width=True)
        
        # Bar Chart
        st.subheader("إحصائية عدد المحطات لكل قطاع")
        sector_counts = df['القطاع'].value_counts().reset_index()
        sector_counts.columns = ['القطاع', 'عدد المحطات']
        fig2 = px.bar(sector_counts, x='القطاع', y='عدد المحطات', color='القطاع', text='عدد المحطات')
        fig2.update_traces(textposition='outside')
        st.plotly_chart(fig2, use_container_width=True)
        
        st.subheader("جدول البيانات")
        st.dataframe(df[['القطاع', 'المحطة', 'ملاحظات']], use_container_width=True)
    else:
        st.error("⚠️ ملف المحطات (Electricity_Stations_Final_Cleaned.xlsx) غير موجود.")

elif page == "الموزعات (517)":
    st.header("توزيع الموزعات")
    df, summ = load_distributors()
    if df is not None:
        st.dataframe(summ, use_container_width=True)
        
        fig_sun = px.sunburst(df, path=['قطاع_للرسم', 'الهندسة', 'الموزع'], values='عدد_الموزعات', height=700)
        fig_sun.update_layout(font=dict(size=14))
        st.plotly_chart(fig_sun, use_container_width=True)
        
        counts = df.groupby(['القطاع', 'الهندسة']).size().reset_index(name='العدد')
        fig_bar = px.bar(counts, x='الهندسة', y='العدد', color='القطاع', text='العدد')
        fig_bar.update_traces(textposition='outside')
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.error("⚠️ ملف الموزعات غير موجود.")

elif page == "شمال الإسماعيلية":
    st.header("تحليل قطاع شمال الإسماعيلية")
    df = load_north_files()
    
    if df is not None:
        # Metrics
        k1, k2, k3 = st.columns(3)
        # تنسيق دقيق للرقم (كسر واحد)
        k1.metric("إجمالي القدرة (kVA)", f"{df['القدرة'].sum():,.1f}")
        k2.metric("عدد المحولات", len(df))
        k3.metric("عدد الهندسات", df['الهندسة'].nunique())
        
        st.divider()
        
        # 1. إجمالي القدرات (بنفس تنسيق الكولاب: .1f)
        st.subheader("1. إجمالي القدرات الكلية (kVA)")
        cap_summary = df.groupby(['الهندسة', 'الملكية'])['القدرة'].sum().reset_index()
        
        fig_main = px.bar(
            cap_summary, 
            x='الهندسة', y='القدرة', color='الملكية', text='القدرة', 
            barmode='group',
            color_discrete_map={'ملك الشركة': '#003f5c', 'ملك الغير': '#bc5090'}
        )
        # هنا السر في ظهور الكسور: texttemplate='%{text:,.1f}'
        fig_main.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
        st.plotly_chart(fig_main, use_container_width=True)
        
        # تجهيز البيانات
        type_stats = df.groupby(['الهندسة', 'الملكية', 'النوع']).agg(
            العدد=('اسم المحول', 'count'),
            إجمالي_القدرة=('القدرة', 'sum')
        ).reset_index()
        category_order = {'النوع': ['كشك', 'غرفة', 'هوائي', 'مبنى']}
        
        # 2. عدد المحولات
        st.subheader("2. عدد المحولات والغرف حسب النوع")
        fig_count = px.bar(
            type_stats,
            x='الهندسة', y='العدد',
            color='النوع',
            facet_col='الملكية',
            barmode='group',
            text='العدد',
            color_discrete_map=COLOR_MAP,
            category_orders=category_order
        )
        fig_count.update_traces(textposition='outside')
        st.plotly_chart(fig_count, use_container_width=True)

        # 3. القدرة حسب النوع
        st.subheader("3. توزيع القدرات حسب النوع")
        fig_cap_type = px.bar(
            type_stats,
            x='الهندسة', y='إجمالي_القدرة',
            color='النوع',
            facet_col='الملكية',
            barmode='group',
            text='إجمالي_القدرة',
            color_discrete_map=COLOR_MAP,
            category_orders=category_order
        )
        # ظهور الكسور هنا كمان
        fig_cap_type.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
        st.plotly_chart(fig_cap_type, use_container_width=True)
        
        # 4. Sunburst
        st.subheader("4. التوزيع الشجري للأحمال")
        df_sun = df[df['القدرة'] > 0]
        fig_sun = px.sunburst(
            df_sun,
            path=['القطاع', 'الهندسة', 'الملكية', 'النوع', 'اسم المحول'],
            values='القدرة',
            height=850,
            color='النوع',
            color_discrete_map=COLOR_MAP
        )
        # Hover بكسور دقيقة
        fig_sun.update_traces(hovertemplate='<b>%{label}</b><br>القدرة: %{value:,.2f} kVA')
        st.plotly_chart(fig_sun, use_container_width=True)
        
        # الجدول
        st.subheader("الجدول التفصيلي")
        st.dataframe(df[['الهندسة', 'الملكية', 'النوع', 'اسم المحول', 'القدرة']], use_container_width=True)
        
    else:
        st.error("⚠️ لم يتم العثور على ملفات قطاع الشمال. تأكد من رفع الملفات في نفس المكان مع app.py")
