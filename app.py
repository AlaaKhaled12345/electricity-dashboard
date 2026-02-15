import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==========================================
# 1. إعداد الصفحة والتصميم
# ==========================================
st.set_page_config(layout="wide", page_title="لوحة تحكم الكهرباء", page_icon="⚡")

st.markdown("""
<style>
    .main {direction: rtl;}
    h1, h2, h3, h4, p, div, span {text-align: right; font-family: 'Segoe UI', sans-serif;}
    .stDataFrame {width: 100%;}
    
    /* تنسيق الكروت (Metrics) */
    div[data-testid="stMetric"] {
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        text-align: center;
    }
    div[data-testid="stMetricValue"] {
        font-size: 26px;
        color: #003f5c;
        font-weight: bold;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 16px;
        color: #555;
    }
    
    /* عنوان الأقسام */
    .section-title {
        font-size: 22px;
        font-weight: bold;
        color: #2E86C1;
        margin-top: 20px;
        margin-bottom: 10px;
        border-bottom: 2px solid #2E86C1;
        padding-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# الألوان
COLOR_MAP = {'كشك': '#2E86C1', 'غرفة': '#E74C3C', 'هوائي': '#8E44AD', 'مبنى': '#F1C40F'}

# القائمة الجانبية
st.sidebar.title("🔍 القائمة الرئيسية")
page = st.sidebar.radio("القسم:", ["الرئيسية", "المحطات العامة", "الموزعات (517)", "شمال الإسماعيلية"])

# ==========================================
# 2. دوال التحميل والمعالجة (Backend)
# ==========================================

@st.cache_data
def load_stations():
    """تحميل المحطات العامة"""
    if os.path.exists('Electricity_Stations_Final_Cleaned.xlsx'):
        df = pd.read_excel('Electricity_Stations_Final_Cleaned.xlsx')
        if 'ملاحظات' in df.columns: df['ملاحظات'] = df['ملاحظات'].fillna('لا توجد ملاحظات')
        else: df['ملاحظات'] = 'غير متوفر'
        df['العدد'] = 1
        return df
    return None

@st.cache_data
def load_distributors():
    """تحميل الموزعات"""
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
    """تصنيف دقيق لنوع المحول"""
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
    return 'كشك' # الافتراضي

def process_file_final(file_path, filename):
    """معالجة ملفات شمال الإسماعيلية"""
    try:
        # البحث عن الهيدر
        df_temp = pd.read_excel(file_path, header=None)
        start_row = 0
        found_header = False
        
        for idx, row in df_temp.head(50).iterrows():
            row_str = " ".join(row.astype(str).values)
            if ('اسم' in row_str and 'محول' in row_str) or \
               ('كشك' in row_str and 'غرفة' in row_str) or \
               ('بيان' in row_str) or \
               ('قدرة' in row_str):
                start_row = idx
                found_header = True
                break
        
        if not found_header: return None, "Header missing"

        df = pd.read_excel(file_path, header=start_row)
        df.columns = df.columns.astype(str).str.strip()

        col_name = next((c for c in df.columns if 'اسم' in c or 'محول' in c or 'بيان' in c or 'عملية' in c), None)
        type_cols = [c for c in df.columns if 'نوع' in c or 'كشك' in c or 'غرف' in c or 'صنف' in c]
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

            # تحديد اسم الهندسة من اسم الملف
            fname_clean = filename.replace('أ', 'ا').replace('ة', 'ه').lower()
            if 'زايد' in fname_clean: dist = 'الشيخ زايد'
            elif ('اول' in fname_clean or '1' in fname_clean) and 'ثان' not in fname_clean: dist = 'إسماعيلية أول'
            elif 'ثان' in fname_clean or '2' in fname_clean or 'تاني' in fname_clean or 'ثانى' in fname_clean: dist = 'إسماعيلية ثان'
            else: dist = 'غير محدد' 

            # تحديد الملكية
            owner = 'ملك الشركة' if 'شركه' in fname_clean else ('ملك الغير' if 'غير' in fname_clean else 'غير محدد')
            if 'شركه' in fname_clean: owner = 'ملك الشركة'

            return pd.DataFrame({
                'الهندسة': dist,
                'الملكية': owner,
                'اسم المحول': df_clean[col_name],
                'النوع': df_clean['النوع_النهائي'],
                'القدرة': df_clean['القدرة_النهائية']
            }), "Success"
            
        return None, "No name column"
    except Exception as e:
        return None, str(e)

def load_all_north_data():
    """تحميل وتجميع كل بيانات شمال الإسماعيلية للحسابات"""
    all_dfs = []
    excluded = ['Electricity_Stations_Final_Cleaned.xlsx', 'requirements.txt', 'app.py', '.git']
    files = [f for f in os.listdir('.') if f.endswith(('.xls', '.xlsx')) and f not in excluded and "517" not in f and not f.startswith('~$')]
    
    for f in files:
        res, _ = process_file_final(f, f)
        if res is not None:
            all_dfs.append(res)
    
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame() # إرجاع جدول فارغ لو مفيش ملفات

# ==========================================
# 3. واجهة التطبيق (UI & Logic)
# ==========================================

if page == "الرئيسية":
    st.title("📊 لوحة القيادة المركزية (Dashboard)")
    st.markdown("---")

    # --- 1. تحميل البيانات ---
    df_stations = load_stations()
    df_dist, _ = load_distributors()
    df_north = load_all_north_data()

    # --- 2. حسابات المستوى الأول (Overview) ---
    total_stations = len(df_stations) if df_stations is not None else 0
    total_distributors = len(df_dist) if df_dist is not None else 0
    total_north_trans = len(df_north) if not df_north.empty else 0
    
    # حساب عدد القطاعات (من ملف الموزعات أو المحطات)
    total_sectors = 0
    if df_dist is not None:
        total_sectors = df_dist['القطاع'].nunique()
    elif df_stations is not None:
        total_sectors = df_stations['القطاع'].nunique()

    # عرض الصف الأول (Overview Row)
    st.markdown('<div class="section-title">نظرة عامة على الشركة</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("عدد القطاعات", total_sectors, "قطاع")
    c2.metric("إجمالي المحطات العامة", total_stations, "محطة")
    c3.metric("إجمالي الموزعات (517)", total_distributors, "موزع")
    c4.metric("إجمالي محولات الشمال", total_north_trans, "محول")

    # --- 3. حسابات تفصيلية لقطاع شمال الإسماعيلية ---
    if not df_north.empty:
        st.markdown('<div class="section-title">تفاصيل مهمات قطاع شمال الإسماعيلية (حسب الملكية)</div>', unsafe_allow_html=True)
        
        # تقسيم البيانات
        df_company = df_north[df_north['الملكية'] == 'ملك الشركة']
        df_others = df_north[df_north['الملكية'] == 'ملك الغير']

        # حسابات ملك الشركة
        co_kiosk = len(df_company[df_company['النوع'] == 'كشك'])
        co_room = len(df_company[df_company['النوع'] == 'غرفة'])
        co_aerial = len(df_company[df_company['النوع'] == 'هوائي'])
        
        # حسابات ملك الغير
        ot_kiosk = len(df_others[df_others['النوع'] == 'كشك'])
        ot_room = len(df_others[df_others['النوع'] == 'غرفة'])
        ot_aerial = len(df_others[df_others['النوع'] == 'هوائي'])

        # عرض صف ملك الشركة
        st.info("🏢 **مهمات ملك الشركة**")
        row1_c1, row1_c2, row1_c3, row1_c4 = st.columns(4)
        row1_c1.metric("إجمالي (ملك شركة)", len(df_company))
        row1_c2.metric("أكشاك (شركة)", co_kiosk)
        row1_c3.metric("غرف (شركة)", co_room)
        row1_c4.metric("هوائي (شركة)", co_aerial)

        # عرض صف ملك الغير
        st.warning("👤 **مهمات ملك الغير**")
        row2_c1, row2_c2, row2_c3, row2_c4 = st.columns(4)
        row2_c1.metric("إجمالي (ملك غير)", len(df_others))
        row2_c2.metric("أكشاك (غير)", ot_kiosk)
        row2_c3.metric("غرف (غير)", ot_room)
        row2_c4.metric("هوائي (غير)", ot_aerial)

        # --- 4. الرسوم البيانية التفاعلية ---
        st.markdown('<div class="section-title">تحليل بياني (شمال الإسماعيلية)</div>', unsafe_allow_html=True)
        
        g1, g2 = st.columns([1, 1])
        
        with g1:
            st.caption("توزيع المهمات حسب النوع والملكية")
            fig_sun = px.sunburst(df_north, path=['الملكية', 'النوع'], title="نسبة التوزيع (Interactive)", color='النوع', color_discrete_map=COLOR_MAP)
            st.plotly_chart(fig_sun, use_container_width=True)
            
        with g2:
            st.caption("عدد المحولات في كل هندسة")
            bar_data = df_north['الهندسة'].value_counts().reset_index()
            bar_data.columns = ['الهندسة', 'العدد']
            fig_bar = px.bar(bar_data, x='الهندسة', y='العدد', color='الهندسة', text='العدد', title="الأعداد لكل هندسة")
            fig_bar.update_traces(textposition='outside')
            st.plotly_chart(fig_bar, use_container_width=True)

    else:
        st.error("⚠️ لا توجد بيانات لقطاع الشمال للعرض في اللوحة الرئيسية. تأكد من رفع الملفات.")

# ==========================================
# باقي الصفحات (كما هي تماماً)
# ==========================================

elif page == "المحطات العامة":
    st.header("توزيع المحطات (العدد والملاحظات)")
    df = load_stations()
    if df is not None:
        fig1 = px.sunburst(df, path=['القطاع', 'المحطة'], values='العدد', height=750, hover_data={'ملاحظات': True, 'العدد': True})
        fig1.update_traces(hovertemplate='<b>%{label}</b><br>عدد المحطات: %{value}<br>الملاحظات: %{customdata[0]}')
        st.plotly_chart(fig1, use_container_width=True)
        cnt = df['القطاع'].value_counts().reset_index()
        cnt.columns = ['القطاع', 'عدد المحطات']
        fig2 = px.bar(cnt, x='القطاع', y='عدد المحطات', color='القطاع', text='عدد المحطات')
        fig2.update_traces(textposition='outside')
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(df[['القطاع', 'المحطة', 'ملاحظات']], use_container_width=True)
    else: st.error("⚠️ ملف المحطات غير موجود.")

elif page == "الموزعات (517)":
    st.header("توزيع الموزعات")
    df, summ = load_distributors()
    if df is not None:
        st.dataframe(summ, use_container_width=True)
        fig_sun = px.sunburst(df, path=['قطاع_للرسم', 'الهندسة', 'الموزع'], values='عدد_الموزعات', height=700)
        fig_sun.update_layout(font=dict(size=14))
        st.plotly_chart(fig_sun, use_container_width=True)
        counts = df.groupby(['القطاع', 'الهندسة']).size().reset_index(name='العدد')
        counts = counts.sort_values(by='العدد', ascending=False)
        fig_bar = px.bar(counts, x='الهندسة', y='العدد', color='القطاع', text='العدد')
        fig_bar.update_traces(textposition='outside')
        fig_bar.update_layout(xaxis=dict(tickmode='linear', tickangle=-90), height=650)
        st.plotly_chart(fig_bar, use_container_width=True)
    else: st.error("⚠️ ملف الموزعات غير موجود.")

elif page == "شمال الإسماعيلية":
    st.header("تحليل قطاع شمال الإسماعيلية (تفصيلي)")
    df = load_all_north_data() # استخدام دالة التحميل المجمعة لعدم التكرار

    if not df.empty:
        k1, k2, k3 = st.columns(3)
        k1.metric("إجمالي القدرة (kVA)", f"{df['القدرة'].sum():,.1f}")
        k2.metric("عدد المحولات", len(df))
        k3.metric("عدد الهندسات", df['الهندسة'].nunique())
        
        st.divider()
        
        st.subheader("1. إجمالي القدرات الكلية (kVA)")
        cap_summary = df.groupby(['الهندسة', 'الملكية'])['القدرة'].sum().reset_index()
        fig_main = px.bar(cap_summary, x='الهندسة', y='القدرة', color='الملكية', text='القدرة', barmode='group',
                          color_discrete_map={'ملك الشركة': '#003f5c', 'ملك الغير': '#bc5090'})
        fig_main.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
        st.plotly_chart(fig_main, use_container_width=True)
        
        type_stats = df.groupby(['الهندسة', 'الملكية', 'النوع']).agg(العدد=('اسم المحول', 'count'), إجمالي_القدرة=('القدرة', 'sum')).reset_index()
        cat_order = {'النوع': ['كشك', 'غرفة', 'هوائي', 'مبنى']}
        
        st.subheader("2. عدد المحولات والغرف حسب النوع")
        fig_count = px.bar(type_stats, x='الهندسة', y='العدد', color='النوع', facet_col='الملكية', barmode='group', text='العدد',
                           color_discrete_map=COLOR_MAP, category_orders=cat_order)
        fig_count.update_traces(textposition='outside')
        st.plotly_chart(fig_count, use_container_width=True)

        st.subheader("3. توزيع القدرات حسب النوع")
        fig_cap = px.bar(type_stats, x='الهندسة', y='إجمالي_القدرة', color='النوع', facet_col='الملكية', barmode='group', text='إجمالي_القدرة',
                         color_discrete_map=COLOR_MAP, category_orders=cat_order)
        fig_cap.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
        st.plotly_chart(fig_cap, use_container_width=True)
        
        st.subheader("4. التوزيع الشجري للأحمال")
        fig_sun = px.sunburst(df[df['القدرة'] > 0], path=['الهندسة', 'الملكية', 'النوع', 'اسم المحول'], values='القدرة',
                              height=850, color='النوع', color_discrete_map=COLOR_MAP)
        fig_sun.update_traces(hovertemplate='<b>%{label}</b><br>القدرة: %{value:,.2f} kVA')
        st.plotly_chart(fig_sun, use_container_width=True)
        
        st.subheader("الجدول التفصيلي")
        st.dataframe(df[['الهندسة', 'الملكية', 'النوع', 'اسم المحول', 'القدرة']], use_container_width=True)
    else:
        st.error("❌ لم يتم العثور على أي ملفات صالحة.")
