from dotenv import load_dotenv
load_dotenv()
import os
from datetime import datetime
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import os
import base64

# --- Configuración fija ---
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

USUARIO_PRINTANISTA = os.environ["PRINTANISTA_USUARIO"]
CONTRASENA_PRINTANISTA = os.environ["PRINTANISTA_CONTRASENA"]

DATOS_FIJOS = {
    "direccion_asistencia": os.environ["DIRECCION_ASISTENCIA"],
    "ciudad": os.environ["CIUDAD"],
    "nombre_solicitante": "Soporte Técnico",
    "correo_contacto": os.environ["PRINTANISTA_USUARIO"],
    "telefono_contacto": os.environ["TELEFONO_CONTACTO"],
    "entidad": os.environ["ENTIDAD"],
    "cantidad_toner": 1,
}

def registrar(mensaje):
    """Escribe una línea en el archivo de registro, con fecha y hora."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ahora}] {mensaje}"
    print(linea)
    with open("bot_log.txt", "a", encoding="utf-8") as archivo:
        archivo.write(linea + "\n")

# --- Parte 1: Gmail ---

def obtener_credenciales_gmail():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0, open_browser=False)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def extraer_cuerpo(payload):
    if "parts" in payload:
        for parte in payload["parts"]:
            resultado = extraer_cuerpo(parte)
            if resultado:
                return resultado
    else:
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return None

def extraer_impresoras(html):
    soup = BeautifulSoup(html, "html.parser")
    tabla = soup.find("table", class_="datatable")
    if not tabla:
        return []
    impresoras = []
    for fila in tabla.find_all("tr", class_="alt"):
        celdas = fila.find_all("td")
        if len(celdas) >= 6:
            impresoras.append({
                "fabricante": celdas[0].get_text(strip=True),
                "modelo": celdas[1].get_text(strip=True),
                "numero_serie": celdas[2].get_text(strip=True),
                "nivel_consumible": celdas[3].get_text(strip=True),
                "ubicacion": celdas[4].get_text(strip=True),
                "direccion_ip": celdas[5].get_text(strip=True),
            })
    return impresoras

def obtener_alertas_printanista(servicio):
    query = 'from:printanistahub.com -label:PROCESADO'
    resultados = servicio.users().messages().list(userId="me", q=query, maxResults=10).execute()
    mensajes = resultados.get("messages", [])

    alertas = []
    for msg in mensajes:
        detalle = servicio.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        cuerpo = extraer_cuerpo(detalle["payload"])
        impresoras = extraer_impresoras(cuerpo)
        alertas.append((msg["id"], impresoras))
    return alertas

# --- Parte 2: Printanista (scraping) ---

def obtener_contadores(numero_serie):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # ya sin ventana visible
        context = browser.new_context(locale="es-ES")
        page = context.new_page()
        
        page.goto("https://pala.printanistahub.com/Login")
        page.fill("#login-email", USUARIO_PRINTANISTA)
        page.fill("#login-password", CONTRASENA_PRINTANISTA)
        page.click("#button-login")
        page.wait_for_timeout(3000)
        
        if "Login" in page.url:
            browser.close()
            raise Exception("El login a Printanista falló. Verificar usuario/contraseña en el .env.")

        page.goto("https://pala.printanistahub.com/Devices")
        page.wait_for_timeout(4000)

        page.screenshot(path="debug_pagina_dispositivos.png")

        page.fill("#input-searchterm", numero_serie)
        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)

        page.screenshot(path="debug_antes_del_clic.png")
        page.click("a.ci-actionlink[href*='/DeviceDetails/Details/']")
        page.wait_for_timeout(2000)
        page.screenshot(path="debug_modal.png")
        
        def obtener_contador(etiquetas_posibles):
            for etiqueta in etiquetas_posibles:
                xpath = f"//td[normalize-space(text())='{etiqueta}']/following-sibling::td[1]"
                elemento = page.locator(f"xpath={xpath}").first
                try:
                    elemento.wait_for(timeout=2000)
                    return elemento.inner_text().strip()
                except:
                    continue  # si no encontró con esta etiqueta, prueba la siguiente
            return "No aplica"

        contadores = {
            "total_paginas": obtener_contador(["Total Páginas", "Total Pages"]),
            "total_mono": obtener_contador(["Total páginas mono", "Total Pages Mono"]),
            "total_color": obtener_contador(["Total Páginas Color", "Total Pages Color"]),
        }

        browser.close()
        return contadores

def armar_texto_correo(pedido):
    es_color = pedido["contador_color"] != "No aplica"

    if es_color:
        lineas_toner = (
            "Cantidad de tóner solicitado negro: 1\n"
            "Cantidad de tóner solicitado cyan: 1\n"
            "Cantidad de tóner solicitado magenta: 1\n"
            "Cantidad de tóner solicitado amarillo: 1"
        )
    else:
        lineas_toner = "Cantidad de tóner solicitado: 1"

    texto = f"""Buenas:

Quisiera realizar el pedido de provisión de tóner para la siguiente impresora:

Impresora: {pedido['impresora']}
N° de Serie: {pedido['numero_serie']}
Contador total: {pedido['contador_total']}
{lineas_toner}
Ubicación: {pedido['ubicacion']}

    Dirección de asistencia: {pedido['direccion_asistencia']}

    Ciudad: {pedido['ciudad']}

    Nombre del solicitante: {pedido['nombre_solicitante']}

    Correo: {pedido['correo_contacto']}

    Teléfono de contacto: {pedido['telefono_contacto']}

    Entidad: {pedido['entidad']}

Agradezco de antemano su pronta atención.

{os.environ['FIRMA_LINEA1']}

{os.environ['FIRMA_LINEA2']}

{os.environ['FIRMA_LINEA3']}

{pedido['entidad']}
"""
    return texto

def enviar_correo(servicio, destinatarios, asunto, cuerpo):
    mensaje = MIMEText(cuerpo)
    mensaje["to"] = ", ".join(destinatarios)
    mensaje["subject"] = asunto

    mensaje_codificado = base64.urlsafe_b64encode(mensaje.as_bytes()).decode()
    cuerpo_envio = {"raw": mensaje_codificado}

    resultado = servicio.users().messages().send(userId="me", body=cuerpo_envio).execute()
    return resultado

def obtener_o_crear_etiqueta(servicio, nombre_etiqueta):
    """Busca el ID de una etiqueta por nombre. Si no existe, la crea."""
    etiquetas = servicio.users().labels().list(userId="me").execute().get("labels", [])
    for etiqueta in etiquetas:
        if etiqueta["name"].upper() == nombre_etiqueta.upper():
            return etiqueta["id"]
    # Si no la encontró, la crea
    nueva = servicio.users().labels().create(
        userId="me",
        body={"name": nombre_etiqueta, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    ).execute()
    return nueva["id"]

def marcar_como_procesado(servicio, msg_id, label_id):
    servicio.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"addLabelIds": [label_id]}
    ).execute()

# --- Programa principal ---

ASUNTO_CORREO = "Solicitud de tóner"
DESTINATARIOS_PEDIDO = [os.environ["DESTINATARIO_1"], os.environ["DESTINATARIO_2"]]
registrar("--- Inicio de ejecución ---")

creds = obtener_credenciales_gmail()
servicio = build("gmail", "v1", credentials=creds)

label_id_procesado = obtener_o_crear_etiqueta(servicio, "PROCESADO")

registrar("Buscando alertas de Printanista en el correo...")
alertas = obtener_alertas_printanista(servicio)

if not alertas:
    registrar("No se encontraron alertas pendientes.")
else:
    registrar(f"Se encontraron {len(alertas)} alerta(s) sin procesar.")

    for msg_id, impresoras in alertas:
        for imp in impresoras:
            registrar(f"Procesando impresora {imp['modelo']} - Serie {imp['numero_serie']}...")
            try:
                contadores = obtener_contadores(imp["numero_serie"])
            except Exception as error:
                registrar(f"ERROR procesando impresora {imp['numero_serie']}: {error}")
            continue
        
            pedido = {
                "impresora": imp["modelo"],
                "numero_serie": imp["numero_serie"],
                "contador_total": contadores["total_paginas"],
                "contador_mono": contadores["total_mono"],
                "contador_color": contadores["total_color"],
                "cantidad_toner": DATOS_FIJOS["cantidad_toner"],
                "ubicacion": imp["ubicacion"],
                **DATOS_FIJOS,
            }

            texto_correo = armar_texto_correo(pedido)

            resultado = enviar_correo(servicio, DESTINATARIOS_PEDIDO, ASUNTO_CORREO, texto_correo)
            registrar(f"Correo enviado. ID: {resultado['id']} - Impresora: {imp['numero_serie']}")

        marcar_como_procesado(servicio, msg_id, label_id_procesado)
        registrar(f"Alerta {msg_id} marcada como PROCESADO.")

registrar("--- Fin de ejecución ---\n")