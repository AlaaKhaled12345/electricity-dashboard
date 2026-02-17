import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==========================================
# 1. إعداد الصفحة والتصميم
# ==========================================
st.set_page_config(layout="wide", page_title="Dashboard Electricity", page_icon="⚡")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Cairo', sans-serif; direction: rtl; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #ffffff; padding: 10px; border-radius: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f8f9fa; border-radius: 10px; color: #4a4a4a; font-weight: bold; border: 1px solid #e9ecef; }
    .stTabs [aria-selected="true"] { background-color: #2E86C1; color: white; border: none; }
    .metric-card { background: linear-gradient(135deg, #ffffff 0%, #f9f9f9 100%); border-right: 5px solid #2E86C1; border-radius: 12px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); text-align: center; margin-bottom: 20px; transition: transform 0.3s ease; }
    .metric-card:hover { transform: translateY(-5px); }
    .metric-title { color: #7f8c8d; font-size: 1.1rem; margin-bottom: 10px; font-weight: 600; }
    .metric-value { color: #2c3e50; font-size: 2.2rem; font-weight: 800; }
    .metric-sub { font-size: 0.9rem; color: #95a5a6; }
    .card-company { border-right-color: #2980b9; }
    .card-private { border-right-color: #c0392b; }
    h3 { color: #2E86C1; border-bottom: 2px solid #eee; padding-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

COLOR_MAP = {'كشك': '#2980b9', 'غرفة': '#c0392b', 'هوائي': '#8e44ad', 'مبنى': '#f1c40f'}

# ==========================================
# 2. الدالة السحرية لتوحيد الأسماء (The Fix)
# ==========================================
def get_standard_sector_name(raw_name):
    """
    دالة تقوم بإجبار الاسم المدخل ليكون واحداً من الأسماء القياسية الـ 11
    """
    s = str(raw_name).strip()
    # تنظيف الحروف (توحيد الهمزات والهاء)
    s = s.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ة', 'ه')
    
    # القواعد (Mapping Rules)
    if 'سويس' in s: return 'قطاع السويس'
    if 'بور' in s and 'سعيد' in s: return 'قطاع بورسعيد'
    if 'مدن' in s and 'جديده' in s: return 'قطاع المدن الجديدة'
    if 'بحر' in s and 'احمر' in s: return 'قطاع البحر الأحمر'
    
    if 'سيناء' in s:
        if 'شمال' in s: return 'قطاع شمال سيناء'
        if 'جنوب' in s: return 'قطاع جنوب سيناء'
        
    if 'شرقيه' in s:
        if 'شمال' in s: return 'قطاع شمال الشرقية'
        if 'جنوب' in s: return 'قطاع جنوب الشرقية'
        if 'وسط' in s: return 'قطاع وسط الشرقية'
        
    if 'اسماعيليه' in s:
        # استبعاد الصفوف التجميعية الغريبة مثل "قطاعي شمال - جنوب"
        if 'شمال' in s and 'جنوب' in s: return None 
        if 'شمال' in s: return 'قطاع شمال الإسماعيلية'
        if 'جنوب' in s: return 'قطاع جنوب الإسماعيلية'
        
    return None # لو الاسم مش مفهوم أو فارغ يرجعه None عشان يتفلتر

# ==========================================
# 3. دوال التحميل (معدلة لتستخدم التوحيد)
# ==========================================

@st.cache_data
def load_stations():
    if os.path.exists('Electricity_Stations_Final_Cleaned.xlsx'):
        df = pd.read_excel('Electricity_Stations_Final_Cleaned.xlsx')
        if 'ملاحظات' in df.columns: df['ملاحظات'] = df['ملاحظات'].fillna('لا توجد ملاحظات')
        else: df['ملاحظات'] = 'غير متوفر'
        
        # تطبيق التوحيد فوراً على العمود
        df['القطاع_الاصلي'] = df['القطاع'] # نحتفظ بالاصلي لو احتجناه
        df['القطاع'] = df['القطاع'].apply(get_standard_sector_name)
        
        # حذف الصفوف التي لم يتم التعرف عليها (None)
        df = df.dropna(subset=['القطاع'])
        
        df['العدد'] = 1
        return df
    return None

@st.cache_data
def load_distributors():
    files = [f for f in os.listdir('.') if "517" in f and (f.endswith('.xlsx') or f.endswith('.csv'))]
    if not files: return None, None
    path = files[0]
    try:
        if path.endswith('.csv'): df = pd.read_csv(path).iloc[:, [1, 2, 3, 4]]
        else: df = pd.read_excel(path).iloc[:, [1, 2, 3, 4]]
            
        df.columns = ['القطاع', 'الهندسة', 'مسلسل', 'الموزع']
        df = df.replace('nan', pd.NA).ffill()
        df = df[pd.to_numeric(df['مسلسل'], errors='coerce').notnull()]
        
        # تطبيق التوحيد هنا أيضاً
        df['القطاع'] = df['القطاع'].apply(get_standard_sector_name)
        df = df.dropna(subset=['القطاع'])
        
        df['الهندسة'] = df['الهندسة'].astype(str).str.strip()
        eng_counts = df.groupby('القطاع')['الهندسة'].nunique()
        df['قطاع_للرسم'] = df['القطاع'].apply(lambda x: f"{x} (هندسات: {eng_counts.get(x, 0)})")
        df['عدد_الموزعات'] = 1
        
        summary = df.groupby('القطاع').agg({'الهندسة': 'nunique', 'الموزع': 'count'}).reset_index()
        summary.columns = ['القطاع', 'عدد الهندسات', 'عدد الموزعات']
        return df, summary
    except Exception as e: return None, None

def strict_classify_multi(row, type_cols, col_name):
    combined_type_text = ""
    if type_cols:
        for col in type_cols:
            val = str(row[col])
            if pd.notna(val) and val.strip() != 'nan': combined_type_text += val + " "
    type_clean = combined_type_text.strip().replace('أ', 'ا').replace('ة', 'ه')
    name_val = str(row[col_name]).strip() if col_name and pd.notna(row[col_name]) else ''
    if 'غرف' in type_clean or 'غرف' in name_val: return 'غرفة'
    if 'هواي' in type_clean or 'علق' in type_clean: return 'هوائي'
    return 'كشك'

def process_file_final(file_path, filename):
    try:
        df_temp = pd.read_excel(file_path, header=None)
        start_row = 0
        found_header = False
        for idx, row in df_temp.head(50).iterrows():
            row_str = " ".join(row.astype(str).values)
            if ('اسم' in row_str and 'محول' in row_str) or ('كشك' in row_str and 'غرفة' in row_str):
                start_row = idx
                found_header = True
                break
        
        if not found_header: return None
        df = pd.read_excel(file_path, header=start_row)
        df.columns = df.columns.astype(str).str.strip()
        col_name = next((c for c in df.columns if 'اسم' in c or 'محول' in c or 'بيان' in c), None)
        type_cols = [c for c in df.columns if 'نوع' in c or 'كشك' in c or 'غرف' in c]
        col_cap = next((c for c in df.columns if 'قدرة' in c or 'kva' in c.lower()), None)

        if col_name:
            df_clean = df.dropna(subset=[col_name]).copy()
            df_clean = df_clean[~df_clean[col_name].astype(str).str.contains('total|اجمالي|عدد', case=False, na=False)]
            df_clean = df_clean[df_clean[col_name].astype(str).str.len() > 1]
            df_clean['النوع_النهائي'] = df_clean.apply(lambda x: strict_classify_multi(x, type_cols, col_name), axis=1)
            
            if col_cap:
                df_clean['القدرة_النهائية'] = pd.to_numeric(df_clean[col_cap].astype(str).str.replace(',', '').str.replace(' ', ''), errors='coerce').fillna(0)
            else: df_clean['القدرة_النهائية'] = 0.0

            fname_clean = filename.replace('أ', 'ا').replace('ة', 'ه').lower()
            if 'زايد' in fname_clean: dist = 'الشيخ زايد'
            elif ('اول' in fname_clean or '1' in fname_clean) and 'ثان' not in fname_clean: dist = 'إسماعيلية أول'
            elif 'ثان' in fname_clean or '2' in fname_clean or 'تاني' in fname_clean: dist = 'إسماعيلية ثان'
            else: dist = 'غير محدد' 
            owner = 'ملك الشركة' if 'شركه' in fname_clean else ('ملك الغير' if 'غير' in fname_clean else 'غير محدد')

            return pd.DataFrame({'الهندسة': dist, 'الملكية': owner, 'اسم المحول': df_clean[col_name], 'النوع': df_clean['النوع_النهائي'], 'القدرة': df_clean['القدرة_النهائية'], 'القطاع': 'شمال الإسماعيلية'}) # هنا ثابت لأنه قطاع واحد
        return None
    except: return None

def load_all_north_data():
    all_dfs = []
    excluded = ['Electricity_Stations_Final_Cleaned.xlsx', 'requirements.txt', 'app.py', '.git']
    files = [f for f in os.listdir('.') if f.endswith(('.xls', '.xlsx')) and f not in excluded and "517" not in f and not f.startswith('~$')]
    for f in files:
        res = process_file_final(f, f)
        if res is not None: all_dfs.append(res)
    if all_dfs: return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()

def metric_card(title, value, subtitle="", style_class=""):
    st.markdown(f"""
    <div class="metric-card {style_class}">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 4. الواجهة الرئيسية
# ==========================================
st.title("⚡ منظومة إدارة الكهرباء - Dashboard")

df_st = load_stations()
df_dst, df_dst_summ = load_distributors()
df_nth = load_all_north_data()

tab_home, tab_north, tab_dist, tab_stations = st.tabs(["🏠 الرئيسية", "🗺️ قطاع شمال الإسماعيلية", "🔌 الموزعات (517)", "🏭 المحطات العامة"])

# --- Tab 1: Home ---
with tab_home:
    st.markdown("### 📊 ملخص بيانات الشركة")
    
    # تجميع القطاعات الفريدة بعد التنظيف
    unique_sectors = set()
    if df_st is not None: unique_sectors.update(df_st['القطاع'].unique())
    if df_dst is not None: unique_sectors.update(df_dst['القطاع'].unique())
    
    # حذف القيم الفارغة إن وجدت
    unique_sectors = {x for x in unique_sectors if x is not None and str(x) != 'nan'}
    
    count_sectors = len(unique_sectors)
    count_st = len(df_st) if df_st is not None else 0
    count_dst = len(df_dst) if df_dst is not None else 0
    count_nth = len(df_nth) if not df_nth.empty else 0
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        metric_card("عدد القطاعات", count_sectors, "قطاع جغرافي")
        with st.expander("عرض القائمة الموحدة"):
            st.write(sorted(list(unique_sectors)))
    with c2: metric_card("المحطات العامة", count_st, "محطة")
    with c3: metric_card("الموزعات", count_dst, "موزع (517)")
    with c4: metric_card("محولات الشمال", count_nth, "محول")

    st.markdown("---")
    
    # تفاصيل الشمال
    if not df_nth.empty:
        df_co = df_nth[df_nth['الملكية'] == 'ملك الشركة']
        df_pr = df_nth[df_nth['الملكية'] == 'ملك الغير']
        col_co, col_pr = st.columns(2)
        with col_co:
            st.info("🏢 **ملك الشركة**")
            k1, k2, k3 = st.columns(3)
            with k1: metric_card("أكشاك", len(df_co[df_co['النوع']=='كشك']), style_class="card-company")
            with k2: metric_card("غرف", len(df_co[df_co['النوع']=='غرفة']), style_class="card-company")
            with k3: metric_card("هوائي", len(df_co[df_co['النوع']=='هوائي']), style_class="card-company")
        with col_pr:
            st.warning("👤 **ملك الغير**")
            p1, p2, p3 = st.columns(3)
            with p1: metric_card("أكشاك", len(df_pr[df_pr['النوع']=='كشك']), style_class="card-private")
            with p2: metric_card("غرف", len(df_pr[df_pr['النوع']=='غرفة']), style_class="card-private")
            with p3: metric_card("هوائي", len(df_pr[df_pr['النوع']=='هوائي']), style_class="card-private")

    st.markdown("---")
    
    # الرسوم المجمعة
    row3_c1, row3_c2, row3_c3 = st.columns(3)
    with row3_c1:
        if df_st is not None:
            st.caption("توزيع المحطات العامة")
            fig1 = px.sunburst(df_st, path=['القطاع', 'المحطة'])
            st.plotly_chart(fig1, use_container_width=True)
    with row3_c2:
        if df_dst is not None:
            st.caption("توزيع الموزعات")
            fig2 = px.sunburst(df_dst, path=['قطاع_للرسم', 'الهندسة'])
            st.plotly_chart(fig2, use_container_width=True)
    with row3_c3:
        if not df_nth.empty:
            st.caption("توزيع محولات الشمال")
            fig3 = px.sunburst(df_nth, path=['الملكية', 'النوع'], color='النوع', color_discrete_map=COLOR_MAP)
            st.plotly_chart(fig3, use_container_width=True)

# --- Tab 2: North Sector ---
with tab_north:
    if not df_nth.empty:
        st.subheader("تحليل قطاع شمال الإسماعيلية")
        all_eng = ['الكل'] + list(df_nth['الهندسة'].unique())
        selected_eng = st.selectbox("اختر الهندسة:", all_eng)
        df_view = df_nth if selected_eng == 'الكل' else df_nth[df_nth['الهندسة'] == selected_eng]
        
        col_n1, col_n2 = st.columns([2, 1])
        with col_n1:
            fig_sun_n = px.sunburst(df_view, path=['الهندسة', 'الملكية', 'النوع', 'اسم المحول'], values='القدرة', color='النوع', color_discrete_map=COLOR_MAP, height=600)
            st.plotly_chart(fig_sun_n, use_container_width=True)
        with col_n2:
            st.metric("إجمالي القدرة", f"{df_view['القدرة'].sum():,.1f} kVA")
            cnt_type = df_view['النوع'].value_counts().reset_index()
            cnt_type.columns = ['النوع', 'العدد']
            fig_bar_n = px.bar(cnt_type, x='النوع', y='العدد', color='النوع', color_discrete_map=COLOR_MAP)
            st.plotly_chart(fig_bar_n, use_container_width=True)
        st.dataframe(df_view)

# --- Tab 3: Distributors ---
with tab_dist:
    if df_dst is not None:
        st.subheader("الموزعات (517)")
        cd1, cd2 = st.columns([1, 2])
        with cd1:
            fig_d_sun = px.sunburst(df_dst, path=['قطاع_للرسم', 'الهندسة', 'الموزع'], height=600)
            st.plotly_chart(fig_d_sun, use_container_width=True)
        with cd2:
            cnt_dst = df_dst.groupby(['القطاع', 'الهندسة']).size().reset_index(name='العدد').sort_values('العدد', ascending=False)
            fig_d_bar = px.bar(cnt_dst, x='الهندسة', y='العدد', color='القطاع', text='العدد')
            st.plotly_chart(fig_d_bar, use_container_width=True)
        st.dataframe(df_dst_summ, use_container_width=True)

# --- Tab 4: Stations ---
with tab_stations:
    if df_st is not None:
        st.subheader("المحطات العامة")
        cs1, cs2 = st.columns([3, 1])
        with cs1:
            fig_s_sun = px.sunburst(df_st, path=['القطاع', 'المحطة'], values='العدد', height=600)
            st.plotly_chart(fig_s_sun, use_container_width=True)
        with cs2:
            cnt_sec = df_st['القطاع'].
