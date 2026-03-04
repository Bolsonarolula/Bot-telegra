import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, CallbackQueryHandler, filters
)
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.types import Channel, Chat

# ======= CONFIGURAÇÕES =======
BOT_TOKEN = "7146425074:AAHf2EhXs2dO6jaiDrnl3F6qnc70Rg_GhZ0"
API_ID = 20305448
API_HASH = "2d9ee612f8ece128cd4bd78b2e71d01e"
OWNER_ID = 8002161328
INTERVALO_ADICAO = 20
LIMITE_ADICOES = 400

CONTAS = {
    1:  "+5522981528428",
    2:  "+5522992373870",
    3:  "+5514991346873",
    4:  "+5511970111825",
    5:  "+5511914000936",
    6:  "+5583914310659",
    7:  "+5584986596437",
    8:  "+5575981794453",
    9:  "+5511971252232",
    10: "+5517996780126",
}
# =============================

os.makedirs("sessions", exist_ok=True)

AGUARDANDO_CODIGO, AGUARDANDO_SENHA = range(2)

clientes = {
    num: TelegramClient(f"sessions/conta_{num}", API_ID, API_HASH)
    for num in CONTAS
}

login_em_andamento = {}

# Controle de execução
operacao_ativa = False
parar_operacao = False


def apenas_dono(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("⛔ Acesso negado.")
            return
        return await func(update, context)
    return wrapper


@apenas_dono
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Comandos disponíveis:\n\n"
        "/login 1 até /login 10 — Autenticar cada conta\n"
        "/status — Ver status de todas as contas\n"
        "/adicionar @origem @destino — Transferir membros\n"
        "/parar — Parar a operação em andamento\n\n"
        f"ℹ️ Limite por operação: {LIMITE_ADICOES} membros"
    )


@apenas_dono
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📋 Status das contas:\n\n"
    for num, phone in CONTAS.items():
        try:
            c = clientes[num]
            if not c.is_connected():
                await c.connect()
            auth = await c.is_user_authorized()
            icone = "✅" if auth else "❌"
            msg += f"{icone} Conta {num} ({phone})\n"
        except Exception:
            msg += f"⚠️ Conta {num} ({phone}) — erro ao verificar\n"

    msg += f"\n🔄 Operação ativa: {'Sim' if operacao_ativa else 'Não'}"
    await update.message.reply_text(msg)


@apenas_dono
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Use: /login <número da conta>\nExemplo: /login 1")
        return ConversationHandler.END

    num = int(context.args[0])
    if num not in CONTAS:
        await update.message.reply_text(f"Conta {num} não existe. Use de 1 a {len(CONTAS)}.")
        return ConversationHandler.END

    try:
        c = clientes[num]
        if not c.is_connected():
            await c.connect()

        if await c.is_user_authorized():
            await update.message.reply_text(f"✅ Conta {num} já está autenticada!")
            return ConversationHandler.END

        await c.send_code_request(CONTAS[num])
        login_em_andamento[update.effective_user.id] = num
        await update.message.reply_text(
            f"📱 Código enviado para conta {num} ({CONTAS[num]}). Digite o código:"
        )
        return AGUARDANDO_CODIGO

    except Exception as e:
        await update.message.reply_text(f"Erro ao iniciar login da conta {num}: {e}")
        return ConversationHandler.END


@apenas_dono
async def receber_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num = login_em_andamento.get(update.effective_user.id)
    if not num:
        await update.message.reply_text("Nenhum login em andamento. Use /login <número>.")
        return ConversationHandler.END

    codigo = update.message.text.strip()
    try:
        await clientes[num].sign_in(CONTAS[num], codigo)
        await update.message.reply_text(f"✅ Conta {num} autenticada com sucesso!")
        login_em_andamento.pop(update.effective_user.id, None)
        return ConversationHandler.END
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("🔐 Verificação em duas etapas ativa. Digite sua senha:")
        return AGUARDANDO_SENHA
    except Exception as e:
        await update.message.reply_text(f"Erro ao confirmar código: {e}")
        return ConversationHandler.END


@apenas_dono
async def receber_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num = login_em_andamento.get(update.effective_user.id)
    if not num:
        return ConversationHandler.END

    senha = update.message.text.strip()
    try:
        await clientes[num].sign_in(password=senha)
        await update.message.reply_text(f"✅ Conta {num} autenticada com sucesso!")
    except Exception as e:
        await update.message.reply_text(f"Erro ao confirmar senha: {e}")

    login_em_andamento.pop(update.effective_user.id, None)
    return ConversationHandler.END


@apenas_dono
async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global parar_operacao
    if not operacao_ativa:
        await update.message.reply_text("ℹ️ Nenhuma operação em andamento.")
        return
    parar_operacao = True
    await update.message.reply_text("⏹️ Sinal de parada enviado. Aguarde finalizar o membro atual...")


async def callback_parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global parar_operacao
    query = update.callback_query
    await query.answer()
    if not operacao_ativa:
        await query.edit_message_text("ℹ️ Nenhuma operação em andamento.")
        return
    parar_operacao = True
    await query.edit_message_text("⏹️ Sinal de parada enviado. Aguarde finalizar o membro atual...")


