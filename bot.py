import logging
import traceback
import json

from telegram import __version__ as TG_VER
try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}. To view the "
        f"{TG_VER} version of this example, "
        f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
    )
    
from telegram import ForceReply, Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Bot, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.error import NetworkError
from models import User, Utm, Transaction, Wallet, WalletTransaction, Withdraw, AddressBook, Trade, RewardHub
from datetime import datetime, timedelta
import re
from random import randint
from utils.tronTool import check_usdt_balance, transfer_usdt_to_address, transfer_trx, create_account
from utils.bep20Tool import check_balance_usdt as check_balance_bep20, create_bep20_wallet
from tasks import check_payment_status, reward_invited_user, send_usdt, send_message_queue, broadcast_all_task, broadcast_investors_task
import requests

# Define your bot token
BOT_TOKEN = '8469039154:AAEA7WRST1ULUx3xxDBJPA70lDS0M-fBxcA'
WITHDRAW_GROUP = -457191733151
ADMIN_ID = 7730427593
ADMIN_IDS = [7730427593, 7730427593]
LOG_GROUP = -10027550338399



def generate_qr_code(data):
    import qrcode
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(f'qrcodes/{data}.png')

    return f'qrcodes/{data}.png'


def load_language(lang_code):
    with open(f'lang/{lang_code}.json', 'r', encoding='utf-8') as f:
        return json.load(f)


# Load default language (English)
languages = {
    'en': load_language('en'),
    'tr': load_language('tr'),
    'ru': load_language('ru'),
    'fa': load_language('fa'),
    'ar': load_language('ar')
}


def get_text(lang_code, key):
    return languages[lang_code].get(key, languages['en'][key])


def main_keyboard(lang_code):
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton(get_text(lang_code, 'menu_tradebot')), KeyboardButton(get_text(lang_code, 'menu_account'))],
        [KeyboardButton(get_text(lang_code, 'menu_referral'))],
        [KeyboardButton(get_text(lang_code, 'menu_support')), KeyboardButton(get_text(lang_code, 'menu_faqs'))],
    ], resize_keyboard=True)
    return keyboard


def dev_main_keyboard(lang_code):
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton(get_text(lang_code, 'menu_tradebot')), KeyboardButton(get_text(lang_code, 'menu_account'))],
        [KeyboardButton(get_text(lang_code, 'menu_referral'))],
        [KeyboardButton(get_text(lang_code, 'menu_support')), KeyboardButton(get_text(lang_code, 'menu_faqs'))],
    ], resize_keyboard=True)
    return keyboard


def is_joined(user_id: any):
    channel_status_1 = requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/getChatMember', data={'chat_id': '@CornexBase', 'user_id': user_id}).json()
    #channel_status_2 = requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/getChatMember', data={'chat_id': '@FiboCapitalChat', 'user_id': user_id}).json()
    #channel_status_3 = requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/getChatMember', data={'chat_id': '@FiboCapitalTrade', 'user_id': user_id}).json()
    #print(channel_status_1)
    #if channel_status_1['result']['status'] == 'left' or channel_status_2['result']['status'] == 'left' and channel_status_3['result']['status'] == 'left':
    #    return False
    if channel_status_1['result']['status'] in ['left', 'kicked', 'restricted']:
        return False
    
    return True


def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    try:
        _, message = update.message.text.split(' ', 1)
    except ValueError:
        return update.message.reply_text("Usage: /broadcast your message")

    # Queue the broadcast to run in background so bot stays responsive
    broadcast_all_task.apply_async(args=[message])

    total_users = User.objects.count()
    return update.message.reply_text(f'Broadcast queued for {total_users} users')


# --- Admin broadcast to investors only ---
def broadcast_investors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast a message only to users with a positive balance (investors). Usage: /broadcast_investors <message>"""

    if update.effective_user.id not in ADMIN_IDS:
        return

    try:
        _, message = update.message.text.split(' ', 1)
    except ValueError:
        return update.message.reply_text("Usage: /broadcast_investors your message")

    # Execute in background via Celery
    broadcast_investors_task.apply_async(args=[message])

    investor_count = User.objects.aggregate({'$lookup': {
        'from': 'transaction',
        'localField': '_id',
        'foreignField': 'user',
        'as': 'txs'
    }})  # quick estimation not critical; just send queued message

    return update.message.reply_text('Broadcast queued for investors')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type in ['group', 'supergroup' ,'channel']:
        return
    
    user = User.objects(telegram_user_id=update.message.from_user.id).first()

    if not user:
        if re.findall(r'/start r(.*)', update.message.text):
            pid = int(re.findall(r'/start r(.*)', update.message.text)[0])
            invited_by = User.objects(telegram_user_id=pid).first()
            if not invited_by:
                return await update.message.reply_text(get_text('en', 'referral_not_found'))
            #reward_invited_user.apply_async(args=[invited_by.telegram_user_id])

            user = User(telegram_user_id=update.message.from_user.id, pid=randint(10000, 999999999), name=update.message.from_user.first_name, step='main_menu', language='en', joined_at=datetime.now(), invited_by=invited_by)
            user.save()
        elif re.findall(r'/start utm_(.*)', update.message.text):
            utm_name = re.findall(r'/start utm_(.*)', update.message.text)[0]
            utm = Utm.objects(name=utm_name).first()
            if not utm:
                utm = Utm(name=utm_name)
                utm.save()

            user = User(telegram_user_id=update.message.from_user.id, pid=randint(10000, 999999999), name=update.message.from_user.first_name, step='main_menu', language='en', joined_at=datetime.now(), utm=utm)
            user.save()
        else:
            user = User(telegram_user_id=update.message.from_user.id, pid=randint(10000, 999999999), name=update.message.from_user.first_name, step='main_menu', language='en', joined_at=datetime.now())
            user.save()

        keyboard = [
            [InlineKeyboardButton("English 🇺🇸", callback_data='set_lang_en')],
            [InlineKeyboardButton("Русский 🇷🇺", callback_data='set_lang_ru')],
            [InlineKeyboardButton("عربى 🇸🇦", callback_data='set_lang_ar')],
            [InlineKeyboardButton("فارسی 🇮🇷", callback_data='set_lang_fa')],
            [InlineKeyboardButton("Türkçe 🇹🇷", callback_data='set_lang_tr')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(get_text('en', 'choose_language'), reply_markup=reply_markup)
    else:
        keyboard = main_keyboard(user.language)

        # check user balance in db if more than 1000 show capitalfund button
        balance = Transaction.objects(user=user, status='completed').sum('amount')
        
        keyboard = main_keyboard(user.language)
        
        user.step = 'main_menu'
        user.save()
        await update.message.reply_text(get_text(user.language, 'welcome_back').format(name=update.effective_user.first_name), reply_markup=keyboard, parse_mode='Markdown')


def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = User.objects(telegram_user_id=update.message.from_user.id).first()
    if not user:
        return start(update, context)

    # return withdout answer group chats

    if update.effective_chat.type in ['group', 'supergroup' ,'channel']:
        return
    
    if not is_joined(update.effective_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'join_channel_chat_button'), url='https://t.me/CornexBase')],
        ])
        return update.message.reply_text(get_text(user.language, 'join_channel_message'), reply_markup=keyboard, parse_mode="markdown")
    
    if user.step == 'main_menu':
        if update.message.text == get_text(user.language, 'menu_tradebot'):
            is_trade_active = user.is_trade_active
            if not is_trade_active:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.language, 'start_trading'), callback_data='start_trading')],
                    [InlineKeyboardButton(get_text(user.language, 'tradebot_statistics_menu'), callback_data='tradebot_statistics_menu')],
                    [InlineKeyboardButton('Signals', url='https://t.me/CornexBase')],
                ])
                return update.message.reply_text(get_text(user.language, 'trading_status_message').format(status=get_text(user.language, 'stopped')), reply_markup=keyboard, parse_mode='markdown')
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.language, 'stop_trading'), callback_data='stop_trading')],
                    [InlineKeyboardButton(get_text(user.language, 'tradebot_statistics_menu'), callback_data='tradebot_statistics_menu')],
                    [InlineKeyboardButton('Signals', url='https://t.me/CornexBase')],
                ])
                return update.message.reply_text(get_text(user.language, 'trading_status_message').format(status=get_text(user.language, 'active')), reply_markup=keyboard, parse_mode='markdown')
        elif update.message.text == get_text(user.language, 'menu_account'):
            total_balance = Transaction.objects(user=user, status='completed').sum('amount')
            in_calculation = Transaction.objects(user=user, status='completed', type='profit', created_at__gte=datetime.now() - timedelta(days=7)).sum('amount')
            total_withdraw = Transaction.objects(user=user, status='completed', type='withdraw').sum('amount')
            total_withdraw_fee = Transaction.objects(user=user, status='completed', type='withdraw_fee').sum('amount')
            total_deposit = Transaction.objects(user=user, status='completed', type='deposit').sum('amount')
            total_trade = Transaction.objects(user=user, status='completed', type='profit').count()

            total_withdraw = (total_withdraw + total_withdraw_fee) * -1

            join_date = user.joined_at.strftime('%Y-%m-%d %H:%M:%S')

            keyboard_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text(user.language, 'menu_topup'), callback_data='menu_topup')],
                [InlineKeyboardButton(get_text(user.language, 'menu_withdraw_funds'), callback_data='menu_withdraw_funds')],
                [InlineKeyboardButton(get_text(user.language, 'menu_referral'), callback_data='menu_referral')],
            ])

            return update.message.reply_text(
                get_text(user.language, 'account_summary_message').format(
                    balance=round(total_balance,2), in_calculation=round(in_calculation,2), total_withdraw=round(total_withdraw,2), total_trades=total_trade, join_date=join_date,
                ),
                reply_markup=keyboard_markup, 
                parse_mode='markdown'
            )
        elif update.message.text == get_text(user.language, 'menu_faqs'):
            keyboard_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text(user.language, 'faq_how_it_works_button'), callback_data='faq_how_it_works')],
                [InlineKeyboardButton(get_text(user.language, 'faq_how_to_make_deposit_button'), callback_data='faq_how_to_make_deposit')],
                [InlineKeyboardButton(get_text(user.language, 'faq_how_to_withdraw_funds_button'), callback_data='faq_how_to_withdraw_funds')],
                [InlineKeyboardButton(get_text(user.language, 'faq_what_is_the_commistion_button'), callback_data='faq_what_is_the_commistion')],
                [InlineKeyboardButton(get_text(user.language, 'faq_minimum_deposit_button'), callback_data='faq_minimum_deposit')],
                [InlineKeyboardButton(get_text(user.language, 'faq_functionnality_description_button'), callback_data='faq_functionnality_description')],
                [InlineKeyboardButton(get_text(user.language, 'faq_bot_trading_exchange_button'), callback_data='faq_bot_trading_exchange')],
                [InlineKeyboardButton(get_text(user.language, 'faq_available_transactions_button'), callback_data='faq_available_transactions')],
                [InlineKeyboardButton(get_text(user.language, 'faq_possible_risks_button'), callback_data='faq_possible_risks')],
                [InlineKeyboardButton(get_text(user.language, 'faq_terms_of_use_button'), callback_data='faq_terms_of_use')],
                [InlineKeyboardButton(get_text(user.language, 'faq_token_storage_button'), callback_data='faq_token_storage')],
                [InlineKeyboardButton(get_text(user.language, 'faq_loss_of_token_button'), callback_data='faq_loss_of_token')],
                [InlineKeyboardButton(get_text(user.language, 'faq_referral_program_button'), callback_data='faq_referral_program')],
                [InlineKeyboardButton(get_text(user.language, 'faq_any_restrictions_button'), callback_data='faq_any_restrictions')],
                [InlineKeyboardButton(get_text(user.language, 'faq_bot_stop_loss_point_button'), callback_data='faq_bot_stop_loss_point')],
                [InlineKeyboardButton(get_text(user.language, 'faq_building_a_trust_button'), callback_data='faq_building_a_trust')],
            ])
            return update.message.reply_text(get_text(user.language, 'faq_message'), reply_markup=keyboard_markup, parse_mode='markdown')
        elif update.message.text == get_text(user.language, 'menu_referral'):
            link = f'https://t.me/CornexBot?start=r{user.telegram_user_id}'
            total_invited = User.objects(invited_by=user).count()
            total_earned = Transaction.objects(user=user, type='referral').sum('amount')
            
            return update.message.reply_text(get_text(user.language, 'referral_message').format(link=link, total_invited=total_invited, total_income=total_earned), parse_mode='markdown')
        elif update.message.text == get_text(user.language, 'menu_support'):
            keyboard_makrup = InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text(user.language, 'write_to_support'), url='https://t.me/CornexSup')],
            ])
            return update.message.reply_text(get_text(user.language, 'support_message'), reply_markup=keyboard_makrup)
        elif update.message.text == get_text(user.language, 'menu_joinus'):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text(user.language, 'send_your_resume'), url='https://t.me/CornexSup')],
            ])
            return update.message.reply_text(get_text(user.language, 'joinus_message'), reply_markup=keyboard, parse_mode='markdown')
        elif update.message.text == get_text(user.language, 'menu_rewardhub'):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text(user.language, 'rewardhub_my_rewards_button'),  callback_data='rewardhub_status'), InlineKeyboardButton(get_text(user.language, 'rewardhub_invite_button'), callback_data='rewardhub_invite')],
            ])
            return update.message.reply_text(get_text(user.language, 'rewardhub_message'), reply_markup=keyboard, parse_mode='markdown')
        elif update.message.text == get_text(user.language, 'referral_leaderboard'):
            inviters = RewardHub.objects().aggregate(
                {'$match': {'reward_type': 'referral_challenge'}},
                {'$match': {'user': {'$ne': None}}},
                {'$group': {'_id': '$user', 'total': {'$sum': 1}}},
                {'$sort': {'total': -1}}
            )
            msg = ''
            # limit the number of users to 10
            num = 1
            for inviter in inviters:
                _user = User.objects(id=inviter['_id']).first()
                if update.effective_user.id == _user.telegram_user_id:
                    msg += f"📍 {num}. {_user.name} {inviter['total']} Invites\n"
                else:
                    msg += f"{num}. {_user.name} {inviter['total']} Invites\n"
                num += 1
                if num > 12:
                    break
            
            amount = RewardHub.objects(user=user, reward_type='referral_challenge').sum('amount')
            count = RewardHub.objects(user=user, reward_type='referral_challenge').count()
            return update.message.reply_text(get_text(user.language, 'referral_leaderboard_message').format(users=msg, total_invited=count, total_invested=amount), parse_mode='markdown')
        else:
            balance = Transaction.objects(user=user, status='completed').sum('amount')
            
            keyboard = main_keyboard(user.language)
            return update.message.reply_text(get_text(user.language, 'welcome_back').format(name=update.effective_user.first_name), reply_markup=keyboard, parse_mode='Markdown')

    elif user.step == 'withdraw_funds':
        if update.message.text == get_text(user.language, 'cancel'):
            user.step = 'main_menu'
            user.save()

            balance = Transaction.objects(user=user, status='completed').sum('amount')
            
            keyboard = main_keyboard(user.language)
            return update.message.reply_text(get_text(user.language, 'withdraw_funds_cancelled'), reply_markup=keyboard)
        
        balance = Transaction.objects(user=user, status='completed').sum('amount')
        in_calculation = Transaction.objects(user=user, status='completed', type='profit', created_at__gte=datetime.now() - timedelta(days=7)).sum('amount')

        balance = balance - in_calculation
        if balance < 20:
            return update.message.reply_text(get_text(user.language, 'withdraw_minimum_amount'))
        
        address_books = AddressBook.objects(user=user)

        withdraw_amount = float(update.message.text)
        if withdraw_amount > balance:
            return update.message.reply_text(get_text(user.language, 'withdraw_insufficient_balance'))
        
        if withdraw_amount < 20:
            return update.message.reply_text(get_text(user.language, 'withdraw_minimum_amount'))

        user.step = f'withdraw_funds_{withdraw_amount}'
        user.save()

        keyboard = ReplyKeyboardMarkup([
            [address.address for address in address_books],
            [KeyboardButton(get_text(user.language, 'cancel'))],
        ], resize_keyboard=True)
        return update.message.reply_text(get_text(user.language, 'withdraw_funds_address_message'), reply_markup=keyboard)
    elif re.findall(r'withdraw_funds_', user.step):
        if update.message.text == get_text(user.language, 'cancel'):
            user.step = 'main_menu'
            user.save()

            balance = Transaction.objects(user=user, status='completed').sum('amount')
            
            keyboard = main_keyboard(user.language)

            return update.message.reply_text(get_text(user.language, 'withdraw_funds_cancelled'), reply_markup=keyboard)
        
        withdraw_amount = float(user.step.split('_')[-1])
        address = update.message.text
        balance = Transaction.objects(user=user, status='completed').sum('amount')

        if withdraw_amount > balance:
            return update.message.reply_text(get_text(user.language, 'withdraw_insufficient_balance'))

        # check bep20 address or trc20 address
        if not re.findall(r'T[0-9a-zA-Z]{33}', address) and not re.findall(r'0x[0-9a-zA-Z]{40}', address):
            return update.message.reply_text(get_text(user.language, 'withdraw_invalid_address'))
        
        withdraw_amount_fee = withdraw_amount * 0.1

        withdraw = Withdraw(user=user, amount=withdraw_amount-withdraw_amount_fee , address=address, status='pending', created_at=datetime.now())
        withdraw.save()

        Transaction(user=user, amount=(withdraw_amount-withdraw_amount_fee) * -1, type='withdraw', status='completed', description=f'withdraw to {address}',created_at=datetime.now()).save()
        Transaction(user=user, amount=withdraw_amount_fee * -1, type='withdraw_fee', status='completed', description=f'withdraw fee to {address}', created_at=datetime.now()).save()

        user.step = 'main_menu'
        user.save()

        address_book = AddressBook.objects(user=user, address=address).first()
        if not address_book:
            AddressBook(user=user, address=address, created_at=datetime.now()).save()

        balance = Transaction.objects(user=user, status='completed').sum('amount')
        keyboard = main_keyboard(user.language)

        total_deposit = Transaction.objects(user=user, status='completed', type='deposit').sum('amount')
        total_profit = Transaction.objects(user=user, status='completed', type='profit').sum('amount')

        msg = f"WithdrawID: `{withdraw.id}`\nUserID: [{user.id}](tg://user?id={user.telegram_user_id})\nAmount: *{withdraw.amount}*\nBalance: *{balance-withdraw.amount}*\nProfit: *{total_profit}*\nDeposit: *{total_deposit}*\nAddress: `{address}`"
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                         data={'chat_id': WITHDRAW_GROUP, 'text': msg, 'parse_mode': 'markdown'}).json()

        # Schedule a friendly follow-up message after 6 hours
        follow_up_text = (
            "🤗 We hope your withdrawal is processed smoothly!\n\n"
            "When it\'s complete, please share your experience with our community ❤️\n"
            "https://t.me/CornexTalk"
        )
        send_message_queue.apply_async(args=[user.telegram_user_id, follow_up_text], countdown=21600)

        return update.message.reply_text(get_text(user.language, 'withdraw_funds_success').format(amount=withdraw_amount, address=address), reply_markup=keyboard, parse_mode='markdown')

async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    callback_data = update.callback_query.data

    user = User.objects(telegram_user_id=update.callback_query.from_user.id).first()

    if re.findall(r'set_lang_', callback_data):
        print(callback_data.split('_'))
        lang_code = callback_data.split('_')[-1]
        user.language = lang_code
        user.save()
        update.callback_query.answer()

        # # context.bot.delete_message(chat_id=update.callback_query.from_user.id, message_id=update.message.message_id)
        # requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
        #                  data={'chat_id': WITHDRAW_GROUP, 'text': msg}).json()
        return await context.bot.send_message(chat_id=update.callback_query.from_user.id, text=get_text(lang_code, 'welcome_back').format(name=update.callback_query.from_user.first_name), reply_markup=main_keyboard(lang_code), parse_mode='Markdown')
    elif callback_data == 'menu_faqs':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'faq_how_it_works_button'), callback_data='faq_how_it_works')],
            [InlineKeyboardButton(get_text(user.language, 'faq_how_to_make_deposit_button'), callback_data='faq_how_to_make_deposit')],
            [InlineKeyboardButton(get_text(user.language, 'faq_how_to_withdraw_funds_button'), callback_data='faq_how_to_withdraw_funds')],
            [InlineKeyboardButton(get_text(user.language, 'faq_what_is_the_commistion_button'), callback_data='faq_what_is_the_commistion')],
            [InlineKeyboardButton(get_text(user.language, 'faq_minimum_deposit_button'), callback_data='faq_minimum_deposit')],
            [InlineKeyboardButton(get_text(user.language, 'faq_functionnality_description_button'), callback_data='faq_functionnality_description')],
            [InlineKeyboardButton(get_text(user.language, 'faq_bot_trading_exchange_button'), callback_data='faq_bot_trading_exchange')],
            [InlineKeyboardButton(get_text(user.language, 'faq_available_transactions_button'), callback_data='faq_available_transactions')],
            [InlineKeyboardButton(get_text(user.language, 'faq_possible_risks_button'), callback_data='faq_possible_risks')],
            [InlineKeyboardButton(get_text(user.language, 'faq_terms_of_use_button'), callback_data='faq_terms_of_use')],
            [InlineKeyboardButton(get_text(user.language, 'faq_token_storage_button'), callback_data='faq_token_storage')],
            [InlineKeyboardButton(get_text(user.language, 'faq_loss_of_token_button'), callback_data='faq_loss_of_token')],
            [InlineKeyboardButton(get_text(user.language, 'faq_referral_program_button'), callback_data='faq_referral_program')],
            [InlineKeyboardButton(get_text(user.language, 'faq_any_restrictions_button'), callback_data='faq_any_restrictions')],
            [InlineKeyboardButton(get_text(user.language, 'faq_bot_stop_loss_point_button'), callback_data='faq_bot_stop_loss_point')],
            [InlineKeyboardButton(get_text(user.language, 'faq_building_a_trust_button'), callback_data='faq_building_a_trust')],
        ])
        return await update.callback_query.edit_message_text(get_text(user.language, 'faq_message'), reply_markup=keyboard, parse_mode='markdown')
    elif re.findall(r'faq_', callback_data):
        faq_key = re.findall(r'faq_(.*)', callback_data)[0]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'faq_back_button'), callback_data='menu_faqs')],
        ])
        return await update.callback_query.edit_message_text(get_text(user.language, f'faq_{faq_key}_message'), reply_markup=keyboard, parse_mode='markdown')
    elif callback_data == 'menu_topup':
        wallets = Wallet.objects(user=user)

        if len(wallets) == 0:
            wallet_trc20 = create_account()
            bep20_account = create_bep20_wallet() 
            wallet_bep20 = Wallet(user=user, address=bep20_account['address'], private_key=bep20_account['private_key'], network='bep20', created_at=datetime.now())
            wallet_bep20.save()
            wallet_trc20 = Wallet(user=user, address=wallet_trc20['base58check_address'], private_key=wallet_trc20['private_key'], network='trc20', created_at=datetime.now())
            wallet_trc20.save()
        elif len(wallets) == 1:
            bep20_account = create_bep20_wallet() 
            wallet_trc20 = Wallet.objects(user=user, network='trc20').first()
            wallet_bep20 = Wallet(user=user, address=bep20_account['address'], private_key=bep20_account['private_key'], network='bep20', created_at=datetime.now())
            wallet_bep20.save()
        else:
            wallet_bep20 = Wallet.objects(user=user, network='bep20').first()
            wallet_trc20 = Wallet.objects(user=user, network='trc20').first()

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'check_payment'), callback_data='check_payment')],
            [InlineKeyboardButton(get_text(user.language, 'wallet_qrcode'), callback_data='wallet_qrcode')],
            [InlineKeyboardButton(get_text(user.language, 'back_to_account'), callback_data='back_to_account')]
        ])
        return await update.callback_query.edit_message_text(get_text(user.language, 'topup_message').format(wallet_trc20_address=wallet_trc20.address, wallet_bep20_address=wallet_bep20.address), parse_mode='markdown', reply_markup=keyboard)
    elif callback_data == 'check_payment':
        wallet = Wallet.objects(user=user).first()
        if not wallet:
            return await update.callback_query.answer(get_text(user.language, 'wallet_not_found'))

        check_payment_status.apply_async(args=[user.telegram_user_id])

        return await update.callback_query.answer(text=get_text(user.language, 'checking_payment_status'))
    
    elif callback_data == 'menu_withdraw_funds':
        balance = Transaction.objects(user=user, status='completed').sum('amount')
        if balance < 20:
            return await update.callback_query.answer(get_text(user.language, 'withdraw_minimum_amount'))
        
        user.step = 'withdraw_funds'
        user.save()

        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton(get_text(user.language, 'cancel'))],
        ], resize_keyboard=True)

        return await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text(user.language, 'withdraw_funds_message'), reply_markup=keyboard)
    elif callback_data == 'wallet_qrcode':
        wallet = Wallet.objects(user=user).first()
        if not wallet:
            return await update.callback_query.answer(get_text(user.language, 'wallet_not_found'))

        qr_code = generate_qr_code(wallet.address)
        # send qr code
        return await context.bot.send_photo(chat_id=update.callback_query.from_user.id, photo=open(qr_code, 'rb'))
    elif callback_data == 'start_trading':
        balance = Transaction.objects(user=user, status='completed').sum('amount')
        
        if balance < 20:
            return await update.callback_query.answer(
                text=get_text(user.language, 'insufficient_balance_trading'),
                show_alert=True
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'stop_trading'), callback_data='stop_trading')],
            [InlineKeyboardButton(get_text(user.language, 'tradebot_statistics_menu'), callback_data='tradebot_statistics_menu')],
            [InlineKeyboardButton('Signals', url='https://t.me/CornexBase')],
        ])
        user.is_trade_active = True
        user.save()
        return await update.callback_query.edit_message_text(get_text(user.language, 'trading_status_message').format(status=get_text(user.language, 'active')), reply_markup=keyboard, parse_mode='markdown')
    elif callback_data == 'stop_trading':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'start_trading'), callback_data='start_trading')],
            [InlineKeyboardButton(get_text(user.language, 'tradebot_statistics_menu'), callback_data='tradebot_statistics_menu')],
            [InlineKeyboardButton('Signals', url='https://t.me/CornexBase')],
        ])
        user.is_trade_active = False
        user.save()
        return await update.callback_query.edit_message_text(get_text(user.language, 'trading_status_message').format(status=get_text(user.language, 'stopped')), reply_markup=keyboard, parse_mode='markdown')
    elif callback_data == 'menu_referral':
        link = f'https://t.me/CornextBot?start=r{user.telegram_user_id}'
        total_invited = User.objects(invited_by=user).count()
        total_earned = Transaction.objects(user=user, type='referral').sum('amount')
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'back_to_account'), callback_data='back_to_account')],
        ])
        return await update.callback_query.edit_message_text(get_text(user.language, 'referral_message').format(link=link, total_invited=total_invited, total_income=total_earned), reply_markup=keyboard, parse_mode='markdown')
    elif callback_data == 'rewardhub_invite':
        link = f'https://t.me/CornextBot?start=r{user.telegram_user_id}'
        total_invited = User.objects(invited_by=user).count()
        total_earned = Transaction.objects(user=user, type='referral').sum('amount')
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'back_to_rewardhub'), callback_data='back_to_rewardhub')],
        ])
        return await update.callback_query.edit_message_text(get_text(user.language, 'referral_message').format(link=link, total_invited=total_invited, total_income=total_earned), reply_markup=keyboard, parse_mode='markdown')
    elif callback_data == 'rewardhub_status':
        invited_user_in_24_hours = User.objects(invited_by=user, joined_at__gte=datetime.now() - timedelta(days=1)).count()
        second_deposit = RewardHub.objects(user=user, reward_type='deposit_cash_back').count()
        extra_deposit = RewardHub.objects(user=user, reward_type='extra_deposit_reward').sum('amount')

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'back_to_rewardhub'), callback_data='back_to_rewardhub')],
        ])

        if second_deposit == 0:
            second_deposit_status = "❌"
        else:
            second_deposit_status = "✅"

        return await update.callback_query.edit_message_text(get_text(user.language, 'rewardhub_status_message').format(second_deposit_status=second_deposit_status, invited_today=invited_user_in_24_hours, estinated_today=10-invited_user_in_24_hours), reply_markup=keyboard, parse_mode='markdown')
    elif callback_data == 'back_to_rewardhub':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'rewardhub_my_rewards_button'),  callback_data='rewardhub_status'), InlineKeyboardButton(get_text(user.language, 'rewardhub_invite_button'), callback_data='menu_referral')],
        ])
        return await update.callback_query.edit_message_text(get_text(user.language, 'rewardhub_message'), reply_markup=keyboard)
    elif callback_data == 'back_to_account':
        total_balance = Transaction.objects(user=user, status='completed').sum('amount')
        in_calculation = Transaction.objects(user=user, status='completed', type='profit', created_at__gte=datetime.now() - timedelta(days=7)).sum('amount')
        total_withdraw = Transaction.objects(user=user, status='completed', type='withdraw').sum('amount')
        total_withdraw_fee = Transaction.objects(user=user, status='completed', type='withdraw_fee').sum('amount')
        total_deposit = Transaction.objects(user=user, status='completed', type='deposit').sum('amount')
        total_trade = Transaction.objects(user=user, status='completed', type='profit').count()

        total_withdraw = (total_withdraw + total_withdraw_fee) * -1

        join_date = user.joined_at.strftime('%Y-%m-%d %H:%M:%S')

        keyboard_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'menu_topup'), callback_data='menu_topup')],
            [InlineKeyboardButton(get_text(user.language, 'menu_withdraw_funds'), callback_data='menu_withdraw_funds')],
            [InlineKeyboardButton(get_text(user.language, 'menu_referral'), callback_data='menu_referral')],
        ])
        return await update.callback_query.edit_message_text(get_text(user.language, 'account_summary_message').format(
                    balance=round(total_balance,2), in_calculation=round(in_calculation,2), total_withdraw=round(total_withdraw,2), total_trades=total_trade, join_date=join_date,
                ), reply_markup=keyboard_markup, parse_mode='markdown')
    elif callback_data == 'tradebot_statistics_menu':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'statistics_24_hours'), callback_data='statistics_24_hours')],
            [InlineKeyboardButton(get_text(user.language, 'statistics_3_days'), callback_data='statistics_3_days')],
            [InlineKeyboardButton(get_text(user.language, 'statistics_7_days'), callback_data='statistics_7_days')],
            [InlineKeyboardButton(get_text(user.language, 'statistics_1_month'), callback_data='statistics_1_month')],
            [InlineKeyboardButton(get_text(user.language, 'statistics_3_months'), callback_data='statistics_3_months')],
            [InlineKeyboardButton(get_text(user.language, 'back_to_account'), callback_data='back_to_account')],
        ])

        return await update.callback_query.edit_message_text(get_text(user.language, 'tradebot_statistics_message'), reply_markup=keyboard, parse_mode='markdown')
    elif re.findall(r'statistics_', callback_data):
        stats_key = re.findall(r'statistics_(.*)', callback_data)[0]

        success_trades = 0
        failed_trades = 0
        percentage_profit = 0

        if stats_key == '24_hours':
            success_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(hours=24), status='success').count()
            failed_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(hours=24), status='failed').count()
            percentage_profit = Trade.objects(created_at__gte=datetime.now()-timedelta(hours=24)).sum('percentage')
        elif stats_key == '3_days':
            success_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(days=3), status='success').count()
            failed_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(days=3), status='failed').count()
            percentage_profit = Trade.objects(created_at__gte=datetime.now()-timedelta(days=3)).sum('percentage')
        elif stats_key == '7_days':
            success_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(days=7), status='success').count()
            failed_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(days=7), status='failed').count()
            percentage_profit = Trade.objects(created_at__gte=datetime.now()-timedelta(days=7)).sum('percentage')
        elif stats_key == '1_month':
            success_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(days=30), status='success').count()
            failed_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(days=30), status='failed').count()
            percentage_profit = Trade.objects(created_at__gte=datetime.now()-timedelta(days=30)).sum('percentage')
        elif stats_key == '3_months':
            success_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(days=90), status='success').count()
            failed_trades = Trade.objects(created_at__gte=datetime.now()-timedelta(days=90), status='failed').count()
            percentage_profit = Trade.objects(created_at__gte=datetime.now()-timedelta(days=90)).sum('percentage')
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'back'), callback_data='tradebot_statistics_menu')],
        ])
        return await update.callback_query.edit_message_text(get_text(user.language, f'statistics_message').format(timeframe=stats_key.replace('_', ' '), success_trades=success_trades, failed_trades=failed_trades, percentage_profit=percentage_profit, total_trades=success_trades+failed_trades), reply_markup=keyboard, parse_mode='markdown')

def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command - Show support/assistance message"""
    user = User.objects(telegram_user_id=update.message.from_user.id).first()
    if not user:
        return start(update, context)
    
    if not is_joined(update.effective_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'join_channel_chat_button'), url='https://t.me/CornexBase')],
        ])
        return update.message.reply_text(get_text(user.language, 'join_channel_message'), reply_markup=keyboard, parse_mode="markdown")
    
    keyboard_makrup = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(user.language, 'write_to_support'), url='https://t.me/CornexSup')],
    ])
    return update.message.reply_text(get_text(user.language, 'support_message'), reply_markup=keyboard_makrup)


def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command - Show account summary"""
    user = User.objects(telegram_user_id=update.message.from_user.id).first()
    if not user:
        return start(update, context)
    
    if not is_joined(update.effective_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'join_channel_chat_button'), url='https://t.me/CornexBase')],
        ])
        return update.message.reply_text(get_text(user.language, 'join_channel_message'), reply_markup=keyboard, parse_mode="markdown")
    
    total_balance = Transaction.objects(user=user, status='completed').sum('amount')
    in_calculation = Transaction.objects(user=user, status='completed', type='profit', created_at__gte=datetime.now() - timedelta(days=7)).sum('amount')
    total_withdraw = Transaction.objects(user=user, status='completed', type='withdraw').sum('amount')
    total_withdraw_fee = Transaction.objects(user=user, status='completed', type='withdraw_fee').sum('amount')
    total_deposit = Transaction.objects(user=user, status='completed', type='deposit').sum('amount')
    total_trade = Transaction.objects(user=user, status='completed', type='profit').count()

    total_withdraw = (total_withdraw + total_withdraw_fee) * -1

    join_date = user.joined_at.strftime('%Y-%m-%d %H:%M:%S')

    keyboard_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(user.language, 'menu_topup'), callback_data='menu_topup')],
        [InlineKeyboardButton(get_text(user.language, 'menu_withdraw_funds'), callback_data='menu_withdraw_funds')],
        [InlineKeyboardButton(get_text(user.language, 'menu_referral'), callback_data='menu_referral')],
    ])

    return update.message.reply_text(
        get_text(user.language, 'account_summary_message').format(
            balance=round(total_balance,2), in_calculation=round(in_calculation,2), total_withdraw=round(total_withdraw,2), total_trades=total_trade, join_date=join_date,
        ),
        reply_markup=keyboard_markup, 
        parse_mode='markdown'
    )


def tradebot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tradebot command - Show trading center status"""
    user = User.objects(telegram_user_id=update.message.from_user.id).first()
    if not user:
        return start(update, context)
    
    if not is_joined(update.effective_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'join_channel_chat_button'), url='https://t.me/CornexBase')],
        ])
        return update.message.reply_text(get_text(user.language, 'join_channel_message'), reply_markup=keyboard, parse_mode="markdown")
    
    is_trade_active = user.is_trade_active
    if not is_trade_active:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'start_trading'), callback_data='start_trading')],
            [InlineKeyboardButton(get_text(user.language, 'tradebot_statistics_menu'), callback_data='tradebot_statistics_menu')],
            [InlineKeyboardButton('Signals', url='https://t.me/CornexBase')],
        ])
        return update.message.reply_text(get_text(user.language, 'trading_status_message').format(status=get_text(user.language, 'stopped')), reply_markup=keyboard, parse_mode='markdown')
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'stop_trading'), callback_data='stop_trading')],
            [InlineKeyboardButton(get_text(user.language, 'tradebot_statistics_menu'), callback_data='tradebot_statistics_menu')],
            [InlineKeyboardButton('Signals', url='https://t.me/CornexBase')],
        ])
        return update.message.reply_text(get_text(user.language, 'trading_status_message').format(status=get_text(user.language, 'active')), reply_markup=keyboard, parse_mode='markdown')


