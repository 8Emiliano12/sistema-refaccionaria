import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import os
import json
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
# ¡¡PEGA AQUÍ TU API KEY DENTRO DE LAS COMILLAS!!
API_KEY = "AIzaSyA5l4tJrEzaG7VJmG86PAKHnr0pGTnW7m8" 

genai.configure(api_key=API_KEY)
FILE_DB = 'inventario_refacciones.xlsx'

# --- 2. FUNCIONES DEL SISTEMA ---

def load_data():
    """Carga la base de datos o crea una nueva si no existe."""
    if not os.path.exists(FILE_DB):
        df = pd.DataFrame(columns=["SKU", "Nombre", "Marca", "Categoria", "Stock", "Precio", "Ultima_Actualizacion"])
        # Guardar un archivo vacío inicial
        with pd.ExcelWriter(FILE_DB, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return df
    try:
        return pd.read_excel(FILE_DB)
    except Exception as e:
        st.error(f"Error al leer el archivo Excel: {e}")
        return pd.DataFrame()

def save_data(df):
    """Guarda los cambios en el Excel."""
    with pd.ExcelWriter(FILE_DB, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)

def analyze_image(image):
    """El cerebro: Envía la foto a Gemini 1.5 Flash."""
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Actúa como un experto almacenista de autopartes. Analiza esta imagen.
    Extrae la información técnica y devuélvela SOLAMENTE en formato JSON.
    Campos requeridos:
    - sku: Busca códigos de barras, números de parte (PN), o códigos impresos. Si no hay, genera uno corto basado en el nombre (ej. FIL-ACE-01).
    - nombre: Nombre técnico de la pieza (ej. Balata Delantera Cerámica).
    - marca: Marca del fabricante (ej. Brembo, Bosch). Si no se ve, pon "Genérico".
    - categoria: Sistema del auto (Frenos, Motor, Suspensión, Eléctrico, Carrocería).
    
    Estructura JSON exacta:
    {
        "sku": "...",
        "nombre": "...",
        "marca": "...",
        "categoria": "..."
    }
    """
    
    try:
        response = model.generate_content([prompt, image])
        # Limpiar la respuesta por si Gemini pone ```json ... ```
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        st.error(f"Error de IA: {e}")
        return None

# --- 3. INTERFAZ GRÁFICA (LO QUE VES) ---

st.set_page_config(page_title="Refaccionaria MAEB", layout="wide", page_icon="🚗")

st.title("🚗 Sistema de Inventario Inteligente")
st.markdown("---")

# Cargar datos
df = load_data()

# Menú lateral
menu = st.sidebar.radio("Menú Principal", ["💰 VENDER", "➕ AGREGAR (IA)", "📊 INVENTARIO COMPLETO"])

# --- PESTAÑA: VENDER ---
if menu == "💰 VENDER":
    st.header("Punto de Venta")
    
    # Buscador
    search = st.text_input("🔍 Buscar pieza (Escribe nombre o SKU):", "")
    
    results = df
    if search:
        mask = df['Nombre'].astype(str).str.contains(search, case=False, na=False) | \
               df['SKU'].astype(str).str.contains(search, case=False, na=False)
        results = df[mask]

    if not results.empty:
        # Selector de producto
        product_list = results.apply(lambda x: f"{x['SKU']} - {x['Nombre']} (Stock: {x['Stock']})", axis=1)
        selected_item_str = st.selectbox("Selecciona el producto:", product_list)
        
        # Obtener el SKU real de la selección
        selected_sku = selected_item_str.split(" - ")[0]
        item = df[df['SKU'] == selected_sku].iloc[0]
        
        st.info(f"💵 Precio Unitario: ${item['Precio']}")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            qty = st.number_input("Cantidad", min_value=1, value=1)
        with col2:
            st.text("") # Espacio
            st.text("") 
            if st.button("✅ REGISTRAR VENTA", type="primary"):
                current_stock = df.loc[df['SKU'] == selected_sku, 'Stock'].values[0]
                
                if current_stock >= qty:
                    # Restar stock
                    df.loc[df['SKU'] == selected_sku, 'Stock'] = current_stock - qty
                    save_data(df)
                    st.toast(f"¡Venta exitosa! Quedan {current_stock - qty} piezas.", icon="🎉")
                    st.rerun()
                else:
                    st.error(f"❌ Stock insuficiente. Solo tienes {current_stock}.")
    else:
        st.warning("No se encontró esa refacción.")

# --- PESTAÑA: AGREGAR ---
elif menu == "➕ AGREGAR (IA)":
    st.header("Ingreso de Mercancía con Visión")
    
    col_cam, col_data = st.columns([1, 1])
    
    with col_cam:
        img_file = st.camera_input("Toma foto de la pieza o caja")
    
    if img_file:
        image = Image.open(img_file)
        
        # Botón para activar la IA
        if st.button("🤖 Analizar con Gemini", use_container_width=True):
            with st.spinner("Analizando pieza..."):
                ai_data = analyze_image(image)
                
                if ai_data:
                    # Guardar datos en "session_state" para que no se borren al recargar
                    st.session_state['ai_result'] = ai_data
        
        # Si ya tenemos datos de la IA, mostramos el formulario
        if 'ai_result' in st.session_state:
            data = st.session_state['ai_result']
            
            with col_data:
                st.subheader("Datos Detectados")
                with st.form("form_alta"):
                    new_sku = st.text_input("SKU / Código", value=data.get('sku', ''))
                    new_name = st.text_input("Nombre", value=data.get('nombre', ''))
                    new_brand = st.text_input("Marca", value=data.get('marca', ''))
                    new_cat = st.selectbox("Categoría", ["Motor", "Frenos", "Suspensión", "Eléctrico", "Carrocería", "Otro"], index=0)
                    
                    c1, c2 = st.columns(2)
                    new_stock = c1.number_input("Cantidad a ingresar", min_value=1, value=1)
                    new_price = c2.number_input("Precio de Venta", min_value=0.0, value=0.0)
                    
                    submitted = st.form_submit_button("💾 Guardar en Inventario")
                    
                    if submitted:
                        # Verificar si existe para sumar o crear
                        if new_sku in df['SKU'].values:
                            df.loc[df['SKU'] == new_sku, 'Stock'] += new_stock
                            st.success(f"SKU existente. Stock actualizado.")
                        else:
                            new_row = {
                                "SKU": new_sku, "Nombre": new_name, "Marca": new_brand,
                                "Categoria": new_cat, "Stock": new_stock, "Precio": new_price,
                                "Ultima_Actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M")
                            }
                            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                        
                        save_data(df)
                        st.success("¡Producto Guardado!")
                        # Limpiar estado
                        del st.session_state['ai_result']
                        st.rerun()

# --- PESTAÑA: INVENTARIO ---
elif menu == "📊 INVENTARIO COMPLETO":
    st.header("Base de Datos Actual")
    st.dataframe(df, use_container_width=True)
    
    st.download_button(
        label="📥 Descargar Inventario en Excel",
        data=open(FILE_DB, "rb").read(),
        file_name="inventario_respaldo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )