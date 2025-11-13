# celery tasks
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
from celery import Celery
from telegram import Bot
from models import User, Transaction, Wallet, WalletTransaction, Withdraw, Utm, RewardHub
from datetime import datetime, timedelta
from utils.tronTool import check_usdt_balance, transfer_trx, transfer_usdt, transfer_usdt_to_address
from utils.bep20Tool import check_balance_usdt, transfer_usdt as transfer_usdt_bep20
import requests
import time
import logging
import traceback
import json
from decimal import Decimal
from kombu import Exchange, Queue
from celery.schedules import crontab

app = Celery('tasks', broker='redis://localhost:6379/1')

bot = Bot(token='8469039154:AAEA7WRST1ULUx3xxDBJPA70lDS0M-fBxcA', )
LOG_GROUP = -1002755033899

app.conf.beat_schedule = getattr(app.conf, 'beat_schedule', {})
app.conf.beat_schedule.update({
    'capitalfund-maintenance-daily': {
        'task': 'tasks.capitalfund_maintenance',
        'schedule': crontab(minute=0, hour=0),  # every day at 00:00
    },
})

def send_message(chat_id, text):
    return requests.post(f'https://api.telegram.org/bot8469039154:AAEA7WRST1ULUx3xxDBJPA70lDS0M-fBxcA/sendMessage',
                         data={'chat_id': chat_id, 'text': text}).json()

