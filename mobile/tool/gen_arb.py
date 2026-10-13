"""Genera lib/l10n/app_es.arb y app_en.arb a partir de una sola tabla.

Mantener los dos idiomas en la misma línea evita que una clave quede sin
traducir. Uso (desde mobile/):  python tool/gen_arb.py && flutter gen-l10n
"""

import json
import pathlib
import re

ENTEROS = {"n", "min", "pct"}

# clave: (español, inglés)
TEXTOS = {
    # --- Generales ---
    "appName": ("Pay & Check", "Pay & Check"),
    "cancel": ("Cancelar", "Cancel"),
    "confirm": ("Confirmar", "Confirm"),
    "retry": ("Reintentar", "Retry"),
    "save": ("Guardar", "Save"),
    "create": ("Crear", "Create"),
    "delete": ("Eliminar", "Delete"),
    "add": ("Registrar", "Add"),
    "send": ("Enviar", "Send"),
    "name": ("Nombre", "Name"),
    "amount": ("Monto", "Amount"),
    "description": ("Descripción", "Description"),
    "category": ("Categoría", "Category"),
    "date": ("Fecha", "Date"),
    "invalidAmount": ("Escribe un monto mayor que cero", "Enter an amount greater than zero"),
    "requiredField": ("Este campo es necesario", "This field is required"),
    "errorInvalidData": ("Revisa los datos e inténtalo de nuevo.", "Check the data and try again."),
    "errorNetwork": (
        "No pudimos conectar. Revisa tu conexión e inténtalo de nuevo.",
        "We couldn't connect. Check your connection and try again.",
    ),
    "errorGeneric": ("Algo no salió como esperábamos. Inténtalo de nuevo.", "Something went wrong. Please try again."),
    # --- Acceso ---
    "loginTitle": ("Hola de nuevo", "Welcome back"),
    "loginSubtitle": ("Tu dinero, a tu ritmo y sin culpas.", "Your money, at your pace, guilt-free."),
    "loginAction": ("Entrar", "Sign in"),
    "continueWithGoogle": ("Continuar con Google", "Continue with Google"),
    "goToRegister": ("¿No tienes cuenta? Crea una", "No account yet? Create one"),
    "registerTitle": ("Crea tu cuenta", "Create your account"),
    "registerSubtitle": ("Un minuto ahora, y tu presupuesto siempre a la vista.", "One minute now, your budget always in sight."),
    "registerAction": ("Crear cuenta", "Create account"),
    "goToLogin": ("Ya tengo cuenta", "I already have an account"),
    "email": ("Correo", "Email"),
    "invalidEmail": ("Escribe un correo válido", "Enter a valid email"),
    "password": ("Contraseña", "Password"),
    "showPassword": ("Mostrar contraseña", "Show password"),
    "hidePassword": ("Ocultar contraseña", "Hide password"),
    "passwordTooShort": ("Usa al menos {min} caracteres", "Use at least {min} characters"),
    # --- Pestañas ---
    "tabHome": ("Inicio", "Home"),
    "tabTransactions": ("Movimientos", "Activity"),
    "tabCoach": ("Coach", "Coach"),
    "tabProgress": ("Progreso", "Progress"),
    "tabProfile": ("Perfil", "Profile"),
    "coachTagline": ("Contigo, sin juzgar", "With you, never judging"),
    "badgesCount": ("{n} de {total} insignias", "{n} of {total} badges"),
    "badgeLocked": ("Por desbloquear", "Locked"),
    # --- Inicio ---
    "homeGreeting": ("Hola, {name}", "Hi, {name}"),
    "streakDays": ("{n, plural, =1{1 día} other{{n} días}}", "{n, plural, =1{1 day} other{{n} days}}"),
    "noBudgetTitle": ("Aún no tienes un presupuesto activo", "You don't have an active budget yet"),
    "noBudgetBody": (
        "Dinos cuánto tienes y hasta cuándo debe alcanzarte, y te diremos cuánto puedes gastar cada día.",
        "Tell us how much you have and how long it must last, and we'll tell you how much you can spend each day.",
    ),
    "createBudget": ("Crear presupuesto", "Create budget"),
    "editBudget": ("Editar presupuesto", "Edit budget"),
    "availablePerDay": ("Disponible por día", "Available per day"),
    "availableTotal": ("{amount} en total", "{amount} in total"),
    "daysLeft": (
        "{n, plural, =1{queda 1 día} other{quedan {n} días}}",
        "{n, plural, =1{1 day left} other{{n} days left}}",
    ),
    "riskBody": (
        "Al ritmo de ahora, el presupuesto alcanzaría hasta el {date}. Un pequeño ajuste esta semana lo estira hasta el final.",
        "At the current pace the budget would last until {date}. A small adjustment this week stretches it to the end.",
    ),
    "spent": ("Gastado", "Spent"),
    "extraIncome": ("Ingresos", "Income"),
    "setAsideTotal": ("Apartado", "Set aside"),
    "coachSays": ("Tu coach dice", "Your coach says"),
    "seeAll": ("Ver todo", "See all"),
    "activeGoal": ("Tu meta", "Your goal"),
    "activeChallenge": ("Reto en curso", "Current challenge"),
    "byCategory": ("Por categoría", "By category"),
    "limitOf": ("límite {amount}", "limit {amount}"),
    # --- Presupuesto y tono ---
    "toneMotivating": ("Motivador", "Motivating"),
    "toneDirect": ("Directo", "Direct"),
    "toneHumorous": ("Con humor", "Humorous"),
    "toneMinimal": ("Minimalista", "Minimal"),
    "budgetDatesError": ("La fecha final debe ser posterior a la inicial.", "The end date must be after the start date."),
    "budgetExplain": (
        "Tu presupuesto es el dinero con el que cuentas para un periodo, por ejemplo un semestre.",
        "Your budget is the money you are counting on for a period, for example a semester.",
    ),
    "budgetAmount": ("Dinero para el periodo", "Money for the period"),
    "startDate": ("Desde", "From"),
    "endDate": ("Hasta", "Until"),
    "coachToneQuestion": ("¿Cómo quieres que te hable tu coach?", "How should your coach talk to you?"),
    # --- Check-in y coach ---
    "moodAnxious": ("Ansiedad", "Anxious"),
    "moodWorried": ("Inquietud", "Worried"),
    "moodNeutral": ("Neutral", "Neutral"),
    "moodCalm": ("Calma", "Calm"),
    "moodConfident": ("Confianza", "Confident"),
    "checkinQuestion": ("¿Cómo te sientes hoy con tu dinero?", "How do you feel about your money today?"),
    "checkinDone": ("Tu check-in de hoy", "Today's check-in"),
    "actionDone": ("Hecho", "Done"),
    "whyThis": ("Basado en:", "Based on:"),
    "coachTips": ("Consejos", "Tips"),
    "coachChat": ("Chat", "Chat"),
    "noInsights": (
        "Cuando registres algunos gastos, aquí verás consejos hechos con tus propios datos.",
        "Once you log a few expenses, you'll see tips built from your own data here.",
    ),
    "coachDisclaimer": (
        "El coach orienta sobre hábitos y presupuesto. No es asesoría financiera ni de inversión.",
        "The coach guides habits and budgeting. It is not financial or investment advice.",
    ),
    "chatEmpty": ("Pregúntale a tu coach cómo vas o qué puedes ajustar.", "Ask your coach how you're doing or what you could adjust."),
    "chatHint": ("Escribe un mensaje", "Type a message"),
    # --- Metas ---
    "goals": ("Metas", "Goals"),
    "newGoal": ("Nueva meta", "New goal"),
    "goalName": ("¿Para qué ahorras?", "What are you saving for?"),
    "goalNameHint": ("Viaje, portátil, fondo de emergencia…", "Trip, laptop, emergency fund…"),
    "goalTarget": ("Monto objetivo", "Target amount"),
    "setAside": ("Apartar", "Set aside"),
    "setAsideFor": ("Apartar para {name}", "Set aside for {name}"),
    "setAsideHint": ("Lo apartado deja de contar como disponible.", "Money set aside no longer counts as available."),
    "setAsideAvailable": (
        "Tienes {amount} disponible. Lo apartado deja de contar para tu gasto diario.",
        "You have {amount} available. Money set aside no longer counts toward your daily spending.",
    ),
    "noGoals": (
        "Una meta le da destino a lo que no gastas. Crea la primera.",
        "A goal gives a destination to what you don't spend. Create your first one.",
    ),
    "goalReached": ("Cumplida", "Reached"),
    "goalVerified": ("Apartado de verdad", "Actually set aside"),
    "undoContribution": ("Devolver al disponible", "Return to available"),
    "deleteGoalTitle": ("¿Eliminar la meta?", "Delete this goal?"),
    "deleteGoalBody": ("Lo que habías apartado vuelve a estar disponible.", "What you had set aside becomes available again."),
    # --- Retos y gamificación ---
    "challenges": ("Retos", "Challenges"),
    "badges": ("Insignias", "Badges"),
    "newBadge": ("Nueva insignia: {names}", "New badge: {names}"),
    "pointsEarned": ("+{n} puntos", "+{n} points"),
    "pointsShort": ("{n} pts", "{n} pts"),
    "pointsTotal": ("{n} puntos", "{n} points"),
    "pointsToNext": ("faltan {n}", "{n} to go"),
    "maxLevel": ("nivel máximo", "top level"),
    "levelTitle": ("Nivel {n} · {name}", "Level {n} · {name}"),
    "metricSavings": ("Ahorro", "Savings"),
    "metricSavingsHint": (
        "Qué parte de lo que te tocaba este mes sigue sin gastarse.",
        "The share of this month's money that remains unspent.",
    ),
    "metricConsistency": ("Constancia", "Consistency"),
    "metricConsistencyHint": (
        "Días con registro en los últimos 30 días.",
        "Days with activity over the last 30 days.",
    ),
    "metricImprovement": ("Mejora", "Improvement"),
    "metricImprovementHint": (
        "Cambio de tu ahorro frente al mes anterior, en puntos porcentuales.",
        "Change in your savings versus last month, in percentage points.",
    ),
    "noChallenges": ("Aún no hay retos. Vuelve cuando tengas algunos gastos registrados.", "No challenges yet. Come back once you have logged some expenses."),
    "suggestedChallenges": ("Retos para ti", "Challenges for you"),
    "acceptChallenge": ("Aceptar reto", "Accept challenge"),
    "pastChallenges": ("Historial", "History"),
    "challengeDone": ("Cumplido · +{n} puntos", "Completed · +{n} points"),
    "challengeMissed": ("Esta vez no se dio. El siguiente es tuyo.", "Not this time. The next one is yours."),
    "challengeSpentSoFar": ("Llevas", "So far"),
    "challengeProgress": ("Avance", "Progress"),
    "endsOn": ("Termina el {date}", "Ends {date}"),
    "abandon": ("Abandonar", "Give up"),
    "abandonTitle": ("¿Abandonar el reto?", "Give up this challenge?"),
    "abandonBody": ("Puedes aceptar otro cuando quieras.", "You can accept another one whenever you like."),
    # --- Movimientos ---
    "expenses": ("Gastos", "Expenses"),
    "incomes": ("Ingresos", "Income"),
    "search": ("Buscar", "Search"),
    "allCategories": ("Todas", "All"),
    "dayToday": ("Hoy", "Today"),
    "dayYesterday": ("Ayer", "Yesterday"),
    "noExpenses": ("Aquí aparecerán tus gastos.", "Your expenses will show up here."),
    "noIncomes": ("Aquí aparecerá el dinero extra que recibas.", "Extra money you receive will show up here."),
    "newExpense": ("Nuevo gasto", "New expense"),
    "editExpense": ("Editar gasto", "Edit expense"),
    "confirmExpense": ("Confirma el gasto", "Confirm the expense"),
    "confirmExpenseHint": (
        "Esto fue lo que entendimos. Corrige lo que haga falta antes de guardar.",
        "This is what we understood. Fix anything you need before saving.",
    ),
    "merchantOptional": ("Comercio (opcional)", "Merchant (optional)"),
    "deleteExpenseTitle": ("¿Eliminar el gasto?", "Delete this expense?"),
    "deleteExpenseBody": ("Tu disponible se recalcula al instante.", "Your available amount is recalculated right away."),
    "deleteIncomeTitle": ("¿Eliminar el ingreso?", "Delete this income?"),
    "deleteIncomeBody": ("Tu disponible se recalcula al instante.", "Your available amount is recalculated right away."),
    "addByText": ("Escribir o dictar", "Type or dictate"),
    "addByTextHint": ("Cuéntalo con tus palabras", "Say it in your own words"),
    "addByReceipt": ("Foto de un recibo", "Receipt photo"),
    "addByReceiptHint": ("La foto no sale de tu teléfono", "The photo never leaves your phone"),
    "addByGallery": ("Recibo desde la galería", "Receipt from gallery"),
    "addManual": ("Formulario manual", "Manual form"),
    "addIncome": ("Dinero que recibí", "Money I received"),
    "confirmIncome": ("Confirma el ingreso", "Confirm the income"),
    "confirmIncomeHint": (
        "Entendimos que recibiste este dinero. Corrige lo que haga falta antes de guardar.",
        "We understood you received this money. Fix anything before saving.",
    ),
    "addIncomeHint": ("Amplía tu disponible sin cambiar el presupuesto original.", "Raises your available amount without changing the original budget."),
    "quickAddExample": ("Ej.: me compré un helado de 5000", "E.g.: I bought an ice cream for 5000"),
    "voiceStart": ("Toca para dictar", "Tap to dictate"),
    "voiceStop": ("Detener", "Stop"),
    "voiceListening": ("Te escucho…", "Listening…"),
    "voiceUnavailable": ("El dictado no está disponible en este teléfono. Puedes escribirlo.", "Dictation isn't available on this phone. You can type instead."),
    "analyze": ("Continuar", "Continue"),
    "receiptReading": ("Leyendo el recibo…", "Reading the receipt…"),
    "receiptUnreadable": ("No logramos leer texto en la foto. Prueba con más luz y el recibo plano.", "We couldn't read any text in the photo. Try more light and a flat receipt."),
    "sourceManual": ("Manual", "Manual"),
    "sourceText": ("Texto", "Text"),
    "sourceVoice": ("Voz", "Voice"),
    "sourceReceipt": ("Recibo", "Receipt"),
    "sourceSms": ("SMS", "SMS"),
    "sourceRecurring": ("Gasto fijo", "Recurring"),
    # --- Categorías y gastos fijos ---
    "categories": ("Categorías", "Categories"),
    "newCategory": ("Nueva categoría", "New category"),
    "editCategory": ("Editar categoría", "Edit category"),
    "limitOptional": ("Límite (opcional)", "Limit (optional)"),
    "fixedExpense": ("Gasto fijo", "Fixed expense"),
    "fixedExpenseHint": ("Algo que sí o sí pagas, como transporte.", "Something you always pay, like transport."),
    "optionalExpense": ("Opcional", "Optional"),
    "defaultCategory": ("predeterminada", "default"),
    "recurringExpenses": ("Gastos fijos semanales", "Weekly recurring expenses"),
    "newRecurring": ("Nuevo gasto fijo", "New recurring expense"),
    "weekday": ("Día de la semana", "Day of the week"),
    "everyWeekday": ("cada {day}", "every {day}"),
    "noRecurring": ("Los gastos que se repiten cada semana se registran solos desde aquí.", "Expenses that repeat every week get logged automatically from here."),
    "deleteRecurringTitle": ("¿Eliminar el gasto fijo?", "Delete this recurring expense?"),
    "deleteRecurringBody": ("Los gastos ya generados se conservan.", "Expenses already generated are kept."),
    # --- Perfil ---
    "sectionCoach": ("Coach", "Coach"),
    "sectionMoney": ("Tu dinero", "Your money"),
    "sectionReports": ("Resúmenes", "Summaries"),
    "sectionApp": ("Aplicación", "App"),
    "coachTone": ("Estilo del coach", "Coach style"),
    "reminder": ("Recordatorio del check-in", "Check-in reminder"),
    "reminderOff": ("Desactivado", "Off"),
    "reminderTime": ("Hora del recordatorio", "Reminder time"),
    "reminderTitle": ("¿Cómo va tu día?", "How is your day going?"),
    "reminderBody": ("Un minuto para tu check-in y tus gastos de hoy.", "One minute for your check-in and today's expenses."),
    "reminderDenied": ("Para recordarte, activa las notificaciones de la app en los ajustes del teléfono.", "To remind you, turn on the app's notifications in your phone settings."),
    "language": ("Idioma", "Language"),
    "theme": ("Apariencia", "Appearance"),
    "themeLight": ("Clara", "Light"),
    "themeDark": ("Oscura", "Dark"),
    "themeSystem": ("Como el teléfono", "Match phone"),
    "privacy": ("Privacidad", "Privacy"),
    "logout": ("Cerrar sesión", "Sign out"),
    "deleteAccount": ("Eliminar mi cuenta", "Delete my account"),
    "deleteAccountBody": (
        "Se borran para siempre tu cuenta y todos tus datos: gastos, metas, retos, check-ins y conversaciones. No se puede deshacer.",
        "Your account and all your data are deleted forever: expenses, goals, challenges, check-ins and conversations. This can't be undone.",
    ),
    # --- Privacidad ---
    "privacyIntro": ("Estos son los datos que usa la app y para qué.", "This is the data the app uses, and what for."),
    "privacyExpensesTitle": ("Tus gastos, ingresos y metas", "Your expenses, income and goals"),
    "privacyExpensesBody": (
        "Se guardan en nuestro servidor para calcular tu disponible, tus retos y tus puntos. No se venden ni se usan para publicidad.",
        "They are stored on our server to compute your available amount, challenges and points. They are never sold or used for advertising.",
    ),
    "privacyReceiptsTitle": ("Fotos de recibos", "Receipt photos"),
    "privacyReceiptsBody": (
        "El texto se reconoce en tu teléfono. La foto no se sube: al servidor solo viaja el texto reconocido.",
        "Text is recognized on your phone. The photo is not uploaded: only the recognized text is sent to the server.",
    ),
    "privacyVoiceTitle": ("Dictado por voz", "Voice dictation"),
    "privacyVoiceBody": (
        "Lo convierte a texto el servicio de voz de tu teléfono. La app solo recibe el texto.",
        "Your phone's speech service turns it into text. The app only receives the text.",
    ),
    "privacySmsTitle": ("SMS del banco", "Bank SMS"),
    "privacySmsBody": (
        "Solo si lo activas. La app lee tus SMS recientes en el teléfono para mostrarte los que parecen movimientos; nada se envía hasta que tú eliges registrar uno.",
        "Only if you turn it on. The app reads your recent SMS on the phone to show the ones that look like transactions; nothing is sent until you choose to log one.",
    ),
    "privacyAiTitle": ("Inteligencia artificial", "Artificial intelligence"),
    "privacyAiBody": (
        "Las frases, los textos de recibos y un resumen de tus cifras se envían a un servicio de IA para interpretarlos y redactar los consejos. El coach explica en qué dato se basa cada sugerencia.",
        "Phrases, receipt text and a summary of your figures are sent to an AI service to interpret them and write the tips. The coach explains which data each suggestion is based on.",
    ),
    "privacyDeleteTitle": ("Tú tienes el control", "You are in control"),
    "privacyDeleteBody": (
        "Puedes eliminar tu cuenta y todos tus datos cuando quieras desde Perfil.",
        "You can delete your account and all your data at any time from Profile.",
    ),
    # --- Reportes ---
    "weeklyReport": ("Reporte de la semana", "Weekly report"),
    "weekSpent": ("Gasto de la semana", "Spent this week"),
    "weekPace": ("Ritmo esperado", "Expected pace"),
    "weekUnderPace": ("Vas {amount} por debajo de tu ritmo semanal.", "You are {amount} below your weekly pace."),
    "weekOverPace": ("Vas {amount} por encima de tu ritmo semanal. Aún hay semana para equilibrar.", "You are {amount} above your weekly pace. There's still week left to balance."),
    "wrappedTitle": ("Tu mes en resumen", "Your month in review"),
    "wrappedSpent": ("{n, plural, =1{en 1 gasto registrado} other{en {n} gastos registrados}}", "{n, plural, =1{across 1 logged expense} other{across {n} logged expenses}}"),
    "wrappedDays": ("días al tanto de tu dinero", "days on top of your money"),
    "wrappedTopCategory": ("fue tu categoría principal: {pct}% del gasto", "was your top category: {pct}% of spending"),
    "wrappedBiggest": ("tu gasto más grande: {desc}", "your biggest expense: {desc}"),
    "wrappedVsLastMonth": ("frente al mes anterior", "versus last month"),
    "wrappedGoals": ("apartados para tus metas", "set aside for your goals"),
    "wrappedPoints": ("puntos ganados", "points earned"),
    "wrappedMood": ("tu ánimo más frecuente: {mood}", "your most frequent mood: {mood}"),
    "wrappedEmpty": ("Este mes aún no tiene gastos registrados.", "This month has no logged expenses yet."),
    "previousMonth": ("Mes anterior", "Previous month"),
    "nextMonth": ("Mes siguiente", "Next month"),
    # --- Análisis y gráficas ---
    "analytics": ("Análisis", "Insights"),
    "thisWeek": ("Esta semana", "This week"),
    "seeAnalytics": ("Ver análisis", "See insights"),
    "otherCategories": ("Otras", "Other"),
    "analyticsEmpty": (
        "Cuando registres gastos, aquí verás cómo se reparten y cómo cambian de una semana a otra.",
        "Once you log expenses, you'll see here how they split up and how they change week to week.",
    ),
    "analyticsEmptyWeek": ("Sin gastos registrados en esta semana.", "No expenses logged in this week."),
    "trend": ("Tendencia", "Trend"),
    "trendWeeks": ("Semanas", "Weeks"),
    "trendDays": ("Días", "Days"),
    "previousWeek": ("Semana anterior", "Previous week"),
    "nextWeek": ("Semana siguiente", "Next week"),
    "weekMoreThanPrevious": ("{pct}% más que la semana anterior", "{pct}% more than the previous week"),
    "weekLessThanPrevious": ("{pct}% menos que la semana anterior", "{pct}% less than the previous week"),
    "weekSameAsPrevious": ("Igual que la semana anterior", "Same as the previous week"),
    "weeklyAverage": ("Promedio semanal: {amount}", "Weekly average: {amount}"),
    "average": ("Promedio", "Average"),
    "badgeUnlocked": ("¡Nueva insignia!", "New badge!"),
    "great": ("¡Genial!", "Great!"),
    # --- SMS ---
    "smsTitle": ("SMS del banco", "Bank SMS"),
    "smsSubtitle": ("Registra movimientos desde los mensajes de tu banco", "Log transactions from your bank's messages"),
    "smsExplain": (
        "Con tu permiso, la app busca en tus SMS de los últimos 14 días los que parecen movimientos bancarios. Se leen en tu teléfono y nada se guarda hasta que tú lo confirmes.",
        "With your permission, the app looks through your SMS from the last 14 days for ones that look like bank transactions. They are read on your phone and nothing is saved until you confirm it.",
    ),
    "smsAllow": ("Permitir lectura de SMS", "Allow SMS access"),
    "smsEmpty": ("No hay mensajes bancarios por revisar.", "No bank messages to review."),
    "smsUnavailable": ("La lectura de SMS no está disponible en este dispositivo.", "SMS reading isn't available on this device."),
    "smsDismiss": ("Descartar", "Dismiss"),
    "smsRegister": ("Registrar", "Log it"),
}


def _arb(indice: int, locale: str) -> dict:
    arb: dict = {"@@locale": locale}
    for clave, textos in TEXTOS.items():
        arb[clave] = textos[indice]
        if indice == 0:
            # Marcadores {x} de primer nivel (los de dentro de un plural repiten el mismo nombre).
            nombres = dict.fromkeys(re.findall(r"\{(\w+)[,}]", textos[0]))
            if nombres:
                arb[f"@{clave}"] = {
                    "placeholders": {n: {"type": "int" if n in ENTEROS else "String"} for n in nombres}
                }
    return arb


def main() -> None:
    destino = pathlib.Path(__file__).resolve().parent.parent / "lib" / "l10n"
    destino.mkdir(parents=True, exist_ok=True)
    for indice, locale in enumerate(("es", "en")):
        contenido = json.dumps(_arb(indice, locale), ensure_ascii=False, indent=2) + "\n"
        (destino / f"app_{locale}.arb").write_bytes(contenido.encode("utf-8"))
    print(f"{len(TEXTOS)} textos -> {destino}")


if __name__ == "__main__":
    main()
