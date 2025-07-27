import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configuracion el logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Diccionario para almacenar las agendas por usuario
agendas = {}
scheduler = AsyncIOScheduler()

async def avisar(user_id, tarea, fecha, hora, application):
    chat_id = user_id
    mensaje = f"¡Recordatorio!\nTarea: {tarea}\nFecha: {fecha.strftime('%d/%m/%y')}\nHora: {hora.strftime('%H:%M')}"
    await application.bot.send_message(chat_id=chat_id, text=mensaje)

# Función para agregar una tarea
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    application = context.application
    if not context.args:
        await update.message.reply_text("Por favor, escribe la tarea después del comando /agregar.\nEjemplo: /agregar Comprar pan /fecha 20/07/25 15:30")
        return

    texto = ' '.join(context.args)
    match = re.search(r'/fecha\s+(\d{2}/\d{2}/\d{2})(?:\s+(\d{2}:\d{2}))?', texto)
    fecha = None
    hora = None
    if match:
        fecha_str = match.group(1)
        hora_str = match.group(2)
        try:
            fecha = datetime.strptime(fecha_str, "%d/%m/%y").date()
            if hora_str:
                hora = datetime.strptime(hora_str, "%H:%M").time()
        except ValueError:
            await update.message.reply_text("La fecha y hora deben tener el formato DD/MM/AA HH:MM. Ejemplo: /agregar Comprar pan /fecha 20/07/25 15:30")
            return
        tarea = texto.replace(match.group(0), '').strip()
    else:
        tarea = texto.strip()

    if not tarea:
        await update.message.reply_text("Por favor, escribe la tarea después del comando /agregar.\nEjemplo: /agregar Comprar pan /fecha 20/07/25 15:30")
        return
    if user_id not in agendas:
        agendas[user_id] = []
    agendas[user_id].append({'tarea': tarea, 'completada': False, 'fecha': fecha, 'hora': hora})
    if fecha and hora:
        await update.message.reply_text(f"Tarea agregada: {tarea}\nFecha: {fecha.strftime('%d/%m/%y')}\nHora: {hora.strftime('%H:%M')}")
        
        # Si se proporciona fecha y hora, programar el aviso
        # Programacion de el aviso
        fecha_hora = datetime.combine(fecha, hora)
        scheduler.add_job(
            avisar,
            'date',
            run_date=fecha_hora,
            args=[user_id, tarea, fecha, hora, application]
        )
    elif fecha:
        await update.message.reply_text(f"Tarea agregada: {tarea}\nFecha: {fecha.strftime('%d/%m/%y')}")
    else:
        await update.message.reply_text(f"Tarea agregada: {tarea}")

# Función para mostrar las tareas
async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in agendas or not agendas[user_id]:
        await update.message.reply_text("No tienes tareas en tu agenda.")
        return
    message = "Tus tareas:\n"
    keyboard = []
    for idx, item in enumerate(agendas[user_id]):
        status = "✅" if item['completada'] else "❌"
        fecha_str = f" (Fecha: {item['fecha'].strftime('%d/%m/%y')})" if item.get('fecha') else ""
        hora_str = f" (Hora: {item['hora'].strftime('%H:%M')})" if item.get('hora') else ""
        message += f"{idx + 1}. {status} {item['tarea']}{fecha_str}{hora_str}\n"
        if not item['completada']:
            keyboard.append([InlineKeyboardButton(f"Marcar como completada {idx + 1}", callback_data=f"done_{idx}")])
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message)

# Función para marcar tarea como completada
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if data.startswith("done_"):
        idx = int(data.split("_")[1])
        if user_id in agendas and 0 <= idx < len(agendas[user_id]):
            agendas[user_id][idx]['completada'] = True
            await query.edit_message_text(f"Tarea marcada como completada: {agendas[user_id][idx]['tarea']}")

