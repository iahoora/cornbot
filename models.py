from mongoengine import *

connect('FiboCapital')

class User(Document):
    telegram_user_id = IntField(required=True)
    pid = IntField(required=True)
    name = StringField(required=True)
    step = StringField(required=True)
    is_trade_active = BooleanField(default=False)
    language = StringField(default='en')
    invited_by = ReferenceField('self')
    utm =  ReferenceField('Utm')
    joined_at = DateTimeField(auto_now_add=True)

    indexed = ['telegram_user_id', 'pid', 'is_trade_active']


class Utm(Document):
    name = StringField(required=True)
    created_at = DateTimeField(auto_now_add=True)

    indexed = ['name']


class Transaction(Document):
    user = ReferenceField('User')
    amount = FloatField(required=True)
    type = StringField(required=True)
    description = StringField()
    status = StringField()
    created_at = DateTimeField(auto_now_add=True)

    indexed = ['user', 'type']


class Wallet(Document):
    user = ReferenceField('User')
    address = StringField(required=True)
    private_key = StringField()
    network = StringField(default='trc20')
    created_at = DateTimeField(auto_now_add=True)

    indexed = ['user']


class WalletTransaction(Document):
    wallet = ReferenceField('Wallet')
    amount = FloatField(required=True)
    from_address = StringField()
    tx_id = StringField()
    status = StringField()
    created_at = DateTimeField(auto_now_add=True)

    indexed = ['wallet', 'type', 'tx_id']


class Withdraw(Document):
    user = ReferenceField('User')
    amount = FloatField(required=True)
    address = StringField(required=True)
    status = StringField(default='pending')
    created_at = DateTimeField(auto_now_add=True)

    indexed = ['user', 'status']
 

class AddressBook(Document):
    user = ReferenceField('User')
    address = StringField(required=True)
    name = StringField()
    created_at = DateTimeField(auto_now_add=True)

    indexed = ['user', 'address']


class Trade(Document):
    pair = StringField(required=True)
    percentage = FloatField(required=True)
    status = StringField(default='on_pro')
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    indexed = ['status', 'pair']


class RewardHub(Document):
    user = ReferenceField('User')
    amount = FloatField(required=True)
    reward_type = StringField(required=True)
    status = StringField(default='pending')
    created_at = DateTimeField(auto_now_add=True)

    indexed = ['user', 'status', 'reward_type']