def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /referral command - Show referral program"""
    user = User.objects(telegram_user_id=update.message.from_user.id).first()
    if not user:
        return start(update, context)
    
    if not is_joined(update.effective_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'join_channel_chat_button'), url='https://t.me/CornexBase')],
        ])
        return update.message.reply_text(get_text(user.language, 'join_channel_message'), reply_markup=keyboard, parse_mode="markdown")
    
    link = f'https://t.me/CornexBot?start=r{user.telegram_user_id}'
    total_invited = User.objects(invited_by=user).count()
    total_earned = Transaction.objects(user=user, type='referral').sum('amount')
    
    return update.message.reply_text(get_text(user.language, 'referral_message').format(link=link, total_invited=total_invited, total_income=total_earned), parse_mode='markdown')


def faqs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /faqs command - Show FAQ menu"""
    user = User.objects(telegram_user_id=update.message.from_user.id).first()
    if not user:
        return start(update, context)
    
    if not is_joined(update.effective_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.language, 'join_channel_chat_button'), url='https://t.me/CornexBase')],
        ])
        return update.message.reply_text(get_text(user.language, 'join_channel_message'), reply_markup=keyboard, parse_mode="markdown")
    
    keyboard_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(user.language, 'faq_how_it_works_button'), callback_data='faq_how_it_works')],
        [InlineKeyboardButton(get_text(user.language, 'faq_how_to_make_deposit_button'), callback_data='faq_how_to_make_deposit')],
        [InlineKeyboardButton(get_text(user.language, 'faq_how_to_withdraw_funds_button'), callback_data='faq_how_to_withdraw_funds')],
        [InlineKeyboardButton(get_text(user.language, 'faq_what_is_the_commistion_button'), callback_data='faq_what_is_the_commistion')],
        [InlineKeyboardButton(get_text(user.language, 'faq_minimum_deposit_button'), callback_data='faq_minimum_deposit')],
        [InlineKeyboardButton(get_text(user.language, 'faq_functionnality_description_button'), callback_data='faq_functionnality_description')],
        [InlineKeyboardButton(get_text(user.language, 'faq_bot_trading_exchange_button'), callback_data='faq_bot_trading_exchange')],
        [InlineKeyboardButton(get_text(user.language, 'faq_available_transactions_button'), callback_data='faq_available_transactions')],
        [InlineKeyboardButton(get_text(user.language, 'faq_possible_risks_button'), callback_data='faq_possible_risks')],
        [InlineKeyboardButton(get_text(user.language, 'faq_terms_of_use_button'), callback_data='faq_terms_of_use')],
        [InlineKeyboardButton(get_text(user.language, 'faq_token_storage_button'), callback_data='faq_token_storage')],
        [InlineKeyboardButton(get_text(user.language, 'faq_loss_of_token_button'), callback_data='faq_loss_of_token')],
        [InlineKeyboardButton(get_text(user.language, 'faq_referral_program_button'), callback_data='faq_referral_program')],
        [InlineKeyboardButton(get_text(user.language, 'faq_any_restrictions_button'), callback_data='faq_any_restrictions')],
        [InlineKeyboardButton(get_text(user.language, 'faq_bot_stop_loss_point_button'), callback_data='faq_bot_stop_loss_point')],
        [InlineKeyboardButton(get_text(user.language, 'faq_building_a_trust_button'), callback_data='faq_building_a_trust')],
    ])
    return update.message.reply_text(get_text(user.language, 'faq_message'), reply_markup=keyboard_markup, parse_mode='markdown')


