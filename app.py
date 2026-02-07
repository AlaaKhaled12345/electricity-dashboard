import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==========================================
# 1. إعداد الصفحة
# ==========================================
st.set_page_config(layout="wide", page_title="لوحة تحكم الكهرباء", page_icon="⚡")
st.markdown("""
<style>
    .main {direction: rtl;}
    h1, h2, h3, h4, p, div {text-align: right; font-family: 'Segoe UI', sans-serif;}
    .stDataFrame {width: 100%;}
    div[data-testid="stMetricValue"] {font-size: 20px;}
</style>
""", unsafe_allow_html=True)

# الألوان (نفس Colab)
COLOR_MAP = {
    'كشك': '#2E86C1',      # أزرق
    'غرفة': '#E74C3C',     # أحمر
    'هوائي': '#8E44AD',    # بنفسجي
    'مبنى': '#F1C40F'      # أصفر
}

st.sidebar.title("🔍 القائمة الرئيسية")
page = st.sidebar.radio("القسم:", ["المحطات العامة", "الموزعات (517)", "شمال الإسماعيلية"])

# ==========================================
# 2. دوال التحميل (المحطات والموزعات)
# ==========================================
@st.cache_data
def load_stations():
    if os.path.exists('Electricity_Stations_Final_Cleaned.xlsx'):
        df = pd.read_excel('Electricity_Stations_Final_Cleaned.xlsx')
        if 'ملاحظات' in df.columns: 
            df['ملاحظات'] = df['ملاحظات'].fillna('لا توجد ملاحظات')
        else: 
            df['ملاحظات'] = 'غير متوفر'
        df['العدد'] = 1
        return df
    return None

@st.cache_data
def load_distributors():
    # البحث عن أي ملف يحتوي على 517
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
    
    # التركة الذكية للرسم
    eng_counts = df.groupby('القطاع')['الهندسة'].nunique()
    df['قطاع_للرسم'] = df['القطاع'].apply(lambda x: f"{x} (هندسات: {eng_counts.get(x, 0)})")
    df['عدد_الموزعات'] = 1
    
    summary = df.groupby('القطاع').agg({'الهندسة': 'nunique', 'الموزع': 'count'}).reset_index()
    summary.columns = ['القطاع', 'عدد الهندسات', 'عدد الموزعات']
    return df, summary

# ==========================================
# 3. معالجة شمال الإسماعيلية (Core Logic)
# ==========================================
def strict_classify_multi(row, type_cols, col_name):
    # تجميع النصوص
    combined_type_text = ""
    if type_cols:
        for col in type_cols:
            val = str(row[col])
            if pd.notna(val) and val.strip() != 'nan':
                combined_type_text += val + " "

    # تنظيف
    type_clean = combined_type_text.strip().replace('أ', 'ا').replace('ة', 'ه')
    name_val = str(row[col_name]).strip() if col_name and pd.notna(row[col_name]) else ''
    name_clean = name_val.replace('أ', 'ا').replace('ة', 'ه')

    # القواعد الصارمة
    if 'غرف' in type_clean: return 'غرفة'
    if 'كشك' in type_clean: return 'كشك'
    if 'هواي' in type_clean or 'علق' in type_clean: return 'هوائي'
    if 'غرف' in name_clean: return 'غرفة'
    
    return 'كشك' # الأصل

