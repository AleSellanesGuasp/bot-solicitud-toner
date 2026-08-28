from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

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

def obtener_o_crear_etiqueta(servicio, nombre_etiqueta):
    etiquetas = servicio.users().labels().list(userId="me").execute().get("labels", [])
    for etiqueta in etiquetas:
        if etiqueta["name"].upper() == nombre_etiqueta.upper():
            return etiqueta["id"]
    nueva = servicio.users().labels().create(
        userId="me",
        body={"name": nombre_etiqueta, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    ).execute()
    return nueva["id"]

# --- Programa principal ---

creds = obtener_credenciales_gmail()
servicio = build("gmail", "v1", credentials=creds)

label_id_procesado = obtener_o_crear_etiqueta(servicio, "PROCESADO")

query = 'from:printanistahub.com -label:PROCESADO'
resultados = servicio.users().messages().list(userId="me", q=query, maxResults=500).execute()
mensajes = resultados.get("messages", [])

print(f"Se encontraron {len(mensajes)} alertas SIN procesar en el historial.\n")

if not mensajes:
    print("No hay nada para limpiar.")
else:
    confirmacion = input(f"¿Confirmás marcar estas {len(mensajes)} alertas como PROCESADO SIN enviar ningún correo? (escribí 'si' para confirmar): ")
    if confirmacion.strip().lower() == "si":
        for i, msg in enumerate(mensajes, 1):
            servicio.users().messages().modify(
                userId="me",
                id=msg["id"],
                body={"addLabelIds": [label_id_procesado]}
            ).execute()
            print(f"[{i}/{len(mensajes)}] Marcado como PROCESADO: {msg['id']}")
        print("\n✅ Limpieza completa. El historial quedó al día.")
    else:
        print("Operación cancelada, no se modificó nada.")