def set_lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = User.objects(telegram_user_id=update.message.from_user.id).first()
    if not user:
        return start(update, context)
    user.step = 'main_menu'
    user.save()
    # todo send select menu lang
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("English 🇺🇸", callback_data='set_lang_en')],
        [InlineKeyboardButton("Türkçe 🇹🇷", callback_data='set_lang_tr')],
        [InlineKeyboardButton("Русский 🇷🇺", callback_data='set_lang_ru')],
        [InlineKeyboardButton("فارسی 🇮🇷", callback_data='set_lang_fa')],
        [InlineKeyboardButton("عربى 🇸🇦", callback_data='set_lang_ar')],
    ])
    return update.message.reply_text(get_text(user.language, 'choose_language'), reply_markup=keyboard)


def reward_hub_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = User.objects(telegram_user_id=update.message.from_user.id).first()
    if not user:
        return start(update, context)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(user.language, 'rewardhub_my_rewards_button'),  callback_data='rewardhub_status'), InlineKeyboardButton(get_text(user.language, 'rewardhub_invite_button'), callback_data='rewardhub_invite')],
    ])
    return update.message.reply_text(get_text(user.language, 'rewardhub_message'), reply_markup=keyboard, parse_mode='markdown')


def confirm_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    _, withdraw_id = update.message.text.split(' ')

    withdraw = Withdraw.objects(id=withdraw_id).first()

    withdraws = Withdraw.objects(user=withdraw.user, status='pending')
    addresses = {}

    for w in withdraws:
        if addresses.get(w.address) is None:
            addresses[w.address] = w.amount
        else:
            addresses[w.address] += w.amount
        w.status = 'success'
        w.save()
    
    for key, value in addresses.items():
        send_usdt.apply_async(args=[key, value])
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                         data={'chat_id': WITHDRAW_GROUP, 'text': f"send withdraw to {key} amount {value}", 'parse_mode': 'markdown'}).json()

    return 