def process_file_final(file_path, filename):
    try:
        # 1. البحث عن بداية الجدول (الهيدر)
        df_temp = pd.read_excel(file_path, header=None)
        start_row = 0
        found = False
        
        # نبحث في أول 50 سطر لضمان التقاط الملفات "العنيدة" مثل إسماعيلية ثان
        for idx, row in df_temp.head(50).iterrows():
            row_str = " ".join(row.astype(str).values)
            # كلمات مفتاحية قوية
            if ('اسم' in row_str and 'محول' in row_str) or \
               ('كشك' in row_str and 'غرفة' in row_str) or \
               ('بيان' in row_str and 'توزيع' in row_str) or \
               ('قدرة' in row_str and 'kva' in row_str.lower()):
                start_row = idx
                found = True
                break
        
        # قراءة الملف من السطر الصحيح
        df = pd.read_excel(file_path, header=start_row)
        df.columns = df.columns.astype(str).str.strip()

        # 2. تحديد الأعمدة (بمرونة عالية)
        col_name = next((c for c in df.columns if 'اسم' in c or 'محول' in c or 'بيان' in c), None)
        type_cols = [c for c in df.columns if 'نوع' in c or 'كشك' in c or 'غرف' in c or 'صنف' in c]
        col_cap  = next((c for c in df.columns if 'قدرة' in c or 'kva' in c.lower() or 'سعة' in c), None)

        if col_name:
            # تنظيف الصفوف
            df_clean = df.dropna(subset=[col_name]).copy()
            # حذف سطور الإجماليات
            df_clean = df_clean[~df_clean[col_name].astype(str).str.contains('total|اجمالي|عدد|تجميع', case=False, na=False)]
            # حذف السطور القصيرة جداً (التي لا تحتوي داتا)
            df_clean = df_clean[df_clean[col_name].astype(str).str.len() > 1]

            # تطبيق التصنيف
            df_clean['النوع_النهائي'] = df_clean.apply(lambda x: strict_classify_multi(x, type_cols, col_name), axis=1)

            # معالجة القدرة (بدون تقريب)
            if col_cap:
                # نحول النص لرقم ونستبدل الفواصل
                df_clean['القدرة_النهائية'] = pd.to_numeric(
                    df_clean[col_cap].astype(str).str.replace(',', '').str.replace(' ', ''),
                    errors='coerce'
                ).fillna(0)
            else:
                df_clean['القدرة_النهائية'] = 0.0

            # 3. استخراج اسم الهندسة والملكية من اسم الملف
            fname_clean = filename.replace('أ', 'ا').replace('ة', 'ه')
            
            # منطق تحديد الهندسة (تم إضافة كل الاحتمالات لظهور إسماعيلية ثان)
            if 'زايد' in fname_clean: dist = 'الشيخ زايد'
            elif 'اول' in fname_clean or '1' in fname_clean: dist = 'إسماعيلية أول'
            elif 'ثان' in fname_clean or '2' in fname_clean or 'تاني' in fname_clean: dist = 'إسماعيلية ثان'
            else: dist = 'غير محدد'

            if 'شركه' in fname_clean or 'شمال' in fname_clean: # افتراض أن ملفات الشمال قد تكون شركة
                owner = 'ملك الشركة'
            if 'غير' in fname_clean or 'اهالي' in fname_clean: 
                owner = 'ملك الغير'
            
            # تصحيح دقيق: إذا كان الاسم يحتوي على "شركة" فهو شركة بالتأكيد
            if 'شركه' in fname_clean: owner = 'ملك الشركة'

            return pd.DataFrame({
                'الهندسة': dist,
                'الملكية': owner,
                'اسم المحول': df_clean[col_name],
                'النوع': df_clean['النوع_النهائي'],
                'القدرة': df_clean['القدرة_النهائية']
            })
        return None
    except Exception as e:
        return None

@st.cache_data
def load_north_files():
    # يقرأ كل الملفات في المسار الحالي
    all_dfs = []
    # نستبعد ملفات النظام والكود
    excluded = ['Electricity_Stations_Final_Cleaned.xlsx', 'requirements.txt', 'app.py', '.git']
    
    files = os.listdir('.')
    for f in files:
        if f.endswith(('.xls', '.xlsx')) and f not in excluded and "517" not in f and not f.startswith('~$'):
            res = process_file_final(f, f)
            if res is not None: 
                all_dfs.append(res)
            
    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True)
        df['القطاع'] = 'شمال الإسماعيلية'
        return df
    return None

# ==========================================
# 4. الواجهة الرسمية
# ==========================================