# Función para eliminar tareas completadas
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in agendas:
        agendas[user_id] = [t for t in agendas[user_id] if not t['completada']]
        await update.message.reply_text("Tareas completadas eliminadas.")
    else:
        await update.message.reply_text("No tienes tareas en tu agenda.")

# Comando de inicio
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "¡Hola! Soy Agenbot, tu asistente de recordatorios.\n\n"
        "Así es como puedo ayudarte:\n\n"
        "* /agregar <tarea> - Agrega una tarea a tu agenda.\n"
        "* /agregar <tarea> /fecha <DD/MM/AA> <HH:MM> - Agrega una tarea con fecha y hora en un solo mensaje.\n"
        "* /fecha <número> <DD/MM/AA> <HH:MM> - Asigna o cambia la fecha y hora de una tarea existente. Ejemplo: /fecha 2 21/07/25 18:00\n"
        "* /lista - Muestra todas tus tareas y sus fechas (si tienen).\n"
        "* /limpiar - Elimina todas las tareas que ya marcaste como completadas.\n"
        "* /eliminar <número> - Elimina una tarea específica por su número en la lista.\n\n"
        "¡Estoy aquí para ayudarte a mantenerte organizado!"
    )
    await update.message.reply_text(mensaje)

# Comando para borrar una tarea específica
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in agendas or not agendas[user_id]:
        await update.message.reply_text("No tienes tareas para borrar.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Debes indicar el número de la tarea a borrar. Ejemplo: /eliminar 2")
        return
    idx = int(context.args[0]) - 1
    if 0 <= idx < len(agendas[user_id]):
        tarea = agendas[user_id].pop(idx)
        await update.message.reply_text(f"Tarea eliminada: {tarea['tarea']}")
    else:
        await update.message.reply_text("Número de tarea inválido.")

# Comando para asignar o modificar la fecha de una tarea existente
async def set_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in agendas or not agendas[user_id]:
        await update.message.reply_text("No tienes tareas en tu agenda.")
        return
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text("Uso correcto: /fecha <número> <DD/MM/AA> [HH:MM]\nEjemplo: /fecha 2 20/07/25 15:30")
        return
    idx = int(context.args[0]) - 1
    fecha_str = context.args[1]
    hora = None
    if len(context.args) == 3:
        hora_str = context.args[2]
        try:
            hora = datetime.strptime(hora_str, "%H:%M").time()
        except ValueError:
            await update.message.reply_text("La hora debe tener el formato HH:MM.\nEjemplo: /fecha 2 20/07/25 15:30")
            return
    try:
        fecha = datetime.strptime(fecha_str, "%d/%m/%y").date()
    except ValueError:
        await update.message.reply_text("La fecha debe tener el formato DD/MM/AA.\nEjemplo: /fecha 2 20/07/25 15:30")
        return
    if 0 <= idx < len(agendas[user_id]):
        agendas[user_id][idx]['fecha'] = fecha
        agendas[user_id][idx]['hora'] = hora
        hora_txt = f" {hora.strftime('%H:%M')}" if hora else ""
        await update.message.reply_text(f"Fecha actualizada para la tarea {idx+1}: {agendas[user_id][idx]['tarea']} -> {fecha.strftime('%d/%m/%y')}{hora_txt}")
    else:
        await update.message.reply_text("Número de tarea inválido.")

# Función principal para iniciar el bot
async def main():
    application = ApplicationBuilder().token('7601407571:AAG_MavD4YTv87RQ2UxB73f39aS79QdEzGA').build()

    #Configuracion del scheduler
    scheduler.start()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('agregar', add))
    application.add_handler(CommandHandler('lista', list_tasks))
    application.add_handler(CommandHandler('limpiar', clear))
    application.add_handler(CommandHandler('eliminar', delete))
    application.add_handler(CommandHandler('fecha', set_fecha))
    application.add_handler(CallbackQueryHandler(button))

    print("Bot en funcionamiento...")
    await application.run_polling()

import nest_asyncio
import asyncio

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
