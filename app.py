import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==========================================
# 1. إعداد الصفحة والتصميم (CSS)
# ==========================================
st.set_page_config(layout="wide", page_title="لوحة تحكم الكهرباء", page_icon="⚡")

# تنسيق CSS لجعل التطبيق احترافياً (RTL)
st.markdown("""
<style>
    .main {direction: rtl;}
    h1, h2, h3, h4, p, div, span {text-align: right; font-family: 'Segoe UI', sans-serif;}
    .stDataFrame {width: 100%;}
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold; color: #003f5c;}
    div[data-testid="stMetricLabel"] {font-size: 16px; font-weight: bold;}
    /* تحسين شكل القائمة الجانبية */
    .css-1d391kg {direction: rtl;}
</style>
""", unsafe_allow_html=True)

# الألوان المميزة للرسم البياني
COLOR_MAP = {'كشك': '#2E86C1', 'غرفة': '#E74C3C', 'هوائي': '#8E44AD', 'مبنى': '#F1C40F'}

st.sidebar.title("🔍 القائمة الرئيسية")
page = st.sidebar.radio("القسم:", ["المحطات العامة", "الموزعات (517)", "شمال الإسماعيلية"])

# ==========================================
# 2. دوال التحميل (Loading Functions)
# ==========================================

@st.cache_data
def load_stations():
    """تحميل بيانات المحطات العامة"""
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
    """تحميل بيانات الموزعات 517"""
    files = [f for f in os.listdir('.') if "517" in f and (f.endswith('.xlsx') or f.endswith('.csv'))]
    if not files: return None, None
    path = files[0]
    
    # قراءة الملف حسب نوعه
    if path.endswith('.csv'):
        df = pd.read_csv(path).iloc[:, [1, 2, 3, 4]]
    else:
        df = pd.read_excel(path).iloc[:, [1, 2, 3, 4]]
        
    df.columns = ['القطاع', 'الهندسة', 'مسلسل', 'الموزع']
    df = df.replace('nan', pd.NA).ffill() # ملء الخلايا الفارغة
    df = df[pd.to_numeric(df['مسلسل'], errors='coerce').notnull()] # تنظيف البيانات
    
    # تنظيف النصوص
    df['القطاع'] = df['القطاع'].astype(str).str.strip()
    df['الهندسة'] = df['الهندسة'].astype(str).str.strip()
    
    # تجهيز البيانات للرسم
    eng_counts = df.groupby('القطاع')['الهندسة'].nunique()
    df['قطاع_للرسم'] = df['القطاع'].apply(lambda x: f"{x} (هندسات: {eng_counts.get(x, 0)})")
    df['عدد_الموزعات'] = 1
    
    # جدول التلخيص
    summary = df.groupby('القطاع').agg({'الهندسة': 'nunique', 'الموزع': 'count'}).reset_index()
    summary.columns = ['القطاع', 'عدد الهندسات', 'عدد الموزعات']
    
    return df, summary

# ==========================================
# 3. منطق معالجة ملفات شمال الإسماعيلية
# ==========================================

def strict_classify_multi(row, type_cols, col_name):
    """تصنيف نوع المحول (كشك/غرفة/هوائي) بناءً على الكلمات المفتاحية"""
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
    """قراءة ومعالجة ملف الإكسل (سواء xls أو xlsx)"""
    try:
        # 1. البحث عن بداية الجدول (Header) في أول 50 سطر
        # نستخدم engine='openpyxl' للملفات الجديدة، وسيتم تغييره تلقائياً للقديمة لو فشل، 
        # لكن الأفضل ترك pandas يحدد الـ engine، بشرط وجود xlrd
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
        
        if not found_header:
            return None, "لم يتم العثور على رأس الجدول (Header)"

        # 2. قراءة البيانات الفعلية
        df = pd.read_excel(file_path, header=start_row)
        df.columns = df.columns.astype(str).str.strip()

        # 3. تحديد الأعمدة المهمة
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

            # القدرة
            if col_cap:
                df_clean['القدرة_النهائية'] = pd.to_numeric(
                    df_clean[col_cap].astype(str).str.replace(',', '').str.replace(' ', ''),
                    errors='coerce'
                ).fillna(0)
            else:
                df_clean['القدرة_النهائية'] = 0.0

            # 4. تحديد اسم الهندسة من اسم الملف
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
            }), "تمت القراءة بنجاح"
            
        return None, "لم يتم العثور على عمود الاسم"
    except Exception as e:
        return None, f"خطأ: {str(e)}"