def log_error_to_telegram(task_name, error, args=None, kwargs=None):
    """Log error to Telegram group"""
    try:
        # Get the full traceback
        tb_list = traceback.format_exception(None, error, error.__traceback__)
        tb_string = ''.join(tb_list)

        # Convert args and kwargs to JSON-serializable format
        def convert_decimal(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, list):
                return [convert_decimal(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: convert_decimal(value) for key, value in obj.items()}
            else:
                return obj

        serializable_args = convert_decimal(args) if args else None
        serializable_kwargs = convert_decimal(kwargs) if kwargs else None

        # Build the message
        message = (
            f'⚠️ *Celery Task Error*\n\n'
            f'*Task:* `{task_name}`\n'
            f'*Error:* `{str(error)}`\n\n'
            f'*Arguments:*\n`{json.dumps({"args": serializable_args, "kwargs": serializable_kwargs}, indent=2, ensure_ascii=False)}`\n\n'
            f'*Traceback:*\n`{tb_string}`'
        )

        # Send to log group
        requests.post(
            f'https://api.telegram.org/bot8469039154:AAEA7WRST1ULUx3xxDBJPA70lDS0M-fBxcA/sendMessage',
            data={
                'chat_id': LOG_GROUP,
                'text': message,
                'parse_mode': 'markdown'
            }
        )
    except Exception as e:
        logging.error(f"Failed to send error message to log group: {e}")

@app.task(bind=True)
def check_payment_status(self, user_id):
    try:
        print('checking payment status1')
        user = User.objects(telegram_user_id=user_id).first()
        wallet_trc20 = Wallet.objects(user=user, network='trc20').first()
        wallet_bep20 = Wallet.objects(user=user, network='bep20').first()

        wallet_transaction = WalletTransaction.objects(wallet=wallet_trc20, status='in_progress').first()
        if wallet_transaction:
            print('checking payment status, trc20')
            return send_message(chat_id=user_id, text=f'You have a pending transaction\n\nAmount: {wallet_transaction.amount}\nStatus: {wallet_transaction.status}')
        
        wallet_transaction = WalletTransaction.objects(wallet=wallet_bep20, status='in_progress').first()
        if wallet_transaction:
            print('checking payment status, bep20')
            return send_message(chat_id=user_id, text=f'You have a pending transaction\n\nAmount: {wallet_transaction.amount}\nStatus: {wallet_transaction.status}')
        

        balance_trc20 = check_usdt_balance(wallet_trc20.address)
        balance_bep20 = check_balance_usdt(wallet_bep20.address)
        if balance_trc20 < 20:
            print(f'You only deposited {balance_trc20} USDT(TRC20). For Top-up, you need to deposit at least 20 USDT')
            send_message(chat_id=user_id, text=f'You only deposited {balance_trc20} USDT(TRC20). For Top-up, you need to deposit at least 20 USDT')
        elif balance_trc20 >= 20:
            print(f'You have {balance_trc20} USDT(TRC20) in your wallet')
            wallet_transaction = WalletTransaction(wallet=wallet_trc20, amount=balance_trc20, status='in_progress', created_at=datetime.now())
            wallet_transaction.save()

            status, data = transfer_trx(wallet_trc20.address)
            if not status:
                WalletTransaction(wallet=wallet_trc20, amount=balance_trc20, status='failed', created_at=datetime.now()).save()
                # TODO send a message to admin
                return send_message(chat_id=user_id, text='Failed to top-up your wallet. Please contact support')
            
            status, data = transfer_usdt(balance_trc20, wallet_trc20.address, wallet_trc20.private_key)
            if not status:
                WalletTransaction(wallet=wallet_trc20, amount=balance_trc20, status='failed', created_at=datetime.now()).save()
                # TODO send a message to admin
                return send_message(chat_id=user_id, text='Failed to top-up your wallet. Please contact support')
        
            wallet_transaction.status = 'completed'
            wallet_transaction.save()

            # Convert to float for calculations and passing to other functions
            balance_trc20_float = float(balance_trc20)

            # Process referral commission for TRC20 deposit
            print(f"DEBUG: user.invited_by = {user.invited_by}")
            if user.invited_by:
                commission = balance_trc20_float * 0.05
                Transaction(
                    user=user.invited_by,
                    amount=commission,
                    type='referral',
                    status='completed',
                    description=f'For User {user.id}'
                ).save()

                # notify asynchronously; if it fails, only the notification is retried
                send_message_queue.delay(user.invited_by.telegram_user_id, 
                                         f'You have received {commission} USDT as a referral bonus')
            else:
                print(f"DEBUG: No inviter found for user {user.telegram_user_id}")

            transaction = Transaction(user=user, amount=balance_trc20_float, type='deposit', status='completed', description=f'transfer from {wallet_trc20.address}', created_at=datetime.now())
            transaction.save()

            top_up_fee = balance_trc20_float * -0.1
            transaction_fee = Transaction(user=user, amount=top_up_fee, type='deposit_fee', status='completed', description=f'Deposit fee transaction id {transaction.id}', created_at=datetime.now())
            transaction_fee.save()

            send_message(chat_id=user_id, text=f'Your wallet has been topped up with {balance_trc20_float + top_up_fee} USDT')
        
        if balance_bep20 < 20:
            print(f'You only deposited {balance_bep20} USDT(BEP20). For Top-up, you need to deposit at least 20 USDT')
            send_message(chat_id=user_id, text=f'You only deposited {balance_bep20} USDT(BEP20). For Top-up, you need to deposit at least 20 USDT')
        elif balance_bep20 >= 20:
            print(f'You have {balance_bep20} USDT(BEP20) in your wallet')
            wallet_transaction = WalletTransaction(wallet=wallet_bep20, amount=balance_bep20, status='in_progress', created_at=datetime.now())
            wallet_transaction.save()

            status, data = transfer_usdt_bep20(wallet_bep20.private_key, "0xb812F69b1184Ee9480D93BB301f5008976B0d958", balance_bep20)
            if not status:
                WalletTransaction(wallet=wallet_bep20, amount=balance_bep20, status='failed', created_at=datetime.now()).save()
                # TODO send a message to admin
                return send_message(chat_id=user_id, text='Failed to top-up your wallet. Please contact support')
        
            wallet_transaction.status = 'completed'
            wallet_transaction.save()

            # Convert to float for calculations and passing to other functions
            balance_bep20_float = float(balance_bep20)

            # Process referral commission for BEP20 deposit
            print(f"DEBUG: user.invited_by = {user.invited_by}")
            #  inside check_payment_status – already executing in a worker
            if user.invited_by:
                commission = balance_bep20_float * 0.05
                Transaction(
                    user=user.invited_by,
                    amount=commission,
                    type='referral',
                    status='completed',
                    description=f'For User {user.id}'
                ).save()

                # notify asynchronously; if it fails, only the notification is retried
                send_message_queue.delay(user.invited_by.telegram_user_id,
                        f'You have received {commission} USDT as a referral bonus')
            else:
                print(f"DEBUG: No inviter found for user {user.telegram_user_id}")

            transaction = Transaction(user=user, amount=balance_bep20_float, type='deposit', status='completed', description=f'transfer from {wallet_bep20.address}', created_at=datetime.now())
            transaction.save()

            top_up_fee = balance_bep20_float * -0.1
            transaction_fee = Transaction(user=user, amount=top_up_fee, type='deposit_fee', status='completed', description=f'Deposit fee transaction id {transaction.id}', created_at=datetime.now())
            transaction_fee.save()

            send_message(chat_id=user_id, text=f'Your wallet has been topped up with {balance_bep20_float + top_up_fee} USDT')

        return
    except Exception as e:
        log_error_to_telegram('check_payment_status', e, args=[user_id])
        raise


@app.task(bind=True)
def referral_icrease(self, ref_user_id, total_amount, user_id):
    try:
        print(f"DEBUG: referral_icrease called with ref_user_id={ref_user_id}, total_amount={total_amount}, user_id={user_id}")
        user = User.objects(telegram_user_id=ref_user_id).first()
        print(f"DEBUG: Found referrer user: {user}")
        if not user:
            print(f"DEBUG: No user found with telegram_user_id={ref_user_id}")
            return
        
        commistion = total_amount * 0.05
        print(f"DEBUG: Calculated commission: {commistion}")
        transaction = Transaction(user=user, amount=commistion, type='referral', status='completed', description=f'For User {user_id}', created_at=datetime.now())
        transaction.save()
        print(f"DEBUG: Transaction saved with ID: {transaction.id}")
        
        result = send_message(chat_id=ref_user_id, text=f'You have received {commistion} USDT as a referral bonus')
        print(f"DEBUG: Message sent to {ref_user_id}, result: {result}")
        return result
    except Exception as e:
        print(f"DEBUG: Error in referral_icrease: {str(e)}")
        log_error_to_telegram('referral_icrease', e, args=[ref_user_id, total_amount, user_id])
        raise


@app.task(bind=True)
def reward_check_second_deposit(self, user_id, amount):
    try:
        user = User.objects(telegram_user_id=user_id).first()
        deposit_count = Transaction.objects(user=user, type='deposit', status='completed').count()
        if deposit_count == 2:
            fee = amount * 0.1
            transaction = Transaction(user=user, amount=fee, type='deposit_cash_back', status='completed', description=f'reward cashback for %10 second deposit', created_at=datetime.now())
            transaction.save()

            reward = RewardHub(user=user, amount=fee, status='send_to_wallet', reward_type='deposit_cash_back', created_at=datetime.now())
            reward.save()
            return send_message(chat_id=user_id, text=f'You have received {fee} USDT as a reward for your second deposit')
    except Exception as e:
        log_error_to_telegram('reward_check_second_deposit', e, args=[user_id, amount])
        raise


@app.task(bind=True)
def reward_invited_user(self, user_id):
    try:
        user = User.objects(telegram_user_id=user_id).first()
        invited_count = User.objects(invited_by=user, joined_at__gte=datetime.now() - timedelta(days=1)).count()
        
        if invited_count >= 10:
            reward = RewardHub(user=user, amount=10, status='in_review', reward_type='invite_10_user', created_at=datetime.now())
            reward.save()
            return send_message(chat_id=user_id, text=f'You will received 10 USDT as a reward for inviting 10 users in 24 hours')
    except Exception as e:
        log_error_to_telegram('reward_invited_user', e, args=[user_id])
        raise


@app.task(bind=True)
def reward_extra_deposit(self, user_id, amount):
    try:
        user = User.objects(telegram_user_id=user_id).first()
        fee = amount * 0.10
        transaction = Transaction(user=user.invited_by, amount=fee, type='extra_deposit_reward', status='completed', description=f'extra reward for %10 deposit', created_at=datetime.now())
        transaction.save()
        reward = RewardHub(user=user.invited_by, amount=fee, status='send_to_wallet', reward_type=f'extra_deposit_reward', created_at=datetime.now())
        reward.save()
        return send_message(chat_id=user_id, text=f'You have received {fee} USDT as a reward for depositing your friend')
    except Exception as e:
        log_error_to_telegram('reward_extra_deposit', e, args=[user_id, amount])
        raise


@app.task(bind=True)
def reward_challenge_referral(self, user_id, deposit_amount):
    try:
        user = User.objects(telegram_user_id=user_id).first()

        if user.invited_by is None:
            return
        
        reward = RewardHub(user=user.invited_by, amount=deposit_amount, status='in_progress', reward_type=f'referral_challenge', created_at=datetime.now())
        reward.save()
    except Exception as e:
        log_error_to_telegram('reward_challenge_referral', e, args=[user_id, deposit_amount])
        raise


@app.task(bind=True)
def send_usdt(self, address, amount):
    try:
        status, msg = transfer_usdt_to_address(amount, address)
        requests.post(f'https://api.telegram.org/bot7011276548:AAHxa90CrlZLCx7s7CiGYPvjRVwhDTa5PGk/sendMessage',
                         data={'chat_id': -4245630611, 'text': f'Withdraw to {address}\namount: {amount}\nstatus: {status}\n{msg}'})
    except Exception as e:
        log_error_to_telegram('send_usdt', e, args=[address, amount])
        raise


@app.task(bind=True, queue='messages')
def send_message_queue(self, chat_id, text):
    try:
        time.sleep(0.2)
        return send_message(chat_id, text)
    except Exception as e:
        log_error_to_telegram('send_message_queue', e, args=[chat_id, text])
        raise


@app.task(bind=True, queue='messages')
def broadcast_all_task(self, message):
    """Send a broadcast message to every user in the database."""
    for user in User.objects():
        send_message_queue.apply_async(args=[user.telegram_user_id, message])


@app.task(bind=True, queue='messages')
def broadcast_investors_task(self, message):
    """Broadcast only to users with a positive balance (investors)."""
    for user in User.objects():
        balance = Transaction.objects(user=user, status='completed').sum('amount') or 0
        if balance > 0:
            send_message_queue.apply_async(args=[user.telegram_user_id, message])

@app.task(bind=True)
def capitalfund_maintenance(self):
    """Daily task to handle Capital Fund profit accrual and unlocks."""
    try:
        now = datetime.utcnow()
        investments = Transaction.objects(status='on_hold_capitalfund', type='capitalfund')
        for inv in investments:
            user = inv.user
            days_passed = (now - inv.created_at).days
            weeks_passed = days_passed // 7
            # count existing profit weeks for this investment
            existing_weeks = Transaction.objects(user=user, type='capitalfund_profit', description__icontains=str(inv.id)).count()
            missing_weeks = weeks_passed - existing_weeks
            if missing_weeks > 0:
                weekly_profit_amount = inv.amount * 0.06 * 7  # 6% per day * 7 days
                for i in range(existing_weeks + 1, existing_weeks + missing_weeks + 1):
                    Transaction(user=user,
                                amount=weekly_profit_amount,
                                type='capitalfund_profit',
                                status='pending',
                                description=f'capitalfund {inv.id} week {i}',
                                created_at=now).save()
            # unlock after 30 days
            if days_passed >= 30:
                # return principal to balance
                Transaction(user=user,
                            amount=inv.amount,
                            type='capitalfund_unlock',
                            status='completed',
                            description=f'capitalfund unlock {inv.id}',
                            created_at=now).save()
                inv.status = 'completed'
                inv.save()
    except Exception as e:
        log_error_to_telegram('capitalfund_maintenance', e)
        raise