@apenas_dono
async def adicionar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global operacao_ativa, parar_operacao

    if operacao_ativa:
        await update.message.reply_text("⚠️ Já existe uma operação em andamento. Use /parar para cancelar.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Uso correto: /adicionar @grupo_origem @grupo_destino")
        return

    origem_id = context.args[0]
    destino_id = context.args[1]

    # Verifica contas ativas
    contas_ativas = []
    for num, c in clientes.items():
        try:
            if not c.is_connected():
                await c.connect()
            if await c.is_user_authorized():
                contas_ativas.append(num)
        except Exception:
            pass

    if not contas_ativas:
        await update.message.reply_text("❌ Nenhuma conta autenticada. Use /login primeiro.")
        return

    # Botão de parar
    keyboard = [[InlineKeyboardButton("⏹️ Parar operação", callback_data="parar")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ {len(contas_ativas)} conta(s) ativa(s): {contas_ativas}\n"
        f"⏳ Coletando membros de {origem_id}...",
        reply_markup=reply_markup
    )

    operacao_ativa = True
    parar_operacao = False

    try:
        c_principal = clientes[contas_ativas[0]]
        origem = await c_principal.get_entity(origem_id)

        membros = []
        async for user in c_principal.iter_participants(origem, aggressive=True):
            if not user.bot and not user.deleted:
                membros.append(user)
                if len(membros) >= LIMITE_ADICOES:
                    break

        await update.message.reply_text(
            f"✅ {len(membros)} membros coletados.\n"
            f"🚀 Iniciando adição (limite: {LIMITE_ADICOES})...",
            reply_markup=reply_markup
        )

        adicionados = 0
        erros = 0
        contas_bloqueadas = []
        conta_index = 0

        for user in membros:
            if parar_operacao:
                await update.message.reply_text(
                    f"⏹️ Operação pausada pelo usuário.\n"
                    f"✅ Adicionados até agora: {adicionados}\n"
                    f"❌ Erros: {erros}"
                )
                break

            if adicionados >= LIMITE_ADICOES:
                await update.message.reply_text(
                    f"🔔 Limite de {LIMITE_ADICOES} adições atingido!\n"
                    f"✅ Adicionados: {adicionados}\n"
                    f"❌ Erros: {erros}"
                )
                break

            # Pula contas bloqueadas
            contas_disponiveis = [n for n in contas_ativas if n not in contas_bloqueadas]
            if not contas_disponiveis:
                await update.message.reply_text(
                    "⛔ Todas as contas estão bloqueadas temporariamente. Tente mais tarde."
                )
                break

            num_conta = contas_disponiveis[conta_index % len(contas_disponiveis)]
            c = clientes[num_conta]

            try:
                destino = await c.get_entity(destino_id)

                if isinstance(destino, Channel):
                    await c(InviteToChannelRequest(destino, [user]))
                elif isinstance(destino, Chat):
                    await c(AddChatUserRequest(destino.id, user, 10))

                adicionados += 1

                if adicionados % 5 == 0:
                    await update.message.reply_text(
                        f"➕ {adicionados}/{LIMITE_ADICOES} adicionados | Conta {num_conta} em uso...",
                        reply_markup=reply_markup
                    )

                await asyncio.sleep(INTERVALO_ADICAO)

            except errors.FloodWaitError as e:
                await update.message.reply_text(
                    f"⚠️ Conta {num_conta} bloqueada pelo Telegram por {e.seconds}s. "
                    f"Pulando para próxima conta..."
                )
                contas_bloqueadas.append(num_conta)
                continue

            except errors.UserPrivacyRestrictedError:
                erros += 1

            except errors.UserAlreadyParticipantError:
                pass

            except Exception as e:
                erros += 1
                print(f"Erro conta {num_conta} ao adicionar {user.id}: {e}")

            conta_index += 1

        else:
            await update.message.reply_text(
                f"🏁 Concluído!\n"
                f"✅ Adicionados: {adicionados}\n"
                f"❌ Erros: {erros}\n"
                f"👥 Contas usadas: {[n for n in contas_ativas if n not in contas_bloqueadas]}\n"
                f"⛔ Contas bloqueadas temporariamente: {contas_bloqueadas if contas_bloqueadas else 'Nenhuma'}"
            )

    except Exception as e:
        await update.message.reply_text(f"Erro geral: {e}")

    finally:
        operacao_ativa = False
        parar_operacao = False


async def post_init(application):
    for num, c in clientes.items():
        try:
            await c.connect()
        except Exception:
            pass
    print("Clientes Telethon conectados!")


async def post_shutdown(application):
    for c in clientes.values():
        try:
            if c.is_connected():
                await c.disconnect()
        except Exception:
            pass


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login)],
        states={
            AGUARDANDO_CODIGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_codigo)],
            AGUARDANDO_SENHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_senha)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("adicionar", adicionar))
    app.add_handler(CommandHandler("parar", parar))
    app.add_handler(CallbackQueryHandler(callback_parar, pattern="^parar$"))
    app.add_handler(conv_handler)

    print("Bot rodando...")
    app.run_polling()


if __name__ == "__main__":
    main()
    