# ==========================================
# 4. واجهة التطبيق (UI Navigation)
# ==========================================

if page == "المحطات العامة":
    st.title("⚡ توزيع المحطات العامة")
    st.markdown("---")
    df = load_stations()
    if df is not None:
        c1, c2 = st.columns([3, 1])
        with c1:
            fig1 = px.sunburst(df, path=['القطاع', 'المحطة'], values='العدد', height=600, hover_data={'ملاحظات': True, 'العدد': True})
            fig1.update_traces(hovertemplate='<b>%{label}</b><br>عدد المحطات: %{value}<br>الملاحظات: %{customdata[0]}')
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            st.info("💡 يمكنك الضغط على أي قطاع في الرسم لتكبير التفاصيل.")
            
        st.subheader("إحصائيات القطاعات")
        cnt = df['القطاع'].value_counts().reset_index()
        cnt.columns = ['القطاع', 'عدد المحطات']
        fig2 = px.bar(cnt, x='القطاع', y='عدد المحطات', color='القطاع', text='عدد المحطات')
        fig2.update_traces(textposition='outside')
        st.plotly_chart(fig2, use_container_width=True)
        
        with st.expander("عرض الجدول التفصيلي"):
            st.dataframe(df[['القطاع', 'المحطة', 'ملاحظات']], use_container_width=True)
    else: st.error("⚠️ ملف المحطات (Electricity_Stations_Final_Cleaned.xlsx) غير موجود.")