def reject_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    _, withdraw_id = update.message.text.split(' ')

    withdraw = Withdraw.objects(id=withdraw_id, status='pending').first()

    withdraw.status = 'rejected'
    withdraw.save()

    withdraw_fee = withdraw.amount / 90 * 10
    Transaction(user=withdraw.user, amount=withdraw.amount, type='withdraw', status='completed', description=f'reject withdraw {withdraw_id}',created_at=datetime.now()).save()
    Transaction(user=withdraw.user, amount=withdraw_fee, type='withdraw_fee', status='completed', description=f'reject withdraw {withdraw_id}', created_at=datetime.now()).save()

    return update.message.reply_text(f'Withdraw was reject: {withdraw_id}\n\nAmount: {withdraw.amount}\nFee: {withdraw_fee}\n\nUser charged')
     

def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    total_deposit = Transaction.objects(status='completed', type='deposit').sum('amount')
    total_profit = Transaction.objects(status='completed', type='profit').sum('amount')
    total_withdraw = Transaction.objects(status='completed', type='withdraw').sum('amount')
    total_referral = Transaction.objects(status='completed', type='referral').sum('amount')
    total_extra_deposit_reward = Transaction.objects(status='completed', type='extra_deposit_reward').sum('amount')

    total_balance = Transaction.objects(status='completed').sum('amount')
    estimated_balance = total_balance - (total_balance/100*10)

    total_users = User.objects().count()

    return update.message.reply_text(f"*Total Deposit:* `${round(total_deposit, 2)}`\n*Total Profit:* `${round(total_profit, 2)}`\n*Total Withdraw:* `${round(total_withdraw, 2)}`\n*Total Referral:* `${round(total_referral, 2)}`\n*Total ExtraCB:* `${round(total_extra_deposit_reward, 2)}`\n`------------`\n*Balance:* `${round(total_balance, 2)}`\n*Estimated Balance:* `${round(estimated_balance, 2)}`\n*Users:* `{total_users}`", parse_mode='markdown')


