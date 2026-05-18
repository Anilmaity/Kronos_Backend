#####################################################################   LIBRARIES   ########################################################################
import inspect
import uuid

import ta
from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager,
                                        PermissionsMixin, User)
from django.contrib.postgres.fields import ArrayField
from django.db import models
# import datetime
from django.utils import timezone

from Kronos_Backend.utils.base_model import BaseModel

from django.contrib.postgres.fields import ArrayField


#########################################################################################################################################################

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=500)
    last_name = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    balance = models.DecimalField(max_digits=25, decimal_places=2, default=100000)
    username = models.CharField(max_length=30)
    profile_image = models.ImageField(upload_to='Profile_image/', max_length=1000, default="Profile_image/profile.jpg")
    profile_description = models.CharField(max_length=500, default="")
    otp_token = models.CharField(max_length=256, default="")

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.email




class CurrencyPair(BaseModel):
    symbol = models.CharField(max_length=100, default="XRPUSDT", unique=True)
    name = models.CharField(max_length=100, default="XRPUSDT")
    ltp = models.CharField(max_length=100, default="0.00")
    tick_size = models.DecimalField(default=0.00, max_digits=25, decimal_places=6)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return str(self.name) + " " + str(self.symbol)


class Signal(BaseModel):
    symbol = models.CharField(max_length=50)
    exchange = models.CharField(max_length=50, default='NFO')
    price = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    description = models.CharField(max_length=500)
    side = models.CharField(max_length=50, default='BUY')
    type = models.CharField(max_length=50, default='CALL')
    strategy = models.ForeignKey("Strategy", on_delete=models.CASCADE)

    def __str__(self):
        return str(self.id)


class UserBroker(BaseModel):
    api_key = models.CharField(max_length=500, unique=True, default=str(uuid.uuid4))
    margin_available = models.CharField(max_length=100, default="")

    margin_used = models.CharField(max_length=100, default="0.00")
    status = models.CharField(max_length=100, default="ACTIVE")

    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


    def __str__(self):
        return  str(self.user.email)





class Strategy(BaseModel):
    name = models.CharField(max_length=500, unique=True)
    description = models.CharField(max_length=500, default="")
    is_active = models.BooleanField(default=True)
    currencypair = models.ForeignKey(CurrencyPair, on_delete=models.CASCADE)
    capital_required = models.CharField(max_length=100, default="100000.00")
    json_data = models.JSONField(default=dict)
    params = models.JSONField(default=dict)
    entry_quantity = models.DecimalField(max_digits=25, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name







class Action(BaseModel):
    ACTION_TYPE = (
        ("STOPLOSS", "STOPLOSS"),
        ("TARGET", "TARGET"),
        ("REPAIR", "REPAIR"),
        ("TRAILING_STOPLOSS", "TRAILING_STOPLOSS"),
        ("EXIT", "EXIT"),
        ("BUY_EXIT", "BUY_EXIT"),
        ("SELL_EXIT", "SELL_EXIT"),
    )


    ACTION = [
        ('BUY', 'BUY'),
        ('SELL', 'SELL'),
    ]
    TRIGGER_TYPE = {
        ("POINTS", "POINTS"),
        ("PERCENTAGE", "PERCENTAGE"),
        ("CUMULATIVE_PNL_VALUE", "CUMULATIVE_PNL_VALUE"),
        ("CUMULATIVE_PNL_PERCENTAGE", "CUMULATIVE_PNL_PERCENTAGE"),
        ("INDEX_POINTS", "INDEX_POINTS"),
        ("TIME_PERIOD", "TIME_PERIOD"),
        ("INDEX_PERCENTAGE", "INDEX_PERCENTAGE"),
        ("CUSTOM", "CUSTOM"),

    }

    TRAILING_TYPE = (
        ("PERCENTAGE", "PERCENTAGE"),
        ("POINTS", "POINTS"),
        ("CUMULATIVE_PNL_VALUE", "CUMULATIVE_PNL_VALUE"),
    )

    action = models.CharField(max_length=100, default="SELL" , choices=ACTION)
    quantity = models.DecimalField(max_digits=25, decimal_places=2, default=0.00)
    trigger_value = models.DecimalField(max_digits=25, decimal_places=2, default=0.00)
    trigger_type = models.CharField(max_length=100, default="PERCENTAGE" , choices=TRIGGER_TYPE)
    action_type = models.CharField(max_length=100, default="ENTRY" , choices=ACTION_TYPE)
    create_trigger = models.BooleanField(default=False)
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE)
    trail_type = models.CharField(max_length=100, default="PERCENTAGE", choices=TRAILING_TYPE)
    trail_value = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)

    def __str__(self):
        return self.action


class UserStrategy(BaseModel):
    name = models.CharField(max_length=100, default="User Strategy")
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    multiplyer = models.IntegerField(default=1)
    user_broker = models.ForeignKey(UserBroker, on_delete=models.CASCADE)
    deployed = models.BooleanField(default=False)


    def __str__(self):
        return (
                str(self.name)
                + " "
                + str(self.user_broker.user)
        )


class Position(BaseModel):
    avg_buy_price = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    avg_sell_price = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    total_buy_quantity = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    symbol = models.CharField(max_length=50)
    quantity = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    profit_loss = models.DecimalField(max_digits=25, decimal_places=2, default=0.00)
    profit_loss_percentage = models.DecimalField(
        max_digits=25, decimal_places=2, default=0.00
    )
    ltp = models.DecimalField(max_digits=25, decimal_places=2, default=0.00)
    realized_profit_loss = models.DecimalField(
        max_digits=25, decimal_places=2, default=0.00
    )
    user_strategy = models.ForeignKey(UserStrategy, on_delete=models.CASCADE)
    currencypair = models.ForeignKey(CurrencyPair, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.symbol)  + " " + str(self.quantity)


class Order(BaseModel):
    symbol = models.CharField(max_length=50)
    exchange = models.CharField(max_length=50, default="NFO")
    price = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    condition = models.CharField(max_length=50, default="ENTRY")
    side = models.CharField(max_length=50, default="BUY")
    amount = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    quantity = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    user_broker = models.ForeignKey(UserBroker, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=50, default="MARKET")
    status = models.CharField(max_length=50, default="PENDING")
    reason = models.CharField(max_length=200, default="NONE")
    broker_order_id = models.CharField(max_length=100, default="")

    def __str__(self):
        return str(self.id)


class Trigger(BaseModel):
    TRIGGER_TYPE = [
        ("TARGET", "TARGET"),
        ("STOPLOSS", "STOPLOSS"),
        ("SUM_STOPLOSS", "SUM_STOPLOSS"),
        ("SUM_TARGET", "SUM_TARGET"),
        ("CUSTOM", "CUSTOM"),
        ("TRAILING_STOPLOSS_POINTS", "TRAILING_STOPLOSS_POINTS"),
        ("TRAILING_STOPLOSS_SUM", "TRAILING_STOPLOSS_SUM"),


        ('ENTRY', 'ENTRY'),
        ('EXIT', 'EXIT'),
    ]

    STATUS = [
        ('PENDING', 'PENDING'),
        ('TRIGGERED', 'TRIGGERED'),
        ('CANCELLED', 'CANCELLED'),
    ]

    date = models.DateField(default=timezone.now)
    symbol = models.CharField(max_length=50, default="")
    trigger_price = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    order_type = models.CharField(max_length=50, default="LIMIT")
    side = models.CharField(max_length=50, default="BUY")
    greater_than = models.BooleanField(default=True)
    quantity = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    broker_order_id = models.CharField(max_length=100, default="")
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    trigger_type = models.CharField(max_length=50, default="STOPLOSS" , choices=TRIGGER_TYPE)
    check_at_broker = models.BooleanField(default=False)
    status = models.CharField(max_length=50, default="PENDING", choices=STATUS)
    trail_value = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)
    trail_points = models.DecimalField(default=0.00, max_digits=25, decimal_places=2)

    def __str__(self):
        return str(self.symbol) + " " + str(self.date)


class StrategySignal(BaseModel):
    STATUS_CHOICES = (
        ("FIRED", "FIRED"),
        ("PLACED", "PLACED"),
        ("REJECTED", "REJECTED"),
    )

    strategy = models.ForeignKey(
        Strategy, on_delete=models.CASCADE, related_name="strategy_signals"
    )
    symbol = models.CharField(max_length=50)
    side = models.CharField(max_length=10)
    entry_price = models.DecimalField(max_digits=25, decimal_places=5)
    stop_loss = models.DecimalField(max_digits=25, decimal_places=5, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=25, decimal_places=5, null=True, blank=True)
    reason = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="FIRED")
    rejection_reason = models.CharField(max_length=500, blank=True, default="")
    position = models.ForeignKey(
        "Position",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="strategy_signals",
    )
    signal_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["strategy"]),
            models.Index(fields=["signal_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.symbol}:{self.side}@{self.entry_price}:{self.status}"


class BacktestReport(BaseModel):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, related_name="backtest_reports")
    run_label = models.CharField(max_length=200)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    trades = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    win_rate_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    pnl_pts = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    max_dd_pts = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    avg_win_pts = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    avg_loss_pts = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    profit_factor = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    expectancy_pts = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    sharpe_daily = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    source_csv = models.CharField(max_length=500, blank=True, default="")
    params_snapshot = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["strategy"]),
            models.Index(fields=["run_label"]),
        ]

    def __str__(self):
        return f"{self.run_label}:{self.strategy_id}"