elif page == "الموزعات (517)":
    st.title("🏭 توزيع الموزعات (517)")
    st.markdown("---")
    df, summ = load_distributors()
    
    if df is not None:
        # عرض الكروت العلوية
        col1, col2 = st.columns(2)
        col1.metric("إجمالي عدد الموزعات", len(df))
        col2.metric("عدد القطاعات", df['القطاع'].nunique())
        
        st.subheader("ملخص البيانات")
        st.dataframe(summ, use_container_width=True)
        
        st.subheader("التوزيع الشجري")
        fig_sun = px.sunburst(df, path=['قطاع_للرسم', 'الهندسة', 'الموزع'], values='عدد_الموزعات', height=700)
        fig_sun.update_layout(font=dict(size=14))
        st.plotly_chart(fig_sun, use_container_width=True)
        
        st.subheader("عدد الموزعات لكل هندسة")
        # --- (التعديل المطلوب: إظهار الأسماء وتدويرها) ---
        counts = df.groupby(['القطاع', 'الهندسة']).size().reset_index(name='العدد')
        counts = counts.sort_values(by='العدد', ascending=False) # ترتيب تنازلي للأجمل
        
        fig_bar = px.bar(counts, x='الهندسة', y='العدد', color='القطاع', text='العدد', 
                         title="عدد الموزعات لكل هندسة (مرتبة)")
        
        fig_bar.update_traces(textposition='outside')
        fig_bar.update_layout(
            xaxis=dict(
                tickmode='linear',  # إجبار المحور على إظهار كل الأسماء
                tickangle=-90,      # تدوير الأسماء لتكون رأسية
                title_font=dict(size=18)
            ),
            height=650, # زيادة الطول لاستيعاب الأسماء
            margin=dict(b=150) # زيادة الهامش السفلي
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else: st.error("⚠️ ملف الموزعات غير موجود. تأكد من وجود ملف باسم يحتوي على '517'.")

elif page == "شمال الإسماعيلية":
    st.title("📊 تحليل قطاع شمال الإسماعيلية")
    st.markdown("---")
    
    # قائمة الاستثناءات
    excluded = ['Electricity_Stations_Final_Cleaned.xlsx', 'requirements.txt', 'app.py', '.git', 'README.md']
    
    # البحث عن الملفات
    files_found = [f for f in os.listdir('.') if f.endswith(('.xls', '.xlsx')) and f not in excluded and "517" not in f and not f.startswith('~$')]
    
    if not files_found:
         st.warning("⚠️ لم يتم العثور على ملفات إكسل خاصة بقطاع الشمال. الرجاء رفع الملفات.")
    else:
        with st.expander(f"📂 تم العثور على {len(files_found)} ملفات (اضغط للتفاصيل)", expanded=False):
            st.write(files_found)

        all_dfs = []
        progress_bar = st.progress(0)
        
        for i, f in enumerate(files_found):
            res, msg = process_file_final(f, f)
            if res is not None:
                all_dfs.append(res)
            else:
                st.toast(f"مشكلة في ملف {f}: {msg}", icon="⚠️")
            progress_bar.progress((i + 1) / len(files_found))
            
        progress_bar.empty()

        if all_dfs:
            df = pd.concat(all_dfs, ignore_index=True)
            
            # مؤشرات الأداء الرئيسية (KPIs)
            st.subheader("نظرة عامة")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("إجمالي القدرة (MVA)", f"{df['القدرة'].sum()/1000:,.2f}")
            k2.metric("عدد المحولات", len(df))
            k3.metric("عدد الهندسات", df['الهندسة'].nunique())
            k4.metric("نسبة ملك الغير", f"{(len(df[df['الملكية']=='ملك الغير'])/len(df))*100:.1f}%")
            
            st.markdown("---")
            
            # 1. إجمالي القدرات (Chart)
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.subheader("إجمالي القدرات (kVA)")
                cap_summary = df.groupby(['الهندسة', 'الملكية'])['القدرة'].sum().reset_index()
                fig_main = px.bar(cap_summary, x='الهندسة', y='القدرة', color='الملكية', text='القدرة', barmode='group',
                                  color_discrete_map={'ملك الشركة': '#003f5c', 'ملك الغير': '#bc5090'})
                fig_main.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
                st.plotly_chart(fig_main, use_container_width=True)
            
            with col_chart2:
                 st.subheader("توزيع الأعداد حسب النوع")
                 type_stats = df.groupby(['الهندسة', 'النوع']).size().reset_index(name='العدد')
                 fig_pie = px.pie(type_stats, names='النوع', values='العدد', color='النوع', color_discrete_map=COLOR_MAP, hole=0.4)
                 st.plotly_chart(fig_pie, use_container_width=True)

            # 2. تفاصيل الأنواع
            st.subheader("تفاصيل أعداد المهمات (كشك - غرفة - هوائي)")
            type_det = df.groupby(['الهندسة', 'الملكية', 'النوع']).size().reset_index(name='العدد')
            cat_order = {'النوع': ['كشك', 'غرفة', 'هوائي']}
            
            fig_count = px.bar(type_det, x='الهندسة', y='العدد', color='النوع', facet_col='الملكية', barmode='group', text='العدد',
                               color_discrete_map=COLOR_MAP, category_orders=cat_order)
            fig_count.update_traces(textposition='outside')
            st.plotly_chart(fig_count, use_container_width=True)

            # 3. Sunburst للأحمال
            st.subheader("توزيع الأحمال التفصيلي")
            fig_sun = px.sunburst(df[df['القدرة'] > 0], path=['الهندسة', 'الملكية', 'النوع', 'اسم المحول'], values='القدرة',
                                  height=800, color='النوع', color_discrete_map=COLOR_MAP)
            fig_sun.update_traces(hovertemplate='<b>%{label}</b><br>القدرة: %{value:,.2f} kVA')
            st.plotly_chart(fig_sun, use_container_width=True)
            
            with st.expander("عرض البيانات الخام"):
                st.dataframe(df, use_container_width=True)
        else:
            st.error("❌ لم يتم قراءة أي بيانات صالحة! تأكد من أن الملفات تحتوي على أعمدة (اسم المحول، القدرة، النوع).")
