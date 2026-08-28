# 🖨️ Bot de Solicitud de Tóner

Automatización que gestiona de punta a punta el pedido de tóner para una flota de impresoras, a partir de las alertas de nivel bajo que envía por correo un sistema de monitoreo de impresoras (Printanista / Print Audit).

## ¿Qué hace?

Cuando una impresora llega a un nivel bajo de tóner, el sistema de monitoreo envía automáticamente una alerta por correo. Este bot:

1. **Lee la alerta** en la bandeja de Gmail y extrae los datos de la impresora (modelo, número de serie, ubicación).
2. **Consulta el contador real** de páginas impresas, haciendo scraping del portal del proveedor (con Playwright).
3. **Arma el correo de pedido** con el formato correcto, distinguiendo automáticamente entre impresoras monocromáticas y a color (que requieren tóner por separado: negro, cyan, magenta, amarillo).
4. **Envía el correo** a la empresa proveedora usando la API de Gmail.
5. **Marca la alerta como procesada** (con una etiqueta de Gmail) para evitar pedidos duplicados.
6. Corre de forma **automática y periódica** (Programador de tareas / cron), sin intervención manual.

## Tecnologías

- **Python 3**
- **Playwright** — automatización del navegador para el scraping del portal de monitoreo
- **Gmail API** (OAuth 2.0) — lectura y envío de correos
- **BeautifulSoup** — parseo del HTML de las alertas
- **python-dotenv** — manejo de configuración sensible fuera del código

## Configuración

1. Cloná el repositorio e instalá las dependencias:

Ejecutar en Consola: pip install -r requirements.txt
Ejecutar en Consola: playwright install

2. Creá un archivo `.env` en la raíz del proyecto con tus propios datos (ver `.env.example`).
3. Generá tus credenciales de Gmail API (`credentials.json`) desde Google Cloud Console y colocalas en la raíz del proyecto.
4. Corré el script una vez para autorizar el acceso a Gmail:

Ejecutar en Consola: python armar_pedido.py


## Nota

Este proyecto fue desarrollado para un caso de uso real de gestión de infraestructura de impresión, pero la lógica es adaptable a cualquier sistema de monitoreo que envíe alertas por correo con un formato consistente.