def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return

    _, user_id = update.message.text.split(' ')


    if len(user_id) == 34:
        wallet = Wallet.objects(address=user_id).first()
        user = wallet.user
    elif len(user_id) == 24:
        user = User.objects(id=user_id).first()
    else:
        user = User.objects(pid=user_id).first()

    if user is None:
        user = User.objects(telegram_user_id=user_id).first()
    
    if user is None:
        return update.message.reply_text(f"User Not Found : {user_id}")
    
    
    
    total_deposit = Transaction.objects(user=user, type='deposit', status='completed').sum('amount')
    total_deposit_fee = Transaction.objects(user=user, type='deposit_fee', status='completed').sum('amount')
    total_withdraw = Transaction.objects(user=user, type='withdraw', status='completed').sum('amount')
    total_withdraw_fee = Transaction.objects(user=user, type='withdraw_fee', status='completed').sum('amount')

    total_invited_users = User.objects(invited_by=user).count()
    total_profit = Transaction.objects(user=user, type='profit', status='completed').sum('amount')
    total_balance = Transaction.objects(user=user, status='completed').sum('amount')

    msg = f"""UserID: {user.telegram_user_id}
SystemID: {user.id}
PID: {user.pid}
Name: {user.name}
InvitedBy: {user.invited_by.telegram_user_id if user.invited_by else 'None'}
JoinedAt: {user.joined_at}
--------
TotalInvite: {total_invited_users}
--------
Deposit: ${round(total_deposit, 2)}
DepositFee: ${round(total_deposit_fee, 2)}
Withdraw: ${round(total_withdraw, 2)}
WithdrawFee: ${round(total_withdraw_fee, 2)}
Profit: ${round(total_profit, 2)}
--------
Balance: ${round(total_balance, 2)}
"""
    return update.message.reply_text(msg, parse_mode='markdown')

