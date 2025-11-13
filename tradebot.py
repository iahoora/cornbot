from models import Trade, User, Transaction
from datetime import datetime
from random import randint, choice
from time import sleep
import requests

CHANNEL_ID = '@CornexBase'
RANGE = [160, 600] # defualt for daily trade is [100, 490]
PAIRS = ['BTCUSDT', 'ETHUSDT', 'TONUSDT', 'BTCUSDT']

def send_message(chat_id, text):
    return requests.post(f'https://api.telegram.org/bot8469039154:AAEA7WRST1ULUx3xxDBJPA70lDS0M-fBxcA/sendMessage',
                         data={'chat_id': chat_id, 'text': text, 'parse_mode': 'markdown'}).json()

def get_balance(user):
    balance = Transaction.objects(user=user, status='completed').sum('amount')
    return balance


while True:
    percentage = randint(RANGE[0], RANGE[1])
    status = choice(['success', 'failed', 'success'])
    emoji = '✅' if status == 'success' else '❌'
    if status == 'failed':
        percentage = percentage * -1

    pair = PAIRS[randint(0, 3)]
    trade = Trade(pair=pair, percentage=percentage/1000, status=status, created_at=datetime.now())
    trade.save()
    print(f'new trade: {trade.id} : {trade.percentage}%')

    users = User.objects(is_trade_active=True)

    for user in users:
        balance = get_balance(user)
        profit = balance * percentage / 100000

        if profit != 0:
            print(f'profit for user {user.telegram_user_id}: {profit}')
            
            transaction = Transaction(user=user, amount=profit, type='profit', status='completed', description=f'profit from trade {trade.id}', created_at=datetime.now())
            transaction.save()

    try:
        send_message(CHANNEL_ID, f'Trade Info\nPair: *{pair}*\nProfit: *{trade.percentage}%*\nResult: *{emoji}{trade.status}*\n\n[@CornexBot](https://t.me/CornexBot)')
    except Exception as e:
        print(e)

    sleep(randint(1200, 2000))
