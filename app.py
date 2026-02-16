import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==========================================
# 1. إعداد الصفحة والتصميم الاحترافي (CSS)
# ==========================================
st.set_page_config(layout="wide", page_title="Dashboard Electricity", page_icon="⚡")

# Custom CSS for Professional Look
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
    }
    
    /* تنسيق التبويبات */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 10px 10px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2E86C1;
        color: white;
    }

    /* تنسيق الكروت (Cards) */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e6e6e6;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        text-align: center;
        transition: transform 0.2s;
        margin-bottom: 10px;
    }
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15);
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #2c3e50;
        margin: 5px 0;
    }
    .metric-label {
        font-size: 14px;
        color: #7f8c8d;
        font-weight: 600;
    }
    
    /* ألوان مخصصة للأرقام */
    .val-blue { color: #2980b9; }   /* كشك */
    .val-red { color: #c0392b; }    /* غرفة */
    .val-purple { color: #8e44ad; } /* هوائي */
    
    h3 { border-bottom: 2px solid #eee; padding-bottom: 10px; color: #2E86C1; }
</style>
""", unsafe_allow_html=True)

# ألوان الرسومات
COLOR_MAP = {'كشك': '#2980b9', 'غرفة': '#c0392b', 'هوائي': '#8e44ad', 'مبنى': '#f1c40f'}
OWNER_COLOR = {'ملك الشركة': '#2c3e50', 'ملك الغير': '#d35400'}

# ==========================================
# 2. دوال المعالجة (Backend Logic)
# ==========================================
@st.cache_data
def load_stations():
    if os.path.exists('Electricity_Stations_Final_Cleaned.xlsx'):
        df = pd.read_excel('Electricity_Stations_Final_Cleaned.xlsx')
        if 'ملاحظات' in df.columns: df['ملاحظات'] = df['ملاحظات'].fillna('لا توجد ملاحظات')
        else: df['ملاحظات'] = 'غير متوفر'
        df['العدد'] = 1
        return df
    return None

@st.cache_data
def load_distributors():
    files = [f for f in os.listdir('.') if "517" in f and (f.endswith('.xlsx') or f.endswith('.csv'))]
    if not files: return None, None
    path = files[0]
    df = pd.read_csv(path).iloc[:, [1, 2, 3, 4]] if path.endswith('.csv') else pd.read_excel(path).iloc[:, [1, 2, 3, 4]]
    df.columns = ['القطاع', 'الهندسة', 'مسلسل', 'الموزع']
    df = df.replace('nan', pd.NA).ffill()
    df = df[pd.to_numeric(df['مسلسل'], errors='coerce').notnull()]
    df['القطاع'] = df['القطاع'].astype(str).str.strip()
    df['الهندسة'] = df['الهندسة'].astype(str).str.strip()
    eng_counts = df.groupby('القطاع')['الهندسة'].nunique()
    df['قطاع_للرسم'] = df['القطاع'].apply(lambda x: f"{x} (هندسات: {eng_counts.get(x, 0)})")
    df['عدد_الموزعات'] = 1
    summary = df.groupby('القطاع').agg({'الهندسة': 'nunique', 'الموزع': 'count'}).reset_index()
    summary.columns = ['القطاع', 'عدد الهندسات', 'عدد الموزعات']
    return df, summary

def strict_classify_multi(row, type_cols, col_name):
    combined_type_text = ""
    if type_cols:
        for col in type_cols:
            val = str(row[col])
            if pd.notna(val) and val.strip() != 'nan': combined_type_text += val + " "
    type_clean = combined_type_text.strip().replace('أ', 'ا').replace('ة', 'ه')
    name_val = str(row[col_name]).strip() if col_name and pd.notna(row[col_name]) else ''
    name_clean = name_val.replace('أ', 'ا').replace('ة', 'ه')
    
    if 'غرف' in type_clean: return 'غرفة'
    if 'كشك' in type_clean: return 'كشك'
    if 'هواي' in type_clean or 'علق' in type_clean: return 'هوائي'
    if 'غرف' in name_clean: return 'غرفة'
    return 'كشك'

def process_file_final(file_path, filename):
    try:
        df_temp = pd.read_excel(file_path, header=None)
        start_row = 0
        found_header = False
        for idx, row in df_temp.head(50).iterrows():
            row_str = " ".join(row.astype(str).values)
            if ('اسم' in row_str and 'محول' in row_str) or ('كشك' in row_str and 'غرفة' in row_str) or ('قدرة' in row_str):
                start_row = idx
                found_header = True
                break
        
        if not found_header: return None
        df = pd.read_excel(file_path, header=start_row)
        df.columns = df.columns.astype(str).str.strip()

        col_name = next((c for c in df.columns if 'اسم' in c or 'محول' in c or 'بيان' in c), None)
        type_cols = [c for c in df.columns if 'نوع' in c or 'كشك' in c or 'غرف' in c]
        col_cap  = next((c for c in df.columns if 'قدرة' in c or 'kva' in c.lower()), None)

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
            if 'شركه' in fname_clean: owner = 'ملك الشركة'

            return pd.DataFrame({'الهندسة': dist, 'الملكية': owner, 'اسم المحول': df_clean[col_name],
                                 'النوع': df_clean['النوع_النهائي'], 'القدرة': df_clean['القدرة_النهائية']})
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

# دالة مساعدة لرسم الكروت
def draw_card(title, value, unit="", color_class=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{title}</div>
        <div class="metric-value {color_class}">{value} <span style="font-size:16px;">{unit}</span></div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. واجهة التطبيق (Tabs Interface)
# ==========================================

# تحميل البيانات مرة واحدة
df_stations = load_stations()
df_dist, dist_summary = load_distributors()
df_north = load_all_north_data()

st.title("⚡ منظومة إدارة الكهرباء - Dashboard")

# إنشاء التبويبات
tab1, tab2, tab3, tab4 = st.tabs(["🏠 الرئيسية", "🗺️ قطاع الشمال (تحليلي)", "🔌 الموزعات", "🏭 المحطات العامة"])

# --- TAB 1: الرئيسية (Overview) ---
with tab1:
    st.subheader("نظرة عامة على القطاعات")
    
    # حسابات عامة
    total_st = len(df_stations) if df_stations is not None else 0
    total_dst = len(df_dist) if df_dist is not None else 0
    total_nth = len(df_north) if not df_north.empty else 0
    
    col1, col2, col3 = st.columns(3)
    with col1: draw_card("إجمالي المحطات", total_st, "محطة")
    with col2: draw_card("إجمالي الموزعات (517)", total_dst, "موزع")
    with col3: draw_card("إجمالي محولات الشمال", total_nth, "محول")
    
    st.markdown("---")
    
    # رسم بياني عام (إذا توفرت داتا الشمال)
    if not df_north.empty:
        st.write("### 📊 توزيع الأحمال في قطاع الشمال")
        fig_main = px.pie(df_north, names='النوع', title='نسبة أنواع المحولات (كشك/غرفة/هوائي)', 
                          color='النوع', color_discrete_map=COLOR_MAP, hole=0.4)
        st.plotly_chart(fig_main, use_container_width=True)

# --- TAB 2: شمال الإسماعيلية (The Professional View) ---
with tab2:
    if not df_north.empty:
        st.markdown("### 🧬 تحليل بيانات قطاع شمال الإسماعيلية")
        
        # --- القسم الأول: كروت الأرقام (الشركة vs الغير) ---
        
        # تصفية البيانات
        df_co = df_north[df_north['الملكية'] == 'ملك الشركة']
        df_ot = df_north[df_north['الملكية'] == 'ملك الغير']
        
        c1, c2 = st.columns(2)
        
        # --- عمود ملك الشركة ---
        with c1:
            st.info("🏢 **بيانات ملك الشركة**")
            # حسابات
            co_total = len(df_co)
            co_kiosk = len(df_co[df_co['النوع'] == 'كشك'])
            co_room = len(df_co[df_co['النوع'] == 'غرفة'])
            co_aerial = len(df_co[df_co['النوع'] == 'هوائي'])
            
            kc1, kc2 = st.columns(2)
            with kc1: draw_card("إجمالي المحولات", co_total)
            with kc2: draw_card("أكشاك", co_kiosk, color_class="val-blue")
            
            kc3, kc4 = st.columns(2)
            with kc3: draw_card("غرف", co_room, color_class="val-red")
            with kc4: draw_card("هوائي", co_aerial, color_class="val-purple")

        # --- عمود ملك الغير ---
        with c2:
            st.warning("👤 **بيانات ملك الغير**")
            # حسابات
            ot_total = len(df_ot)
            ot_kiosk = len(df_ot[df_ot['النوع'] == 'كشك'])
            ot_room = len(df_ot[df_ot['النوع'] == 'غرفة'])
            ot_aerial = len(df_ot[df_ot['النوع'] == 'هوائي'])
            
            oc1, oc2 = st.columns(2)
            with oc1: draw_card("إجمالي المحولات", ot_total)
            with oc2: draw_card("أكشاك", ot_kiosk, color_class="val-blue")
            
            oc3, oc4 = st.columns(2)
            with oc3: draw_card("غرف", ot_room, color_class="val-red")
            with oc4: draw_card("هوائي", ot_aerial, color_class="val-purple")

        st.markdown("---")

        # --- القسم الثاني: الرسوم البيانية التفاعلية ---
        st.subheader("📈 الرسوم البيانية التفاعلية")
        
        g_col1, g_col2 = st.columns([1, 1])
        
        with g_col1:
            # Sunburst
            fig_sun = px.sunburst(df_north, path=['الهندسة', 'الملكية', 'النوع'], values='القدرة',
                                  color='الملكية', color_discrete_map=OWNER_COLOR,
                                  title="توزيع القدرات (kVA) حسب الهندسة والملكية")
            fig_sun.update_layout(height=500)
            st.plotly_chart(fig_sun, use_container_width=True)

        with g_col2:
            # Stacked Bar Chart
            counts = df_north.groupby(['الهندسة', 'النوع']).size().reset_index(name='العدد')
            fig_bar = px.bar(counts, x='الهندسة', y='العدد', color='النوع', barmode='group',
                             color_discrete_map=COLOR_MAP, text='العدد',
                             title="مقارنة أنواع المحولات بين الهندسات")
            fig_bar.update_traces(textposition='outside')
            fig_bar.update_layout(height=500)
            st.plotly_chart(fig_bar, use_container_width=True)

        # جدول البيانات
        with st.expander("📂 عرض الجدول التفصيلي للبيانات"):
            st.dataframe(df_north, use_container_width=True)

    else:
        st.error("⚠️ يرجى رفع ملفات الاكسيل الخاصة بقطاع الشمال لظهور البيانات.")

# --- TAB 3: الموزعات ---
with tab3:
    if df_dist is not None:
        st.subheader("تحليل الموزعات (كود 517)")
        st.dataframe(dist_summary, use_container_width=True)
        
        col_d1, col_d2 = st.columns([1, 2])
        with col_d1:
            fig_d_sun = px.sunburst(df_dist, path=['القطاع', 'الهندسة'], title="توزيع الهندسات")
            st.plotly_chart(fig_d_sun, use_container_width=True)
        with col_d2:
            cnt_dist = df_dist.groupby(['القطاع', 'الهندسة']).size().reset_index(name='العدد')
            cnt_dist = cnt_dist.sort_values('العدد', ascending=False)
            fig_d_bar = px.bar(cnt_dist, x='الهندسة', y='العدد', color='القطاع', text='العدد')
            fig_d_bar.update_traces(textposition='outside')
            fig_d_bar.update_layout(xaxis=dict(tickangle=-45))
            st.plotly_chart(fig_d_bar, use_container_width=True)
    else:
        st.warning("لم يتم العثور على ملف الموزعات.")

# --- TAB 4: المحطات ---
with tab4:
    if df_stations is not None:
        st.subheader("خريطة المحطات العامة")
        fig_st = px.treemap(df_stations, path=['القطاع', 'المحطة'], values='العدد', 
                            color='القطاع', hover_data=['ملاحظات'])
        fig_st.update_layout(height=600)
        st.plotly_chart(fig_st, use_container_width=True)
        st.dataframe(df_stations)
    else:
        st.warning("لم يتم العثور على ملف المحطات.")