def charge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    _, user_id, amount = update.message.text.split(' ')

    user = User.objects(pid=user_id).first()

    if user is None:
        user = User.objects(telegram_user_id=user_id).first()
        
    if user is None:
        return update.message.reply_text(f"User Not Found : {user_id}")
    
    transaction = Transaction(user=user, amount=float(amount), type='owener', status='completed', created_at=datetime.now())
    transaction.save()

    return update.message.reply_text(f"UserID {user.telegram_user_id} Balance increased ${transaction.amount}")


def check_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    in_progress_transactions = WalletTransaction.objects(status='in_progress')
    
    for ipt in in_progress_transactions:
        ipt.status = 'deleted'
        ipt.save()
        check_payment_status.apply_async(args=[ipt.wallet.user.telegram_user_id])
        return update.message.reply_text(f"User deposit check automatic: {ipt.wallet.user.telegram_user_id}")


def withdraw_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    withdraws = Withdraw.objects(status='pending')

    if len(withdraws) == 0:
        return update.message.reply_text('Any withdraws not found')
    

    for w in withdraws:
        balance = Transaction.objects(user=w.user, status='completed').sum('amount')
        total_deposit = Transaction.objects(user=w.user, status='completed', type='deposit').sum('amount')
        total_profit = Transaction.objects(user=w.user, status='completed', type='profit').sum('amount')

        msg = f"WithdrawID: `{w.id}`\nUserID: [{w.user.id}](tg://user?id={w.user.telegram_user_id})\nAmount: *{w.amount}*\nBalance: *{balance}*\nProfit: *{total_profit}*\nDeposit: *{total_deposit}*"
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                         data={'chat_id': WITHDRAW_GROUP, 'text': msg, 'parse_mode': 'markdown'}).json()
        
    return


def top_inviter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    
    inviters = RewardHub.objects().aggregate(
        {'$match': {'reward_type': 'referral_challenge'}},
        {'$match': {'user': {'$ne': None}}},
        {'$group': {'_id': '$user', 'total': {'$sum': 1}}},
        {'$sort': {'total': -1}}
    )
    msg = ''
    # limit the number of users to 10
    num = 1
    for inviter in inviters:
        user = User.objects(id=inviter['_id']).first()
        amount = RewardHub.objects(user=user, reward_type='referral_challenge').sum('amount')
        msg += f"{num}. {user.name} {user.telegram_user_id} - {inviter['total']} users- ${amount}\n"
        num += 1
        if num > 11:
            break

    return update.message.reply_text(msg)


def confirm_withdraw_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    try:
        _, withdraw_id = update.message.text.split(' ')
    except ValueError:
        return update.message.reply_text("Please provide a withdraw ID. Usage: /cws withdraw_id")

    withdraw = Withdraw.objects(id=withdraw_id).first()
    if not withdraw:
        return update.message.reply_text(f"Withdraw not found with ID: {withdraw_id}")

    if withdraw.status != 'pending':
        return update.message.reply_text(f"Withdraw {withdraw_id} is not pending. Current status: {withdraw.status}")

    withdraws = Withdraw.objects(user=withdraw.user, status='pending')
    for w in withdraws:
        w.status = 'success'
        w.save()

    return update.message.reply_text(f"Successfully marked withdraw {withdraw_id} and {len(withdraws)-1} other pending withdraws as success")

def dev_main_keyboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    user = User.objects(telegram_user_id=update.message.from_user.id).first()
    if not user:
        return start(update, context)
    
    return update.message.reply_text(get_text(user.language, 'dev_main_keyboard'), reply_markup=dev_main_keyboard(user.language))

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the user."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logging.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)

    # Build the message with some markup and additional information about what happened.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f'⚠️ *Error Report*\n\n'
        f'*Update:*\n`{json.dumps(update_str, indent=2, ensure_ascii=False)}`\n\n'
        f'*Error:*\n`{context.error}`\n\n'
        f'*Traceback:*\n`{tb_string}`'
    )

    # Send the message to the log group
    
    await context.bot.send_message(
        chat_id=LOG_GROUP,
        text=message,
        parse_mode='markdown'
    )


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().concurrent_updates(32).connection_pool_size(5000).token(BOT_TOKEN).build()

    # Add error handler
    application.add_error_handler(error_handler)

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("lang", set_lang_command))
    application.add_handler(CommandHandler("reward", reward_hub_command))
    
    # Command shortcuts for main menu items
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("tradebot", tradebot_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("faqs", faqs_command))

    application.add_handler(CommandHandler("cw", confirm_withdraw))
    application.add_handler(CommandHandler("cws", confirm_withdraw_status))
    application.add_handler(CommandHandler("rw", reject_withdraw))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("info", user_info))
    application.add_handler(CommandHandler("charge", charge_command))
    application.add_handler(CommandHandler("check_deposits", check_deposits))
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    application.add_handler(CommandHandler("broadcast_investors", broadcast_investors))
    application.add_handler(CommandHandler("withdraw_reqs", withdraw_requests))
    application.add_handler(CommandHandler("top_inviter", top_inviter))
    application.add_handler(CommandHandler("dev", dev_main_keyboard_command))
    
    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(CallbackQueryHandler(callback_query))

    # Run the bot until the user presses Ctrl-C
    # skip_updates=True
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