if page == "المحطات العامة":
    st.header("توزيع المحطات (العدد والملاحظات)")
    df = load_stations()
    if df is not None:
        fig1 = px.sunburst(df, path=['القطاع', 'المحطة'], values='العدد', height=650, hover_data={'ملاحظات': True})
        fig1.update_traces(hovertemplate='<b>%{label}</b><br>عدد المحطات: %{value}<br>الملاحظات: %{customdata[0]}')
        st.plotly_chart(fig1, use_container_width=True)
        
        cnt = df['القطاع'].value_counts().reset_index()
        cnt.columns = ['القطاع', 'عدد المحطات']
        fig2 = px.bar(cnt, x='القطاع', y='عدد المحطات', color='القطاع', text='عدد المحطات')
        fig2.update_traces(textposition='outside')
        st.plotly_chart(fig2, use_container_width=True)
        
        st.dataframe(df[['القطاع', 'المحطة', 'ملاحظات']], use_container_width=True)
    else:
        st.error("⚠️ ملف المحطات غير موجود.")

elif page == "الموزعات (517)":
    st.header("توزيع الموزعات")
    df, summ = load_distributors()
    if df is not None:
        st.dataframe(summ, use_container_width=True)
        
        fig_sun = px.sunburst(df, path=['قطاع_للرسم', 'الهندسة', 'الموزع'], values='عدد_الموزعات', height=700)
        fig_sun.update_layout(font=dict(size=14))
        st.plotly_chart(fig_sun, use_container_width=True)
        
        cnt = df.groupby(['القطاع', 'الهندسة']).size().reset_index(name='العدد').sort_values('العدد', ascending=False)
        fig_bar = px.bar(cnt, x='الهندسة', y='العدد', color='القطاع', text='العدد')
        fig_bar.update_layout(xaxis=dict(tickmode='linear')) # إظهار كل الأسماء
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
        # تنسيق دقيق للرقم
        k1.metric("إجمالي القدرة (kVA)", f"{df['القدرة'].sum():,.2f}") 
        k2.metric("عدد المحولات", len(df))
        k3.metric("عدد الهندسات", df['الهندسة'].nunique())
        
        st.divider()
        
        # 1. إجمالي القدرات (بالكسور)
        st.subheader("1. إجمالي القدرات الكلية (kVA)")
        cap_summary = df.groupby(['الهندسة', 'الملكية'])['القدرة'].sum().reset_index()
        
        fig_main = px.bar(
            cap_summary, 
            x='الهندسة', y='القدرة', color='الملكية', text='القدرة', 
            barmode='group',
            color_discrete_map={'ملك الشركة': '#003f5c', 'ملك الغير': '#bc5090'}
        )
        # السر في إظهار الكسور هنا: texttemplate
        fig_main.update_traces(texttemplate='%{text:,.2f}', textposition='outside')
        st.plotly_chart(fig_main, use_container_width=True)
        
        # تجهيز البيانات
        type_stats = df.groupby(['الهندسة', 'الملكية', 'النوع']).agg(
            العدد=('اسم المحول', 'count'),
            إجمالي_القدرة=('القدرة', 'sum')
        ).reset_index()
        
        # ترتيب الفئات
        category_order = {'النوع': ['كشك', 'غرفة', 'هوائي', 'مبنى']}
        
        # 2. الأعداد
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

        # 3. القدرات حسب النوع (بالكسور)
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
        # إظهار الكسور هنا أيضاً
        fig_cap_type.update_traces(texttemplate='%{text:,.2f}', textposition='outside')
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
        fig_sun.update_traces(hovertemplate='<b>%{label}</b><br>القدرة: %{value:,.2f} kVA')
        st.plotly_chart(fig_sun, use_container_width=True)
        
        # الجدول
        st.subheader("الجدول التفصيلي")
        st.dataframe(df[['الهندسة', 'الملكية', 'النوع', 'اسم المحول', 'القدرة']], use_container_width=True)
        
    else:
        st.error("لم يتم العثور على ملفات البيانات. تأكد من رفع ملفات الإكسل بجانب ملف app.py")
