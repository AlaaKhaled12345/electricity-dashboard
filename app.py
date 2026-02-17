import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==========================================
# 1. إعداد الصفحة والتصميم (CSS)
# ==========================================
st.set_page_config(layout="wide", page_title="Dashboard Electricity", page_icon="⚡")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
    }
    
    /* تنسيق التبويبات */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #ffffff;
        padding: 10px;
        border-radius: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f8f9fa;
        border-radius: 10px;
        color: #4a4a4a;
        font-weight: bold;
        border: 1px solid #e9ecef;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2E86C1;
        color: white;
        border: none;
    }

    /* تنسيق الكروت (Metric Cards) */
    .metric-card {
        background: linear-gradient(135deg, #ffffff 0%, #f9f9f9 100%);
        border-right: 5px solid #2E86C1;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 20px;
        transition: transform 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .metric-title {
        color: #7f8c8d;
        font-size: 1.1rem;
        margin-bottom: 10px;
        font-weight: 600;
    }
    .metric-value {
        color: #2c3e50;
        font-size: 2.2rem;
        font-weight: 800;
    }
    .metric-sub {
        font-size: 0.9rem;
        color: #95a5a6;
    }

    /* ألوان مخصصة */
    .card-company { border-right-color: #2980b9; }
    .card-private { border-right-color: #c0392b; }
    
    h3 { color: #2E86C1; border-bottom: 2px solid #eee; padding-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# خريطة الألوان الموحدة
COLOR_MAP = {'كشك': '#2980b9', 'غرفة': '#c0392b', 'هوائي': '#8e44ad', 'مبنى': '#f1c40f'}

# ==========================================
# 2. دوال المعالجة والتحميل (Backend Logic)
# ==========================================

@st.cache_data
def load_stations():
    """تحميل بيانات المحطات العامة"""
    if os.path.exists('Electricity_Stations_Final_Cleaned.xlsx'):
        df = pd.read_excel('Electricity_Stations_Final_Cleaned.xlsx')
        # تنظيف بسيط للأعمدة
        if 'ملاحظات' in df.columns: 
            df['ملاحظات'] = df['ملاحظات'].fillna('لا توجد ملاحظات')
        else: 
            df['ملاحظات'] = 'غير متوفر'
        
        # التأكد من أن عمود القطاع نصي
        df['القطاع'] = df['القطاع'].astype(str)
        df['العدد'] = 1
        return df
    return None

@st.cache_data
def load_distributors():
    """تحميل بيانات الموزعات (517)"""
    files = [f for f in os.listdir('.') if "517" in f and (f.endswith('.xlsx') or f.endswith('.csv'))]
    if not files: return None, None
    
    path = files[0]
    try:
        if path.endswith('.csv'):
            df = pd.read_csv(path).iloc[:, [1, 2, 3, 4]]
        else:
            df = pd.read_excel(path).iloc[:, [1, 2, 3, 4]]
            
        df.columns = ['القطاع', 'الهندسة', 'مسلسل', 'الموزع']
        df = df.replace('nan', pd.NA).ffill()
        df = df[pd.to_numeric(df['مسلسل'], errors='coerce').notnull()]
        
        # تحويل الأعمدة لنصوص صريحة للتنظيف
        df['القطاع'] = df['القطاع'].astype(str).str.strip()
        df['الهندسة'] = df['الهندسة'].astype(str).str.strip()
        
        # التركة: حساب عدد الهندسات لكل قطاع وإضافته للاسم
        eng_counts = df.groupby('القطاع')['الهندسة'].nunique()
        df['قطاع_للرسم'] = df['القطاع'].apply(lambda x: f"{x} (هندسات: {eng_counts.get(x, 0)})")
        
        df['عدد_الموزعات'] = 1
        
        # جدول الملخص
        summary = df.groupby('القطاع').agg({'الهندسة': 'nunique', 'الموزع': 'count'}).reset_index()
        summary.columns = ['القطاع', 'عدد الهندسات', 'عدد الموزعات']
        
        return df, summary
    except Exception as e:
        return None, None

# دوال مساعدة لقطاع الشمال
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
        # قراءة ذكية لاكتشاف بداية الجدول
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
                df_clean['القدرة_النهائية'] = pd.to_numeric(
                    df_clean[col_cap].astype(str).str.replace(',', '').str.replace(' ', ''), 
                    errors='coerce'
                ).fillna(0)
            else: 
                df_clean['القدرة_النهائية'] = 0.0

            fname_clean = filename.replace('أ', 'ا').replace('ة', 'ه').lower()
            if 'زايد' in fname_clean: dist = 'الشيخ زايد'
            elif ('اول' in fname_clean or '1' in fname_clean) and 'ثان' not in fname_clean: dist = 'إسماعيلية أول'
            elif 'ثان' in fname_clean or '2' in fname_clean or 'تاني' in fname_clean: dist = 'إسماعيلية ثان'
            else: dist = 'غير محدد' 
            
            owner = 'ملك الشركة' if 'شركه' in fname_clean else ('ملك الغير' if 'غير' in fname_clean else 'غير محدد')

            return pd.DataFrame({
                'الهندسة': dist, 
                'الملكية': owner, 
                'اسم المحول': df_clean[col_name],
                'النوع': df_clean['النوع_النهائي'], 
                'القدرة': df_clean['القدرة_النهائية'],
                'القطاع': 'شمال الإسماعيلية' # توحيد اسم القطاع هنا
            })
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

# دالة رسم الكارت HTML
def metric_card(title, value, subtitle="", style_class=""):
    st.markdown(f"""
    <div class="metric-card {style_class}">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. واجهة التطبيق (الرئيسية)
# ==========================================

st.title("⚡ منظومة إدارة الكهرباء - Dashboard")

# تحميل البيانات عند بدء التشغيل
df_st = load_stations()
df_dst, df_dst_summ = load_distributors()
df_nth = load_all_north_data()

# تعريف التبويبات
tab_home, tab_north, tab_dist, tab_stations = st.tabs([
    "🏠 الرئيسية (Dashboard)", 
    "🗺️ قطاع شمال الإسماعيلية", 
    "🔌 الموزعات (517)", 
    "🏭 المحطات العامة"
])

# -----------------------------------------------------------------------------
# TAB 1: الصفحة الرئيسية (الملخص)
# -----------------------------------------------------------------------------
with tab_home:
    st.markdown("### 📊 ملخص بيانات الشركة")
    
    # ----------------------------------------------------
    # الحل الجذري لمشكلة عدد القطاعات (التنظيف الشامل)
    # ----------------------------------------------------
    all_sectors_raw = []
    
    # 1. تجميع الأسماء من كل المصادر المتاحة
    if df_st is not None: 
        all_sectors_raw.extend(df_st['القطاع'].astype(str).tolist())
    if df_dst is not None: 
        all_sectors_raw.extend(df_dst['القطاع'].astype(str).tolist())
    
    # 2. عملية الفلترة والتوحيد (Normalization)
    clean_sectors_set = set()
    
    for s in all_sectors_raw:
        # مسح المسافات الزائدة
        s_clean = s.strip()
        
        # توحيد الحروف (اختياري لزيادة الدقة)
        # يحول "أ" و "إ" و "آ" إلى "ا" 
        # يحول "ة" إلى "ه"
        s_clean = s_clean.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ة', 'ه')
        
        # استبعاد القيم غير الصحيحة
        invalid_values = ['nan', 'none', 'null', '', 'nat']
        if s_clean.lower() not in invalid_values:
            # استبعاد العناوين الغريبة اللي ظهرت في الصورة زي "قطاعي شمال - جنوب"
            # (اختياري: لو عايزه تشيلي حاجات معينة ضيفي شرط هنا)
            if "قطاعى" not in s_clean: 
                 clean_sectors_set.add(s_clean)
            
    count_sectors = len(clean_sectors_set)
    
    # باقي العدادات
    count_st = len(df_st) if df_st is not None else 0
    count_dst = len(df_dst) if df_dst is not None else 0
    count_nth = len(df_nth) if not df_nth.empty else 0
    
    # عرض الكروت
    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        metric_card("عدد القطاعات", count_sectors, "قطاع جغرافي")
        # زرار فحص للتأكد
        with st.expander("🔍 عرض أسماء القطاعات (للمراجعة)"):
            st.write(sorted(list(clean_sectors_set)))
            
    with c2: metric_card("المحطات العامة", count_st, "محطة")
    with c3: metric_card("الموزعات", count_dst, "موزع (517)")
    with c4: metric_card("محولات الشمال", count_nth, "محول (شركة + غير)")

    st.markdown("---")
    
    # تفاصيل قطاع الشمال
    if not df_nth.empty:
        st.markdown("### 🧬 تفاصيل محولات قطاع الشمال")
        
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
    st.markdown("### 📈 الرسوم التوضيحية المجمعة")
    
    # رسومات Sunburst مجمعة
    row3_c1, row3_c2, row3_c3 = st.columns(3)
    
    with row3_c1:
        if df_st is not None:
            fig1 = px.sunburst(df_st, path=['القطاع', 'المحطة'], title="توزيع المحطات العامة")
            st.plotly_chart(fig1, use_container_width=True)
            
    with row3_c2:
        if df_dst is not None:
            # استخدام العمود المنظف للعرض
            fig2 = px.sunburst(df_dst, path=['قطاع_للرسم', 'الهندسة'], title="توزيع الموزعات")
            st.plotly_chart(fig2, use_container_width=True)
            
    with row3_c3:
        if not df_nth.empty:
            fig3 = px.sunburst(df_nth, path=['الملكية', 'النوع'], title="توزيع محولات الشمال", color='النوع', color_discrete_map=COLOR_MAP)
            st.plotly_chart(fig3, use_container_width=True)

    # Bar Chart إجمالي
    st.markdown("#### مقارنة حجم البيانات")
    data_counts = {
        'الفئة': ['محطات عامة', 'موزعات', 'محولات الشمال'],
        'العدد': [count_st, count_dst, count_nth]
    }
    fig_bar_summ = px.bar(data_counts, x='الفئة', y='العدد', color='الفئة', text='العدد', title="مقارنة أعداد الأصول")
    fig_bar_summ.update_traces(textposition='outside')
    st.plotly_chart(fig_bar_summ, use_container_width=True)


# -----------------------------------------------------------------------------
# TAB 2: شمال الإسماعيلية
# -----------------------------------------------------------------------------
with tab_north:
    if not df_nth.empty:
        st.subheader("تحليل تفصيلي - قطاع الشمال")
        
        all_eng = ['الكل'] + list(df_nth['الهندسة'].unique())
        selected_eng = st.selectbox("اختر الهندسة:", all_eng)
        
        df_view = df_nth if selected_eng == 'الكل' else df_nth[df_nth['الهندسة'] == selected_eng]
        
        col_n1, col_n2 = st.columns([2, 1])
        
        with col_n1:
            fig_sun_n = px.sunburst(df_view, path=['الهندسة', 'الملكية', 'النوع', 'اسم المحول'], values='القدرة',
                                    color='النوع', color_discrete_map=COLOR_MAP, height=700,
                                    title=f"توزيع الأحمال والقدرات ({selected_eng})")
            fig_sun_n.update_traces(hovertemplate='<b>%{label}</b><br>القدرة: %{value:,.1f} kVA')
            st.plotly_chart(fig_sun_n, use_container_width=True)
            
        with col_n2:
            st.write("#### إحصائيات سريعة")
            st.metric("إجمالي القدرة", f"{df_view['القدرة'].sum():,.1f} kVA")
            st.metric("عدد المحولات", len(df_view))
            
            cnt_type = df_view['النوع'].value_counts().reset_index()
            cnt_type.columns = ['النوع', 'العدد']
            fig_bar_n = px.bar(cnt_type, x='النوع', y='العدد', color='النوع', color_discrete_map=COLOR_MAP)
            st.plotly_chart(fig_bar_n, use_container_width=True)

        st.dataframe(df_view)
    else:
        st.warning("لا توجد بيانات لقطاع الشمال (تأكد من وجود ملفات Excel).")

# -----------------------------------------------------------------------------
# TAB 3: الموزعات
# -----------------------------------------------------------------------------
with tab_dist:
    if df_dst is not None:
        st.subheader("تحليل الموزعات (517)")
        
        cd1, cd2 = st.columns([1, 2])
        with cd1:
            fig_d_sun = px.sunburst(df_dst, path=['قطاع_للرسم', 'الهندسة', 'الموزع'], height=700)
            st.plotly_chart(fig_d_sun, use_container_width=True)
            
        with cd2:
            cnt_dst = df_dst.groupby(['القطاع', 'الهندسة']).size().reset_index(name='العدد').sort_values('العدد', ascending=False)
            fig_d_bar = px.bar(cnt_dst, x='الهندسة', y='العدد', color='القطاع', text='العدد', title="عدد الموزعات لكل هندسة")
            fig_d_bar.update_layout(xaxis=dict(tickmode='linear', tickangle=-90))
            st.plotly_chart(fig_d_bar, use_container_width=True)
        
        st.write("### ملخص البيانات:")
        st.dataframe(df_dst_summ, use_container_width=True)
    else:
        st.warning("ملف الموزعات (517) غير موجود.")

# -----------------------------------------------------------------------------
# TAB 4: المحطات العامة
# -----------------------------------------------------------------------------
with tab_stations:
    if df_st is not None:
        st.subheader("المحطات العامة")
        
        cs1, cs2 = st.columns([3, 1])
        with cs1:
            fig_s_sun = px.sunburst(df_st, path=['القطاع', 'المحطة'], values='العدد', height=700, hover_data=['ملاحظات'])
            st.plotly_chart(fig_s_sun, use_container_width=True)
        with cs2:
            cnt_sec = df_st['القطاع'].value_counts().reset_index()
            cnt_sec.columns = ['القطاع', 'العدد']
            fig_s_bar = px.bar(cnt_sec, x='القطاع', y='العدد', color='القطاع', text='العدد')
            st.plotly_chart(fig_s_bar, use_container_width=True)
            
        st.dataframe(df_st)
    else:
        st.warning("ملف المحطات العامة غير موجود.")
